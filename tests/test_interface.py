"""Regression checks for the local UI bridge and shared assistant request path."""
import atexit
import json
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules import interface as ui
import main as assistant

# Importing the app must not overwrite personal memory during tests.
atexit.unregister(assistant.save_memory)


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = ui.start(open_browser=False).split("/#")[0]

    @classmethod
    def tearDownClass(cls):
        ui.stop()

    def setUp(self):
        ui.set_state("idle")
        with ui._lock:
            ui._conversation.clear()
            ui._voice_enabled = True
        while ui.next_input() is not None:
            pass
        ui._preview = False
        assistant.session_memory = []

    def request(self, path, data=None, authorized=True):
        headers = {"Authorization": "Bearer " + ui._token} if authorized else {}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.url + path, data=None if data is None else json.dumps(data).encode(), headers=headers)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_private_state_requires_session(self):
        ui.set_conversation(question="private prompt")
        self.assertEqual(self.request("/api/state", authorized=False)[0], 403)
        self.assertEqual(self.request("/api/prompt", {"text": "hello"}, authorized=False)[0], 403)
        self.assertEqual(self.request("/api/devices", authorized=False)[0], 403)
        self.assertEqual(self.request("/api/devices", {"microphone": "", "camera": ""}, authorized=False)[0], 403)

    def test_device_selection_endpoint_and_busy_guard(self):
        catalog = {"microphones": [], "cameras": [], "selected": {"microphone": "", "camera": ""}, "errors": {}}
        with patch.object(ui.devices, "list_devices", return_value=catalog), patch.object(ui.devices, "select_devices", return_value=catalog) as choose:
            self.assertEqual(self.request("/api/devices")[1], catalog)
            self.assertEqual(self.request("/api/devices", {"microphone": "mic", "camera": "cam"})[0], 200)
            choose.assert_called_once_with("mic", "cam")
            ui.set_state("listening")
            self.assertEqual(self.request("/api/devices", {"microphone": "mic", "camera": "cam"})[0], 409)
            self.assertEqual(choose.call_count, 1)
        ui.set_state("idle")
        with patch.object(ui.devices, "select_devices", side_effect=ValueError("Disconnected")):
            self.assertEqual(self.request("/api/devices", {"microphone": "lost", "camera": ""})[0], 400)

    def test_typed_prompt_reaches_shared_assistant_path(self):
        self.assertEqual(self.request("/api/prompt", {"text": "Tell me a short joke."})[0], 200)
        self.assertTrue(ui.has_pending_input())
        prompt = ui.next_input()
        with patch.object(assistant, "ask_llm", return_value="A byte walks into a bar."), patch.object(assistant, "speak") as speak:
            assistant.handle_prompt(prompt["text"])
        speak.assert_called_once_with("A byte walks into a bar.")
        messages = self.request("/api/state")[1]["messages"]
        self.assertEqual([m["role"] for m in messages], ["user", "assistant"])
        self.assertEqual(assistant.session_memory, messages)

    def test_invalid_and_busy_prompts_are_rejected(self):
        for value in (" ", "a" * 4001, 17):
            self.assertEqual(self.request("/api/prompt", {"text": value})[0], 400)
        ui.set_state("thinking")
        self.assertEqual(self.request("/api/prompt", {"text": "hello"})[0], 409)
        self.assertIsNone(ui.next_input())
        ui.set_state("idle")
        self.assertEqual(self.request("/api/prompt", {"text": "one"})[0], 200)
        self.assertEqual(self.request("/api/prompt", {"text": "two"})[0], 409)

    def test_microphone_and_mute(self):
        self.assertEqual(self.request("/api/listen", {})[0], 200)
        self.assertEqual(ui.next_input(), {"type": "voice"})
        self.assertEqual(self.request("/api/voice", {"enabled": False})[0], 200)
        with patch.object(assistant, "_speak") as speak:
            assistant.speak("quiet")
        speak.assert_not_called()
        self.assertFalse(self.request("/api/state")[1]["voice"])

    def test_camera_and_search_still_use_existing_actions(self):
        with patch.object(assistant, "capture_and_analyze", return_value="A desk."), patch.object(assistant, "ask_llm", return_value="I see a desk."), patch.object(assistant, "speak"):
            assistant.handle_prompt("What do you see?")
        self.assertEqual(ui._snapshot()["messages"][-1]["content"], "A desk.")
        self.assertEqual(assistant.detect_intent("Search for space discoveries.")["action"], "search_web")

    def test_long_responses_are_preserved_as_text(self):
        answer = "<script>alert('not executable')</script> " + "Long response. " * 300
        ui.set_conversation(question="Explain", answer=answer)
        self.assertEqual(self.request("/api/state")[1]["messages"][-1]["content"], answer)

    def test_preview_does_not_queue_real_actions(self):
        ui._preview = True
        self.assertEqual(self.request("/api/prompt", {"text": "hello"})[0], 409)
        self.assertIsNone(ui.next_input())

    def test_only_packaged_assets_are_served(self):
        self.assertEqual(self.request("/../main.py")[0], 404)
        for path in ("/", "/style.css", "/app.js", "/assets/robot.png"):
            with urlopen(self.url + path) as response:
                self.assertEqual(response.status, 200)
                self.assertGreater(len(response.read()), 100)


if __name__ == "__main__":
    unittest.main()
