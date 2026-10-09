# RIKO — A Personalized Local AI Companion

RIKO is a modular, local-first AI companion built around personalized conversations, local language-model inference, and a voice interaction pipeline.

The project separates conversational logic, prompt management, and interface-specific behaviour so Text Chat and Voice Chat can evolve independently.

## Current Features

- **Local LLM:** Uses Ollama with `qwen3:4b-instruct`.
- **Streaming responses:** Displays generated responses incrementally.
- **Text Chat:** Runs as a separate mode without initializing the voice engine.
- **Voice Chat:** Integrates Kokoro ONNX text-to-speech with audio playback.
- **Prompt management:** Builds prompts using persona, user-profile, behaviour, and mode-specific style configuration.
- **Conversation management:** Maintains conversation history during a session.
- **Configuration fallback:** Supports example profile configuration when local profile data is unavailable.
- **Privacy-conscious configuration:** Keeps private local settings out of version control.

## Architecture

```text
RIKO_PROJECT/
├── audio/
│   ├── playback.py
│   └── kokoro/
│       └── tts.py
├── config/
│   ├── defaults/
│   ├── examples/
│   ├── local/
│   └── personas/
├── models/
│   └── kokoro/
│       ├── kokoro-v1.0.int8.onnx
│       └── voices-v1.0.bin
├── prompts/
│   ├── system_prompt.txt
│   ├── text_style.txt
│   └── voice_style.txt
├── src/
│   ├── modes/
│   │   ├── text_chat.py
│   │   └── voice_chat.py
│   ├── conversation_manager.py
│   ├── create_user_profile.py
│   ├── main.py
│   ├── ollama_client.py
│   ├── prompt_manager.py
│   └── test_*.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Requirements

- Python 3.14.8 — current development environment
- Ollama installed and running locally
- `qwen3:4b-instruct` available in Ollama
- Python packages listed in `requirements.txt`
- Kokoro ONNX model and voice files for Voice Chat
- A working audio output device for Voice Chat

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/amartyasinghnamra/RIKO-Major-Project.git
cd RIKO-Major-Project
```

### 2. Create a Python environment

On Windows:

```cmd
python -m venv .venv-tts
.venv-tts\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Ollama

Install Ollama, start its local service, and pull the model:

```bash
ollama pull qwen3:4b-instruct
```

### 4. Configure Kokoro

Place the required Kokoro ONNX model and voice file in:

```text
models/kokoro/
```

The expected filenames are:

```text
kokoro-v1.0.int8.onnx
voices-v1.0.bin
```

Model weights are not committed to this repository. Obtain them separately from a source you trust and follow the applicable model licence.

### 5. Run RIKO

From the project root:

```cmd
python src\main.py
```

Select one of the available modes:

- `1` — Text Chat
- `2` — Voice Chat
- `0` — Exit

## Testing

Run the core test scripts from the project root:

```cmd
python -m compileall -q src audio
python src\test_persona_manager.py
python src\test_prompt_manager.py
python src\test_conversation_manager.py
python src\test_prompt_fallback.py
python src\test_ollama_client.py
```

The Ollama client test may require the local Ollama service and model.

Additional audio test scripts are available for manual testing of synthesis and playback. Some audio tests require the local Kokoro model files and an audio output device.

## Privacy

RIKO is designed to keep local profile configuration and private behaviour overrides on the user's machine. Do not commit credentials, `.env` files, private profiles, or personal configuration.

Local-first inference does not imply that every optional integration is offline: verify the behaviour of any external service before using it with private data.

## Project Status

RIKO is under active development. Text Chat, the conversational core, and the Kokoro-based Voice Chat implementation are present in the current development version. Further work includes improving conversational behaviour, testing, modularity, and the overall user experience.

## License

RIKO is licensed under the MIT License. See [LICENSE](LICENSE) for details.