
from audio.kokoro.tts import KokoroTTS

riko_tts = KokoroTTS(
    voice="af_sarah",
    speed=1.0,
)

print("Test 1: Direct text")
riko_tts.speak_text("Hello! I'm Riko. My voice is working.")

print("Test 2: Multiline text")
riko_tts.speak_multiline(
    "This is the first line.\n"
    "This is the second line."
)

print("Test 3: Streamed text")
tokens = iter([
    "Hey there! ",
    "I'm Riko. ",
    "Let's build something wonderful.",
])
received_text = riko_tts.speak_stream(tokens)

print("Received:", received_text)
print("All tests completed.")
