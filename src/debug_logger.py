"""Timestamped logging for RIKO."""

from datetime import datetime
from pathlib import Path
from threading import Lock
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_LOG_FILE = LOG_DIR / "riko_debug.log"
_LOCK = Lock()
_START_TIME = perf_counter()


def log_event(component: str, event: str, **details) -> None:
    """Print and persist a timestamped diagnostic event."""
    timestamp = datetime.now().astimezone().isoformat(
        sep=" ",
        timespec="milliseconds",
    )
    elapsed = perf_counter() - _START_TIME

    suffix = " ".join(
        f"{key}={value!r}" for key, value in details.items()
    )
    message = (
        f"[{timestamp}] [+{elapsed:.3f}s] "
        f"[{component.upper()}] {event}"
    )

    if suffix:
        message += f" | {suffix}"

    with _LOCK:
        print(message, flush=True)
        with _LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(message + "\n")


def log_exception(component: str, event: str, error: Exception) -> None:
    """Log an exception without hiding its details."""
    log_event(
        component,
        event,
        error_type=type(error).__name__,
        error=str(error),
    )