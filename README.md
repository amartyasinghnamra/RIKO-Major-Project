\# RIKO â€” A Personalized Local AI Companion



RIKO is a modular, local-first AI companion project focused on personalized conversations, local language-model inference, and a future voice-interaction pipeline.



The project is being developed with an emphasis on modularity, configurable conversational behaviour, and user privacy.



\## Project Goals



\- Run language-model inference locally using Ollama.

\- Support streaming conversational responses.

\- Separate conversation management, model communication, and prompt management.

\- Allow configurable assistant behaviour and personalized user profiles.

\- Develop speech recognition and voice synthesis modules as future components.



\## Current Features



\- \*\*Local LLM integration:\*\* Communicates with Ollama using the configured `qwen3:4b-instruct` model.

\- \*\*Streaming chat:\*\* Processes responses incrementally.

\- \*\*Conversation management:\*\* Organizes conversation flow and history.

\- \*\*Prompt management:\*\* Loads system prompts, default behaviour, and user-profile configuration.

\- \*\*Configuration fallback:\*\* Uses example profile configuration when a local profile is unavailable.

\- \*\*Local profile creation:\*\* Provides an interactive utility for creating a personal user profile.

\- \*\*Tests:\*\* Includes test scripts for the main conversation, prompt-management, and Ollama-client components.



\## Architecture



```text

RIKO\_PROJECT/

â”œâ”€â”€ config/

â”‚   â”œâ”€â”€ defaults/

â”‚   â”‚   â””â”€â”€ behavior.default.json

â”‚   â””â”€â”€ examples/

â”‚       â””â”€â”€ user\_profile.example.json

â”œâ”€â”€ prompts/

â”‚   â””â”€â”€ system\_prompt.txt

â”œâ”€â”€ src/

â”‚   â”œâ”€â”€ main.py

â”‚   â”œâ”€â”€ conversation\_manager.py

â”‚   â”œâ”€â”€ ollama\_client.py

â”‚   â”œâ”€â”€ prompt\_manager.py

â”‚   â”œâ”€â”€ create\_user\_profile.py

â”‚   â””â”€â”€ test\_\*.py

â”œâ”€â”€ .gitignore

â””â”€â”€ README.md

```



The local configuration directory may contain personal settings and is intentionally excluded from version control.



\## Requirements



\- Python 3

\- Ollama installed and running

\- The `qwen3:4b-instruct` model available locally



\## Getting Started



\### 1. Clone the repository



```bash

git clone https://github.com/amartyasinghnamra/RIKO-Major-Project.git

cd RIKO-Major-Project

```



\### 2. Start Ollama



Make sure Ollama is running and the configured model is available:



```bash

ollama pull qwen3:4b-instruct

ollama run qwen3:4b-instruct

```



You can exit the interactive model session after confirming that it works.



\### 3. Run RIKO



From the project root, run:



```bash

python src/main.py

```



If your environment uses the `python3` command instead, use:



```bash

python3 src/main.py

```



\## Configuration and Privacy



RIKO supports default configuration and local personalization.



\- `config/defaults/` contains default behaviour settings.

\- `config/examples/` contains example configuration files.

\- `config/local/` is reserved for private, machine-specific configuration.



Personal profiles, local behaviour overrides, credentials, and other private settings should not be committed to Git.



\## Testing



Run the available test scripts from the project root:



```bash

python src/test\_prompt\_manager.py

python src/test\_conversation\_manager.py

python src/test\_prompt\_fallback.py

python src/test\_ollama\_client.py

```



The Ollama-client test requires a working local Ollama service and the configured model.



\## Roadmap



Planned development includes:



\- Speech-to-text integration using Faster-Whisper.

\- Voice synthesis integration using GPT-SoVITS.

\- A modular pipeline connecting conversation generation, text chunking, and speech synthesis.

\- Further improvements to personalization and conversational behaviour.

\- Testing and performance evaluation of the integrated voice pipeline.



These voice capabilities are planned components and should not be considered integrated features until implementation and testing are complete.



\## Project Status



RIKO is under active development. The current focus is establishing a clean, modular conversational core before expanding into voice interaction.


## License

RIKO is licensed under the [MIT License](LICENSE).
