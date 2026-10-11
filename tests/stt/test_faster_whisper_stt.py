"""Offline unit tests for RIKO's Faster-Whisper wrapper; no model download needed."""
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from audio.stt.faster_whisper_stt import FasterWhisperSTT


class FasterWhisperSTTTests(unittest.TestCase):
    def setUp(self):
        self.audio = np.full(16000 * 4, 0.05, dtype=np.float32)
        self.segments = [
            SimpleNamespace(text=" Hello "),
            SimpleNamespace(text="RIKO!"),
            SimpleNamespace(text="   "),
        ]
        self.info = SimpleNamespace(
            language="en", language_probability=0.98, duration=4.0
        )
        self.model = MagicMock()
        self.model.transcribe.return_value = (iter(self.segments), self.info)

    def make_stt(self, **kwargs):
        stt = FasterWhisperSTT(**kwargs)
        stt._model = self.model
        return stt

    def test_defaults_enable_vad_and_disable_previous_text_context(self):
        stt = self.make_stt()
        result = stt.transcribe(self.audio)
        self.assertEqual(result.text, "Hello RIKO!")
        args, options = self.model.transcribe.call_args
        self.assertEqual(args[0].dtype, np.float32)
        self.assertEqual(options["beam_size"], 5)
        self.assertTrue(options["vad_filter"])
        self.assertEqual(options["vad_parameters"]["min_silence_duration_ms"], 500)
        self.assertEqual(options["vad_parameters"]["threshold"], 0.35)
        self.assertEqual(options["vad_parameters"]["speech_pad_ms"], 700)
        self.assertFalse(options["condition_on_previous_text"])
        self.assertEqual(options["initial_prompt"], "RIKO, GATE, Ollama, Kokoro, numpy, Hinglish")

    def test_language_modes(self):
        for mode, expected in (("auto", None), ("hinglish", None), ("english", "en"), ("hindi", "hi")):
            with self.subTest(mode=mode):
                self.model.transcribe.reset_mock()
                stt = self.make_stt(language_mode=mode)
                stt.transcribe(self.audio)
                self.assertEqual(self.model.transcribe.call_args.kwargs["language"], expected)

    def test_explicit_language_overrides_mode(self):
        stt = self.make_stt(language="en", language_mode="hindi")
        stt.transcribe(self.audio)
        self.assertEqual(self.model.transcribe.call_args.kwargs["language"], "en")

    def test_model_is_reused_across_transcriptions(self):
        fake_module = types.ModuleType("faster_whisper")
        fake_module.WhisperModel = MagicMock(return_value=self.model)
        stt = FasterWhisperSTT()
        with patch.dict(sys.modules, {"faster_whisper": fake_module}):
            stt.transcribe(self.audio)
            stt.transcribe(self.audio)
        fake_module.WhisperModel.assert_called_once_with("small", device="cpu", compute_type="int8")
        self.assertEqual(self.model.transcribe.call_count, 2)

    def test_empty_and_silent_audio_do_not_load_model(self):
        stt = FasterWhisperSTT()
        with patch.object(stt, "load") as load:
            self.assertEqual(stt.transcribe(np.array([], dtype=np.float32)).text, "")
            self.assertEqual(stt.transcribe(np.zeros(16000, dtype=np.float32)).text, "")
            load.assert_not_called()

    def test_nonfinite_audio_is_rejected(self):
        stt = self.make_stt()
        with self.assertRaises(ValueError):
            stt.transcribe(np.array([0.1, np.nan], dtype=np.float32))

    def test_vad_can_be_disabled_without_vad_parameters(self):
        stt = self.make_stt(vad_filter=False)
        stt.transcribe(self.audio)
        options = self.model.transcribe.call_args.kwargs
        self.assertFalse(options["vad_filter"])
        self.assertNotIn("vad_parameters", options)


if __name__ == "__main__":
    unittest.main(verbosity=2)
