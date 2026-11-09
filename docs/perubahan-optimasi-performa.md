# Perubahan Optimasi Performa RobotInsight

Tanggal: 9 November 2026
Commit kondisi sebelum perubahan: `e41b909`

Dokumen ini mencatat apa yang diubah agar respons AI RobotInsight lancar di laptop ini, beserta alasan dan hasil pengukurannya.

## Spesifikasi laptop dan dampaknya

| Komponen | Nilai | Dampak pada program |
| --- | --- | --- |
| Prosesor | Intel Core i7-1255U, 2 core P + 8 core E, 12 thread | Daya hanya sekitar 15 W, sehingga menambah thread tidak mempercepat model. |
| GPU | Intel Iris Xe (terintegrasi) | Tidak dipakai Ollama secara default, padahal jauh lebih cepat dari CPU untuk model ini. |
| RAM | 15,7 GB, sekitar 6,3 GB kosong saat diukur | Bandwidth memori membatasi model besar. Model yang lebih kecil lebih cepat dan lebih hemat. |
| Penyimpanan | SSD NVMe 1 TB, 717 GB kosong | Bukan hambatan. Tidak perlu penghematan ruang. |

## Penyebab respons lambat

1. **Model dijalankan di CPU.** Prompt diproses sekitar 16 token/detik dan jawaban sekitar 4,7 token/detik. Hasilnya hampir sama dari 2 sampai 8 thread, jadi hambatannya adalah bandwidth memori dan daya CPU.
2. **Cache prompt sering terbuang.** Instruksi bahasa berada di awal prompt, dan riwayat digeser setiap giliran. Akibatnya Ollama sering membaca ulang seluruh prompt.
3. **Whisper bekerja dua kali.** Mode bahasa otomatis menjalankan encoder sekali untuk deteksi bahasa dan sekali lagi untuk transkripsi, sekitar 10 detik per ucapan.
4. **Suara dibuat setelah kalimat sebelumnya selesai diputar.** Kokoro butuh sekitar 4 detik per kalimat panjang, sehingga muncul jeda antarkalimat.
5. **Prompt pencarian terlalu besar.** Empat hasil masing-masing 600 karakter ditambah URL. Di CPU, waktu ini bisa melewati batas tunggu 30 detik sehingga muncul pesan koneksi terputus.

## Perubahan

### `Start_RobotInsight.bat`

- Menjalankan instance Ollama khusus di port 11435 dengan iGPU aktif (`OLLAMA_VULKAN=1`, `OLLAMA_IGPU_ENABLE=1`). Pengaturan Ollama utama di laptop tidak berubah.
- Instance ini berjalan di jendela launcher yang sama, bukan jendela terpisah.
- Pilihan `ROBOT_USE_IGPU=0` mengembalikan ke Ollama biasa di CPU.
- Model default menjadi `qwen3:1.7b`.

### `main.py`

- Model default menjadi `qwen3:1.7b` (RAM sekitar 1,5 GB, sebelumnya 2,9 GB).
- Instruksi bahasa dipindah tepat sebelum pesan terbaru dengan tujuan menjaga cache persona dan riwayat saat bahasa berganti. **Koreksi:** cara ini tidak berlaku untuk `qwen3:1.7b`, karena templatenya memindahkan semua pesan system ke awal prompt, sehingga cache riwayat tetap terbuang. Instruksi bahasa kini digabung ke pesan user terakhir. Lihat `docs/perubahan-akurasi-pengetahuan.md`.
- Riwayat dipotong per blok: maksimal 12 pesan, lalu disisakan 4 pesan terakhir.
- Pemanasan saat startup kini mengirim prompt persona asli, sehingga pertanyaan pertama sudah memakai cache.
- Log startup menampilkan persentase model yang berjalan di GPU.
- Prompt pencarian dibatasi 3 sumber, 280 karakter per sumber, tanpa URL.
- Batas tunggu model dinaikkan dari 30 menjadi 120 detik.
- Jawaban panjang tanpa streaming, seperti deskripsi kamera, kini disuarakan per kalimat.

### `modules/text_to_speech.py`

- Kalimat berikutnya disintesis di latar belakang saat kalimat sekarang masih diputar.
- Kokoro dan Piper dipanaskan saat startup, karena sintesis pertama jauh lebih lambat.

### `modules/speech_to_text.py`

- Hasil encoder deteksi bahasa dipakai ulang untuk transkripsi.
- Thread Whisper diturunkan dari 4 menjadi 2, yang terukur paling cepat di CPU ini.

### `tests/test_web_search.py`

- Satu asersi disesuaikan karena URL tidak lagi dikirim ke model.

### `README.md`

- Model default, variabel lingkungan, dan panduan masalah diperbarui.

## Hasil pengukuran

