RIKO capabilities and limitations

Recently tested:
- Python terminal application with text and voice modes.
- Local Ollama language-model communication.
- Streaming conversational text.
- Microphone input and Faster-Whisper transcription.
- Kokoro ONNX speech generation and audio playback.
- Configurable prompts/persona inputs.
- Timestamped diagnostic logging.
- Native Tkinter desktop interface routed through the shared text and voice session functions.
- Personal, bundled Demo, and named local profile selection; supported profile context is inserted through the existing system-prompt template placeholder.
- Profile schema validation and prompt assembly covered by automated unit tests; these do not verify a live microphone session.

Do not assume the following are implemented or guaranteed:
- A GTK4 desktop interface; the current native desktop GUI is built with Tkinter.
- Reliable persistent long-term memory across sessions.
- Perfect speech recognition or barge-in in every language, room, or hardware configuration.
- Zero-latency conversation.
- Guaranteed offline operation of every dependency.
- Support for Linux distributions beyond the installer’s Debian/Ubuntu target.

The design is local-first. Do not claim all processing is local in every configuration without checking runtime settings. State uncertainty rather than inventing details.
