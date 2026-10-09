# RIKO — A Personalized Local AI Companion

RIKO is a modular, local-first AI companion project focused on personalized conversations, local language-model inference, and a future voice-interaction pipeline.

The project emphasizes modularity, configurable conversational behaviour, privacy, and the ability to personalize the assistant through user-specific profiles.

## Project Goals

- Run language-model inference locally using Ollama.
- Support streaming conversational responses.
- Separate conversation management, model communication, and prompt management.
- Allow configurable assistant behaviour and personalized user profiles.
- Develop speech recognition and voice synthesis as future components.

## Current Features

- **Local LLM integration:** Communicates with Ollama using the `qwen3:4b-instruct` model.
- **Streaming chat:** Processes model responses incrementally.
- **Conversation management:** Organizes conversation flow and history.
- **Prompt management:** Loads system prompts, default behaviour, and user-profile configuration.
- **Pluggable personas:** The assistant's identity and tone come from a
  persona file, not from source code. See *Personas and Privacy* below.
- **Configuration fallback:** Uses example profile configuration when a local profile is unavailable.
- **Local profile creation:** Provides an interactive utility for creating a personal user profile.
- **Test scripts:** Includes tests for conversation management, prompt management, fallback behaviour, and the Ollama client.

## Architecture

```text
RIKO_PROJECT/
├── config/
│   ├── defaults/
│   │   └── behavior.default.json
│   ├── personas/              # Public, neutral example personas
│   │   ├── assistant.json
│   │   └── tutor.json
│   ├── examples/
│   │   └── user_profile.example.json
│   └── local/                 # Private local configuration (gitignored)
├── prompts/
│   └── system_prompt.txt
├── src/
│   ├── main.py
│   ├── conversation_manager.py
│   ├── ollama_client.py
│   ├── prompt_manager.py
│   ├── create_user_profile.py
│   ├── test_conversation_manager.py
│   ├── test_ollama_client.py
│   ├── test_prompt_fallback.py
│   └── test_prompt_manager.py
├── .gitignore
├── LICENSE
└── README.md
```

## Requirements

- Python 3
- [Ollama](https://ollama.com/)
- The `qwen3:4b-instruct` model available locally

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/amartyasinghnamra/RIKO-Major-Project.git
cd RIKO-Major-Project
```

### 2. Download the model

Make sure Ollama is installed and running, then run:

```bash
ollama pull qwen3:4b-instruct
```

You can verify the model with:

```bash
ollama run qwen3:4b-instruct
```

Exit the interactive session after confirming that the model works.

### 3. Run RIKO

From the project root, execute:

```bash
python src/main.py
```

If your system uses `python3`, run:

```bash
python3 src/main.py
```

## Personas and Privacy

RIKO separates the assistant's **persona** from the framework that runs it.

- `config/defaults/behavior.default.json` holds neutral, professional
  defaults and is published as-is.
- `config/personas/` holds public example personas (`assistant`, `tutor`).
  These are deliberately neutral so the repository is safe to share.
- `config/local/personas/` holds private personas. This folder is
  gitignored and is never published.
- `config/local/config.json` selects the active persona with a single
  field:

  ```json
  { "persona": "assistant" }
  ```

Loading order is **defaults -> persona -> local override**, so a local file
always wins. If a persona file is missing or malformed, RIKO falls back to
the bundled `assistant` persona instead of crashing.

The important consequence: the *framework* is the project. Any particular
persona is just configuration, and personal configuration never leaves the
machine.

## Configuration and Privacy

RIKO separates default settings, example profiles, and private local configuration.

- `config/defaults/` contains default behaviour settings.
- `config/examples/` contains example configuration files.
- `config/local/` is reserved for private, machine-specific configuration.
- `prompts/` contains the system prompt.

Personal profiles, local behaviour overrides, credentials, and other private settings should not be committed to version control.

## Testing

Run the available tests from the project root:

```bash
python src/test_persona_manager.py
python src/test_prompt_manager.py
python src/test_conversation_manager.py
python src/test_prompt_fallback.py
python src/test_ollama_client.py
```

The Ollama-client test may require a running local Ollama service and the configured model.

## Roadmap

Planned development includes:

- Speech-to-text integration using Faster-Whisper.
- Voice synthesis integration using GPT-SoVITS.
- A modular pipeline connecting language generation, text chunking, and speech synthesis.
- Improvements to personalization and conversational behaviour.
- A persona-selection interface.
- Testing and performance evaluation of the integrated voice pipeline.

**Note:** Speech recognition and voice synthesis are planned components. They should not be considered integrated features until implementation and testing are complete.

## Project Status

RIKO is under active development. The current focus is on building a clean, modular conversational core with a configurable persona layer before expanding into voice interaction.

## License

RIKO is licensed under the [MIT License](LICENSE).
