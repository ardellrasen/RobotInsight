"""Local Faster-Whisper recognition with speech-driven recording endpoints."""
from collections import deque
import os
import threading
import time

import numpy as np
from modules.devices import microphone_settings, to_model_rate
from modules.setup_speech import STT_DIR

SAMPLERATE = 16000
FRAME_SAMPLES = 512
FRAME_SECONDS = FRAME_SAMPLES / SAMPLERATE
_model = None
_vad = None
_load_lock = threading.Lock()


class SpeechEndpoint:
    """Keep the start of speech and stop after a natural pause, not a fixed timer."""
    def __init__(self, silence_seconds=0.65, wait_seconds=6, max_seconds=25):
        self.pre_roll = deque(maxlen=10)
        self.frames = []
        self.started = False
        self.voiced = 0
        self.quiet = 0
        self.total = 0
        self.silence_frames = round(silence_seconds / FRAME_SECONDS)
        self.wait_frames = round(wait_seconds / FRAME_SECONDS)
        self.max_frames = round(max_seconds / FRAME_SECONDS)

    def feed(self, frame, probability):
        self.total += 1
        voiced = probability >= 0.5
        if not self.started:
            self.pre_roll.append(frame.copy())
            self.voiced = self.voiced + 1 if voiced else 0
            if self.voiced >= 2:
                self.started = True
                self.frames.extend(self.pre_roll)
            return self.total >= self.wait_frames and not self.started
        self.frames.append(frame.copy())
        if voiced:
            self.voiced += 1
            self.quiet = 0
        else:
            self.quiet += 1
        return self.quiet >= self.silence_frames or len(self.frames) >= self.max_frames

    def audio(self):
        if not self.frames or self.voiced < 4:
            return np.empty(0, dtype=np.float32)
        return np.concatenate(self.frames).astype(np.float32)


def initialize():
    global _model, _vad
    with _load_lock:
        if _model is None:
            from faster_whisper import WhisperModel
            if not (STT_DIR / "model.bin").is_file():
                raise FileNotFoundError("Speech model missing. Run Start_RobotInsight.bat to finish setup.")
            _model = WhisperModel(str(STT_DIR), device="cpu", compute_type="int8",
                                  cpu_threads=min(4, os.cpu_count() or 2), num_workers=1,
                                  local_files_only=True)
        if _vad is None:
            from silero_vad import load_silero_vad
            _vad = load_silero_vad(onnx=True)
    return _model


def transcribe_audio(audio, language=None):
    model = initialize()
    chosen = language or os.environ.get("ROBOT_STT_LANGUAGE", "auto")
    segments, _info = model.transcribe(
        np.asarray(audio, dtype=np.float32), language=None if chosen == "auto" else chosen,
        beam_size=3, temperature=0, condition_on_previous_text=False,
        vad_filter=True, vad_parameters={"min_silence_duration_ms": 300},
        no_speech_threshold=0.6, compression_ratio_threshold=2.4,
    )
    if chosen == "auto" and _info.language not in {"en", "id"}:
        # Restrict ambiguous short clips to the user's two languages. Malay can
        # otherwise win over Indonesian despite Indonesian being the intent.
        probabilities = getattr(_info, "all_language_probs", None) or []
        allowed = [(code, probability) for code, probability in probabilities if code in {"en", "id"}]
        selected = "id" if _info.language == "ms" else max(allowed, key=lambda item: item[1], default=("en", 0))[0]
        return transcribe_audio(audio, language=selected)
    # Silence/hallucination filtering applies to each segment, never a guessed prompt.
    return " ".join(segment.text.strip() for segment in segments
                    if segment.no_speech_prob < 0.65 and segment.avg_logprob > -1.2).strip()


def listen(interrupt=None):
    import sounddevice as sd
    import torch
    from modules.interface import set_state, set_voice_status
    initialize()
    _vad.reset_states()
    endpoint = SpeechEndpoint()
    device, sample_rate = microphone_settings()
    capture_samples = round(FRAME_SECONDS * sample_rate)
    print("[STT] Listening; stops after you finish speaking.")
    try:
        with sd.InputStream(device=device, samplerate=sample_rate, channels=1,
                            blocksize=capture_samples, dtype="float32") as stream:
            while True:
                if interrupt is not None and interrupt():
                    return ""
                audio, overflowed = stream.read(capture_samples)
                frame = to_model_rate(audio.flatten(), sample_rate).astype(np.float32)
                frame = np.pad(frame, (0, max(0, FRAME_SAMPLES - len(frame))))[:FRAME_SAMPLES]
                probability = float(_vad(torch.from_numpy(frame), SAMPLERATE).item())
                set_voice_status(level=min(1.0, float(np.sqrt(np.mean(frame * frame))) * 12))
                if overflowed:
                    print("[STT] Audio overflow; consider a different microphone.")
                if endpoint.feed(frame, probability):
                    break
        utterance = endpoint.audio()
        if len(utterance) == 0:
            return ""
        set_state("transcribing")
        started = time.monotonic()
        result = transcribe_audio(utterance)
        print(f"[STT] {time.monotonic() - started:.2f}s: {result}")
        return result
    except Exception as error:
        print(f"[STT] {error}")
        set_voice_status(message="Could not record your microphone. Check Devices.")
        return ""
