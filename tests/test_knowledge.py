"""Event questions use the knowledge file; other chat and search are unaffected."""
import atexit
import unittest
from unittest.mock import patch

import main as assistant
from modules import knowledge

atexit.unregister(assistant.save_memory)


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        assistant.session_memory = []
        assistant._last_knowledge = ""
        assistant._pending_search = False

    def test_spellings_of_each_event_find_their_section(self):
        for question, title in (("Apa itu ITB Insight 2026?", "ITB Insight 2026"), ("apa itu itb in sight", "ITB Insight 2026"),
                                ("Apa itu Play-Tech?", "Play-Tech:"), ("apa itu playtech", "Play-Tech:"), ("what is play tech", "Play-Tech:"),
                                ("Apa itu Show Tech?", "Show-Tech:"), ("Teknik Fisika itu apa?", "Latar belakang")):
            self.assertIn(title, knowledge.lookup(question), question)

    def test_date_and_place_are_available_for_short_questions(self):
        for question in ("Kapan ITB Insight diadakan?", "Kapan acaranya?", "Di mana lokasi acara?"):
            found = knowledge.lookup(question)
            self.assertIn("28 November 2026", found, question)
            self.assertIn("ITB Ganesha, Kota Bandung", found, question)

    def test_comparison_gets_both_programs(self):
        found = knowledge.lookup("Apa bedanya Playtech dan Showtech?")
        self.assertIn("bermain, mencoba", found)
        self.assertIn("melihat, merasakan", found)

    def test_unrelated_words_do_not_match(self):
        for question in ("Can you show technology trends?", "What is a transistor?", "Give me an insight about cats", "Hey Insight apa kabar?"):
            self.assertEqual(knowledge.lookup(question), "", question)

    def test_event_year_does_not_trigger_web_search_but_explicit_search_does(self):
        self.assertEqual(assistant.detect_intent("Apa itu ITB Insight 2026?")["action"], "event_info")
        self.assertEqual(assistant.detect_intent("Cari di internet ITB Insight 2026")["action"], "search_web")

    def test_answer_is_grounded_and_followup_keeps_the_facts(self):
        with patch.object(assistant, "ask_llm", return_value="Itu demonstrasi teknologi.") as llm, patch.object(assistant, "speak"):
            assistant.handle_prompt("Apa itu Play-Tech?")
            first = llm.call_args.args[1]
            self.assertIn("bermain, mencoba", first[-2]["content"])
            self.assertEqual(first[-1]["content"], "Apa itu Play-Tech?")
            assistant.handle_prompt("Tell me more.")
            self.assertIn("bermain, mencoba", llm.call_args.args[1][-2]["content"])
            assistant.handle_prompt("Apa kabar kamu hari ini?")
            self.assertTrue(all("informasi resmi" not in message["content"] for message in llm.call_args.args[1]))

    def test_saved_history_excludes_the_injected_facts(self):
        with patch.object(assistant, "ask_llm", return_value="Oke."), patch.object(assistant, "speak"):
            assistant.handle_prompt("Apa itu Show-Tech?")
        self.assertEqual([message["role"] for message in assistant.session_memory], ["user", "assistant"])
        self.assertNotIn("merasakan", str(assistant.session_memory))


if __name__ == "__main__":
    unittest.main()
