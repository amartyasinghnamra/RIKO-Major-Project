# RIKO — A Local AI Companion

RIKO is a modular, local-first AI companion for text and voice interaction. It separates conversation management, prompt handling, language-model access, speech recognition, speech synthesis, and configuration so components can evolve independently.

> **Project status:** Active development. Features, interfaces, and setup requirements may change.

## Features

- **Local LLM integration:** Connects to Ollama using `qwen3:4b-instruct`.
- **Text and voice modes:** Select Text Chat or Voice Chat from the application entry point.
- **Streaming responses:** Supports incremental model output.
- **Speech recognition:** Includes microphone capture and a Faster-Whisper speech-to-text (STT) pipeline.
- **Speech synthesis:** Uses Kokoro ONNX for local text-to-speech (TTS) and audio playback.
- **Prompt and persona management:** Keeps prompts, persona settings, user-profile configuration, and mode-specific styles separate.
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
- A working microphone and audio output device for live Voice Chat.

## Install and run

The root-level install scripts create or reuse a project-local `.venv-tts`, install Python requirements, fetch Kokoro model and voice files, install/check Ollama, download `qwen3:4b-instruct`, warm the Faster-Whisper `base` cache, and finally run the separate interactive profile setup. They are designed to be safely rerun. Existing model files are preserved and checked for a minimum size; an existing local profile is preserved unchanged.

### Windows CMD

```bat
git clone https://github.com/amartyasinghnamra/RIKO-Major-Project.git RIKO_PROJECT
cd RIKO_PROJECT
install.bat
run.bat
```

Git is needed to clone the repository. If Python, Ollama, or curl is missing, `install.bat` installs it through `winget`; open a new CMD window and rerun the installer if a newly installed command has not appeared on PATH. Without `winget`, install Python 3.11+, Ollama, and curl from their official installers, then rerun `install.bat`.

### Linux (Debian/Ubuntu)

```sh
git clone https://github.com/amartyasinghnamra/RIKO-Major-Project.git RIKO_PROJECT
cd RIKO_PROJECT
bash install.sh
bash run.sh
```

`install.sh` uses `sudo` to install apt packages and Ollama. Other Linux distributions are not auto-configured; install Python 3.10+, venv/pip, a compiler toolchain, PortAudio, libsndfile, libespeak-ng, curl, and Ollama before adapting/running the script. The virtual environment is always project-local and `run.sh` invokes it without needing shell activation.

### Profile and local assets

After dependency and model setup succeeds, the installer calls `src/create_user_profile.py` as a separate interactive step. You can skip saving at the confirmation prompt and create it later with the `.venv-tts` Python interpreter. The profile lives in Git-ignored `config/local/user_profile.json`; an existing profile is never overwritten by the installer. Project prompts, personas, and other tracked files come from the clone. The installers do not copy the repository tree or process Git-ignored paths. Kokoro assets go under Git-ignored `models/kokoro/`; partial downloads are ignored too. Large/generated model files and local user configuration are not included in Git. Review upstream model and voice terms before redistribution.

The menu offers:

- `1` — Text Chat
- `2` — Voice Chat
- `0` — Exit

Text Chat requires the local Ollama service and downloaded chat model. Voice Chat additionally requires the speech/audio packages and model assets installed by the OS-specific installer, plus a microphone and audio output device. Faster-Whisper may use additional model cache space on its first load if the cache was cleared.

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
│   ├── local/               # Private local configuration
│   └── personas/
├── knowledge/
│   └── architecture/        # Architecture knowledge used by the tool
├── models/
│   └── kokoro/              # Local model assets; weights are not committed
├── prompts/                 # System prompts and mode styles
├── src/
│   ├── modes/               # Text Chat and Voice Chat
│   ├── tools/               # Architecture-information tool
│   ├── conversation_manager.py
│   ├── debug_logger.py
│   ├── ollama_client.py
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
