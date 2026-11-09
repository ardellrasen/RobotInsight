"""Deterministic speech endpoint, streaming and routing regressions; no mic opens."""
import atexit
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as assistant
atexit.unregister(assistant.save_memory)
from modules import interface as ui
from modules.speech_to_text import SpeechEndpoint
from modules.text_to_speech import clean_text
from modules.weather import describe_weather
from modules.wakeword import WakeWordDetector


class SpeechTests(unittest.TestCase):
    def setUp(self):
        with ui._lock:
            ui._conversation.clear()
        assistant.session_memory = []

    def test_endpoint_stops_after_speech_and_preserves_pre_roll(self):
        endpoint = SpeechEndpoint()
        frame = np.zeros(512, np.float32)
        for _ in range(8):
            self.assertFalse(endpoint.feed(frame, 0.05))
        for _ in range(15):
            self.assertFalse(endpoint.feed(frame + .1, .95))
        stopped = False
        for _ in range(23):
            if endpoint.feed(frame, .02):
                stopped = True
                break
        self.assertTrue(stopped)
        self.assertGreater(len(endpoint.audio()), 512 * 15)
        self.assertLess(endpoint.total * .032, 2)

    def test_long_utterance_is_not_cut_at_five_seconds(self):
        endpoint = SpeechEndpoint()
        for _ in range(280):
            self.assertFalse(endpoint.feed(np.ones(512, np.float32) * .1, .95))
        self.assertGreater(len(endpoint.audio()), 16000 * 8)

    def test_silence_and_short_noise_do_not_become_transcriptions(self):
        endpoint = SpeechEndpoint(wait_seconds=1)
        for index in range(35):
            stopped = endpoint.feed(np.zeros(512, np.float32), .95 if index == 2 else .01)
            if stopped:
                break
        self.assertTrue(stopped)
        self.assertEqual(len(endpoint.audio()), 0)

    def test_tts_preserves_punctuation_for_intonation(self):
        text = clean_text("**Really?** Yes, let's try it! <think>secret</think> [More](https://example.com)")
        self.assertEqual(text, "Really? Yes, let's try it! More")

    def test_streaming_replaces_one_answer_and_speaks_each_sentence_once(self):
        chunks = ["Hi", " there! ", "Let’s ", "explore."]
        client = Mock()
        client.chat.return_value = iter({"message": {"content": part}} for part in chunks)
        speech = Mock()
        ui.set_conversation(question="Hello")
        with patch.object(assistant, "_llm_client", client), patch.object(assistant, "_active_speech", speech):
            result = assistant.ask_llm("Hello", [])
        self.assertEqual(result, "Hi there! Let’s explore.")
        self.assertEqual([call.args[0] for call in speech.add.call_args_list], ["Hi there! ", "Let’s explore."])
        self.assertEqual(len(ui._snapshot()["messages"]), 2)
        self.assertEqual(ui._snapshot()["messages"][-1]["content"], result)

    def test_stable_knowledge_and_emotional_chat_skip_web_search(self):
        for prompt in ("What is a transistor?", "Explain why rainbows form.", "I've felt sad recently.", "Tell me a story today."):
            self.assertIsNone(assistant.detect_intent(prompt))
        self.assertEqual(assistant.detect_intent("Who is the current president?")["action"], "search_web")

    def test_time_and_camera_do_not_need_another_language_model_call(self):
        with patch.object(assistant, "ask_llm") as llm, patch.object(assistant, "speak"):
            assistant.handle_prompt("What time is it?")
        llm.assert_not_called()
        with patch.object(assistant, "ask_llm") as llm, patch.object(assistant, "speak"), patch.object(assistant, "capture_and_analyze", return_value="A blue notebook."):
            assistant.handle_prompt("What do you see?")
        llm.assert_not_called()

    def test_example_prompts_route_to_the_advertised_tools(self):
        cases = {"What’s the date today?": "get_date", "Will it rain in Jakarta tomorrow?": "get_weather",
                 "Look on the internet for space news.": "search_web", "Describe what’s in front of you.": "capture_image",
                 "What can you do?": "get_capabilities"}
        for prompt, action in cases.items():
            self.assertEqual(assistant.detect_intent(prompt)["action"], action)

    def test_weather_asks_for_city_without_guessing_location(self):
        with patch("modules.weather._get") as request:
            self.assertIn("Which city", describe_weather("What's the weather?"))
        request.assert_not_called()

    def test_weather_uses_live_data_without_llm(self):
        with patch("modules.weather._get", side_effect=[
            {"results": [{"name": "Jakarta", "country": "Indonesia", "latitude": -6.2, "longitude": 106.8}]},
            {"current": {"temperature_2m": 30, "apparent_temperature": 33, "time": "2026-10-20T14:15"},
             "daily": {"temperature_2m_min": [25, 24], "temperature_2m_max": [31, 32], "precipitation_probability_max": [50, 80]}}
        ]):
            result = describe_weather("Will it rain in Jakarta tomorrow?")
        self.assertIn("80 percent", result)
        self.assertIn("24 to 32", result)

    def test_wakeword_accepts_one_peak_and_uses_selected_native_rate(self):
        detector = WakeWordDetector.__new__(WakeWordDetector)
        detector.owwModel = Mock()
        detector.owwModel.predict.return_value = {"hey_in_site": .8}
        detector.samplerate, detector.chunk_size = 16000, 1280
        stream = Mock()
        stream.read.return_value = (np.ones((3840, 1), np.float32) * .03, False)
        context = Mock()
        context.__enter__ = Mock(return_value=stream)
        context.__exit__ = Mock(return_value=False)
        with patch("modules.wakeword.microphone_settings", return_value=(7, 48000)), patch("modules.wakeword.sd.InputStream", return_value=context) as open_stream, patch("modules.wakeword.time.sleep"):
            self.assertTrue(detector.start_listening())
        self.assertEqual(open_stream.call_args.kwargs["device"], 7)
        pcm = detector.owwModel.predict.call_args.args[0]
        self.assertEqual(pcm.dtype, np.int16)
        self.assertEqual(len(pcm), 1280)

    def test_wakeword_interrupt_does_not_open_microphone(self):
        detector = WakeWordDetector.__new__(WakeWordDetector)
        detector.owwModel = Mock()
        with patch("modules.wakeword.sd.InputStream") as open_stream:
            self.assertFalse(detector.start_listening(interrupt=lambda: True))
        open_stream.assert_not_called()


if __name__ == "__main__":
    unittest.main()
