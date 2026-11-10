"""Regression checks for the local UI bridge and shared assistant request path."""
import atexit
import json
import sys
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules import interface as ui, text_to_speech
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

    def test_language_endpoint_switches_mode_and_rejects_unknown_values(self):
        from modules import language
        self.addCleanup(language.set_language_mode, "auto")
        ui._preview = True  # Preview mode never writes the saved choice.
        self.assertEqual(self.request("/api/language", {"mode": "en"}), (200, {"language": "en"}))
        self.assertEqual(self.request("/api/state")[1]["language"], "en")
        self.assertEqual(self.request("/api/language", {"mode": "fr"})[0], 400)
        self.assertEqual(language.language_mode(), "en")

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

    def test_stop_endpoint_only_acts_on_a_response(self):
        self.assertEqual(self.request("/api/stop", {}, authorized=False)[0], 403)
        generation = ui.stop_generation()
        self.assertEqual(self.request("/api/stop", {}), (200, {"stopped": False}))
        ui.set_state("listening")
        self.assertEqual(self.request("/api/stop", {}), (200, {"stopped": False}))
        self.assertEqual(ui.stop_generation(), generation)
        for state in ("thinking", "searching", "capturing", "speaking"):
            ui.set_state(state)
            self.assertEqual(self.request("/api/stop", {}), (200, {"stopped": True}))
            self.assertEqual(ui.get_state(), "idle")

    def test_stopped_response_cannot_change_the_state(self):
        ui.set_state("thinking")
        turn = ui.stop_generation()
        ui.stop_response()
        ui.set_state("speaking", turn=turn)
        self.assertEqual(ui.get_state(), "idle")

    def test_stop_returns_at_once_and_a_late_answer_is_discarded(self):
        started, release = threading.Event(), threading.Event()
        def slow_model(*_args, **_kwargs):
            started.set()
            release.wait(5)
            return "A late answer."
        with patch.object(assistant, "ask_llm", side_effect=slow_model), patch.object(assistant, "speak") as speak:
            caller = threading.Thread(target=assistant.respond, args=("Tell me a story",), daemon=True)
            caller.start()
            self.assertTrue(started.wait(3))
            self.assertEqual(ui.get_state(), "thinking")
            self.assertEqual(self.request("/api/stop", {})[1], {"stopped": True})
            caller.join(1)
            self.assertFalse(caller.is_alive())  # The model is still blocked at this point.
            workers = [t for t in threading.enumerate() if t.name == "Assistant request"]
            release.set()
            for worker in workers:
                worker.join(3)
        speak.assert_not_called()
        self.assertEqual(ui.get_state(), "idle")
        self.assertEqual(assistant.session_memory, [])
        self.assertEqual([m["content"] for m in ui._snapshot()["messages"]][0], "Tell me a story")
        self.assertNotIn("A late answer.", [m["content"] for m in ui._snapshot()["messages"]])
        self.assertIn(ui._snapshot()["messages"][-1]["content"], ("Stopped.", "Dihentikan."))

    def test_stop_closes_the_stream_and_keeps_the_partial_text(self):
        closed = []
        def stream():
            try:
                yield {"message": {"content": "Halfway"}}
                ui.set_state("thinking")
                ui.stop_response()
                yield {"message": {"content": " there."}}
                self.fail("The stream continued after Stop.")
            finally:
                closed.append(True)
        client = Mock()
        client.chat.return_value = stream()
        speech = Mock()
        ui.set_conversation(question="Hello")
        turn = ui.stop_generation()
        with patch.object(assistant, "_llm_client", client), patch.object(assistant, "_active_speech", speech):
            with self.assertRaises(assistant.TurnStopped):
                assistant.ask_llm("Hello", [], turn=turn)
        self.assertEqual(closed, [True])
        speech.add.assert_not_called()
        self.assertEqual(ui._snapshot()["messages"][-1]["content"], "Halfway")

    def test_stop_ends_playback_of_the_current_sentence(self):
        fake_sound = Mock()
        fake_sound.get_stream.return_value.active = True
        def sound_stops():
            fake_sound.get_stream.return_value.active = False
        fake_sound.stop.side_effect = sound_stops
        fake_sound.play.side_effect = lambda *_args: (ui.set_state("speaking"), ui.stop_response())
        with patch.dict(sys.modules, {"sounddevice": fake_sound}), patch("modules.text_to_speech.synthesize", return_value=(np.ones(10), 22050)):
            text_to_speech.speak("Halo.", language="id")
        fake_sound.stop.assert_called_once()

    def test_stop_skips_the_sentences_still_queued(self):
        ui.set_state("thinking")
        speaker = Mock()
        session = text_to_speech.SpeechSession(speaker, lambda: True, turn=ui.stop_generation())
        ui.stop_response()
        session.add("Should stay silent.")
        session.finish()
        speaker.assert_not_called()
        self.assertEqual(ui.get_state(), "idle")

    def test_answer_returns_to_standby_without_listening_again(self):
        closed = threading.Event()
        states_at_wake = []
        def wake(**_kwargs):
            states_at_wake.append(ui.get_state())
            if len(states_at_wake) == 1:
                return True
            closed.set()
            return False
        detector = Mock()
        detector.start_listening.side_effect = wake
        listen = Mock(return_value="Halo robot")
        with patch.object(assistant, "start_ui"), patch.object(assistant, "restore_language_mode"), \
                patch("ollama.Client"), patch.object(assistant, "is_closed", closed.is_set), \
                patch("modules.text_to_speech.initialize"), patch("modules.text_to_speech.warm_up"), \
                patch("modules.speech_to_text.initialize"), patch("modules.speech_to_text.listen", listen), \
                patch("modules.wakeword.WakeWordDetector", return_value=detector), \
                patch.object(assistant, "handle_prompt") as handle:
            assistant.main()
        handle.assert_called_once()
        self.assertEqual(handle.call_args.args[0], "Halo robot")
        listen.assert_called_once()
        self.assertEqual(states_at_wake[-1], "idle")

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
