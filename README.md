# RobotInsight

RobotInsight is a voice-first Windows assistant that understands English and Indonesian. A central animated robot listens for “Hey In Site,” answers aloud, and supports weather, web search, camera questions, and typed conversations. Speech and AI models run locally, with no paid AI API or API key. Weather and web search need an internet connection.

## What your PC needs

**Required**

- Windows 10 or 11, 64-bit
- Git for Windows
- Python 3.11, 64-bit, with the Python Launcher selected during installation
- Microsoft Edge (recommended for the desktop window), or another modern default browser
- Ollama for Windows
- A microphone and speakers or headphones
- Internet access for the first setup, model downloads, and web search
- At least 15 GB of free disk space for Python packages and the local models

**Recommended**

- 16 GB RAM for smoother use; 8 GB may work but can be slow or run out of memory
- A recent 4-core-or-better processor
- An NVIDIA GPU can improve local model speed, but is optional
- A webcam for camera questions

The default Qwen3 1.7B chat model is quantized to about 1.4 GB. First setup also downloads the vision model, Faster-Whisper small, Kokoro and its female English voices, a native Indonesian Piper voice, and the wake-word audio feature models. The app can run without a webcam, but its vision feature needs one.

## First-time setup

1. Install [Python 3.11 for Windows](https://www.python.org/downloads/release/python-3119/). In the installer, enable the Python Launcher option.
2. Install [Ollama for Windows](https://ollama.com/download/windows). Ollama supplies the local language and vision models.
3. Open PowerShell or Command Prompt and clone this repository:

   ```powershell
   git clone https://github.com/ardellrasen/RobotInsight.git
   cd RobotInsight
   ```

4. Double-click **Start_RobotInsight.bat**.

The launcher creates a private Python environment, installs the packages, downloads the speech, wake-word, chat and vision models, and starts the assistant. First setup can take a while and download several gigabytes. Later runs reuse the installed packages and models.

The launcher opens a dedicated Edge window, or your default browser if Edge is unavailable. When the robot is ready, say **“Hey In Site”**, click the microphone, or type in the message box. Press Enter to send and Shift+Enter for a new line. Use the fullscreen button to expand the interface and Escape to leave fullscreen. Close the terminal window or press Ctrl+C there to stop the program.

For your first voice conversation:

1. Open **Devices**, select your microphone and camera, and apply your choices.
2. Wait for the standby message **Listening for “Hey In Site”**.
3. Say the wake phrase, pause for the listening expression, then ask your question in English or Indonesian.
4. After each answer the robot returns to standby. To ask again, say the wake phrase or click the microphone. While it is responding, the microphone is replaced by a **Stop** button that ends the response at once.

## Konfigurasi

RobotInsight bisa langsung dijalankan tanpa konfigurasi, tanpa file `.env`, dan tanpa API key. Pengaturan hanya perlu diubah kalau ingin menyesuaikan perangkat, bahasa, model, atau materi acara.

| Yang ingin diubah | Tempat mengubahnya |
| --- | --- |
| Mikrofon dan kamera | Panel **Devices** di antarmuka, lalu klik **Apply devices**. |
| Bahasa (ID, EN, Auto) | Tombol bahasa di bagian atas antarmuka. Pertama kali dijalankan, bahasanya ID. |
| Materi yang dijawab robot tentang acara | File `docs/pengetahuan-itb-insight.md`, lihat [Event knowledge](#event-knowledge). |
| Model, suara, dan kepekaan wake word | Environment variable, lihat di bawah. |

### Environment variable

Di Command Prompt, buka folder proyek, atur nilainya, lalu jalankan launcher dari jendela yang sama:

```bat
set ROBOT_WAKE_THRESHOLD=0.35
set ROBOT_LLM_MODEL=qwen3:4b-instruct-2507-q4_K_M
Start_RobotInsight.bat
```

Di PowerShell:

```powershell
$env:ROBOT_WAKE_THRESHOLD = "0.35"
.\Start_RobotInsight.bat
```

Nilai di atas hanya berlaku untuk jendela itu. Kalau `Start_RobotInsight.bat` dijalankan dengan klik dua kali, nilainya harus disimpan permanen dulu dengan `setx ROBOT_WAKE_THRESHOLD 0.35`, lalu berlaku di jendela yang dibuka setelahnya.

| Variabel | Default | Fungsi |
| --- | --- | --- |
| `ROBOT_LLM_MODEL` | `qwen3:1.7b` | Model chat Ollama. Launcher mengunduhnya kalau belum ada. `qwen3:4b-instruct-2507-q4_K_M` memberi jawaban lebih baik, tetapi lebih lambat. |
| `ROBOT_USE_IGPU` | `1` | `1` menjalankan Ollama khusus di GPU terintegrasi lewat port 11435. `0` memakai layanan Ollama biasa. |
| `ROBOT_WAKE_THRESHOLD` | `0.45` | Makin rendah makin peka, tetapi makin sering terpicu tanpa sengaja. |
| `ROBOT_STT_MODEL` | `small` | Model Faster-Whisper, misalnya `base` atau `medium`. Launcher mengunduhnya ke `models/whisper/` saat dijalankan berikutnya. |
| `ROBOT_STT_LANGUAGE` | `auto` | `id` atau `en` untuk memaksa satu bahasa pengenalan suara. Hanya berpengaruh saat tombol bahasa berada di **Auto**. |
| `ROBOT_TTS_ENGINE` | `piper` | Mesin suara bahasa Inggris. `kokoro` terdengar lebih alami, tetapi sekitar 10 kali lebih lambat. Suara bahasa Indonesia selalu memakai Piper. |
| `ROBOT_TTS_VOICE` | `af_heart` | Suara Kokoro, misalnya `af_bella` atau `af_sarah`. Hanya dipakai dengan `ROBOT_TTS_ENGINE=kokoro`. |

### File pengaturan lokal

File berikut dibuat otomatis di folder proyek dan tidak masuk Git. Hapus salah satunya untuk mengembalikan bagian itu ke awal.

| File | Isi |
| --- | --- |
| `device_settings.json` | Pilihan mikrofon dan kamera. |
| `language_setting.json` | Mode bahasa: `id`, `en`, atau `auto`. |
| `memory.json` | Riwayat percakapan. |
| `.setup_complete` | Penanda bahwa paket Python sudah terpasang. Kalau dihapus, launcher memasang ulang paketnya. |

## The companion interface

- A pearl white robot with animated cyan eyes: it follows the cursor, blinks, and changes expression while listening, thinking, searching, looking, and speaking. Click it or press Enter while it is focused to say hello.
- A large central robot and microphone button for voice use. The latest response appears beneath the robot.
- An optional **Conversation** side panel with complete responses, selectable text, a copy button, and a text composer. The latest 100 messages stay available during the current run.
- A microphone button, camera shortcut, and keyboard button. Typed and spoken questions use the same assistant and conversation context.
- A **Devices** panel with detected microphone and camera selectors, refresh, and saved preferences.
- A language switch at the top: **ID** and **EN** lock speech recognition, replies, voice, weather and camera to one language, and **Auto** detects it per message. The choice is saved; the first run starts in ID.
- A **Try asking** panel on the left with eight feature groups and five clickable examples per group. On small screens, open it with the sparkle button.
- A voice toggle for spoken responses, a live activity indicator, and a camera preview during analysis.
- A responsive layout and support for the operating system's reduced motion preference.

The interface uses a local server bound to `127.0.0.1` and bundled assets. No external fonts or hosted UI services are needed. Speech, wake-word detection, chat, and camera analysis run locally. Web search sends queries to the search provider; weather sends the city you request to Open-Meteo. Text chat remains available if microphone setup fails.

## Speech and response speed

- **Wake word:** the custom “Hey In Site” model runs through openWakeWord. The launcher downloads its melspectrogram and embedding ONNX models into `models/wakeword/`, and startup validates them. A single score above 0.45 triggers the assistant. The UI shows whether wake-word listening is actually ready, with a live microphone level. Hardware failures are retried instead of silently disabling standby.
- **Speech recognition:** [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) small, running locally with CPU int8 inference. Silero detects when you start and finish; recordings include a short pre-roll and end after about 650 ms of silence, rather than always waiting five seconds or cutting off at five seconds. The maximum utterance is 25 seconds. English and Indonesian are detected automatically on each utterance; ambiguous Malay detections are retried as Indonesian. No microphone audio is uploaded.
- **Speech synthesis:** English uses the female Piper `en_US-hfc_female-medium` voice. Indonesian uses the native [Piper id_ID news_tts voice](https://huggingface.co/rhasspy/piper-voices/tree/main/id/id_ID/news_tts/medium) with a brighter, slightly higher tone; this is a different speaker, rather than English pronunciation applied to Indonesian. Engines stay loaded in memory. Questions, commas, contractions and exclamations are preserved for natural phrasing. [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) remains available for English through `ROBOT_TTS_ENGINE=kokoro`; it sounds more natural but is about 10 times slower here. Muting stops playback as well as future speech. The name is written “Hey Insight” in the interface, while the wake phrase is still spoken as “Hey In Site”.
- **Conversation:** [Qwen3 1.7B](https://ollama.com/library/qwen3:1.7b) answers directly with its reasoning phase disabled, running on the integrated GPU through a private Ollama instance on port 11435. It uses a short, cheerful companion persona and a smaller context. Replies follow English or Indonesian from the latest message and remember the language for ambiguous short follow-ups. Tokens appear as they arrive and completed sentences are spoken while generation continues. The model is warmed at startup and kept loaded for 30 minutes. Initial model loading is slower than warm requests.
- **Fast paths:** time, date, capabilities and [Open-Meteo weather](https://open-meteo.com/) use direct results without a language-model round trip. English camera descriptions are returned directly; Indonesian camera requests translate the description locally. Ordinary explanations and chat stay local; explicit internet requests and current factual questions trigger web search. Small local models can make factual mistakes; ask for a web search when you want grounded information.

Kokoro and Qwen3 4B Instruct have Apache-licensed weights; Faster-Whisper is MIT-licensed. Piper voice licensing follows its linked model card and source dataset. There are no paid AI APIs or API keys. The optional public weather service and search provider still require internet access. Voice quality and recognition accuracy depend on the microphone, accent and room; these local models do not guarantee parity with Google's hosted speech services.

Optional settings are listed under [Konfigurasi](#konfigurasi).

To inspect the design without loading speech models, opening a microphone, or connecting to Ollama:

```powershell
.venv\Scripts\python.exe -m modules.interface --preview
```

Preview mode is identified in the connection indicator's tooltip and does not execute prompts or camera requests. Device detection and selection remain available without starting a recording. To run the regression suite:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The suite covers device preferences, the authenticated local UI bridge, speech endpoints, English/Indonesian routing, voice selection, and web-search clarification and fallback behavior. Tests mock hardware and external services. They do not establish recognition accuracy for your accent or room; use [TEST_PHRASES.md](TEST_PHRASES.md) for live checks.

## Microphone and camera

Open **Devices** in the top bar, choose a detected microphone and camera, and click **Apply devices**. Your microphone choice is shared by wake-word detection and voice questions. The camera choice is used for camera questions. Changes apply to the next request; the panel waits for any active recording or response to finish before applying them.

Use **Refresh** after connecting devices. Preferences are stored locally in `device_settings.json`, which is excluded from Git. If a saved device is disconnected, the panel shows it as unavailable so you can choose another. Use the default options to follow the Windows default microphone and OpenCV's default camera. Detection does not open the camera or record microphone audio. Allow microphone and camera access for desktop apps in Windows Privacy settings.

Microphones that require a native sample rate (such as 48 kHz) are recorded at that rate and resampled to 16 kHz for the speech and wake-word models. Camera names and capture indices are resolved with [cv2-enumerate-cameras](https://github.com/lukehugh/cv2_enumerate_cameras); microphone enumeration and format checks use [sounddevice](https://python-sounddevice.readthedocs.io/en/0.4.7/api/checking-hardware.html).

## Features to try

- “What time is it?” or “Jam berapa sekarang?”
- “What is a transistor?” — gives a quick local explanation
- “What’s the weather in Jakarta?” or “Bagaimana cuaca di Jakarta besok?” — checks Open-Meteo
- “Search for the latest NASA Artemis news.”
- “Can you explain that more simply?” — follows up on the previous answer
- “What do you see?” or “Apa yang kamu lihat?” — describes the webcam image
- “Istirahat” or “Go to sleep” — returns to wake-word standby
- “Tell me a short joke.” — general conversation through the local model

More test phrases are in [TEST_PHRASES.md](TEST_PHRASES.md).

You can also say “Look on the internet” or “Cari di internet” without a topic. The robot asks what to search for, then searches your next reply. Say “Cancel” or “Batal” to leave that prompt, or give another direct command. Explicit search requests use the web even when the topic mentions weather or a camera. Search uses a free provider with alternate providers on failure; empty or failed searches get a direct explanation rather than a guessed model answer.

## Troubleshooting

- **Python 3.11 was not found:** install the 64-bit Python version linked above, including the Python Launcher, then reopen the `.bat` file.
- **Ollama was not found:** install Ollama and reopen the launcher.
- **Ollama cannot connect:** open Ollama from the Start menu and try again.
- **Microphone or camera errors:** choose a connected device in **Devices**, click **Apply devices**, and check Windows privacy permissions.
- **Dependency setup needs to run again:** delete `.setup_complete` and launch the `.bat` file again.
- **Wake word never responds:** run `Start_RobotInsight.bat` again to repair missing speech resources. Check the standby message and microphone level, then choose the intended microphone in **Devices**. Say “Hey In Site,” pause briefly for the listening expression, then ask your question.
- **The model is slow:** allow startup warmup to finish, and check that the terminal prints `[LLM] Ready: 100% on GPU`. A lower number means Ollama is using the CPU. The default is `qwen3:1.7b`; simple time/date/weather queries avoid the chat model entirely. See [docs/perubahan-optimasi-performa.md](docs/perubahan-optimasi-performa.md).
- **A search asks what to look for:** give a topic, such as “NASA Artemis news.” A bare “Look on the internet” starts a topic prompt rather than searching punctuation.
- **Web search is unavailable:** verify your internet connection and try again. The app tries alternate free search providers, but provider outages or blocked connections can still prevent results. A failed search does not mean the local chat model has lost its connection.

## Event knowledge

The robot answers ITB Insight questions from `docs/pengetahuan-itb-insight.md`. The event committee can change that file without touching the code, and edits apply on the next question. Each `## Title` is one section, and these optional lines control it:

| Line | Effect |
| --- | --- |
| `Selalu dipakai: ya` | Sends the section with every chat turn. Keep it to about 40–60 words. |
| `Kata kunci utama:` | 3 points. One main keyword is enough to pick the section. |
| `Kata kunci pendukung:` | 1 point. Needs a second keyword before the section is picked. |
| `Kata kunci longgar:` | 3 points and tolerates small mishearing, such as “pley tek”. Use it for names only. |
| `Kata kunci:` | The older form, treated as `Kata kunci utama:`. |

The highest-scoring section is used, plus a second one only when its score is within 1 point. A short follow-up that refers back, such as “Di mana tempatnya?”, keeps the facts for up to 2 more turns. Another action, another section, or an unrelated question clears them.

Each model turn logs `[LLM] Prompt tokens: N/2048`, and a warning appears above 1700. When an answer is cut off after its sentence limit, Ollama never reports the count, so the log shows an estimate marked `(perkiraan)`.

## Privacy and network use

Speech recognition, language generation, vision analysis, and text-to-speech run on the PC. The assistant sends web-search queries to its search provider when web lookup is needed, and requested cities to Open-Meteo for weather. The first run downloads Python packages and model files. No API key is required.

Downloaded models, voice samples, conversation memory, and device preferences are excluded from Git. The repository includes the UI assets, application code, tests, and setup scripts; a fresh clone downloads its models through the launcher.

## Project layout

| Path | Purpose |
| --- | --- |
| `main.py` | Shared voice/text request loop, conversation, and tool routing. |
| `modules/` | Speech engines, wake word, devices, local UI server, weather, and search. |
| `modules/hey_in_site.onnx` | Custom wake-word model used by the app. |
| `ui/` | Browser interface and animated robot asset. |
| `docs/pengetahuan-itb-insight.md` | Event facts the robot answers from; edits apply without a restart. |
| `tests/` | Automated regression tests. |
| `Start_RobotInsight.bat` | Windows setup and launch entry point. |
| `models/` | Downloaded speech resources, created locally by setup. |

The interface draws robot expressions in the browser; the legacy JPG animation folders and their diagnostic scripts are no longer needed. Speech setup is handled by `python -m modules.setup_speech`; use `--wake-only` to download only the wake-word feature resources.
