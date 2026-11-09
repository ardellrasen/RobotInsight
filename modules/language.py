"""Small English/Indonesian routing helpers; no extra language model or network."""
import re

INDONESIAN = set("apa bagaimana gimana tolong saya aku kamu jam berapa pukul sekarang cuaca besok hari tanggal ceritakan jelaskan cari carikan lihat berita terbaru sederhana lagi terima kasih kabar halo hai selamat hujan suhu di ini itu bisa mengapa kenapa buat dengan untuk dan istirahat berhenti mendengarkan lanjutkan dong boleh mau tunggu cukup waktu bulan contoh dalam lebih tentang baca bacakan depan buku yang apakah kapan dimana siapa penampilan membangunkanmu fitur lakukan dongeng lelucon makasih bantu dengar tulisan cerah awan panas dingin tanaman daun pelangi ngobrol makanan suka musik lagu jelasin nggak enggak gak kok deh yuk siap baik baiklah bosen bosan".split())
ENGLISH = set("what when where who please tell explain how show the is in and can me you weather time now why give more hello hi thanks tomorrow today read search look something are a it for of on your with want good great okay fine yes no maybe help story joke bored sad happy blue green plant plants leaves".split())


def detect_language(text, fallback="en"):
    words = re.findall(r"[^\W\d_]+", text.lower(), re.UNICODE)
    indonesian = sum(word in INDONESIAN for word in words)
    english = sum(word in ENGLISH for word in words)
    if indonesian > english:
        return "id"
    if english > indonesian:
        return "en"
    return fallback if fallback in {"en", "id"} else "en"


def choose(language, english, indonesian):
    return indonesian if language == "id" else english


def is_standby(text):
    return bool(re.fullmatch(r"(?:go to sleep|stop listening|that'?s all|stand by|istirahat|berhenti mendengarkan|cukup|sudah cukup|tunggu dulu|mode siaga)[.!? ]*", text.strip(), re.I))