| Tahap | Sebelum | Sesudah |
| --- | --- | --- |
| Kata pertama dari LLM, chat | 11–13 detik | 0,3–0,9 detik |
| Kecepatan menghasilkan jawaban | 4,7 token/detik | sekitar 15 token/detik |
| Kata pertama dari LLM, pencarian | tidak diukur | 2 detik |
| Whisper, satu ucapan pendek | sekitar 10 detik | sekitar 4,5 detik |
| Jeda antarkalimat saat berbicara | sekitar 4 detik (perkiraan dari waktu sintesis) | di bawah 0,05 detik |
| Suara mulai setelah teks diterima, chat | tidak diukur | 1,7–4 detik |
| RAM model chat | 2,9 GB | 1,5 GB |

Angka "sebelum" untuk LLM diukur tanpa cache prompt. Di aplikasi lama, cache kadang berlaku, sehingga sebagian giliran bisa lebih cepat dari angka itu.

## Opsi yang diuji dan tidak dipakai

| Opsi | Hasil |
| --- | --- |
| Mengatur jumlah thread Ollama | Tidak berpengaruh dari 2 sampai 8 thread. Lebih lambat di 10 dan 12 thread. |
| `qwen3:4b` dengan iGPU | Suara mulai 5,5–17 detik, karena CPU dan iGPU berbagi daya. Kualitas jawaban lebih baik. |
| `gemma3:1b` | Tetap menjawab bahasa Inggris untuk pertanyaan Bahasa Indonesia. |
| Whisper `base` | Sekitar 1,4 detik, tetapi menulis "dibandung" dan "kotabandung", sehingga kota pada perintah cuaca bisa tidak terbaca. |
| Kokoro `int8` | Tidak terbukti lebih cepat. |

## Perubahan lanjutan: suara dan teks UI

- **Suara Inggris memakai Piper.** Sebelumnya Kokoro. Waktu sintesis dua kalimat panjang turun dari 6,3–6,8 detik menjadi 0,6–0,9 detik, dan kalimat pendek dari sekitar 2 detik menjadi sekitar 0,3 detik. Kokoro umumnya terdengar lebih alami dan masih bisa dipakai dengan `ROBOT_TTS_ENGINE=kokoro`.
- **Nada suara Indonesia menjadi "cerah".** Nada dinaikkan 8% dari sekitar 256 Hz menjadi sekitar 277 Hz.
- **Teks UI menjadi "Hey Insight".** Frasa panggilan yang diucapkan tetap "Hey In Site", dan model wake word tidak berubah.
- **Pelafalan nama.** Tulisan "Insight" dibaca "Insait" oleh suara Indonesia dan "In Site" oleh suara Inggris.
- **Hanya satu salinan program.** Launcher kini menutup sesi RobotInsight sebelumnya lewat `modules/stop_previous_instance.ps1`. Tanpa ini, setiap salinan yang masih berjalan ikut mendengar panggilan dan menjawab.

- **Tombol bahasa ID, EN, Auto.** Deteksi otomatis memakai daftar kata yang kecil, dan kalimat yang tidak dikenali mengikuti bahasa giliran sebelumnya. ID dan EN kini mengunci bahasa untuk pengenalan ucapan, jawaban, suara, cuaca, dan kamera. Pilihan disimpan di `language_setting.json`, dan awalnya ID.

## Keterbatasan

- **Kualitas jawaban turun.** Model 1.7B lebih sering salah fakta. Contoh dari pengujian: warna langit dijelaskan keliru dan makanan khas Bandung disebut rendang. Untuk fakta penting, minta robot mencari di internet.
- **Belum diuji dengan perangkat asli:** mikrofon, wake word, speaker, kamera, dan jendela Edge. Pengujian memakai perangkat simulasi, gambar `ui/assets/robot.png` sebagai kamera, dan hasil pencarian tiruan.
- **Akurasi Whisper** diuji dengan 5 kalimat suara sintetis. Pada satu kalimat, satu kata berubah ("kerjanya" menjadi "kerdanya").
- **Penghentian Ollama saat jendela launcher ditutup** belum diuji. Jika proses di port 11435 masih berjalan, launcher berikutnya akan memakainya kembali.
- Kecepatan bisa turun saat laptop memakai baterai atau panas.

## Cara mengganti atau mengembalikan

Memakai model yang lebih akurat tetapi lebih lambat, dari Command Prompt di folder proyek:

```bat
set ROBOT_LLM_MODEL=qwen3:4b-instruct-2507-q4_K_M
Start_RobotInsight.bat
```

Menjalankan tanpa iGPU, misalnya jika driver bermasalah:

```bat
set ROBOT_USE_IGPU=0
Start_RobotInsight.bat
```

Mengembalikan semua kode ke kondisi sebelum optimasi:

```bat
git switch main
```

Hasil optimasi kini tersimpan di branch `akurasi-pengetahuan` (commit `876a0f4`), dan `main` masih berada di kondisi sebelum optimasi (`e41b909`). Commit atau simpan dulu perubahan yang masih terbuka sebelum berpindah branch.
