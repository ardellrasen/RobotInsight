"""Scoring, misheard names, follow-ups and prompt layout for event questions."""
import atexit
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import main as assistant
from modules import knowledge
from modules import interface as ui

atexit.unregister(assistant.save_memory)

EVENT = "ITB Insight 2026:"
PLAY = "Play-Tech:"
SHOW = "Show-Tech:"
BACKGROUND = "Latar belakang Play-Tech dan Show-Tech:"
ROBOT = "Tentang robot ini:"
UNKNOWN = "Informasi yang belum tersedia:"
ALL_TITLES = (EVENT, PLAY, SHOW, BACKGROUND, ROBOT, UNKNOWN)


def titles(question):
    found = knowledge.lookup(question)
    return {title for title in ALL_TITLES if ("\n\n" + found).count("\n\n" + title)}


class LookupTests(unittest.TestCase):
    def assert_cases(self, cases):
        for question, expected in cases:
            with self.subTest(question=question):
                self.assertEqual(titles(question), set(expected))

    def test_ordinary_event_questions(self):
        self.assert_cases((
            ("Kapan acara ITB Insight?", [EVENT]),
            ("Apa tema acara ini?", [EVENT]),
            ("Apa itu Play-Tech?", [PLAY]),
            ("Show Tech itu apa?", [SHOW]),
            ("Apa bedanya Playtech dan Showtech?", [PLAY, SHOW]),
            ("Apa latar belakang play tech?", [BACKGROUND]),
            ("Teknik Fisika itu apa?", [BACKGROUND]),
            ("Kamu project apa?", [ROBOT]),
        ))

    def test_misheard_names_still_match(self):
        self.assert_cases((
            ("pley tek itu apa?", [PLAY]),
            ("Apa itu plei tech?", [PLAY]),
            ("Apa itu plai tek?", [PLAY]),
            ("Coba jelaskan shou tek", [SHOW]),
            ("apa itu sou tek", [SHOW]),
            ("Apa itu ITB Insait?", [EVENT]),
            ("Kapan ITB in sait?", [EVENT]),
            ("Apa itu ITB Insigt?", [EVENT]),
        ))

    def test_unknown_details_point_to_the_committee_section(self):
        self.assert_cases((
            ("Jam buka pameran kapan?", [UNKNOWN]),
            ("Jam berapa acaranya mulai?", [UNKNOWN]),
            ("Mulai jam berapa?", [UNKNOWN]),
            ("Berapa harga tiket?", [UNKNOWN]),
            ("Apakah gratis?", [UNKNOWN]),
            ("Ada rundown nya?", [UNKNOWN]),
            ("Di mana peta booth?", [UNKNOWN]),
            ("Berapa harga tiket ITB Insight?", [UNKNOWN, EVENT]),
        ))

    def test_unrelated_sentences_do_not_match(self):
        for question in (
                "Bagaimana cuaca di Bandung besok?", "Jam berapa sekarang?", "Apa yang kamu lihat?",
                "Apa ibu kota Jepang?", "Bagaimana cara ini bekerja?", "Caranya memasak nasi bagaimana?",
                "Kapan cara terbaik belajar?", "Siapa pemeran ini?", "Latihan fisik apa yang bagus?",
                "Is this even possible?", "Show me the text", "I love playtime and showtime",
                "Plastik bisa didaur ulang?", "Play test game ini", "Hey Insight apa kabar?",
                "Give me an insight about cats", "Tiket kereta ke Jakarta berapa?", "Ada acara apa di televisi?",
                "Apa saja mata acara?",
        ):
            with self.subTest(question=question):
                self.assertEqual(knowledge.lookup(question), "")

    def test_followup_detector(self):
        for question in ("Di mana tempatnya?", "Kapan?", "Tempatnya di mana?", "Harganya berapa ya?",
                         "Kalau lokasinya?", "Where is it?", "How much is it?", "Terus kapan?"):
            with self.subTest(question=question):
                self.assertTrue(knowledge.refers_to_previous(question))
        for question in ("Apa kabar kamu hari ini?", "Apa itu transistor?", "Di mana Jakarta?", "Kapan Indonesia merdeka?",
                         "Siapa namamu?", "Bagaimana cara memasak nasi?", "Terima kasih", ""):
            with self.subTest(question=question):
                self.assertFalse(knowledge.refers_to_previous(question))


