# RIKO — A Local AI Companion

RIKO is a modular, local-first AI companion for text and voice interaction. It runs a language model, speech recognition and speech synthesis on your own machine, so conversations are not sent to a hosted model service in the default setup.

> **Project status:** Active development. Features, interfaces and setup requirements may change.

RIKO ships as a **native desktop application** built with Python and Tkinter, with an **equivalent terminal mode** that shares the same engine, the same chat sessions and the same audio pipeline. Pick the surface that fits the moment.

---

## Contents

- [What RIKO does](#what-riko-does)
- [Architecture at a glance](#architecture-at-a-glance)
- [How a turn works](#how-a-turn-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Desktop application](#desktop-application)
- [Terminal mode](#terminal-mode)
- [Behaviour, personas and profiles](#behaviour-personas-and-profiles)
- [Privacy](#privacy)
- [Project status](#project-status)
- [Repository structure](#repository-structure)
- [Licence and third-party notices](#licence-and-third-party-notices)
- [Credits](#credits)

---

## What RIKO does

- **Native desktop application.** A Tkinter window that calls the Python conversation, microphone, Faster-Whisper, Kokoro and playback components directly. It is not an Electron or browser wrapper, and it runs no local web server. Rounded cards and chat surfaces are drawn with Tkinter Canvas, so the styling is cross-platform; the operating system draws the title bar.
- **Equivalent terminal mode.** A full-featured CLI sharing chat sessions and the audio pipeline with the desktop application.
- **Local language model.** Connects to a locally running Ollama service and uses `qwen3:4b-instruct`. No hosted LLM API is configured in the default setup.
- **Streaming replies.** Model output is consumed as a stream of chunks, not waited for in full.
- **Speech recognition.** Microphone capture and a Faster-Whisper speech-to-text pipeline running on the CPU in int8 mode.
- **Speech synthesis.** Kokoro ONNX for local text-to-speech, with streaming playback.
- **Hands-free voice mode.** Select **Voice** to start listening; select **Chat** to stop listening and playback. Markdown markers are stripped before speech so that characters such as `**` are never spoken.
- **Text chat actions.** Every assistant reply offers **Regenerate** and **Read aloud**. Read aloud uses Kokoro and is never automatic.
- **Manual dictation.** A microphone control beside **Send** records up to two minutes, renders rolling Faster-Whisper drafts in the composer, and finalises the transcript there for review before sending.
- **Stop and cancel.** While a reply is generating, **Send** becomes **Stop**; pressing it, or pressing **Escape**, cancels the active Ollama stream and any Kokoro playback.
- **Voice interruption (prototype).** A barge-in monitor can detect speech while a reply is playing and queue the interruption for the next turn. Short spoken commands such as "stop", "wait", "pause" or "hold on" are treated as controls rather than as new questions. There is no acoustic echo cancellation, so headphones are recommended.
- **Eleven configurable behaviour parameters.** Cuteness, playfulness, teasing, affection, energy, talkativeness, spontaneity, conversation initiative, emotional awareness, reassurance and response style, alongside response-style presets. These local preferences yield to the user's explicit instruction and serious tone.
- **Personas and profiles.** Selectable persona documents and an editable private profile. A guided wizard runs during installation or on demand.
- **Two bounded local tools.** An allow-listed architecture lookup that answers questions about RIKO's own documentation, and a read-only source explorer that lists and searches project text files.
- **Optional speech cache.** Read aloud can reuse locally synthesised audio for repeated phrases. It is off by default, capped at 128 MB, and can be cleared in Preferences.
- **Zoom.** The desktop interface scales from 80% to 160% using the controls beside the persona name, `Ctrl`/`Command` shortcuts, or `Ctrl`/`Command` plus the mouse wheel.
- **Modular startup.** Text chat can be selected without importing voice-specific dependencies.

---

## Architecture at a glance

```text
                            User
                             |
              +--------------+--------------+
              |                             |
      Desktop GUI (Tkinter)          Terminal mode
              |                             |
              +--------------+--------------+
                             |
                     Text  /  Voice
                             |
                   Conversation Manager
                             |
                      Prompt Manager
                             |
              +--------------+--------------+
              |                             |
     Ollama (127.0.0.1:11434)      Voice pipeline
     qwen3:4b-instruct             STT → reply → TTS
```

Four layers carry the system:

| Layer | Responsibility | Character |
|---|---|---|
| Surface | Desktop GUI and terminal mode | Owned by the project |
| Orchestration | Conversation state, prompt assembly, settings, behaviour | Owned by the project |
| Models | Local LLM, speech recognition, speech synthesis | Swappable behind module interfaces |
| Storage | Personas, behaviour defaults, profiles, settings | Local files, partly excluded from version control |

---

## How a turn works

### Text path

1. The user types in the desktop application or selects Text Chat in the terminal mode.
2. `PromptManager` loads the selected persona, the shared behaviour defaults, the user profile when present, and the text style prompt, and composes them into one system prompt.
3. `ConversationManager` keeps the active conversation in process memory and submits it to the local Ollama HTTP interface at `127.0.0.1:11434`.
4. Ollama runs `qwen3:4b-instruct` and streams the reply in chunks.
5. The reply is rendered with Markdown formatting and retained in the in-memory conversation. **Regenerate** retries the latest turn; **Read aloud** synthesises it on request.

The text path runs without initialising any audio device.

### Voice path

1. Selecting **Voice** starts listening automatically; selecting **Chat** stops listening and playback.
2. `sounddevice` captures microphone audio, converted to mono floating-point samples at 16 kHz.
3. Streaming voice input detects utterance boundaries; silence marks the end of a turn rather than a fixed recording window.
4. Faster-Whisper transcribes the collected audio on the CPU in int8 mode, with automatic language detection.
5. The transcript is passed to the shared `ConversationManager`, which is the same component the text path uses.
6. Ollama generates the reply using the same prompt assembly.
7. The cleaned text is synthesised by Kokoro ONNX in chunks and played as it is produced, so playback begins before the reply is complete.
8. The barge-in monitor may capture a new utterance during playback and queue it for the next turn.

---

## Requirements

Estimates for a comfortable local experience. Hardware figures are conservative planning estimates derived from the published size of the models and from CPU-based inference behaviour. They are not benchmarks.

### Minimum — text chat only

| Component | Requirement |
|---|---|
| Operating system | Windows 10 or 11 (64-bit) / Debian or Ubuntu (64-bit) |
| Processor | Recent 64-bit dual-core. AVX2 recommended, not required. |
| Memory | 8 GB RAM |
| Free disk space | 10 GB before installation |
| Graphics | No dedicated GPU required |
| Python | 3.10 or newer |
| Network | Internet connection during initial setup |

Text generation is usable but slow on a dual-core processor. Closing memory-heavy applications helps.

> **Linux download retry note:** If a Kokoro asset download fails, `install.sh` preserves the partial file under `models/kokoro/` with a `.part` suffix. Inspect or remove that partial asset before retrying.

### Recommended — text and voice chat

| Component | Requirement |
|---|---|
| Operating system | Windows 11 / Ubuntu 22.04 or newer (64-bit) |
| Processor | Recent 64-bit quad-core or better |
| Memory | 16 GB RAM |
| Free disk space | 20 GB before installation |
| Graphics | Dedicated GPU optional |
| Audio | A stable microphone and speakers or headphones. Headphones are recommended to reduce echo. |
| Python | 3.11 or newer |

### Disk space

| Asset | Approximate size |
|---|---|
| Ollama runtime | ~1 GB |
| Chat model, `qwen3:4b-instruct` (Q4_K_M) | ~2.5 GB |
| Kokoro model and voice data | ~120 MB |
| Faster-Whisper base cache | ~150–300 MB |
| Python virtual environment and packages | ~1.5–2 GB |
| **Installation total** | **~5–6 GB** |
| **Plus caches, model updates and temporary downloads** | **10 GB minimum, 20 GB comfortable** |

### Memory

| Loaded component | Approximate RAM |
|---|---|
| Operating system and desktop | 2–3 GB |
| Ollama and the chat model with context | 4–5 GB |
| Faster-Whisper base model (int8) | 0.5–1 GB |
| Kokoro ONNX synthesis | ~0.3 GB |
| **Text-only peak** | **6–7 GB** (8 GB is tight but workable) |
| **Voice peak, all components loaded** | **7–9 GB** (16 GB comfortable) |

### Notes on these figures

- No minimum processor generation and no minimum GPU or VRAM requirement is claimed, because neither has been established by testing across representative machines.
- The size of a model file is not the same as total runtime memory use.
- RIKO is designed to run without a dedicated GPU. Speech recognition is explicitly configured for CPU execution in int8 mode. The language model runs through Ollama, which may use supported hardware acceleration when available, and performance varies accordingly.
- Persistent **text** history grows at roughly 70 MB per year of daily use. Retaining audio is optional and off by default; uncompressed audio grows at roughly 2 MB per minute, so audio retention should be capped or stored compressed.
- Installation requires internet access. RIKO is local-first; that does not mean installation is offline.

---

## Installation

The installer and launcher scripts live at the **repository root**. There is no subdirectory nesting.

### Windows

```bat
:: clone the repository
git clone https://github.com/amartyasinghnamra/RIKO-Major-Project
cd RIKO-Major-Project

:: install, then run
install.bat
run.bat
run-gui.bat
```

The Windows installer can use `winget` to install missing Python, Ollama or curl. If a newly installed command is not recognised in the current shell, open a new command window and run `install.bat` again.

### Debian / Ubuntu Linux

```sh
# clone the repository
git clone https://github.com/amartyasinghnamra/RIKO-Major-Project
cd RIKO-Major-Project

# install, then run
bash install.sh
bash run.sh
bash run-gui.sh
```

The Linux installer uses `sudo` (or root) with `apt-get` and configures **Debian and Ubuntu only**. Other distributions are not automatically configured; install Python 3.10+, venv and pip, Tkinter, a compiler toolchain, PortAudio, libsndfile, libespeak-ng, curl and Ollama before adapting the script.

### Downloadable packages

The `Build desktop packages` GitHub Actions workflow creates a Windows `RIKO-Setup.exe` installer and an x86_64 Linux AppImage. Push a `v*` tag to build both packages and automatically publish a GitHub Release with the installers attached. Builds triggered by pushes to `main` or manual workflow runs are available as Actions artifacts for 14 days.

Both packages download Python dependencies and model assets during setup rather than bundling them. Windows installs RIKO per user and runs the existing setup script. Its Desktop and Start Menu shortcuts launch the GUI directly without opening a console. The AppImage copies RIKO to `${XDG_DATA_HOME:-~/.local/share}/RIKO` and creates Desktop and application-menu launchers for future GUI-only launches. Its first launch opens a terminal for setup. Linux setup installs system prerequisites with `apt-get` and may request `sudo`; automatic setup supports Debian/Ubuntu. Internet access is required. The AppImage is an installer/launcher, not a fully self-contained offline runtime.

### What happens during installation

1. **Virtual environment.** Creates or reuses a repository-local `.venv-tts`.
2. **Dependencies.** Installs `kokoro-onnx 0.4.7`, `faster-whisper`, `sounddevice 0.5.6`, `soundfile 0.14.0` and NumPy `>=2.0.2,<3`.
3. **Speech assets (~120 MB).** Fetches the Kokoro v1.0 INT8 ONNX model and `voices-v1.0.bin` into `models/kokoro/`.
4. **Runtime and model (~2.5 GB).** Verifies or provisions Ollama and pulls `qwen3:4b-instruct` (Q4_K_M).
5. **Recognition cache.** Prepares the Faster-Whisper base model cache.
6. **Profile wizard.** Calls `src/create_user_profile.py` as a separate interactive step when no personal profile exists.

### Caveats

- **Retry (Linux).** If a Kokoro download fails, the installer preserves a `.part` file under `models/kokoro/`. Inspect or remove that partial asset before retrying; reruns are not failure-proof.
- **Repository contents.** Model assets and personal profiles are generated locally and are excluded from Git. The installers do not copy the repository tree or process Git-ignored paths.
- **Setup needs the internet.** Dependencies and model assets are downloaded from external services. We do not claim that every integration works offline.

---

## Desktop application

Launch with `run-gui.bat` (Windows) or `bash run-gui.sh` (Linux), or select the GUI from `src/main.py`.

The desktop application and the terminal mode use the same functions in `src/main.py`: `create_chat_session`, `run_text_chat` and `run_voice_chat`. Voice mode uses the same voice-chat session as the CLI: streaming voice input detects utterance boundaries, Faster-Whisper transcribes, Ollama streams a reply into the Kokoro pipeline, and the barge-in monitor can interrupt playback.

**Text mode.** Replies render with Markdown formatting and stream in as they arrive. Each reply has **Regenerate** and **Read aloud**. **Enable text in, voice out** in Preferences controls whether Read aloud is available.

**Voice mode.** The composer is hidden; the interface shows the recognised transcript and the streamed reply. There is no separate record control — selecting **Voice** starts the session.

**Controls.** **Send** becomes **Stop** while a reply is generating; **Stop** or **Escape** cancels the stream and any playback. Preferences can be saved while a reply is running: conversation style applies to the next model turn, while voice and pace apply to the next spoken phrase.

**Zoom.** 80% to 160% via the `− / +` controls, `Ctrl`/`Command` `+` and `-`, or `Ctrl`/`Command` plus the mouse wheel. `Ctrl`/`Command` `0` resets to 100%.

**Preferences.**

- **Behaviour.** Eleven adjustable parameters with response-style presets. Teasing remains gentle, and affection is non-romantic by default.
- **Speech.** Kokoro voice and pace.
- **Cache Read aloud audio locally.** Off by default, capped at 128 MB, stored under the Git-ignored `config/local/audio_cache/`, and clearable in Preferences. Caching applies to Read aloud; hands-free voice mode keeps the low-latency streaming pipeline.

Close the desktop window to exit.

---

## Terminal mode

The terminal mode also offers:

- `1` — Text Chat
- `2` — Voice Chat
- `3` — Settings and Selectors
- `0` — Exit

**Settings and Selectors** covers persona selection, Kokoro voice and pace, the profile context used by the next session, and the behaviour parameters. Create or edit local profiles from the repository root:

```bat
python src\create_user_profile.py
python src\create_user_profile.py --id study
```

---

## Behaviour, personas and profiles

### Behaviour parameters

Eleven parameters describe the companion's conversational character. Each is a named value in a behaviour document:

| Parameter | What it governs |
|---|---|
| Cuteness | Lightness of tone and playful softness in phrasing |
| Playfulness | Willingness to joke, tease and introduce levity |
| Teasing | Frequency and warmth of affectionate needling |
| Affection | Directness of expressed warmth towards the user |
| Energy | Overall liveliness of the register |
| Talkativeness | Length of replies relative to the minimum needed |
| Spontaneity | Tendency to volunteer observations the user did not ask for |
| Conversation initiative | Whether the companion opens or re-opens a conversation |
| Emotional awareness | Degree to which the companion attends to and names the user's state |
| Reassurance | Tendency to reassure and encourage rather than to inform only |
| Response style | Form and pacing of replies, including sentence length and structure |

Local preferences yield to the user's explicit instruction and serious tone.

### Personas

Personas are small JSON documents that override a subset of the behaviour parameters and add persona-specific prompt material. Three ship with the repository: an **assistant** persona, a **tutor** persona oriented towards explanation and study, and a neutral **demo** persona for public or evaluative use. Because a persona states only what makes it different, the documents are short.

### Configuration layers

Four sources are merged at runtime, in order:

| Order | Source | Location | In version control |
|---|---|---|---|
| 1 | Shared behaviour defaults | `config/defaults/` | Yes |
| 2 | Selected persona | `config/personas/` | Yes (neutral personas only) |
| 3 | Private configuration | `config/local/` | No |
| 4 | User profile | `config/local/` | No |

The merge is deep, so a later source may override a single nested value without replacing the containing structure. A user who wants a quieter companion changes one value in one file; every other inherited setting survives.

### Profiles

The profile wizard covers optional identity, interests, goals, learning preferences and response preferences. Saving or replacing requires explicit confirmation, and an existing profile is preserved rather than overwritten. The personal profile lives in the Git-ignored `config/local/user_profile.json`. Additional named profiles can be created with `python src/create_user_profile.py --id study` and are saved under `config/local/profiles/`. A fictional, read-only demo profile is included at `config/examples/profiles/demo.json` and is used only when explicitly selected.

`PromptManager` inserts profile data through the `{user_profile}` placeholder and formats behaviour settings through `{behavior_instructions}`; neither rewrites `prompts/system_prompt.txt`.

---

## Privacy

- **Conversations stay local.** Chat sessions, personal profiles and the optional speech cache live on your machine. The default setup sends prompts and messages only to the local Ollama HTTP service at `127.0.0.1:11434`, and configures no hosted LLM API.
- **No persistent chat history store.** The active conversation is held in process memory for the running session only.
- **Git-ignored local configuration.** Personal preferences, persona choices, behaviour overrides, speech-cache files and profile data live under `config/local/` and are not committed.
- **Local diagnostic logging.** Logs are written under `logs/` and record timing, event information, error details and some tool-call metadata. Review local logs before sharing them.
- **Setup is not offline.** Dependencies and model assets are downloaded during installation. Local-first inference does not make the installation offline.
- **Bounded tools.** The codebase explorer is read-only and excludes sensitive paths, environment files, binary files, model files, logs and virtual environments. This is a safety boundary for that tool, not a security audit of the machine.

---

## Project status

### Working today

- Desktop GUI (Tkinter) on Windows and Linux, with an OS-native title bar, and an equivalent terminal mode
- Text chat with Markdown replies, streaming, **Regenerate** and **Read aloud**
- Hands-free voice mode with Kokoro speech and interruption controls
- Local Faster-Whisper transcription with rolling drafts and a two-minute limit
- CLI menu: Text Chat, Voice Chat, Settings and Selectors, Exit
- Stop control that cancels the active Ollama stream and Kokoro playback
- Local profiles, eleven behaviour parameters, and response-style presets
- Zoom from 80% to 160% via controls, shortcuts and mouse wheel
- Two bounded local tools: architecture lookup and read-only source explorer

### Planned

| Item | State |
|---|---|
| Persistent conversation history | planned |
| Growth mode and voice barge-in tuning | in progress |
| Desktop GUI in GTK4 | in progress |
| Synthesis engine evaluation | planned |
| Web interface | planned |

Voice interruption is a prototype: acoustic echo cancellation is not implemented, so headphones are recommended.

### Current limitations

- No persistent long-term memory or saved chat transcript across launches.
- A full microphone-to-model-to-speech session should be validated on each target operating system and hardware configuration.
- Barge-in and echo behaviour depend on the microphone, speakers, room and audio drivers.
- Voice mode requires the Kokoro model files, voice data, recognition cache, microphone access and a working audio output device.
- The automated Linux installer targets Debian and Ubuntu, not every distribution.
- The test suites cover units and selected integration and audio behaviour; they do not replace a live full-stack demonstration.
- The language model can produce inaccurate output. A 4-billion-parameter model running locally will sometimes generate plausible but incorrect statements.
- No formal version number is assigned. Interfaces and setup details may change.

---

## Repository structure

```text
RIKO-Major-Project/
├── GUI/
│   └── app.py                 native Tkinter desktop application
├── audio/
│   ├── stt/                   microphone capture, streaming voice input,
│   │                          silence detection, Faster-Whisper transcription,
│   │                          barge-in monitoring
│   ├── kokoro/                Kokoro text-to-speech integration, voice registry
│   └── playback.py            streaming audio output
├── config/
│   ├── defaults/              shared behaviour defaults
│   ├── personas/              bundled personas: assistant, tutor, demo
│   ├── examples/              example and demo profile data
│   └── local/                 private configuration and profiles (Git-ignored)
├── knowledge/
│   └── architecture/          documentation consumed by the architecture lookup
├── prompts/                   system prompt, text style, voice style
├── src/
│   ├── main.py                entry point: terminal menu and GUI launcher
│   ├── conversation_manager.py  conversation state, streaming, tool orchestration
│   ├── ollama_client.py       HTTP client for the local Ollama API
│   ├── prompt_manager.py      assembles prompt, persona, behaviour, profile, style
│   ├── settings_manager.py    reads and writes local persona, TTS and behaviour settings
│   ├── behavior_preferences.py  behaviour parameters and presets
│   ├── user_profile.py        profile loading and context
│   ├── create_user_profile.py   interactive profile wizard
│   ├── modes/                 text chat and voice chat entry points
│   └── tools/                 architecture lookup, read-only source explorer
├── tests/                     unit, integration, speech-recognition and audio tests
├── install.bat   run.bat   run-gui.bat      Windows
├── install.sh    run.sh    run-gui.sh       Debian / Ubuntu
├── requirements.txt
├── LICENSE
└── README.md
```

The virtual environment is `.venv-tts` and is Git-ignored. Kokoro assets live under `models/kokoro/`, which is also Git-ignored.

---

## Licence and third-party notices

The RIKO source code in this repository is released under the **MIT License**. You are free to use, modify, inspect and extend it.

Third-party components retain their own terms:

| Component | Notes |
|---|---|
| `qwen3:4b-instruct` | 4.02B parameter language model, Apache 2.0 |
| Faster-Whisper | Reimplementation of Whisper on CTranslate2, by SYSTRAN |
| Kokoro ONNX | ONNX speech engine and voice assets, by thewh1teagle |
| Ollama | Local model runtime |

Review the upstream model pages and their licences before redistributing the application or its model assets.

---

## Credits

Initiated by **Amartya Singh Namra** (B.Tech, Artificial Intelligence and Machine Learning), with **Priyanshu Tiwari** and **Saurabh Pandey**.

Developed as a major academic project in Artificial Intelligence and Machine Learning, focused on local-first multimodal conversational interfaces.

**Repository:** https://github.com/amartyasinghnamra/RIKO-Major-Project
