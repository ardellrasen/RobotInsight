"""Detect capture devices and share the chosen hardware with all assistant paths.

Enumeration never starts a camera capture or microphone recording. Preferences use
device identities rather than OpenCV/PortAudio indices, which can change at boot.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import threading

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "device_settings.json"
_lock = threading.RLock()
_catalog = None
_microphone_changed = threading.Event()


def _load_preferences():
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return {key: data.get(key) if isinstance(data.get(key), str) else ""
                for key in ("microphone", "camera")}
    except (OSError, ValueError, AttributeError):
        return {"microphone": "", "camera": ""}


_preferences = _load_preferences()


def _identity(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _scan_microphones():
    import sounddevice as sd
    hosts = sd.query_hostapis()
    found, occurrences = [], {}
    for index, info in enumerate(sd.query_devices()):
        if info["max_input_channels"] < 1:
            continue
        host = hosts[info["hostapi"]]["name"]
        # This assistant uses PortAudio's blocking read API. WDM-KS does not
        # implement that API and also exposes disconnected Windows endpoints.
        if host == "Windows WDM-KS":
            continue
        key = f"{info['name']}|{host}"
        ordinal = occurrences.get(key, 0)
        occurrences[key] = ordinal + 1
        found.append({"id": _identity(f"{key}|{ordinal}"), "index": index,
                      "name": info["name"], "host": host, "ordinal": ordinal})
    # PortAudio exposes the same microphone through several Windows APIs. Keep
    # one entry per name, preferring full WASAPI names over truncated MME names.
    priority = {"Windows WASAPI": 0, "Windows DirectSound": 1, "MME": 2, "Windows WDM-KS": 3}
    unique = []
    for item in sorted(found, key=lambda item: priority.get(item["host"], 4)):
        name = item["name"].casefold()
        if name in {"microsoft sound mapper - input", "primary sound capture driver"}:
            continue
        if any(other["host"] != item["host"] and other["ordinal"] == item["ordinal"]
               and (other["name"].casefold() == name
                    or (item["host"] == "MME" and len(name) >= 30
                        and other["name"].casefold().startswith(name)))
               for other in unique):
            continue
        unique.append(item)
    for item in unique:
        if item["ordinal"]:
            item["name"] += f" ({item['ordinal'] + 1})"
    return unique


def _scan_cameras():
    import cv2
    from cv2_enumerate_cameras import enumerate_cameras
    # Select one Windows backend to avoid listing each physical camera twice.
    backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
    cameras = enumerate_cameras(backend)
    if not cameras and os.name == "nt":
        cameras = enumerate_cameras(cv2.CAP_MSMF)
    return [{"id": _identity(f"{c.backend}|{c.path or str(c.index) + c.name}"),
             "index": int(c.index), "backend": int(c.backend), "name": c.name}
            for c in cameras]


def list_devices(refresh=False):
    global _catalog
    with _lock:
        if _catalog is None or refresh:
            microphones, cameras, errors = [], [], {}
            try:
                microphones = _scan_microphones()
            except Exception as error:
                print(f"[DEVICES] Microphone enumeration failed: {error}")
                errors["microphone"] = "Microphone detection unavailable. Run the launcher to check audio dependencies."
            try:
                cameras = _scan_cameras()
            except Exception as error:
                print(f"[DEVICES] Camera enumeration failed: {error}")
                errors["camera"] = "Camera detection unavailable. Run the launcher to check camera dependencies."
            _catalog = {"microphones": microphones, "cameras": cameras, "errors": errors}
        return {**_catalog, "selected": dict(_preferences)}


def select_devices(microphone, camera):
    """Validate both choices before saving either. Empty means system/default."""
    global _preferences
    if not isinstance(microphone, str) or not isinstance(camera, str):
        raise ValueError("Choose a microphone and camera from the detected devices.")
    with _lock:
        catalog = list_devices(refresh=True)
        for kind, choice, items in (("microphone", microphone, catalog["microphones"]),
                                    ("camera", camera, catalog["cameras"])):
            if choice and not any(item["id"] == choice for item in items):
                raise ValueError(f"That {kind} is no longer detected. Refresh and choose another device.")
        preferences = {"microphone": microphone, "camera": camera}
        temporary = SETTINGS_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(preferences, indent=2), encoding="utf-8")
        temporary.replace(SETTINGS_PATH)
        # Reapplying the current pair also retries a microphone after reconnect.
        changed = microphone != _preferences["microphone"] or preferences == _preferences
        _preferences = preferences
        if changed:
            _microphone_changed.set()
        return {**catalog, "selected": dict(preferences)}


def _selected(kind):
    with _lock:
        choice = _preferences[kind]
        if not choice:
            return None
        items = list_devices()["microphones" if kind == "microphone" else "cameras"]
        for item in items:
            if item["id"] == choice:
                return item
    raise RuntimeError(f"The selected {kind} is disconnected. Choose another in Devices.")


def microphone_settings():
    """Return an input index and supported capture rate, without opening a stream."""
    import sounddevice as sd
    selected = _selected("microphone")
    index = selected["index"] if selected else None
    info = sd.query_devices(index, "input")
    rate = 16000
    try:
        sd.check_input_settings(device=index, channels=1, dtype="float32", samplerate=rate)
    except Exception:
        # WASAPI/USB devices can require their native rate. Resample for models.
        rate = int(info["default_samplerate"])
        sd.check_input_settings(device=index, channels=1, dtype="float32", samplerate=rate)
    return index, rate


def to_model_rate(audio, sample_rate):
    if sample_rate == 16000:
        return audio
    from scipy.signal import resample_poly
    divisor = math.gcd(sample_rate, 16000)
    return resample_poly(audio, 16000 // divisor, sample_rate // divisor)


def camera_settings():
    selected = _selected("camera")
    return (selected["index"], selected["backend"]) if selected else (0, 0)


def microphone_changed():
    return _microphone_changed.is_set()


def consume_microphone_change():
    changed = _microphone_changed.is_set()
    _microphone_changed.clear()
    return changed
