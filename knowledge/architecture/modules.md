RIKO modules

- src/main.py: application entry point and mode selection.
- src/prompt_manager.py: builds the system prompt from applicable prompts and configuration.
- src/settings_manager.py: stores the selected persona, profile context, and Kokoro preferences in local configuration.
- src/user_profile.py: validates and normalizes the supported user-profile schema.
- src/create_user_profile.py: interactive setup/editor for the personal profile and named local profiles.
- GUI/app.py: native Tkinter interface for shared text/voice chat and local profile selection/editing.
- src/conversation_manager.py: manages messages and model responses.
- src/ollama_client.py: communicates with Ollama.
- src/modes/voice_chat.py: coordinates voice conversation.
- src/debug_logger.py: records timestamped diagnostic events and exceptions.
- audio/stt/streaming_voice_input.py: microphone listening, speech boundaries, and transcription.
- audio/kokoro/tts.py: streaming text-to-speech and audio delivery.
- prompts/system_prompt.txt: core identity and conversational rules.
- prompts/text_style.txt: text presentation rules.
- prompts/voice_style.txt: spoken-output rules.
- config/examples/profiles/demo.json: fictional, read-only profile preset for demonstrating profile-aware prompt context.

Paths can differ by project version. Verify the active repository before asserting unlisted modules or responsibilities.
