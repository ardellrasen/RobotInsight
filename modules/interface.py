"""Loopback desktop UI. Preview: python -m modules.interface --preview."""
import base64
import io
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from modules import devices

_lock = threading.Lock()
_current_state = "warmup"
_conversation = []
_capture_image = None
_voice_enabled = True
_pending = queue.Queue(maxsize=1)
_shutdown = threading.Event()
_server = None
_token = secrets.token_urlsafe(32)
_preview = False
_revision = 0
_voice_status = {"wakeword": "starting", "message": "Starting voice input", "level": 0.0, "score": 0.0}
WEB_ROOT = Path(__file__).resolve().parent.parent / "ui"
STATES = {"idle", "warmup", "listening", "transcribing", "thinking", "searching", "capturing", "speaking", "error"}


def set_state(state):
    global _current_state
    if state not in STATES:
        raise ValueError(f"Unknown UI state: {state}")
    with _lock:
        _current_state = state


def get_state():
    with _lock:
        return _current_state


def set_conversation(question=None, answer=None):
    global _revision
    with _lock:
        if question is not None:
            _conversation.append({"role": "user", "content": str(question)})
        if answer:
            _conversation.append({"role": "assistant", "content": str(answer)})
        del _conversation[:-100]
        _revision += 1


def update_answer(answer):
    """Replace the current assistant message while tokens arrive."""
    global _revision
    with _lock:
        if _conversation and _conversation[-1]["role"] == "assistant":
            _conversation[-1]["content"] = answer
        else:
            _conversation.append({"role": "assistant", "content": answer})
        del _conversation[:-100]
        _revision += 1


def set_voice_status(**fields):
    with _lock:
        _voice_status.update({key: value for key, value in fields.items() if key in _voice_status})


def show_capture(pil_image):
    global _capture_image
    image = pil_image.copy()
    image.thumbnail((640, 480))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    with _lock:
        _capture_image = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def clear_capture():
    global _capture_image
    with _lock:
        _capture_image = None


def voice_enabled():
    with _lock:
        return _voice_enabled


def has_pending_input():
    return not _pending.empty() or _shutdown.is_set() or devices.microphone_changed()


def next_input():
    try:
        return _pending.get_nowait()
    except queue.Empty:
        return None


def is_closed():
    return _shutdown.is_set()


def _snapshot():
    with _lock:
        return {"state": _current_state, "messages": list(_conversation),
                "capture": _capture_image, "voice": _voice_enabled,
                "revision": _revision, "preview": _preview, "voice_status": dict(_voice_status)}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _send(self, status, content, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _json(self, status, value):
        self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def _authorized(self):
        return secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + _token)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/state":
            if not self._authorized():
                return self._json(403, {"error": "Open the assistant from its launcher."})
            return self._json(200, _snapshot())
        if path == "/api/devices":
            if not self._authorized():
                return self._json(403, {"error": "Open the assistant from its launcher."})
            return self._json(200, devices.list_devices(refresh=True))
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/style.css": ("style.css", "text/css; charset=utf-8"),
                 "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                 "/assets/robot.png": ("assets/robot.png", "image/png")}
        if path not in files:
            return self._json(404, {"error": "Not found"})
        filename, mime = files[path]
        try:
            self._send(200, (WEB_ROOT / filename).read_bytes(), mime)
        except FileNotFoundError:
            self._json(404, {"error": "Asset missing"})

    def do_POST(self):
        global _voice_enabled
        if not self._authorized():
            return self._json(403, {"error": "Session expired. Relaunch RobotInsight."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                return self._json(400, {"error": "Request too large or empty."})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Expected an object")
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"error": "Invalid request."})
        path = urlsplit(self.path).path
        if path == "/api/devices":
            if get_state() not in {"idle", "error"} or not _pending.empty():
                return self._json(409, {"error": "Wait until the current recording or response finishes, then apply devices."})
            try:
                result = devices.select_devices(data.get("microphone", ""), data.get("camera", ""))
            except ValueError as error:
                return self._json(400, {"error": str(error)})
            except OSError:
                return self._json(500, {"error": "Could not save device preferences. Check folder write permissions."})
            return self._json(200, result)
        if path == "/api/prompt":
            prompt = data.get("text", "")
            if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 4000:
                return self._json(400, {"error": "Enter a prompt of 1–4,000 characters."})
            item = {"type": "text", "text": prompt.strip()}
        elif path == "/api/listen":
            item = {"type": "voice"}
        elif path == "/api/voice":
            with _lock:
                _voice_enabled = bool(data.get("enabled", True))
            return self._json(200, {"ok": True})
        else:
            return self._json(404, {"error": "Not found"})
        if _preview:
            return self._json(409, {"error": "Design preview. Run Start_RobotInsight.bat to use the assistant."})
        if get_state() not in {"idle", "listening"} or not _pending.empty():
            return self._json(409, {"error": "Let me finish this response first."})
        try:
            _pending.put_nowait(item)
        except queue.Full:
            return self._json(409, {"error": "Please wait for your previous request."})
        self._json(200, {"ok": True})


def _open_window(url):
    # Edge app mode uses the installed browser as a dedicated desktop window.
    for base in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
        edge = Path(base) / "Microsoft/Edge/Application/msedge.exe"
        if edge.is_file():
            subprocess.Popen([str(edge), "--app=" + url, "--window-size=1440,940"])
            return
    webbrowser.open(url)


def start(open_browser=True, preview=False, port=0):
    global _server, _preview
    if _server is not None:
        return _server.url
    _preview = preview
    _shutdown.clear()
    _server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    _server.daemon_threads = True
    _server.url = f"http://127.0.0.1:{_server.server_port}/#{_token}"
    threading.Thread(target=_server.serve_forever, daemon=True, name="RobotInsight UI").start()
    if preview:
        set_state("idle")
        set_voice_status(wakeword="preview", message="Preview mode · start the app for voice input")
    print(f"[UI] {'Design preview' if preview else 'Interface ready'}: {_server.url}", flush=True)
    if open_browser:
        _open_window(_server.url)
    return _server.url


def stop():
    global _server
    _shutdown.set()
    if _server:
        _server.shutdown()
        _server.server_close()
        _server = None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    start(not args.no_browser, args.preview, args.port)
    try:
        while not is_closed():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stop()
