"""Rolling-window live transcription for RIKO with timestamped debugging."""

from __future__ import annotations

import queue
import threading
from time import monotonic

import numpy as np

from src.debug_logger import log_event, log_exception
from audio.stt.faster_whisper_stt import FasterWhisperSTT
from audio.stt.microphone import MicrophoneCapture
from audio.stt.silence_detector import SilenceDetector


SAMPLE_RATE = 16000


class StreamingVoiceInput:
    """Continuous microphone capture with provisional and final transcripts."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language_mode: str = "auto",
        silence_duration: float = 1.2,
        energy_threshold: float = 0.001,
        speech_timeout: float = 10.0,
        max_record_seconds: float = 20.0,
        update_interval: float = 0.8,
        window_seconds: float = 6.0,
        microphone_device=None,
    ):
        if update_interval <= 0:
            raise ValueError("update_interval must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.silence_duration = silence_duration
        self.energy_threshold = energy_threshold
        self.speech_timeout = speech_timeout
        self.max_record_seconds = max_record_seconds
        self.update_interval = update_interval
        self.window_seconds = window_seconds
        self.microphone_device = microphone_device

        log_event(
            "STT",
            "Initializing transcription engine",
            model=model_size,
            device=device,
            compute_type=compute_type,
        )

        self.stt = FasterWhisperSTT(
            model_size=model_size,
            device=device,
            compute_type=compute_type,
            language_mode=language_mode,
        )

        log_event("STT", "Transcription engine initialized")

    def listen_once(self) -> str:
        """Capture one utterance, display draft transcripts, and finalize it."""

        listen_started = monotonic()

        log_event(
            "STT",
            "Listening session started",
            sample_rate=SAMPLE_RATE,
            energy_threshold=self.energy_threshold,
            silence_duration=self.silence_duration,
        )

        detector = SilenceDetector(
            sample_rate=SAMPLE_RATE,
            silence_duration=self.silence_duration,
            energy_threshold=self.energy_threshold,
        )

        audio_chunks: list[np.ndarray] = []
        partial_queue: queue.Queue = queue.Queue(maxsize=1)
        worker_stop = object()

        speech_started = False
        started = monotonic()
        speech_started_at = None
        last_update = started
        latest_partial = ""
        partial_lock = threading.Lock()

        def transcribe_partials():
            nonlocal latest_partial

            while True:
                item = partial_queue.get()

                try:
                    if item is worker_stop:
                        return

                    partial_started = monotonic()
                    log_event(
                        "STT",
                        "Partial transcription started",
                        audio_seconds=round(len(item) / SAMPLE_RATE, 2),
                    )

                    result = self.stt.transcribe(item)
                    partial_elapsed = monotonic() - partial_started
                    text = result.text.strip()

                    log_event(
                        "STT",
                        "Partial transcription completed",
                        duration_seconds=round(partial_elapsed, 3),
                        has_text=bool(text),
                    )

                    if text:
                        with partial_lock:
                            if text != latest_partial:
                                latest_partial = text
                                print(
                                    f"\r[RIKO live draft] {text}     ",
                                    flush=True,
                                )

                except Exception as exc:
                    log_exception("STT", "Partial transcription failed", exc)
                    print(f"\n[RIKO partial STT warning] {exc}")

                finally:
                    partial_queue.task_done()

        worker = threading.Thread(
            target=transcribe_partials,
            name="riko-live-stt",
            daemon=True,
        )
        worker.start()

        def schedule_partial():
            snapshot = np.concatenate(audio_chunks).astype(
                np.float32,
                copy=False,
            )

            max_samples = int(self.window_seconds * SAMPLE_RATE)
            snapshot = snapshot[-max_samples:].copy()

            try:
                partial_queue.put_nowait(snapshot)

            except queue.Full:
                try:
                    partial_queue.get_nowait()
                    partial_queue.task_done()
                except queue.Empty:
                    pass

                try:
                    partial_queue.put_nowait(snapshot)
                except queue.Full:
                    pass

        print("\n[RIKO] Listening continuously... Speak when ready.")
        log_event("STT", "Microphone capture starting")

        try:
            with MicrophoneCapture(
                sample_rate=SAMPLE_RATE,
                device=self.microphone_device,
            ) as microphone:

                started = monotonic()
                last_update = started
                log_event("STT", "Microphone capture active")

                while True:
                    now = monotonic()
                    elapsed = now - started

                    if not speech_started and elapsed >= self.speech_timeout:
                        log_event(
                            "STT",
                            "Speech timeout",
                            timeout_seconds=self.speech_timeout,
                        )
                        print("\n[RIKO] I didn't hear speech. Try again.")
                        return ""

                    if (
                        speech_started
                        and speech_started_at is not None
                        and now - speech_started_at >= self.max_record_seconds
                    ):
                        log_event(
                            "STT",
                            "Maximum recording duration reached",
                            duration_seconds=round(
                                now - speech_started_at, 2
                            ),
                        )
                        print("\n[RIKO] Maximum recording time reached.")
                        break

                    try:
                        chunk = microphone.read(timeout=0.5)
                    except queue.Empty:
                        continue

                    audio_chunks.append(chunk)
                    finished = detector.process(chunk)

                    if detector.speech_detected and not speech_started:
                        speech_started = True
                        speech_started_at = monotonic()
                        last_update = speech_started_at

                        log_event(
                            "STT",
                            "Speech detected",
                            elapsed_since_listen_seconds=round(
                                speech_started_at - listen_started, 3
                            ),
                        )
                        print("[RIKO] Speech detected...")

                    now = monotonic()

                    if (
                        speech_started
                        and now - last_update >= self.update_interval
                    ):
                        duration = (
                            sum(len(part) for part in audio_chunks)
                            / SAMPLE_RATE
                        )

                        if duration >= 1.5:
                            #schedule_partial()
                            last_update = now

                    if finished:
                        log_event(
                            "STT",
                            "Speech boundary detected",
                            captured_audio_seconds=round(
                                sum(len(part) for part in audio_chunks)
                                / SAMPLE_RATE,
                                2,
                            ),
                        )
                        print("\n[RIKO] Speech boundary detected.")
                        break

        except KeyboardInterrupt:
            log_event("STT", "Listening cancelled by keyboard interrupt")
            print("\n[RIKO] Listening cancelled.")
            raise

        except Exception as exc:
            log_exception("STT", "Microphone capture failed", exc)
            raise

        finally:
            # Drain queued snapshots and stop the partial worker before final STT.
            while True:
                try:
                    pending = partial_queue.get_nowait()
                    partial_queue.task_done()

                    if pending is worker_stop:
                        break

                except queue.Empty:
                    break

            partial_queue.put(worker_stop)
            worker.join()

            log_event(
                "STT",
                "Partial transcription worker stopped",
                listening_elapsed_seconds=round(
                    monotonic() - listen_started, 3
                ),
            )

        if not speech_started or not audio_chunks:
            log_event("STT", "No speech captured")
            return ""

        audio = np.concatenate(audio_chunks).astype(
            np.float32,
            copy=False,
        )

        if not np.all(np.isfinite(audio)):
            log_event("STT", "Invalid audio values detected")
            print("[RIKO] Invalid audio.")
            return ""

        rms = float(np.sqrt(np.mean(audio * audio)))

        if rms < 1e-5:
            log_event("STT", "Recording was silent", rms=rms)
            print("[RIKO] Recording was silent.")
            return ""

        audio_seconds = len(audio) / SAMPLE_RATE

        log_event(
            "STT",
            "Final transcription started",
            audio_seconds=round(audio_seconds, 2),
            rms=round(rms, 6),
        )

        final_started = monotonic()

        try:
            result = self.stt.transcribe(audio)
        except Exception as exc:
            log_exception("STT", "Final transcription failed", exc)
            raise

        final_elapsed = monotonic() - final_started
        transcript = result.text.strip()

        log_event(
            "STT",
            "Final transcription completed",
            duration_seconds=round(final_elapsed, 3),
            audio_seconds=round(audio_seconds, 2),
            real_time_factor=round(
                final_elapsed / audio_seconds, 3
            ) if audio_seconds else None,
            has_text=bool(transcript),
            language=getattr(result, "language", None),
        )

        if transcript:
            print(f"[You said] {transcript}")
        else:
            log_event("STT", "Final transcription was empty")
            print("[RIKO] I couldn't understand that.")

        log_event(
            "STT",
            "Listening session completed",
            total_seconds=round(monotonic() - listen_started, 3),
        )

        return transcript