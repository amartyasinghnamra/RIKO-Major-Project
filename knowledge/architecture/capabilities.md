RIKO capabilities and limitations

Recently tested:
- Python terminal application with text and voice modes.
- Local Ollama language-model communication.
- Streaming conversational text.
- Microphone input and Faster-Whisper transcription.
- Kokoro ONNX speech generation and audio playback.
- Configurable prompts/persona inputs.
- Timestamped diagnostic logging.

Do not assume the following are implemented:
- GUI.
- Reliable persistent long-term memory across sessions.
- Natural interruption while RIKO is speaking.
- Perfect speech recognition in every language or environment.
- Zero-latency conversation.
- Architecture-document retrieval before the tool-calling loop is installed.
- Guaranteed offline operation of every dependency.

The design is local-first. Do not claim all processing is local in every configuration without checking runtime settings. State uncertainty rather than inventing details.
