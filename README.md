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

- Windows is the current documented development environment.
- A Python version compatible with the project's dependencies.
- Ollama installed and running locally.
- The `qwen3:4b-instruct` model downloaded into Ollama.
- Kokoro ONNX model and voice assets for Voice Chat.
- A working microphone and audio output device for live voice interaction.
- Faster-Whisper and its runtime dependencies for speech recognition.

## Installation (Windows CMD)

### 1. Clone the repository

```bat
git clone https://github.com/amartyasinghnamra/RIKO-Major-Project.git
cd RIKO-Major-Project
```

### 2. Create and activate a virtual environment

```bat
python -m venv .venv-tts
.venv-tts\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If Faster-Whisper is not included in the installed dependency list, install it separately:

```bat
python -m pip install faster-whisper
```

### 3. Set up Ollama

Install Ollama and make sure its local service is running. Then run:

```bat
ollama pull qwen3:4b-instruct
ollama list
```

### 4. Add Kokoro model assets

Place the required assets in `models/kokoro/`:

```text
models/kokoro/
├── kokoro-v1.0.int8.onnx
└── voices-v1.0.bin
```

Model weights are not committed to this repository. Obtain them from a trusted source and review the applicable model and voice licences.

### 5. Launch RIKO

From the repository root, with the virtual environment active:

```bat
python src\main.py
```

The menu offers:

- `1` — Text Chat
- `2` — Voice Chat
- `0` — Exit

Text Chat requires a working local Ollama setup and project configuration. Voice Chat additionally requires the speech/audio dependencies, model assets, microphone, and audio output device.

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
