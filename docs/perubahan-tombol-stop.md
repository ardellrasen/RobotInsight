# Perubahan Tombol Stop dan Alur Mendengar RobotInsight

Tanggal: 10 November 2026
Commit kondisi sebelum perubahan: `c2bd964` (branch `akurasi-pengetahuan`)

Dokumen ini mencatat apa yang diubah agar pengguna bisa menghentikan respons robot, dan agar robot hanya menerima pertanyaan baru setelah dipanggil.

## Masalah sebelumnya

1. **Respons tidak bisa dihentikan.** Pengguna harus menunggu sampai robot selesai menjawab. Satu-satunya cara menghentikan suara adalah mematikan Voice, dan itu tidak menghentikan pembuatan jawaban.
2. **Robot langsung mendengar lagi setelah menjawab.** Setelah pertanyaan lewat suara, robot membuka mikrofon tanpa diminta, sehingga obrolan di sekitarnya bisa dianggap pertanyaan.

## Perilaku baru

| Situasi | Perilaku |
| --- | --- |
| Robot sedang berpikir, mencari, memakai kamera, atau berbicara | Tombol mic berganti menjadi tombol **Stop**. |
| Stop ditekan | Suara dan pembuatan jawaban berhenti, lalu tombol mic dan "Hey Insight" aktif kembali. |
| Robot selesai menjawab | Robot kembali siaga. Pertanyaan berikutnya lewat tombol mic atau "Hey Insight". |
| Robot bertanya balik, misalnya "Mau cari apa di internet?" | Jawaban pengguna juga harus didahului tombol mic atau "Hey Insight". |
| Pertanyaan diketik di kolom chat | Tetap bisa dikirim saat robot siaga. |
| Jawaban dihentikan di tengah | Teks yang sudah muncul tetap tampil, tetapi tidak disimpan ke ingatan percakapan. |
| Dihentikan sebelum ada teks | Muncul tulisan "Dihentikan." atau "Stopped.". |

## Perubahan

### `main.py`

- Mode mendengar lanjutan (`followup`) dihapus. Setelah setiap jawaban, status kembali ke `idle`.
- Fungsi baru `respond()` menjalankan setiap permintaan di thread sendiri. Stop bisa melepas permintaan itu seketika, walaupun model, pencarian, atau kamera masih memproses.
- `handle_prompt()` dan `ask_llm()` menerima `turn`, dan berhenti lewat `TurnStopped` setelah setiap panggilan yang lama.
- Saat dihentikan, koneksi streaming ke Ollama ditutup, jadi pembuatan jawaban ikut berhenti begitu token berikutnya tiba.
- Anjuran "Ucapkan istirahat kalau sudah selesai" dihapus dari jawaban kemampuan robot. Perintah "Istirahat" masih berfungsi.

### `modules/interface.py`

- Endpoint baru `POST /api/stop`. Endpoint ini hanya berpengaruh saat robot sedang merespons.
- Setiap Stop menaikkan nomor generasi (`_stop_generation`). Pekerjaan dari generasi lama tidak bisa lagi mengubah status antarmuka.

### `modules/text_to_speech.py`

- Pemutaran kalimat yang sedang berjalan dihentikan saat Stop ditekan, dan kalimat yang masih mengantre dilewati.

### `ui/index.html`, `ui/app.js`, `ui/style.css`

- Tombol Stop berada di posisi tombol mic selama robot merespons.
- Setelah Stop diklik, tombol mic dinonaktifkan selama 0,6 detik, supaya klik ganda tidak langsung membuka mikrofon.

### `tests/test_interface.py`

- 7 test baru: endpoint Stop, status dari respons yang sudah dihentikan, jawaban yang datang terlambat, penutupan streaming, pemutaran suara, kalimat yang mengantre, dan kembali siaga tanpa membuka mikrofon.

### `README.md` dan `TEST_PHRASES.md`

- Langkah percakapan dan daftar uji disesuaikan dengan perilaku baru.

## Hasil pengujian

Seluruh 87 test lolos. Pengujian program asli memakai Ollama biasa di CPU dengan `qwen3:1.7b`, dan tombol Stop diklik di Edge tanpa jendela. Mikrofon dan speaker tidak dipakai.

| Skenario | Hasil |
| --- | --- |
| Stop saat jawaban sedang muncul | Teks berhenti dan tidak bertambah lagi. Ingatan percakapan tetap kosong. |
| Stop sebelum kata pertama muncul | Status langsung kembali siaga. |
| Pertanyaan baru tepat setelah Stop | Diterima, mulai diproses dalam 0,03 detik, dan terjawab normal. |
| Setelah jawaban selesai | Mikrofon tidak terbuka sendiri, dan robot kembali menunggu panggilan. |

## Keterbatasan

- **Belum diuji dengan perangkat asli:** speaker, mikrofon, dan wake word. Penghentian suara diuji dengan audio simulasi.
- **Stop saat kamera dan pencarian internet belum diuji sungguhan.** Keduanya memakai mekanisme yang sama dengan model, yang diuji lewat model yang dibuat tertahan.
- **Proses yang dilepas tetap selesai di latar belakang.** Pencarian atau analisis kamera yang dihentikan tetap berjalan sampai selesai, tetapi hasilnya dibuang. Instance iGPU hanya memproses satu permintaan, jadi pertanyaan berikutnya bisa menunggu sebentar.
- **Di layar selebar 650 piksel atau kurang,** panel Conversation menutupi tombol Stop. Tutup panelnya dulu untuk menekan Stop.

## Cara mengembalikan

Setelah perubahan ini di-commit sebagai satu commit di atas `c2bd964`, dan selama belum ada commit lain sesudahnya, batalkan dengan:

```bat
git revert HEAD
```

Perintah di atas membuat commit baru yang membatalkan perubahan ini, jadi riwayatnya tetap tersimpan. Commit atau simpan dulu perubahan yang masih terbuka sebelum menjalankannya.
