
import numpy as np
from audio.kokoro.tts import KokoroTTS

tts = KokoroTTS()

text = "That's everything I wanted to say. Talk to you soon!"

print("Generating final response chunk...")
samples, sample_rate = tts.synthesize(text)

audio = np.asarray(samples, dtype=np.float32).reshape(-1)

print(f"Sample rate: {sample_rate} Hz")
print(f"Audio duration: {len(audio) / sample_rate:.3f} seconds")
print(f"Peak amplitude: {np.max(np.abs(audio)):.6f}")

# Inspect the final 100 ms in 10 ms windows.
print("\nFinal 100 ms of generated audio:")

window_size = max(1, sample_rate // 100)
start = max(0, len(audio) - sample_rate // 10)

for pos in range(start, len(audio), window_size):
    window = audio[pos:min(pos + window_size, len(audio))]
    if len(window) == 0:
        continue

    rms = np.sqrt(np.mean(window ** 2))
    offset_ms = pos / sample_rate * 1000

    print(f"{offset_ms:9.1f} ms from start | RMS: {rms:.6f}")

peak = np.max(np.abs(audio))
threshold = peak * 0.01  # 1% of peak amplitude

active = np.flatnonzero(np.abs(audio) > threshold)

if len(active):
    last_active = active[-1]
    trailing_ms = (len(audio) - 1 - last_active) / sample_rate * 1000

    print(f"\nLast sample above threshold: {last_active / sample_rate:.3f} s")
    print(f"Trailing quiet duration: {trailing_ms:.1f} ms")
else:
    print("No samples exceeded the threshold.")
