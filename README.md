RIKO — A Local AI Companion
RIKO is a modular, local-first AI companion built around conversational AI, text chat, and voice interaction. Its design separates conversation management, prompt handling, language-model access, speech recognition, and speech synthesis so the components can evolve independently.
Status: Active development. Features, interfaces, and setup requirements may change.
Features
·	Local LLM: Connects to Ollama and the qwen3:4b-instruct model.
·	Text and voice modes: Choose Text Chat or Voice Chat from the application entry point.
·	Streaming responses: Supports incremental model output.
·	Speech recognition: Includes a microphone capture and Faster-Whisper STT pipeline, including rolling-window draft transcription.
·	Speech synthesis: Uses Kokoro ONNX for local text-to-speech and audio playback.
·	Prompt management: Separates persona, user-profile configuration, system prompts, and mode-specific styles.
·	Conversation management: Maintains session conversation history and coordinates model interactions.
·	Architecture-aware answers: A constrained tool retrieves documented information about RIKO's models, modules, configuration, voice pipeline, capabilities, and development status.
·	Modular startup: Text Chat can be selected without immediately importing voice-specific dependencies.
Architecture at a Glance
                    ┌─────────────────────┐
                    │         User        │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
               Text Chat              Voice Chat
                                          │
                                     Microphone
                                          │
                                 Silence Detection
                                          │
                                   Faster-Whisper
                                          │
                                   Recognized text
                    │                     │
                    └──────────┬──────────┘
                               │
                      Conversation Manager
                               │
                         Prompt Manager
                               │
                         Ollama / Qwen
                               │
                         Model response
                               │
                    ┌──────────┴──────────┐
                    │                     │
                Text output          Kokoro ONNX
                                          │
                                     Audio playback
This is a conceptual overview, not a guarantee that every path or feature is fully production-ready.
Technology Stack
Component	Technology
Language	Python
Local LLM runtime	Ollama
Chat model	qwen3:4b-instruct
Speech-to-text	Faster-Whisper
Text-to-speech	Kokoro ONNX
Audio I/O	sounddevice, soundfile
Numerical audio processing	NumPy
Tests	Python test scripts and STT-focused tests

Requirements
·	Windows is the current documented development environment.
·	Python compatible with the project's dependencies. The current development environment uses Python 3.14.8; if a dependency does not support that version, use a Python version supported by the dependency.
·	Ollama installed and running locally.
·	The qwen3:4b-instruct model downloaded into Ollama.
·	Kokoro ONNX model and voice assets for Voice Chat.
·	A working microphone and audio output device for live voice interaction.
·	Faster-Whisper and its runtime dependencies for speech recognition.
Installation (Windows CMD)
1. Clone the repository
git clone https://github.com/amartyasinghnamra/RIKO-Major-Project.git
cd RIKO-Major-Project
2. Create and activate a virtual environment
python -m venv .venv-tts
.venv-tts\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
Install Faster-Whisper if it is not already installed by the project's dependency list:
python -m pip install faster-whisper
3. Set up Ollama
Install Ollama, make sure its local service is running, then run:
ollama pull qwen3:4b-instruct
ollama list
4. Add Kokoro model assets
Place the required assets in models/kokoro/:
models/kokoro/
├── kokoro-v1.0.int8.onnx
└── voices-v1.0.bin
Model weights are not committed to this repository. Obtain them from a trusted source and review the applicable model and voice licences.
5. Launch RIKO
From the repository root, with the virtual environment active:
python src\main.py
Choose from the menu:
·	1 — Text Chat
·	2 — Voice Chat
·	0 — Exit
Text Chat requires a working local Ollama setup and project configuration. Voice Chat additionally requires the speech/audio dependencies, model assets, microphone, and audio output device.
Development and Testing
Compile the Python source files:
python -m compileall -q src audio
STT-focused tests are located under tests/stt/. Where the installed environment supports them, run the test suite with:
python -m unittest discover -s tests
Some tests may require optional dependencies, audio hardware, model assets, or a running Ollama service. Compilation checks syntax; it does not prove that the full live voice pipeline works. Perform a real microphone-to-transcription-to-response-to-audio test before a demo or release.
Configuration and Privacy
·	Keep private profile data and local overrides on your machine; do not commit them.
·	Never commit credentials, API keys, .env files, private recordings, or personal configuration.
·	Local inference reduces dependence on hosted model APIs, but it does not automatically mean every dependency or integration is offline. Verify each component before using sensitive data.
·	RIKO's architecture lookup uses allow-listed documentation topics; it is not designed to expose arbitrary filesystem paths.
Repository Layout
This is a high-level guide to the main areas, not an exhaustive listing of every file.
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
├── prompts/                 # System prompt and mode styles
├── src/
│   ├── modes/               # Text Chat and Voice Chat
│   ├── tools/               # Architecture-information tool
│   ├── conversation_manager.py
│   ├── debug_logger.py
│   ├── ollama_client.py
│   └── prompt_manager.py
├── tests/
│   └── stt/                 # Speech-recognition tests
├── requirements.txt
├── .gitignore
└── README.md
Known Limitations
·	RIKO is under active development; behaviour and interfaces may change.
·	Transcription quality and latency depend on the STT model, microphone, CPU performance, and environment.
·	Initial model downloads and initialization may take time.
·	Voice interaction depends on correctly installed audio dependencies and local model assets.
·	Automated tests do not replace a live end-to-end voice test.
License
RIKO is released under the MIT License. See LICENSE for details.
