"""Local female speech: Piper for English and Indonesian, Kokoro optional for English."""
from concurrent.futures import ThreadPoolExecutor
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
# Piper is about 10x faster than Kokoro on this CPU; Kokoro sounds more natural.
ENGLISH_ENGINE = os.environ.get("ROBOT_TTS_ENGINE", "piper")
# The "cerah" tone: a higher pitch (about 276 Hz), with length_scale offsetting
# the speed-up that the pitch shift causes.
INDONESIAN_PITCH = 1.08
INDONESIAN_TONE = {"length_scale": 1.08, "noise_scale": 0.75}
# One worker: sentences are synthesized in order and never compete with each other.
_prepare_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="Robot speech prep")
_prepared = {}
_prepared_lock = threading.Lock()


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
        if ENGLISH_ENGINE == "kokoro":
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
                print(f"[TTS] Kokoro unavailable: {error}. Using Piper.")
        if _engine is None:
            _engine = _load_piper(Path(__file__).with_name("en_US-hfc_female-medium.onnx"))
            _engine_name = "piper"
        print(f"[TTS] {_engine_name} ready (female voice).")
        return _engine


def synthesize(text, language=None):
    text = clean_text(text)
    if not text:
        return np.empty(0, dtype=np.float32), 24000
    with _engine_lock:
        indonesian = (language or detect_language(text)) == "id"
        # The name is written "Insight" but each voice needs its own spelling to say it.
        text = re.sub(r"\bInsight\b", "Insait" if indonesian else "In Site", text)
        if indonesian:
            text = re.sub(r"\bPlay[\s-]?Tech\b", "Plei Tek", text, flags=re.I)
            text = re.sub(r"\bShow[\s-]?Tech\b", "Syo Tek", text, flags=re.I)
        if indonesian:
            global _indonesian_engine
            if _indonesian_engine is None:
                _indonesian_engine = _load_piper(INDONESIAN_VOICE)
            from piper.voice import SynthesisConfig
            from scipy.signal import resample_poly
            chunks = list(_indonesian_engine.synthesize(text, syn_config=SynthesisConfig(**INDONESIAN_TONE)))
            if not chunks:
                return np.empty(0, dtype=np.float32), 22050
            audio = np.concatenate([chunk.audio_float_array for chunk in chunks])
            # Fewer samples at the same playback rate raises the pitch.
            return resample_poly(audio, 100, round(100 * INDONESIAN_PITCH)).astype(np.float32), chunks[0].sample_rate
        engine = initialize()
        if _engine_name == "kokoro":
            return engine.create(text, voice=VOICE, speed=1.03, lang="en-us")
        chunks = list(engine.synthesize(text))
        if not chunks:
            return np.empty(0, dtype=np.float32), 22050
        return np.concatenate([chunk.audio_float_array for chunk in chunks]), chunks[0].sample_rate


def warm_up():
    """The first synthesis per engine is several times slower; absorb it at startup."""
    for sample, language in (("Hello there.", "en"), ("Halo, apa kabar?", "id")):
        try:
            synthesize(sample, language=language)
        except Exception as error:
            print(f"[TTS] Warmup failed for {language}: {error}")


def prepare(text, language=None):
    """Queue synthesis ahead of playback so consecutive sentences have no gap."""
    key = (text, language)
    with _prepared_lock:
        if key in _prepared:
            return
        while len(_prepared) >= 8:  # Abandoned when voice is muted mid-answer.
            _prepared.pop(next(iter(_prepared)))
        _prepared[key] = _prepare_pool.submit(synthesize, text, language)


def speak(text, language=None):
    import sounddevice as sd
    from modules.interface import voice_enabled
    if not voice_enabled():
        return
    try:
        started = time.monotonic()
        with _prepared_lock:
            pending = _prepared.pop((text, language), None)
        audio, rate = pending.result() if pending else synthesize(text, language=language)
        print(f"[TTS] Audio ready in {time.monotonic() - started:.2f}s")
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
    def __init__(self, speaker, enabled, prepare=None):
        self.speaker = speaker
        self.enabled = enabled
        self.prepare = prepare
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
            if self.prepare is not None:
                self.prepare(sentence.strip())
            self.items.put(sentence.strip())

    def finish(self):
        self.items.put(None)
        self.thread.join()