class FileFormatTests(unittest.TestCase):
    def use_file(self, text):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "facts.md"
        path.write_text(text, encoding="utf-8")
        replacement = patch.object(knowledge, "KNOWLEDGE_PATH", path)
        replacement.start()
        self.addCleanup(replacement.stop)

    def test_old_keyword_line_counts_as_main(self):
        self.use_file("## Lama\n\nKata kunci: robot merah\n\nFakta lama.\n")
        self.assertEqual(knowledge.lookup("ada robot merah"), "Lama:\nFakta lama.")

    def test_supporting_keywords_need_two_and_a_clear_winner_stands_alone(self):
        self.use_file("## A\n\nKata kunci pendukung: merah, biru\n\nFakta A.\n\n"
                      "## B\n\nKata kunci utama: kuning\nKata kunci pendukung: hijau\n\nFakta B.\n\n"
                      "## C\n\nKata kunci utama: ungu\n\nFakta C.\n")
        self.assertEqual(knowledge.lookup("warna merah"), "")
        self.assertIn("Fakta A.", knowledge.lookup("merah dan biru"))
        self.assertEqual(knowledge.lookup("kuning hijau merah"), "B:\nFakta B.")
        found = knowledge.lookup("kuning hijau ungu")
        self.assertIn("Fakta B.", found)
        self.assertIn("Fakta C.", found)

    def test_only_three_or_more_sections_are_cut_to_two(self):
        self.use_file("".join(f"## {name}\n\nKata kunci utama: {name}\n\nFakta {name}.\n\n" for name in ("satu", "dua", "tiga")))
        self.assertEqual(knowledge.lookup("satu dua tiga").count("Fakta"), 2)

    def test_always_on_section_is_separate_from_lookup(self):
        self.use_file("## Dasar\n\nSelalu dipakai: ya\n\nFakta dasar.\n\n## Lain\n\nKata kunci utama: lain\n\nFakta lain.\n")
        self.assertEqual(knowledge.base_context(), "Fakta dasar.")
        self.assertEqual(knowledge.lookup("fakta dasar"), "")

    def test_only_loose_keywords_tolerate_misspelling(self):
        self.use_file("## Longgar\n\nKata kunci longgar: gamelan robot\n\nA.\n\n## Ketat\n\nKata kunci utama: wayang digital\n\nB.\n")
        self.assertIn("A.", knowledge.lookup("gamelan robat"))
        self.assertEqual(knowledge.lookup("wayang digitel"), "")


