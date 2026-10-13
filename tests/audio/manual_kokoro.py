
from pathlib import Path

import soundfile as sf
from kokoro_onnx import Kokoro

MODEL = Path("models/kokoro/kokoro-v1.0.int8.onnx")
VOICES = Path("models/kokoro/voices-v1.0.bin")
OUTPUT = Path("kokoro_test.wav")

print("Loading Kokoro...")
tts = Kokoro(str(MODEL), str(VOICES))
print("Generating speech...")

text = "Hey! I'm Riko. It's nice to finally talk to you. How has your day been?"

samples, sample_rate = tts.create(
    text,
    voice="af_sarah",
    speed=1.0,
    lang="en-us",
)

sf.write(str(OUTPUT), samples, sample_rate)

print(f"Done! Audio saved to: {OUTPUT.resolve()}")
print(f"Sample rate: {sample_rate} Hz")
