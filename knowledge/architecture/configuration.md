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

The architecture knowledge files live under knowledge/architecture/. Their existence does not itself enable retrieval. The Python tool and Ollama tool-call loop must execute and return the requested content.

Never expose private profile contents, secrets, credentials, or unrelated local configuration.
