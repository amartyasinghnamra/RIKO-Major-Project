# RIKO — A Local AI Companion

RIKO is a modular, local-first AI companion for text and voice interaction. It separates conversation management, prompt handling, language-model access, speech recognition, speech synthesis, and configuration so components can evolve independently.

> **Project status:** Active development. Features, interfaces, and setup requirements may change.

## Features

- **Local LLM integration:** Connects to Ollama using `qwen3:4b-instruct`.
- **Text and voice modes:** Select Text Chat or Voice Chat from the terminal menu or the GUI.
- **Cross-platform desktop GUI:** A native Tkinter window calls RIKO's Python conversation, microphone, Faster-Whisper, Kokoro, and audio playback components directly. It does not use a browser or local GUI web server.
- **Streaming responses:** Supports incremental model output.
- **Speech recognition:** Includes microphone capture and a Faster-Whisper speech-to-text (STT) pipeline.
- **Speech synthesis:** Uses Kokoro ONNX for local text-to-speech (TTS) and audio playback.
- **Profiles, personas, and behavior controls:** Offers an editable private profile, selectable bundled/custom profile contexts, and adjustable cuteness, playfulness, teasing, affection/warmth, energy, talkativeness, spontaneity, initiative, emotional awareness, reassurance, and response style.
- **Optional speech cache:** Read Aloud can reuse local Kokoro audio for repeated phrases. It is off by default, capped at 128 MB, and can be cleared in Preferences.
- **Conversation management:** Maintains session history and coordinates model interactions.
- **Architecture-aware answers:** An allow-listed tool retrieves documented information about RIKO's architecture, modules, configuration, and capabilities.
- **Modular startup:** Text Chat can be selected without immediately importing voice-specific dependencies.

## Architecture at a Glance

```text
                         User
                          |
                +---------+---------+
                |                   |
             Text Chat           Voice Chat
                                    |
                                Microphone
                                    |
                          Speech Recognition (STT)
                                    |
                              Recognized text
                |                   |
                +---------+---------+
                          |
                 Conversation Manager
                          |
                     Prompt Manager
                          |
                    Ollama / Qwen
                          |
                    Model response
                          |
                +---------+---------+
                |                   |
            Text output         Kokoro ONNX
                                    |
                               Audio playback
```

This is a conceptual overview; it does not imply that every path or feature is production-ready.

## Technology Stack

| Component | Technology |
|---|---|
| Language | Python |
| Local LLM runtime | Ollama |
| Chat model | `qwen3:4b-instruct` |
| Speech-to-text | Faster-Whisper |
| Text-to-speech | Kokoro ONNX |
| Audio I/O | `sounddevice`, `soundfile` |
| Numerical audio processing | NumPy |
| Tests | Python tests organized by test type |

## Requirements

- **Windows:** Windows 10/11, CMD, Git, `curl.exe`, and `winget` for automatic Python/Ollama installation when missing. Python 3.10+ is required; Python 3.11 is installed by winget if needed.
- **Linux:** Debian/Ubuntu with `apt-get`, `sudo` (or root), and Python 3.10+ available through distribution repositories. The installer installs Python venv/build tools, audio libraries, and Ollama.
- Internet access and enough free disk space for the Python environment, Ollama model, Kokoro files (about 120 MB combined), and Faster-Whisper model cache.
- Tkinter desktop support (included with standard Windows Python distributions; installed by the Debian/Ubuntu installer).
- A working microphone and audio output device for live Voice Chat and the desktop GUI's Voice mode.

## Install and run

The root-level install scripts create or reuse a project-local `.venv-tts`, install Python requirements, fetch Kokoro model and voice files, install/check Ollama, download `qwen3:4b-instruct`, warm the Faster-Whisper `base` cache, and finally run the separate interactive profile setup when no personal profile exists. The profile setup asks before saving. Installers are designed to be safely rerun; existing model files and profiles are preserved.

### Windows CMD

```bat
git clone https://github.com/amartyasinghnamra/RIKO-Major-Project.git
cd RIKO-Major-Project
install.bat
run.bat
```

Git is needed to clone the repository. If Python, Ollama, or curl is missing, `install.bat` installs it through `winget`; open a new CMD window and rerun the installer if a newly installed command has not appeared on PATH. Without `winget`, install Python 3.11+, Ollama, and curl from their official installers, then rerun `install.bat`.

### Linux (Debian/Ubuntu)

