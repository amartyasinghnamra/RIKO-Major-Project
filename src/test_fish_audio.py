
import os
import time
from pathlib import Path

from fishaudio import FishAudio
from fishaudio.utils import save

api_key = os.getenv("FISH_API_KEY")
if not api_key:
    raise SystemExit(
        "FISH_API_KEY is missing. Set it in this terminal first."
    )

client = FishAudio(api_key=api_key)

text = (
    "Hello! I'm Riko. "
    "This is my first voice test using Fish Audio."
)

print("Generating speech...")
start = time.perf_counter()

audio = client.tts.convert(
    text=text,
    model="s2.1-pro",
)

output = Path("fish_test.mp3")
save(audio, str(output))

print(f"Audio saved to: {output.resolve()}")
print(f"Generation time: {time.perf_counter() - start:.2f} seconds")
