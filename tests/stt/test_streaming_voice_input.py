
from audio.stt.streaming_voice_input import StreamingVoiceInput


def main():
    voice = StreamingVoiceInput(
        model_size="small",
        device="cpu",
        compute_type="int8",
        language_mode="auto",
        update_interval=0.8,
        window_seconds=6.0,
    )

    print("Speak naturally. Pause after your sentence.")
    text = voice.listen_once()
    print("\nFINAL TRANSCRIPT:", repr(text))


if __name__ == "__main__":
    main()
