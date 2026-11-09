"""Idempotent, project-local downloads for offline speech. Run via the launcher."""
from pathlib import Path
import os
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models"
STT_NAME = os.environ.get("ROBOT_STT_MODEL", "small")
KOKORO_MODEL = MODEL_DIR / "kokoro" / "kokoro-v1.0.onnx"
KOKORO_VOICES = MODEL_DIR / "kokoro" / "voices-v1.0.bin"
STT_DIR = MODEL_DIR / "whisper" / STT_NAME
WAKE_DIR = MODEL_DIR / "wakeword"
INDONESIAN_VOICE = MODEL_DIR / "piper" / "id_ID-news_tts-medium.onnx"


def download(url, destination):
    if destination.is_file() and destination.stat().st_size > 1024:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    print(f"[SETUP] Downloading {destination.name}", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "RobotInsight/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, length=256 * 1024)
        if temporary.stat().st_size < 1024:
            raise RuntimeError(f"Downloaded file is incomplete: {destination.name}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def setup_wakeword():
    import openwakeword
    for feature in openwakeword.FEATURE_MODELS.values():
        url = feature["download_url"].replace(".tflite", ".onnx")
        download(url, WAKE_DIR / url.rsplit("/", 1)[-1])


def setup_tts():
    release = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
    download(release + KOKORO_MODEL.name, KOKORO_MODEL)
    download(release + KOKORO_VOICES.name, KOKORO_VOICES)
    base = "https://huggingface.co/rhasspy/piper-voices/resolve/main/id/id_ID/news_tts/medium/"
    download(base + INDONESIAN_VOICE.name, INDONESIAN_VOICE)
    download(base + INDONESIAN_VOICE.name + ".json", Path(str(INDONESIAN_VOICE) + ".json"))


def setup_stt():
    if all((STT_DIR / name).is_file() for name in ("model.bin", "config.json", "tokenizer.json")):
        return
    from huggingface_hub import snapshot_download
    snapshot_download(f"Systran/faster-whisper-{STT_NAME}", local_dir=str(STT_DIR),
                      allow_patterns=["model.bin", "config.json", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"])


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wake-only", action="store_true")
    args = parser.parse_args()
    setup_wakeword()
    if not args.wake_only:
        setup_tts()
        setup_stt()
    print("[SETUP] Speech assets ready.", flush=True)