```sh
git clone https://github.com/amartyasinghnamra/RIKO-Major-Project.git
cd RIKO-Major-Project
bash install.sh
bash run.sh
```

`install.sh` uses `sudo` to install apt packages, Tkinter, and Ollama. Other Linux distributions are not auto-configured; install Python 3.10+, venv/pip, Tkinter, a compiler toolchain, PortAudio, libsndfile, libespeak-ng, curl, and Ollama before adapting/running the script. The virtual environment is always project-local and `run.sh` invokes it without needing shell activation.

### Graphical interface

RIKO also includes a native desktop GUI built with Python's Tkinter toolkit. The GUI and terminal menu use the shared mode functions in `src/main.py`: `create_chat_session`, `run_text_chat`, and `run_voice_chat`. Voice chat uses the same `VoiceChatSession` as the CLI: its `StreamingVoiceInput` detects utterance boundaries, Faster-Whisper transcribes speech, Ollama streams a reply into Kokoro's speech pipeline, and the barge-in monitor can interrupt playback. The GUI displays the recognized transcript and streamed response while the voice session stays hands-free; the text composer is hidden in Voice mode. Select **Voice** to start listening automatically, then select **Chat** to stop listening and playback. Voice mode has no separate record control. Microphone and speaker access use the operating system's audio devices directly; there is no browser permission prompt or local GUI web server.

In Text mode, each assistant reply has **Regenerate** and **Read aloud** actions. Regenerate retries the latest text turn using the conversation context that preceded that turn. Read aloud uses Kokoro and removes Markdown formatting before speech synthesis; it can be stopped from the same action button. **Enable text in, voice out** in Preferences controls whether Read aloud is available, and speech only plays when requested. The optional **Cache Read aloud audio locally** preference reuses synthesized phrases and stores them under Git-ignored `config/local/audio_cache/`. It is disabled by default, limited to 128 MB, and can be cleared from Preferences. Caching applies to Read aloud; hands-free Voice mode retains the low-latency streaming pipeline. The microphone button beside **Send** starts a manual recording; Faster-Whisper drafts appear in the composer while recording, and pressing the button again finalizes the transcript there. Review the transcript and press **Send** when ready. Recording is capped at two minutes per take.

While a reply is generating, the **Send** button changes to **■ Stop**; pressing it or **Escape** cancels the active Ollama stream and Kokoro playback. In Voice mode the session stays active and returns to listening. Speaking over a voice reply also stops generation and captures the interruption; short commands such as “stop,” “wait,” “pause,” or “hold on” are treated as controls instead of new questions. Headphones are recommended because this prototype does not include acoustic echo cancellation. Preferences can be saved while a reply is running: conversation style applies to the next model turn, while Kokoro voice and pace apply to the next spoken phrase.

The desktop UI can be zoomed from **80% to 160%** using the **− / +** controls beside the persona name. Use **Ctrl + Plus** (or **Ctrl + =**) and **Ctrl + -** to zoom on Windows/Linux, or **Command + Plus/Minus** on macOS; **Ctrl/Command + 0** resets to 100%. Holding Ctrl/Command while using the mouse wheel also zooms. Rounded cards and chat surfaces are drawn with Tkinter Canvas, so this styling does not depend on Windows-only window effects; the operating system continues to draw the title bar.

Windows CMD: run-gui.bat

Debian/Ubuntu Linux: bash run-gui.sh

The GUI uses the same `.venv-tts`, Ollama model, Kokoro assets, local persona, speech settings, and selected profile context as the CLI. **Tune RIKO's personality** opens ten 0–10 controls and response-style presets. Teasing remains gentle, affection/warmth is non-romantic by default, and the user's present request and serious tone take priority. Overrides live in Git-ignored `config/local/behavior.local.json` and apply to the next model reply. **Your profile** page lets you select Personal, Demo, or another available profile for prompt context and edit your private personal profile. Close the desktop window to exit.

### Profile and local assets

