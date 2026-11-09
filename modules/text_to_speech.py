"""Local female English Kokoro and native Indonesian Piper speech."""
import os
import json
from pathlib import Path
import queue
import re
import threading
import time
import unicodedata

import numpy as np
from modules.setup_speech import KOKORO_MODEL, KOKORO_VOICES, INDONESIAN_VOICE
from modules.language import detect_language

_engine = None
_engine_name = ""
_indonesian_engine = None
_engine_lock = threading.RLock()
VOICE = os.environ.get("ROBOT_TTS_VOICE", "af_heart")


def _load_piper(path):
    import onnxruntime as ort
    from piper import PiperConfig, PiperVoice
    options = ort.SessionOptions()
    options.intra_op_num_threads = min(4, os.cpu_count() or 2)
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(path), sess_options=options,
                                  providers=["CPUExecutionProvider"])
    config = PiperConfig.from_dict(json.loads(Path(str(path) + ".json").read_text(encoding="utf-8")))
    return PiperVoice(session=session, config=config)


def clean_text(text):
    """Preserve punctuation: questions, commas and exclamations carry prosody."""
    text = re.sub(r"<think>.*?(?:</think>|$)", "", text, flags=re.I | re.S)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[`*_#]+", "", text)
    text = "".join(char for char in text if unicodedata.category(char) not in {"So", "Cs"})
    return re.sub(r"\s+", " ", text).strip()


def initialize():
    global _engine, _engine_name
    with _engine_lock:
        if _engine is not None:
            return _engine
        try:
            import onnxruntime as ort
            from kokoro_onnx import Kokoro
            if not KOKORO_MODEL.is_file() or not KOKORO_VOICES.is_file():
                raise FileNotFoundError("Kokoro assets missing. Run the launcher.")
            options = ort.SessionOptions()
            options.intra_op_num_threads = min(4, os.cpu_count() or 2)
            options.inter_op_num_threads = 1
            session = ort.InferenceSession(str(KOKORO_MODEL), sess_options=options,
                                          providers=["CPUExecutionProvider"])
            _engine = Kokoro.from_session(session, str(KOKORO_VOICES))
            _engine_name = "kokoro"
        except Exception as error:
            print(f"[TTS] Kokoro unavailable: {error}. Trying the local female fallback.")
            path = Path(__file__).with_name("en_US-hfc_female-medium.onnx")
            _engine = _load_piper(path)
            _engine_name = "piper"
        print(f"[TTS] {_engine_name} ready (female voice).")
        return _engine


def synthesize(text, language=None):
    text = clean_text(text)
    if not text:
        return np.empty(0, dtype=np.float32), 24000
    with _engine_lock:
        if (language or detect_language(text)) == "id":
            global _indonesian_engine
            if _indonesian_engine is None:
                _indonesian_engine = _load_piper(INDONESIAN_VOICE)
            chunks = list(_indonesian_engine.synthesize(text))
            if not chunks:
                return np.empty(0, dtype=np.float32), 22050
            return np.concatenate([chunk.audio_float_array for chunk in chunks]), chunks[0].sample_rate
        engine = initialize()
        if _engine_name == "kokoro":
            return engine.create(text, voice=VOICE, speed=1.03, lang="en-us")
        chunks = list(engine.synthesize(text))
        if not chunks:
            return np.empty(0, dtype=np.float32), 22050
        return np.concatenate([chunk.audio_float_array for chunk in chunks]), chunks[0].sample_rate


def speak(text, language=None):
    import sounddevice as sd
    from modules.interface import voice_enabled
    if not voice_enabled():
        return
    try:
        started = time.monotonic()
        audio, rate = synthesize(text, language=language)
        print(f"[TTS] Synthesized in {time.monotonic() - started:.2f}s")
        if len(audio) and voice_enabled():
            sd.play(audio, rate)
            while sd.get_stream().active:
                if not voice_enabled():
                    sd.stop()
                    break
                time.sleep(0.03)
    except Exception as error:
        print(f"[TTS] Playback failed: {error}")


class SpeechSession:
    """Speak completed sentences as generation continues; always join before recording."""
    def __init__(self, speaker, enabled):
        self.speaker = speaker
        self.enabled = enabled
        self.items = queue.Queue(maxsize=16)
        self.sentences = 0
        self.thread = threading.Thread(target=self._run, daemon=True, name="Robot speech")
        self.thread.start()

    def _run(self):
        from modules.interface import set_state
        while True:
            sentence = self.items.get()
            if sentence is None:
                return
            if self.enabled():
                set_state("speaking")
                try:
                    self.speaker(sentence)
                except Exception as error:
                    print(f"[TTS] Sentence failed: {error}")

    def add(self, sentence):
        if sentence.strip():
            self.sentences += 1
            self.items.put(sentence.strip())

    def finish(self):
        self.items.put(None)
        self.thread.join()
