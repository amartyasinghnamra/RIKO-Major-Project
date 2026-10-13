
from kokoro_onnx import Kokoro
from audio.playback import AudioPlayback

tts = Kokoro(
    "models/kokoro/kokoro-v1.0.int8.onnx",
    "models/kokoro/voices-v1.0.bin",
)

player = AudioPlayback()

print("Generating speech...")
samples, sample_rate = tts.create(
    "Hey! I'm Riko. Let's talk.",
    voice="af_sarah",
    speed=1.0,
    lang="en-us",
)

print("Playing generated samples directly...")
player.play_samples(samples, sample_rate)

print("Direct playback completed.")
