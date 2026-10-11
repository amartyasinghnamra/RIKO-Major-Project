
import unittest

import numpy as np

from audio.stt.microphone import MicrophoneCapture


class MicrophoneCaptureTests(unittest.TestCase):
    def test_initial_state(self):
        mic = MicrophoneCapture()
        self.assertFalse(mic.running)
        self.assertEqual(mic.dropped_chunks, 0)

    def test_callback_queues_audio(self):
        mic = MicrophoneCapture()
        audio = np.ones((1600, 1), dtype=np.float32)

        mic._audio_callback(audio, 1600, None, None)
        chunk = mic.read(timeout=0.1)

        self.assertEqual(chunk.ndim, 1)
        self.assertEqual(chunk.dtype, np.float32)
        self.assertEqual(chunk.size, 1600)

    def test_stereo_input_is_converted_to_mono(self):
        mic = MicrophoneCapture(channels=2)
        audio = np.ones((1600, 2), dtype=np.float32)

        mic._audio_callback(audio, 1600, None, None)
        chunk = mic.read(timeout=0.1)

        self.assertEqual(chunk.ndim, 1)
        self.assertTrue(np.allclose(chunk, 1.0))

    def test_queue_overflow_does_not_block_callback(self):
        mic = MicrophoneCapture(queue_size=1)
        audio = np.zeros((1600, 1), dtype=np.float32)

        mic._audio_callback(audio, 1600, None, None)
        mic._audio_callback(audio, 1600, None, None)

        self.assertEqual(mic.dropped_chunks, 1)


if __name__ == "__main__":
    unittest.main()
