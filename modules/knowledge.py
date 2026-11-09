"""Answer event questions from docs/pengetahuan-itb-insight.md instead of model memory."""
from pathlib import Path
import re

KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "docs" / "pengetahuan-itb-insight.md"
_KEYWORDS_LINE = re.compile(r"^Kata kunci:\s*(.+)$", re.I | re.M)


def _keyword_pattern(keyword):
    parts = [re.escape(part) for part in re.split(r"[\s-]+", keyword.strip()) if part]
    return re.compile(r"\b" + r"[\s-]*".join(parts) + r"\b", re.I)


def _sections():
    """Parse on every lookup so edits to the file apply without a restart."""
    try:
        text = KNOWLEDGE_PATH.read_text(encoding="utf-8")
    except OSError as error:
        print(f"[KNOWLEDGE] Could not read the file: {error}")
        return []
    found = []
    for block in re.split(r"^## +", text, flags=re.M)[1:]:
        title, _, body = block.partition("\n")
        keywords = _KEYWORDS_LINE.search(body)
        if keywords:
            found.append((title.strip(), [_keyword_pattern(word) for word in keywords[1].split(",") if word.strip()],
                          _KEYWORDS_LINE.sub("", body, count=1).strip()))
    return found


def lookup(question):
    """Return the matching sections as one text, or "" when none apply."""
    return "\n\n".join(f"{title}:\n{body}" for title, patterns, body in _sections()
                       if any(pattern.search(question) for pattern in patterns))


def grounded_prompt(knowledge):
    return ("Berikut informasi resmi tentang acara ini. Jawab pertanyaan pengguna hanya berdasarkan informasi ini. "
            "Jika jawabannya tidak ada di sini, katakan terus terang bahwa kamu belum punya informasinya. "
            "Jangan menambahkan tanggal, tempat, harga, nama, atau fakta lain.\n\n" + knowledge)
