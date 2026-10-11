
import unittest

import numpy as np

from audio.stt.silence_detector import SilenceDetector


class SilenceDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = SilenceDetector(
            sample_rate=16000,
            silence_duration=1.0,
            frame_duration=0.02,
            energy_threshold=0.01,
        )

    def test_initial_silence_does_not_finish_utterance(self):
        silence = np.zeros(16000, dtype=np.float32)
        self.assertFalse(self.detector.process(silence))
        self.assertFalse(self.detector.speech_detected)

    def test_speech_followed_by_significant_silence(self):
        speech = np.full(8000, 0.1, dtype=np.float32)
        silence = np.zeros(20000, dtype=np.float32)

        self.assertFalse(self.detector.process(speech))
        self.assertTrue(self.detector.speech_detected)
        self.assertTrue(self.detector.process(silence))

    def test_new_speech_resets_silence_counter(self):
        speech = np.full(8000, 0.1, dtype=np.float32)
        short_silence = np.zeros(6400, dtype=np.float32)

        self.detector.process(speech)
        self.assertFalse(self.detector.process(short_silence))

        self.detector.process(speech)
        self.assertEqual(self.detector.silence_seconds, 0.0)

    def test_reset_starts_new_utterance(self):
        speech = np.full(8000, 0.1, dtype=np.float32)
        silence = np.zeros(20000, dtype=np.float32)

        self.detector.process(speech)
        self.assertTrue(self.detector.process(silence))

        self.detector.reset()
        self.assertFalse(self.detector.speech_detected)
        self.assertEqual(self.detector.silence_seconds, 0.0)

    def test_empty_chunk_is_safe(self):
        self.assertFalse(
            self.detector.process(np.array([], dtype=np.float32))
        )


if __name__ == "__main__":
    unittest.main()
