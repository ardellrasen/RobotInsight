"""Answer event questions from docs/pengetahuan-itb-insight.md instead of model memory."""
from dataclasses import dataclass
import difflib
from pathlib import Path
import re

KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "docs" / "pengetahuan-itb-insight.md"
PRIMARY_WEIGHT = 3
SUPPORTING_WEIGHT = 1
# One main keyword, or two different supporting keywords.
MIN_SCORE = 2
# A second section joins only when its score is this close to the best one.
SECOND_SECTION_GAP = 1
FUZZY_CUTOFF = 0.84
FUZZY_MAX_LENGTH_GAP = 2
FOLLOWUP_MAX_WORDS = 6

_FIELD_LINE = re.compile(r"^(Kata kunci(?: utama| pendukung| longgar)?|Selalu dipakai):[ \t]*(.*)$", re.I | re.M)
_WORD = re.compile(r"\w+")

# A turn counts as a follow-up only when every word comes from these two lists,
# so "Di mana tempatnya?" qualifies but "Di mana Jakarta?" does not.
_FOLLOWUP_REFERENCES = frozenset("""
    mana dimana kapan berapa siapa bagaimana gimana apa apakah
    tempatnya lokasinya alamatnya tanggalnya harinya waktunya jamnya mulainya selesainya
    harganya tiketnya biayanya bayarnya masuknya temanya konsepnya tujuannya isinya
    pesertanya pembicaranya penyelenggaranya panitianya
    tempat lokasi alamat tanggal harga tiket biaya gratis bayar
    where when who what how much place location address date ticket price free
""".split())
_FOLLOWUP_FILLERS = frozenset("""
    di ke itu ya sih dong kah nya lalu terus trus kalau kalo dan dengan tentang tepatnya persisnya
    nggak gak enggak tidak atau acara
    is it s the that there about and then a an to
""".split())


@dataclass(frozen=True)
class Section:
    title: str
    body: str
    always: bool
    primary: tuple
    supporting: tuple
    loose: tuple


def _keywords(line):
    return tuple(word.strip() for word in line.split(",") if word.strip())


def _keyword_pattern(keyword):
    parts = [re.escape(part) for part in re.split(r"[\s-]+", keyword.strip()) if part]
    return re.compile(r"\b" + r"[\s-]*".join(parts) + r"\b", re.I)


def _parse_section(block):
    title, _, text = block.partition("\n")
    fields = {name.lower(): value for name, value in _FIELD_LINE.findall(text)}
    return Section(
        title=title.strip(),
        body=re.sub(r"\n{3,}", "\n\n", _FIELD_LINE.sub("", text)).strip(),
        always=fields.get("selalu dipakai", "").strip().lower() == "ya",
        # The old "Kata kunci:" line keeps working as a main keyword.
        primary=_keywords(fields.get("kata kunci", "")) + _keywords(fields.get("kata kunci utama", "")),
        supporting=_keywords(fields.get("kata kunci pendukung", "")),
        loose=_keywords(fields.get("kata kunci longgar", "")),
    )


def _sections():
    """Parse on every lookup so edits to the file apply without a restart."""
    try:
        text = KNOWLEDGE_PATH.read_text(encoding="utf-8")
    except OSError as error:
        print(f"[KNOWLEDGE] Could not read the file: {error}")
        return []
    return [_parse_section(block) for block in re.split(r"^## +", text, flags=re.M)[1:]]


def _squash(text):
    """Comparable form: no spaces, and Whisper's tech/tek spellings made equal."""
    return "".join(_WORD.findall(re.sub(r"tech\b", "tek", text.lower())))


def _fuzzy_span(keyword, words):
    """Find words that sound like a name. Used only for "Kata kunci longgar"."""
    target = _squash(keyword)
    size = len(_WORD.findall(keyword))
    for count in range(max(1, size - 1), size + 2):
        for start in range(len(words) - count + 1):
            window = words[start:start + count]
            heard = _squash(" ".join(word.group() for word in window))
            if (heard[:1] == target[:1] and abs(len(heard) - len(target)) <= FUZZY_MAX_LENGTH_GAP
                    and difflib.SequenceMatcher(None, heard, target).ratio() >= FUZZY_CUTOFF):
                return window[0].start(), window[-1].end()
    return None


def _find_matches(section, question):
    """Return (start, end, weight) for each keyword heard in the question."""
    found = []
    words = list(_WORD.finditer(question))
    for keyword in section.loose:
        exact = _keyword_pattern(keyword).search(question)
        span = exact.span() if exact else _fuzzy_span(keyword, words)
        if span:
            found.append((*span, PRIMARY_WEIGHT))
    for keywords, weight in ((section.primary, PRIMARY_WEIGHT), (section.supporting, SUPPORTING_WEIGHT)):
        for keyword in keywords:
            exact = _keyword_pattern(keyword).search(question)
            if exact:
                found.append((*exact.span(), weight))
    return found


def _is_shadowed(match, others):
    """A phrase inside a longer phrase from another section says less than it does."""
    start, end, _ = match
    return any(other_start <= start and end <= other_end and other_end - other_start > end - start
               for other_start, other_end, _ in others)


def _score(matches):
    """Sum the weights; several spellings of one spoken phrase count once."""
    total, taken = 0, []
    for start, end, weight in sorted(matches, key=lambda item: (-item[2], item[0] - item[1])):
        if all(end <= other_start or other_end <= start for other_start, other_end in taken):
            taken.append((start, end))
            total += weight
    return total


def lookup(question):
    """Return the best one or two sections as one text, or "" when none qualify."""
    sections = [section for section in _sections() if not section.always]
    matches = [_find_matches(section, question) for section in sections]
    scored = []
    for index, section in enumerate(sections):
        others = [match for other, found in enumerate(matches) if other != index for match in found]
        score = _score([match for match in matches[index] if not _is_shadowed(match, others)])
        if score >= MIN_SCORE:
            scored.append((score, section))
    scored.sort(key=lambda item: -item[0])
    chosen = [section for score, section in scored[:2] if scored[0][0] - score <= SECOND_SECTION_GAP]
    return "\n\n".join(f"{section.title}:\n{section.body}" for section in chosen)


def base_context():
    """Facts marked "Selalu dipakai: ya", sent with every chat turn."""
    return "\n\n".join(section.body for section in _sections() if section.always)


def refers_to_previous(question):
    """True for a short question that only makes sense with the previous topic."""
    words = _WORD.findall(question.replace("’", "'").lower())
    return (0 < len(words) <= FOLLOWUP_MAX_WORDS
            and all(word in _FOLLOWUP_REFERENCES or word in _FOLLOWUP_FILLERS for word in words)
            and any(word in _FOLLOWUP_REFERENCES for word in words))


def grounded_prompt(knowledge):
    return ("Berikut informasi resmi tentang acara ini. Jawab hanya dari informasi ini. "
            "Jika jawabannya tidak ada di sini, katakan kamu belum tahu dan arahkan ke panitia di meja informasi. "
            "Jangan menambahkan tanggal, tempat, harga, nama, atau fakta lain.\n\n" + knowledge)
