# Perubahan Akurasi Pengetahuan RobotInsight

Tanggal: 9 November 2026
Commit kondisi sebelum perubahan: `876a0f4` (branch `akurasi-pengetahuan`)

Dokumen ini mencatat apa yang diubah agar robot menjawab pertanyaan tentang ITB Insight dengan lebih tepat, beserta alasan dan hasil pengukurannya. Logika ditaruh di kode, karena model `qwen3:1.7b` dengan `num_ctx` 2048 tidak mampu mengikuti instruksi panjang.

## Penyebab jawaban kurang tepat

1. **Semua bagian yang cocok dikirim.** Tidak ada skor, jadi satu pertanyaan bisa membawa beberapa bagian panjang.
2. **Salah dengar langsung gagal.** "pley tek" dan "ITB Insait" tidak cocok dengan kata kunci apa pun.
3. **Pertanyaan lanjutan kehilangan konteks.** "Di mana tempatnya?" setelah "Kapan acara ITB Insight?" tidak lagi membawa fakta acara.
4. **Hal yang belum diketahui tidak ditangani.** Pertanyaan tiket atau jam buka memicu bagian acara yang tidak memuat jawabannya, sehingga model bisa mengarang.
5. **Pesan system tidak berada di tempat yang dimaksud kode.** Template qwen3 memindahkan semua pesan system ke awal prompt, sehingga instruksi bahasa dan fakta per giliran membatalkan cache riwayat.

## Perubahan

### `docs/pengetahuan-itb-insight.md`

- Format baru: `Selalu dipakai`, `Kata kunci utama`, `Kata kunci pendukung`, dan `Kata kunci longgar`. Petunjuknya ada di awal file.
- Bagian baru `Konteks dasar` dan `Informasi yang belum tersedia`.
- Kalimat mata acara diperbaiki, dan ejaan "insait" serta "in sait" ditambahkan.

### `modules/knowledge.py`

- Skor: utama dan longgar +3, pendukung +1, ambang minimum 2.
- Satu bagian dengan skor tertinggi. Bagian kedua ikut hanya jika selisih skornya maksimal 1.
- Kata kunci pendek yang berada di dalam kecocokan lebih panjang dari bagian lain diabaikan.
- Pencocokan fuzzy memakai `difflib` dengan ambang 0,84, huruf pertama harus sama, dan hanya untuk `Kata kunci longgar`.
- `refers_to_previous()` mengenali kalimat pendek yang merujuk topik sebelumnya.
- `grounded_prompt()` kini mengarahkan ke panitia di meja informasi.

### `main.py`

- Konteks dasar dikirim tepat setelah `ASSISTANT_STYLE`, termasuk saat pemanasan model.
- Fakta bertahan paling lama 2 giliran untuk kalimat lanjutan. Aksi lain, bagian lain, atau pertanyaan umum menghapusnya.
- Fakta per giliran dan instruksi bahasa digabung ke pesan user terakhir tepat sebelum dikirim. `session_memory` tetap hanya menyimpan pertanyaan asli.
- Log `[LLM] Prompt tokens: N/2048` di setiap panggilan model, dengan peringatan di atas 1700.

### `tests/test_knowledge_accuracy.py`

- 20 test baru, termasuk 43 pertanyaan `lookup()`: acara biasa, salah dengar, hal yang belum diketahui, dan kalimat yang tidak berhubungan. Pertanyaan lanjutan diuji lewat detektor dan alur percakapan.

## Hasil pengukuran

Waktu pemrosesan prompt pada giliran kedua. Median dari 3 putaran, model dikeluarkan dari memori sebelum setiap putaran. Isi prompt sama, hanya tata letaknya yang berbeda. Diukur di Ollama biasa yang berjalan di CPU.

| Skenario | Sebelum | Sesudah | Perubahan |
| --- | --- | --- | --- |
| Ganti bahasa | 5.252 ms | 2.467 ms | turun 53% |
| Ganti topik acara | 9.339 ms | 8.489 ms | turun 9% |
| Pertanyaan acara lalu pertanyaan umum | 6.636 ms | 2.675 ms | turun 60% |

Penurunan saat ganti topik kecil karena teks fakta yang baru tetap harus dibaca model.

| Ukuran prompt | Token |
| --- | --- |
| Terbesar pada percakapan nyata | 734 dari 2048 |
| Kasus terburuk buatan: 12 pesan riwayat panjang dan 2 bagian terpanjang | 1.692 dari 2048 |

Pemanasan startup terbukti berguna: pertanyaan pertama diproses 1.438 ms, sedangkan pemanasannya sendiri 7.045 ms.

## Keterbatasan

- **Kecepatan iGPU belum diukur.** Angka di atas dari CPU. Launcher memakai instance iGPU di port 11435, jadi angka di sana akan berbeda.
- **Belum diuji dengan suara asli.** Salah dengar Whisper disimulasikan lewat teks.
- **Jawaban lanjutan belum selalu tepat.** Pada satu uji, "Where is it?" setelah "What is Show-Tech?" dijawab dengan mengulang penjelasan Show-Tech, bukan lokasinya. Pada uji sebelumnya pertanyaan yang sama dijawab benar.
- **Ejaan salah bisa terbawa.** Robot menjawab "Pley Tek cocok untuk...", mengikuti ejaan yang didengar.
- **"Harga tiket" bersifat umum.** "Berapa harga tiket pesawat?" juga dijawab "belum tersedia, tanya panitia".
- **"Tanggal berapa?" tanpa kata acara** tetap menjawab tanggal hari ini, sesuai aturan aksi lain.
- **Angka token saat jawaban terpotong** adalah perkiraan bertanda `(perkiraan)`, karena Ollama tidak sempat mengirim jumlahnya. Pada dua prompt uji, selisihnya di bawah 2%.

## Cara mengembalikan

Perubahan ini tersimpan sebagai satu commit di atas `876a0f4`. Selama belum ada commit lain sesudahnya, batalkan dengan:

```bat
git revert HEAD
```

Perintah di atas membuat commit baru yang membatalkan perubahan ini, jadi riwayatnya tetap tersimpan. Commit atau simpan dulu perubahan yang masih terbuka sebelum menjalankannya.
