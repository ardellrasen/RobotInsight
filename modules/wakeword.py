import numpy as np
import sounddevice as sd
from openwakeword.model import Model
import os
import time
from modules.devices import microphone_settings, to_model_rate
from modules.setup_speech import WAKE_DIR, setup_wakeword

class WakeWordDetector:
    def __init__(self):
        print("[WAKEWORD] Initializing...")
        module_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(module_dir, "hey_in_site.onnx")

        print(f"[WAKEWORD] Looking for model at: {model_path}")
        print(f"[WAKEWORD] Model exists: {os.path.exists(model_path)}")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Custom wake word model not found: {model_path}")

        setup_wakeword()

        try:
            self.owwModel = Model(
                wakeword_models=[model_path],
                inference_framework="onnx",
                melspec_model_path=str(WAKE_DIR / "melspectrogram.onnx"),
                embedding_model_path=str(WAKE_DIR / "embedding_model.onnx"),
            )
            self.samplerate = 16000
            self.chunk_size = 1280
            print("[WAKEWORD] Custom model 'hey_in_site.onnx' loaded successfully!")
        except Exception as e:
            print(f"[WAKEWORD] Error loading model: {e}")
            raise

    def start_listening(self, interrupt=None):
        from modules.interface import set_voice_status
        print("[WAKEWORD] Listening for 'Hey In Site'...")

        # Reset model scores so leftover high scores don't instantly re-trigger
        self.owwModel.reset()

        # How many chunks must score HIGH in a row before we accept it
        # Prevents a single noisy frame from triggering
        THRESHOLD = float(os.environ.get("ROBOT_WAKE_THRESHOLD", "0.45"))
        # A short custom wake phrase may peak for just one 80 ms frame.
        CONFIRM_CHUNKS = 1
        COOLDOWN_AFTER = 0.12

        # Let a typed prompt or the microphone button interrupt wake-word standby.
        deadline = time.monotonic() + COOLDOWN_AFTER
        while time.monotonic() < deadline:
            if interrupt is not None and interrupt():
                return False
            time.sleep(0.05)

        consecutive = 0
        device, sample_rate = microphone_settings()
        capture_chunk = round(self.chunk_size * sample_rate / self.samplerate)

        with sd.InputStream(
            device=device,
            samplerate=sample_rate,
            channels=1,
            blocksize=capture_chunk,
            dtype="float32"
        ) as stream:
            set_voice_status(wakeword="ready", message="Say “Hey In Site”", level=0, score=0)
            last_meter = 0
            while True:
                if interrupt is not None and interrupt():
                    return False
                audio, _ = stream.read(capture_chunk)
                if len(audio) == 0:
                    continue

                model_audio = to_model_rate(audio.flatten(), sample_rate)
                pcm = (np.clip(model_audio, -1, 1) * 32767).astype(np.int16)
                predictions = self.owwModel.predict(pcm)
                if time.monotonic() - last_meter >= 0.2:
                    set_voice_status(level=min(1.0, float(np.sqrt(np.mean(model_audio ** 2))) * 12),
                                     score=float(max(predictions.values(), default=0)))
                    last_meter = time.monotonic()

                detected = any(score > THRESHOLD for score in predictions.values())

                if detected:
                    consecutive += 1
                    if consecutive >= CONFIRM_CHUNKS:
                        score = max(predictions.values())
                        print(f"[WAKEWORD] Confirmed wake word (Score: {score:.2f})")
                        self.owwModel.reset()  # clear state so it doesn't re-fire
                        return True
                else:
                    consecutive = 0  # reset streak if any chunk drops below threshold
