
from audio.playback import AudioPlayback

player = AudioPlayback()

print("Testing WAV playback...")
player.play_file("kokoro_test.wav")

print("Playback completed successfully.")
