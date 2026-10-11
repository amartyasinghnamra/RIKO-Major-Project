RIKO is a local-first AI companion and major academic project initiated by Amartya Singh Namra with teammates Priyanshu Tiwari and Saurabh Pandey.

The goal is natural, context-aware text and voice conversation.

Text flow: user text -> conversation and prompt processing -> Ollama language model -> streamed text.

Voice flow: microphone -> speech capture and boundary detection -> speech recognition -> conversation and prompt processing -> Ollama language model -> response text -> text-to-speech -> audio playback.

The Python application coordinates the components. Ollama serves the language model. Speech recognition and speech synthesis are separate from the LLM.

Recent test configuration: Ollama model qwen3:4b-instruct; Faster-Whisper model size small, CPU, int8; Kokoro ONNX voice af_sarah at 24 kHz. Treat these as documented test settings, not a guarantee that every installation has identical settings.

Do not claim unverified features such as a GUI, persistent long-term memory, natural interruption, or guaranteed offline operation.