class PromptFlowTests(unittest.TestCase):
    def setUp(self):
        with ui._lock:
            ui._conversation.clear()
        assistant.session_memory = []
        assistant._last_knowledge = ""
        assistant._knowledge_turns_left = 0
        assistant._pending_search = False

    def ask(self, *questions):
        with patch.object(assistant, "ask_llm", return_value="Oke.") as llm, patch.object(assistant, "speak"):
            for question in questions:
                assistant.handle_prompt(question)
        return llm

    @staticmethod
    def has_facts(llm):
        return any("informasi resmi" in message["content"] for message in llm.call_args.args[1])

    def test_followup_after_event_question_keeps_the_facts(self):
        llm = self.ask("Kapan acara ITB Insight?", "Di mana tempatnya?")
        self.assertTrue(self.has_facts(llm))

    def test_followups_expire_after_two_turns(self):
        llm = self.ask("Apa itu Play-Tech?", "Kapan?", "Di mana?")
        self.assertTrue(self.has_facts(llm))
        llm = self.ask("Berapa?")
        self.assertFalse(self.has_facts(llm))

    def test_general_question_drops_the_facts(self):
        self.assertFalse(self.has_facts(self.ask("Apa itu Play-Tech?", "Apa itu transistor?")))

    def test_another_action_drops_the_facts(self):
        with patch.object(assistant, "speak"), patch.object(assistant, "ask_llm", return_value="Oke."):
            assistant.handle_prompt("Apa itu Play-Tech?")
            assistant.handle_prompt("Jam berapa sekarang?")
        self.assertEqual(assistant._last_knowledge, "")

    def test_another_section_replaces_the_facts(self):
        llm = self.ask("Apa itu Play-Tech?", "Apa itu Show-Tech?")
        facts = next(message["content"] for message in llm.call_args.args[1] if "informasi resmi" in message["content"])
        self.assertIn("melihat, merasakan", facts)
        self.assertNotIn("bermain, mencoba", facts)

    def test_base_context_follows_the_persona_in_chat_only(self):
        llm = self.ask("Ceritakan lelucon.")
        messages = llm.call_args.args[1]
        self.assertEqual(messages[0]["content"], assistant.ASSISTANT_STYLE)
        self.assertIn("28 November 2026", messages[1]["content"])
        self.assertNotIn("28 November", assistant.final_only_system("x"))

    def test_history_keeps_only_the_visitor_question(self):
        self.ask("Apa itu Show-Tech?", "Di mana tempatnya?")
        self.assertEqual(assistant.session_memory[0], {"role": "user", "content": "Apa itu Show-Tech?"})
        self.assertEqual(assistant.session_memory[2], {"role": "user", "content": "Di mana tempatnya?"})
        self.assertNotIn("informasi resmi", str(assistant.session_memory))
        self.assertNotIn("Pesan pengunjung", str(assistant.session_memory))


class LlmRequestTests(unittest.TestCase):
    def run_llm(self, messages, chunks):
        client = Mock()
        client.chat.return_value = iter(chunks)
        with patch.object(assistant, "_llm_client", client), patch.object(assistant, "_active_speech", None), patch("builtins.print") as output:
            assistant.ask_llm("Apa itu Play-Tech?", messages)
        return client.chat.call_args.kwargs["messages"], [" ".join(map(str, call.args)) for call in output.call_args_list]

    def test_context_is_folded_after_history_and_leaves_no_private_field(self):
        sent, _ = self.run_llm([{"role": "system", "content": "Persona"}, {"role": "user", "content": "Lama"}, {"role": "assistant", "content": "Ya"},
                                {"role": "system", "content": "Fakta", "turn_context": True}, {"role": "user", "content": "Apa itu Play-Tech?"}],
                               [{"message": {"content": "Oke."}}])
        self.assertEqual([message["role"] for message in sent], ["system", "user", "assistant", "user"])
        self.assertEqual(sent[1]["content"], "Lama")
        self.assertTrue(sent[3]["content"].startswith("Fakta\n\n"))
        self.assertTrue(sent[3]["content"].endswith("Pesan pengunjung: Apa itu Play-Tech?"))
        self.assertTrue(all(set(message) == {"role", "content"} for message in sent))

    def test_prompt_size_is_logged_and_warned(self):
        _, logs = self.run_llm([{"role": "user", "content": "Halo"}], [{"message": {"content": "Oke."}, "prompt_eval_count": 500}])
        self.assertIn("[LLM] Prompt tokens: 500/2048", logs)
        self.assertFalse(any("Peringatan" in line for line in logs))
        _, logs = self.run_llm([{"role": "user", "content": "Halo"}], [{"message": {"content": "Oke."}, "prompt_eval_count": 1701}])
        self.assertTrue(any("Peringatan" in line for line in logs))

    def test_answer_cut_short_reports_an_estimate(self):
        _, logs = self.run_llm([{"role": "user", "content": "Halo"}],
                               [{"message": {"content": "Satu. "}}, {"message": {"content": "Dua. "}}, {"message": {"content": "Tiga. "}}])
        self.assertTrue(any("(perkiraan)" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
