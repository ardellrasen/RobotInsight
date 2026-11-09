"""Bilingual routing, transcription and voice selection without hardware."""
import atexit
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import main as assistant
from modules.language import detect_language, is_standby
from modules import speech_to_text as stt, text_to_speech as tts
from modules.weather import describe_weather

atexit.unregister(assistant.save_memory)


class BilingualTests(unittest.TestCase):
    def test_language_switches_and_ambiguous_followups_keep_context(self):
        self.assertEqual(detect_language("Bagaimana cuaca di Jakarta besok?"), "id")
        self.assertEqual(detect_language("What time is it?", fallback="id"), "en")
        self.assertEqual(detect_language("Jakarta", fallback="id"), "id")

    def test_indonesian_commands_route_to_real_tools(self):
        cases = {"Jam berapa sekarang?": "get_time", "Hari ini tanggal berapa?": "get_date",
                 "Apa yang kamu lihat?": "capture_image", "Kamu bisa apa?": "get_capabilities",
                 "Bagaimana cuaca di Jakarta besok?": "get_weather",
                 "Cari di internet tentang NASA": "search_web",
                 "Siapa presiden Indonesia?": "search_web"}
        for question, action in cases.items():
            with self.subTest(question=question):
                self.assertEqual(assistant.detect_intent(question)["action"], action)
        for question in ("Jelaskan lebih sederhana.", "Kenapa begitu?", "Lanjutkan."):
            self.assertIsNone(assistant.detect_intent(question))

    def test_native_standby_commands(self):
        for phrase in ("Istirahat.", "Berhenti mendengarkan", "Sudah cukup!", "Go to sleep"):
            self.assertTrue(is_standby(phrase))
        self.assertFalse(is_standby("Ceritakan tentang istirahat"))

    def test_auto_stt_does_not_force_english(self):
        model = Mock()
        segment = SimpleNamespace(text=" Jam berapa sekarang?", no_speech_prob=.01, avg_logprob=-.1)
        model.transcribe.return_value = ([segment], SimpleNamespace(language="id"))
        with patch.object(stt, "initialize", return_value=model), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(stt.transcribe_audio(np.zeros(16000)), "Jam berapa sekarang?")
        self.assertIsNone(model.transcribe.call_args.kwargs["language"])
        self.assertEqual(model.transcribe.call_count, 1)

    def test_malay_detection_retries_as_indonesian(self):
        model = Mock()
        segment = SimpleNamespace(text="Cuaca besok", no_speech_prob=.01, avg_logprob=-.1)
        model.transcribe.side_effect = [([], SimpleNamespace(language="ms")),
                                        ([segment], SimpleNamespace(language="id"))]
        with patch.object(stt, "initialize", return_value=model), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(stt.transcribe_audio(np.zeros(16000)), "Cuaca besok")
        self.assertEqual(model.transcribe.call_args.kwargs["language"], "id")

    def test_indonesian_voice_uses_native_piper(self):
        native = Mock()
        native.synthesize.return_value = [SimpleNamespace(audio_float_array=np.zeros(100), sample_rate=22050)]
        with patch.object(tts, "_indonesian_engine", native), patch.object(tts, "initialize") as english:
            audio, rate = tts.synthesize("Halo, aku siap membantu!")
        english.assert_not_called()
        native.synthesize.assert_called_once()
        self.assertEqual((len(audio), rate), (100, 22050))

    def test_camera_receives_a_supported_visual_instruction(self):
        from modules.vision import vision_prompt
        self.assertEqual(vision_prompt("What do you see?"), "What do you see?")
        self.assertIn("Read the text", vision_prompt("Bacakan teks di depanmu."))
        self.assertIn("color", vision_prompt("Apa warna benda itu?"))
        self.assertIn("appearance", vision_prompt("Bagaimana penampilanku?"))
        self.assertIn("describe", vision_prompt("Apa yang kamu lihat?"))

    def test_english_voice_stays_kokoro(self):
        english = Mock()
        english.create.return_value = (np.zeros(100), 24000)
        with patch.object(tts, "initialize", return_value=english), patch.object(tts, "_engine_name", "kokoro"), patch.object(tts, "_indonesian_engine") as native:
            tts.synthesize("Hello! How are you?")
        english.create.assert_called_once()
        native.synthesize.assert_not_called()

    def test_direct_answers_use_indonesian(self):
        with patch.object(assistant, "_reply_language", "id"):
            self.assertIn("Sekarang pukul", assistant.execute_action({"action": "get_time"}))
            self.assertIn("Sekarang hari", assistant.execute_action({"action": "get_date"}))
            self.assertIn("Ucapkan Hey In Site", assistant.execute_action({"action": "get_capabilities"}))

    def test_weather_uses_indonesian_city_and_tomorrow(self):
        with patch("modules.weather._get", side_effect=[
            {"results": [{"name": "Jakarta", "latitude": -6.2, "longitude": 106.8}]},
            {"daily": {"temperature_2m_min": [25, 24], "temperature_2m_max": [31, 32], "precipitation_probability_max": [50, 80]}}
        ]) as request:
            result = describe_weather("Bagaimana cuaca di Jakarta besok?")
        self.assertEqual(request.call_args_list[0].args[1]["name"], "Jakarta")
        self.assertEqual(request.call_args_list[0].args[1]["language"], "id")
        self.assertIn("Besok di Jakarta", result)
        self.assertIn("80 persen", result)
        self.assertIn("24 sampai 32", result)

    def test_chat_requests_native_language(self):
        client = Mock()
        client.chat.return_value = iter([{"message": {"content": "Halo, aku siap membantu!"}}])
        with patch.object(assistant, "_llm_client", client), patch.object(assistant, "_active_speech", None):
            assistant.ask_llm("Halo, apa kabar?", [{"role": "user", "content": "Halo, apa kabar?"}])
        arguments = client.chat.call_args.kwargs
        self.assertIn("Bahasa Indonesia", arguments["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main()
