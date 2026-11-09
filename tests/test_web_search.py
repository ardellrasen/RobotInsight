"""Search requests must carry a real topic and use retrieved evidence."""
import atexit
import json
import unittest
from unittest.mock import Mock, patch

import main as assistant
from modules import interface as ui
from modules.web_search import search_request

atexit.unregister(assistant.save_memory)


class WebSearchTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("_pending_search", False), ("_reply_language", "en"), ("session_memory", [])):
            replacement = patch.object(assistant, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        with ui._lock:
            ui._conversation.clear()

    def test_topic_free_commands_are_recognized_without_punctuation_queries(self):
        for text in ("Look on the internet.", "Search the internet.", "Search the web!",
                     "Please look online.", "Can you search the internet for?", "Google.",
                     "Cari di internet.", "Tolong cari di web tentang."):
            with self.subTest(text=text):
                self.assertEqual(assistant.detect_intent(text), {"action": "search_web", "value": ""})

    def test_topics_are_preserved_and_explicit_search_takes_priority(self):
        for text, query in (("Look on the internet for NASA Artemis news.", "NASA Artemis news"),
                            ("Could you please search the web about C++?", "C++"),
                            ("Cari di internet tentang berita NASA.", "berita NASA"),
                            ("Search for the weather in Jakarta.", "the weather in Jakarta")):
            self.assertEqual(assistant.detect_intent(text), {"action": "search_web", "value": query})
        self.assertIsNone(search_request("What is Google?"))
        self.assertIsNone(search_request("Explain how internet search works."))

    def test_empty_query_never_reaches_the_search_provider(self):
        with patch("ddgs.DDGS") as provider:
            self.assertEqual(assistant.execute_action({"action": "search_web", "value": ".?!"}), {"type": "search_clarification"})
        provider.assert_not_called()

    def test_bare_request_asks_then_searches_next_reply(self):
        with patch("ddgs.DDGS") as provider, patch.object(assistant, "ask_llm") as llm, patch.object(assistant, "speak"):
            assistant.handle_prompt("Look on the internet.")
        self.assertIn("What would you like me to search", ui._snapshot()["messages"][-1]["content"])
        provider.assert_not_called()
        llm.assert_not_called()
        self.assertTrue(assistant._pending_search)
        result = {"type": "search_results", "sources": [{"title": "NASA", "snippet": "Artemis explores the Moon.", "url": "https://www.nasa.gov/"}]}
        with patch.object(assistant, "execute_action", return_value=result) as execute, patch.object(assistant, "ask_llm", return_value="NASA's Artemis program explores the Moon.") as llm, patch.object(assistant, "speak"):
            assistant.handle_prompt("NASA Artemis")
        execute.assert_called_once_with({"action": "search_web", "value": "NASA Artemis"})
        messages = llm.call_args.args[1]
        self.assertIn("ALREADY performed a live internet search", messages[0]["content"])
        self.assertEqual(json.loads(messages[1]["content"])["search_results"], result["sources"])
        self.assertFalse(assistant._pending_search)

    def test_indonesian_clarification_and_topic_reply(self):
        with patch.object(assistant, "speak"):
            assistant.handle_prompt("Tolong cari di internet.")
        self.assertIn("Mau cari apa", ui._snapshot()["messages"][-1]["content"])
        with patch.object(assistant, "execute_action", return_value={"type": "search_results", "sources": []}) as execute, patch.object(assistant, "speak"):
            assistant.handle_prompt("berita NASA")
        execute.assert_called_once_with({"action": "search_web", "value": "berita NASA"})

    def test_cancel_and_new_commands_leave_topic_prompt(self):
        for prompt in ("Never mind.", "What time is it?"):
            assistant._pending_search = True
            with patch.object(assistant, "ask_llm") as llm, patch("ddgs.DDGS") as provider, patch.object(assistant, "speak"):
                assistant.handle_prompt(prompt)
            self.assertFalse(assistant._pending_search)
            llm.assert_not_called()
            provider.assert_not_called()

    def test_provider_receives_the_clean_query_and_returns_sources(self):
        provider = Mock()
        provider.__enter__ = Mock(return_value=provider)
        provider.__exit__ = Mock(return_value=False)
        provider.text.return_value = [{"title": "NASA", "body": "Moon missions", "href": "https://www.nasa.gov/"}]
        with patch("ddgs.DDGS", return_value=provider):
            result = assistant.execute_action({"action": "search_web", "value": "NASA."})
        self.assertEqual(provider.text.call_args.args[0], "NASA")
        self.assertEqual(result["sources"][0]["url"], "https://www.nasa.gov/")

    def test_provider_failure_tries_a_fallback(self):
        provider = Mock()
        provider.__enter__ = Mock(return_value=provider)
        provider.__exit__ = Mock(return_value=False)
        provider.text.side_effect = [RuntimeError("network unreachable"),
                                    [{"title": "NASA", "body": "Moon missions", "href": "https://www.nasa.gov/"}]]
        with patch("ddgs.DDGS", return_value=provider):
            result = assistant.execute_action({"action": "search_web", "value": "NASA"})
        self.assertEqual(result["type"], "search_results")
        self.assertEqual([call.kwargs["backend"] for call in provider.text.call_args_list], ["yahoo", "google,duckduckgo,brave"])

    def test_empty_snippets_and_unsafe_urls_do_not_become_evidence(self):
        provider = Mock()
        provider.__enter__ = Mock(return_value=provider)
        provider.__exit__ = Mock(return_value=False)
        provider.text.return_value = [{"title": "No evidence", "body": "", "href": "https://example.com/"},
                                     {"title": "Bad link", "body": "Anything", "href": "javascript:alert(1)"}]
        with patch("ddgs.DDGS", return_value=provider):
            result = assistant.execute_action({"action": "search_web", "value": "NASA"})
        self.assertEqual(result, {"type": "search_results", "sources": []})

    def test_provider_failure_and_no_results_skip_the_language_model(self):
        for result in ({"type": "search_error", "message": "timeout"}, {"type": "search_results", "sources": []}):
            with patch.object(assistant, "execute_action", return_value=result), patch.object(assistant, "ask_llm") as llm, patch.object(assistant, "speak"):
                assistant.handle_prompt("Search for NASA.")
            llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
