RIKO voice pipeline

1. MicrophoneCapture captures audio.
2. StreamingVoiceInput manages listening and speech boundaries.
3. Faster-Whisper transcribes the captured speech.
4. Voice chat passes the transcript into conversation processing.
5. OllamaClient communicates with the configured local language model.
6. Response text is streamed.
7. KokoroTTS chunks the incoming text and synthesizes audio.
8. AudioPlayback plays the generated audio.
9. The application returns to listening for the next turn.

Relevant modules:
- src/modes/voice_chat.py: coordinates the voice loop.
- audio/stt/streaming_voice_input.py: microphone listening and transcription workflow.
- audio/kokoro/tts.py: streaming speech synthesis and audio delivery.
- src/conversation_manager.py: conversation orchestration.
- src/ollama_client.py: Ollama communication.

STT, LLM generation, and TTS are distinct stages. Do not claim natural interruption, full-duplex conversation, or zero latency unless separately verified. Timing depends on input length, model loading, CPU load, generation, synthesis, and playback.
