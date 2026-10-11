RIKO development status

Implemented and recently tested:
- Python terminal application.
- Text-chat mode.
- Voice loop using speech recognition, local LLM generation, speech synthesis, and playback.
- Prompt/persona management.
- Streaming response text.
- Debug logging.

Architecture retrieval is a new enhancement. It is not operational until the complete request -> tool execution -> tool result -> final response cycle has been tested.

Remaining validation:
1. Register the architecture tool schema with Ollama.
2. Detect and execute tool calls.
3. Return tool results to the model.
4. Continue generation for a natural-language answer.
5. Test both text and voice modes.
6. Handle missing files, invalid arguments, and tool errors.