After dependency and model setup succeeds, the installer calls `src/create_user_profile.py` as a separate interactive step when no personal profile exists. The profile covers optional identity, interests, goals, learning preferences, and response preferences. Saving or replacing requires explicit confirmation. The personal profile lives in Git-ignored `config/local/user_profile.json`; additional named profiles can be created with `python src/create_user_profile.py --id study` and are saved under `config/local/profiles/`. Select the active profile in the GUI's profile page or the CLI Settings menu. A fictional, read-only Demo profile is included at `config/examples/profiles/demo.json`; it is only used when explicitly selected. `PromptManager` inserts profile data through `{user_profile}` and formats behavior settings through `{behavior_instructions}`; neither feature rewrites `prompts/system_prompt.txt`. Behavior overrides live in `config/local/behavior.local.json`. Personal/named profile data, behavior overrides, speech-cache files, and settings stay local and are not committed; the bundled Demo preset is tracked. Project prompts, personas, and other tracked files come from the clone. The installers do not copy the repository tree or process Git-ignored paths. Kokoro assets go under Git-ignored `models/kokoro/`; partial downloads are ignored too. Large/generated model files and local user configuration are not included in Git. Review upstream model and voice terms before redistribution.

The terminal menu offers:

- `1` — Text Chat
- `2` — Voice Chat
- `0` — Exit

The Settings menu can also select which profile context is used by the next chat session. Create or edit local profiles from the repository root with:

```bat
python src\create_user_profile.py
python src\create_user_profile.py --id study
```

```sh
.venv-tts/bin/python src/create_user_profile.py
.venv-tts/bin/python src/create_user_profile.py --id study
```

The GUI and CLI both build system context through `PromptManager`. Profile data uses the existing `{user_profile}` placeholder and behavior controls are formatted through `{behavior_instructions}`; neither feature rewrites `prompts/system_prompt.txt`.

Text Chat requires the local Ollama service and downloaded chat model. Voice Chat additionally requires the speech/audio packages and model assets installed by the OS-specific installer, plus a microphone and audio output device. Faster-Whisper may use additional model cache space on its first load if the cache was cleared.

The current website content and design constraints are recorded in [website_prompt.md](website_prompt.md). Keep its implementation claims aligned with the tested project capabilities.

## Development and Testing

Compile the Python source files:

```bat
python -m compileall -q src audio
```

Tests are organized under `tests/` by type, including unit, integration, and audio tests. Run the test suite using the test runner and dependencies configured for your checkout. For example, if `pytest` is installed and configured:

```bat
python -m pytest
```

Some tests may require optional dependencies, audio hardware, model assets, or a running Ollama service. Compilation checks syntax; it does not prove that the full live voice pipeline works. Perform a real microphone-to-transcription-to-response-to-audio test before a demo or release.

## Configuration and Privacy

- Keep private profile data and local overrides on your machine; do not commit them.
- Never commit credentials, API keys, `.env` files, private recordings, or personal configuration.
- Local inference can reduce dependence on hosted model APIs, but it does not automatically mean every dependency or integration works offline. Verify each component before using sensitive data.
- RIKO's architecture lookup uses allow-listed documentation topics; it is not designed to expose arbitrary filesystem paths.

## Repository Layout

This is a high-level guide to the main areas, not an exhaustive listing of every file.

```text
RIKO-Major-Project/
├── audio/
│   ├── kokoro/              # Text-to-speech
│   └── stt/                 # Microphone input and speech recognition
├── config/
│   ├── defaults/
│   ├── examples/
│   │   └── profiles/       # Bundled fictional profile presets
│   ├── local/               # Private local configuration
│   └── personas/
├── knowledge/
│   └── architecture/        # Architecture knowledge used by the tool
├── models/
│   └── kokoro/              # Local model assets; weights are not committed
├── prompts/                 # System prompts and mode styles
├── GUI/                     # Native Tkinter desktop chat and voice interface
├── src/
│   ├── modes/               # Text Chat and Voice Chat
│   ├── tools/               # Architecture-information tool
│   ├── conversation_manager.py
│   ├── debug_logger.py
│   ├── ollama_client.py
│   ├── user_profile.py      # Profile schema validation and normalization
│   ├── create_user_profile.py # Interactive local profile setup/editor
│   └── prompt_manager.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── audio/
├── requirements.txt
├── install.bat
├── install.sh
├── run.bat
├── run.sh
├── run-gui.bat
├── run-gui.sh
├── .gitignore
└── README.md
```

## Known Limitations

- RIKO is under active development; behaviour and interfaces may change.
- Transcription quality and latency depend on the STT model, microphone, CPU performance, and environment.
- Initial model downloads and initialization may take time.
- Voice interaction depends on correctly installed audio dependencies and local model assets.
- Automated tests do not replace a live end-to-end voice test.

## License

RIKO is released under the MIT License. See [LICENSE](LICENSE) for details.
