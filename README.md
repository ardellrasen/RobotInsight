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

The default Qwen3 4B Instruct chat model is quantized to about 2.5 GB. First setup also downloads the vision model, Faster-Whisper small, Kokoro and its female English voices, a native Indonesian Piper voice, and the wake-word audio feature models. The app can run without a webcam, but its vision feature needs one.

## First-time setup

1. Install [Python 3.11 for Windows](https://www.python.org/downloads/release/python-3119/). In the installer, enable the Python Launcher option.
2. Install [Ollama for Windows](https://ollama.com/download/windows). Ollama supplies the local language and vision models.
3. Open PowerShell or Command Prompt and clone this repository:

   ```powershell
   git clone https://github.com/naufshidqiz/RobotInsight.git
   cd RobotInsight
   ```

4. Double-click **Start_RobotInsight.bat**.

The launcher creates a private Python environment, installs the packages, downloads the speech, wake-word, chat and vision models, and starts the assistant. First setup can take a while and download several gigabytes. Later runs reuse the installed packages and models.

The launcher opens a dedicated Edge window, or your default browser if Edge is unavailable. When the robot is ready, say **“Hey In Site”**, click the microphone, or type in the message box. Press Enter to send and Shift+Enter for a new line. Use the fullscreen button to expand the interface and Escape to leave fullscreen. Close the terminal window or press Ctrl+C there to stop the program.

For your first voice conversation:

1. Open **Devices**, select your microphone and camera, and apply your choices.
2. Wait for the standby message **Listening for “Hey In Site”**.
3. Say the wake phrase, pause for the listening expression, then ask your question in English or Indonesian.
4. Continue with a follow-up after the spoken answer. Say **“Go to sleep”** or **“Istirahat”** to return to wake-word standby. Silence also ends follow-up listening.

## The companion interface

- A pearl white robot with animated cyan eyes: it follows the cursor, blinks, and changes expression while listening, thinking, searching, looking, and speaking. Click it or press Enter while it is focused to say hello.
- A large central robot and microphone button for voice use. The latest response appears beneath the robot.
- An optional **Conversation** side panel with complete responses, selectable text, a copy button, and a text composer. The latest 100 messages stay available during the current run.
- A microphone button, camera shortcut, and keyboard button. Typed and spoken questions use the same assistant and conversation context.
- A **Devices** panel with detected microphone and camera selectors, refresh, and saved preferences.
- A **Try asking** panel on the left with eight feature groups and five clickable examples per group. On small screens, open it with the sparkle button.
- A voice toggle for spoken responses, a live activity indicator, and a camera preview during analysis.
- A responsive layout and support for the operating system's reduced motion preference.

The interface uses a local server bound to `127.0.0.1` and bundled assets. No external fonts or hosted UI services are needed. Speech, wake-word detection, chat, and camera analysis run locally. Web search sends queries to the search provider; weather sends the city you request to Open-Meteo. Text chat remains available if microphone setup fails.

## Speech and response speed

- **Wake word:** the custom “Hey In Site” model runs through openWakeWord. The launcher downloads its melspectrogram and embedding ONNX models into `models/wakeword/`, and startup validates them. A single score above 0.45 triggers the assistant. The UI shows whether wake-word listening is actually ready, with a live microphone level. Hardware failures are retried instead of silently disabling standby.
- **Speech recognition:** [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) small, running locally with CPU int8 inference. Silero detects when you start and finish; recordings include a short pre-roll and end after about 650 ms of silence, rather than always waiting five seconds or cutting off at five seconds. The maximum utterance is 25 seconds. English and Indonesian are detected automatically on each utterance; ambiguous Malay detections are retried as Indonesian. No microphone audio is uploaded.
- **Speech synthesis:** English uses [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) with the female `af_heart` voice. Indonesian uses the native [Piper id_ID news_tts voice](https://huggingface.co/rhasspy/piper-voices/tree/main/id/id_ID/news_tts/medium); this is a different speaker, rather than English pronunciation applied to Indonesian. Engines stay loaded in memory. Questions, commas, contractions and exclamations are preserved for natural phrasing. A local female Piper voice is the English fallback if Kokoro cannot load. Muting stops playback as well as future speech.
- **Conversation:** [Qwen3 4B Instruct](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M) answers directly without a reasoning phase. It uses a short, cheerful companion persona and a smaller context. Replies follow English or Indonesian from the latest message and remember the language for ambiguous short follow-ups. Tokens appear as they arrive and completed sentences are spoken while generation continues. The model is warmed at startup and kept loaded for 30 minutes. Initial model loading is slower than warm requests.
- **Fast paths:** time, date, capabilities and [Open-Meteo weather](https://open-meteo.com/) use direct results without a language-model round trip. English camera descriptions are returned directly; Indonesian camera requests translate the description locally. Ordinary explanations and chat stay local; explicit internet requests and current factual questions trigger web search. Small local models can make factual mistakes; ask for a web search when you want grounded information.

Kokoro and Qwen3 4B Instruct have Apache-licensed weights; Faster-Whisper is MIT-licensed. Piper voice licensing follows its linked model card and source dataset. There are no paid AI APIs or API keys. The optional public weather service and search provider still require internet access. Voice quality and recognition accuracy depend on the microphone, accent and room; these local models do not guarantee parity with Google's hosted speech services.

Optional settings can be set before launching:

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `ROBOT_STT_LANGUAGE` | `auto` | Automatically recognize English/Indonesian; set `en` or `id` to force one language. |
| `ROBOT_STT_MODEL` | `small` | Faster-Whisper model name; rerun speech setup after changing it. |
| `ROBOT_TTS_VOICE` | `af_heart` | Kokoro female voice, e.g. `af_bella` or `af_sarah`. |
| `ROBOT_LLM_MODEL` | `qwen3:4b-instruct-2507-q4_K_M` | Ollama chat model; the launcher downloads it if missing. |
| `ROBOT_WAKE_THRESHOLD` | `0.45` | Lower is more sensitive and may trigger more false wakes. |

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
- **The model is slow:** allow startup warmup to finish. Ollama can use the CPU, but a supported GPU improves chat response time. The default is `qwen3:4b-instruct-2507-q4_K_M`; simple time/date/weather queries avoid the chat model entirely.
- **A search asks what to look for:** give a topic, such as “NASA Artemis news.” A bare “Look on the internet” starts a topic prompt rather than searching punctuation.
- **Web search is unavailable:** verify your internet connection and try again. The app tries alternate free search providers, but provider outages or blocked connections can still prevent results. A failed search does not mean the local chat model has lost its connection.

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
| `tests/` | Automated regression tests. |
| `Start_RobotInsight.bat` | Windows setup and launch entry point. |
| `models/` | Downloaded speech resources, created locally by setup. |

The interface draws robot expressions in the browser; the legacy JPG animation folders and their diagnostic scripts are no longer needed. Speech setup is handled by `python -m modules.setup_speech`; use `--wake-only` to download only the wake-word feature resources.
