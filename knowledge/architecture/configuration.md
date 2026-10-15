RIKO prompt and configuration

PromptManager builds the system prompt from the core template and applicable configuration.

Known template placeholders:
- {persona_name}: selected persona name.
- {persona_description}: persona description.
- {behavior_instructions}: configured behavioural rules.
- {user_profile}: available user-profile context.

Prompt files:
- prompts/system_prompt.txt: identity, honesty, privacy, and architecture lookup guidance.
- prompts/text_style.txt: text presentation rules.
- prompts/voice_style.txt: spoken-output rules.

Profile selection and data:
- SettingsManager stores the active profile ID in config/local/config.json; it defaults to "user" for existing installations.
- The "text_to_voice_enabled" setting defaults to true and controls whether text-mode assistant replies expose a manual Kokoro Read aloud action. Speech is not automatic.
- Behavior overrides are stored separately in Git-ignored `config/local/behavior.local.json`. The GUI exposes ten 0–10 style controls and response-style presets; these override persona/default values and are formatted into the existing `{behavior_instructions}` prompt field. The core prompt file is not modified.
- Optional Kokoro Read aloud audio caching is disabled by default. When enabled in Preferences, complete phrases are stored in Git-ignored `config/local/audio_cache/`, bounded to 128 MiB, and removable with the clear-cache action. Hands-free Voice mode remains streamed and does not use this cache.
- The private personal profile is config/local/user_profile.json. Additional named local profiles live in config/local/profiles/.
- The fictional bundled Demo profile is config/examples/profiles/demo.json. It is read-only and only enters the prompt when selected.
- PromptManager resolves the selected profile, normalizes supported fields with src/user_profile.py, then supplies the profile JSON through the existing {user_profile} template placeholder.
- src/create_user_profile.py interactively creates or edits the personal profile or a named local profile. The GUI profile page and terminal Settings menu select the active prompt context.
- config/local/ is Git-ignored. Do not expose private profile contents in architecture answers.

The architecture knowledge files live under knowledge/architecture/. Their existence does not itself enable retrieval. The Python tool and Ollama tool-call loop must execute and return the requested content.

Never expose private profile contents, secrets, credentials, or unrelated local configuration.
