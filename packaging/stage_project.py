#!/usr/bin/env python3
"""Create a clean source payload for native RIKO setup packages."""

from __future__ import annotations

import argparse
import fnmatch
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    "LICENSE",
    "README.md",
    "requirements.txt",
    "install.bat",
    "install.sh",
    "run.bat",
    "run.sh",
    "run-gui.bat",
    "run-gui.sh",
)
SOURCE_DIRS = ("audio", "config", "GUI", "knowledge", "models", "prompts", "src")
IGNORED_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".venv",
    ".venv-tts",
    ".git",
    "logs",
}
IGNORED_PATTERNS = ("*.bak", "*.pyc", "*.part", "*.npz", "*.onnx", "*.bin")


def _ignore(directory: str, names: list[str]) -> set[str]:
    path = Path(directory).resolve()
    ignored = set(names).intersection(IGNORED_NAMES)
    ignored.update(
        name
        for name in names
        if any(fnmatch.fnmatch(name, pattern) for pattern in IGNORED_PATTERNS)
    )
    if path == PROJECT_ROOT / "config":
        ignored.add("local")
    return ignored


def stage_project(destination: Path) -> None:
    destination = destination.resolve()
    if destination == PROJECT_ROOT:
        raise ValueError("The staging destination cannot be the project root.")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Staging destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    for relative in ROOT_FILES:
        source = PROJECT_ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(f"Required package input is missing: {source}")
        shutil.copy2(source, destination / relative)

    linux_setup = PROJECT_ROOT / "packaging" / "linux" / "setup-and-run.sh"
    if not linux_setup.is_file():
        raise FileNotFoundError(f"Required package input is missing: {linux_setup}")
    shutil.copy2(linux_setup, destination / "riko-setup-and-run.sh")

    for relative in SOURCE_DIRS:
        source = PROJECT_ROOT / relative
        if not source.is_dir():
            raise FileNotFoundError(f"Required package directory is missing: {source}")
        shutil.copytree(
            source,
            destination / relative,
            ignore=_ignore,
            dirs_exist_ok=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    stage_project(arguments.destination)
    print(f"Staged RIKO package payload at {arguments.destination.resolve()}")


if __name__ == "__main__":
    main()
