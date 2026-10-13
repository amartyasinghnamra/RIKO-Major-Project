"""Central diagnostic logging for RIKO."""

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
_DEVELOPER_MODE = False


def enable_developer_mode() -> None:
    """Enable detailed diagnostic output in this process."""
    global _DEVELOPER_MODE
    with _LOCK:
        _DEVELOPER_MODE = True


def disable_developer_mode() -> None:
    """Disable detailed diagnostic output in this process."""
    global _DEVELOPER_MODE
    with _LOCK:
        _DEVELOPER_MODE = False


def is_developer_mode_enabled() -> bool:
    """Return whether detailed diagnostic output is enabled."""
    with _LOCK:
        return _DEVELOPER_MODE


def log_event(component: str, event: str, **details) -> None:
    """Always write diagnostics to file; print them only in developer mode."""
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
        with _LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(message + "\n")
        if _DEVELOPER_MODE:
            print(message, flush=True)


def log_exception(component: str, event: str, error: Exception) -> None:
    """Persist exception details and keep actionable errors visible."""
    log_event(
        component,
        event,
        error_type=type(error).__name__,
        error=str(error),
    )
    print(
        f"[RIKO {component.upper()} error] {event}: "
        f"{type(error).__name__}: {error}",
        flush=True,
    )
