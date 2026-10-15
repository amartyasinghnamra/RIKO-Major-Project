"""Create or edit a private RIKO user profile from the command line."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

from prompt_manager import PromptManager
from settings_manager import SettingsManager
from user_profile import default_profile, normalize_profile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILE_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def ask_text(label: str, default: str) -> str:
    answer = input(f"{label} [{default or 'optional'}]: ").strip()
    if answer == "-":
        return ""
    return answer if answer else default


def ask_list(label: str, defaults: list[str]) -> list[str]:
    print(f"\n{label}")
    print("Current values:", ", ".join(defaults) or "none")
    print("Enter comma-separated values; press Enter to keep them or - to clear.")

    while True:
        answer = input("> ").strip()
        if not answer:
            return defaults.copy()
        if answer == "-":
            return []
        items = [item.strip() for item in answer.split(",")]
        if any(not item for item in items):
            print("Please remove empty items and try again.")
            continue
        return list(dict.fromkeys(items))


def ask_boolean(label: str, default: bool) -> bool:
    default_label = "Y/n" if default else "y/N"
    while True:
        answer = input(f"{label} ({default_label}): ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Enter yes or no.")


def collect_profile(profile: dict) -> dict:
    updated = json.loads(json.dumps(profile))
    identity = updated["identity"]
    learning = updated["learning_preferences"]
    communication = updated["communication_preferences"]

    print("\n=== RIKO Profile Setup ===")
    print("Profile details are saved locally and used only as relevant context.")
    print("Press Enter to keep a value; enter - to clear a text field.\n")

    identity["preferred_name"] = ask_text(
        "Preferred name (optional)", identity["preferred_name"]
    )
    identity["role"] = ask_text(
        "Role or occupation (optional)", identity["role"]
    )
    updated["interests"] = ask_list("Interests", updated["interests"])
    updated["current_goals"] = ask_list("Current goals", updated["current_goals"])
    learning["explanation_style"] = ask_text(
        "Preferred explanation style (optional)",
        learning["explanation_style"],
    )
    learning["pace"] = ask_text(
        "Preferred learning pace (optional)", learning["pace"]
    )
    learning["code_explanations"] = ask_boolean(
        "Include code explanations when discussing code",
        learning["code_explanations"],
    )
    communication["response_language"] = ask_text(
        "Preferred response language (optional)",
        communication["response_language"],
    )

    print("\nPreferred response length:")
    print("1. Concise")
    print("2. Balanced")
    print("3. Detailed")
    length_map = {"1": "concise", "2": "balanced", "3": "detailed"}
    current_length = communication["response_length"]
    current_choice = {value: key for key, value in length_map.items()}.get(
        current_length, "2"
    )
    length_choice = input(f"Choose 1-3 [{current_choice}]: ").strip()
    if length_choice:
        if length_choice not in length_map:
            raise ValueError("Response length must be selected with 1, 2, or 3.")
        communication["response_length"] = length_map[length_choice]
    communication["tone"] = ask_text(
        "Preferred communication tone (optional)", communication["tone"]
    )
    return normalize_profile(updated)


def _load_existing_profile(path: Path) -> dict:
    if not path.is_file():
        return default_profile()
    try:
        return normalize_profile(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Existing profile could not be loaded: {error}")
        print("Starting with an empty profile. The old file remains unchanged until confirmed.")
        return default_profile()


def _save_profile(path: Path, profile: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.stem}-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(profile, temp_file, indent=2, ensure_ascii=False)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def create_profile(profile_id: str = "user", project_root: Path = PROJECT_ROOT) -> bool:
    if not isinstance(profile_id, str) or not PROFILE_ID.fullmatch(profile_id):
        raise ValueError("Profile IDs may use 1–40 letters, numbers, underscores, or hyphens.")

    manager = PromptManager(project_root)
    existing = next(
        (item for item in manager.list_profiles() if item["id"] == profile_id),
        None,
    )
    if existing and existing["source"] == "bundled":
        raise ValueError(
            f"{profile_id!r} is a bundled read-only profile. Choose a new ID "
            "to make your own copy."
        )

    path = manager.profile_storage_path(profile_id)
    current = _load_existing_profile(path)
    profile = collect_profile(current)

    print("\n=== Profile Preview ===")
    print(json.dumps(profile, indent=2, ensure_ascii=False))
    prompt = "Replace this local profile? Type yes to confirm: " if path.exists() else "Save this profile? Type yes to confirm: "
    if input(f"\n{prompt}").strip().lower() != "yes":
        print("Profile not saved; existing files were left unchanged.")
        return False

    _save_profile(path, profile)
    SettingsManager(project_root).set_profile(profile_id)
    print(f"\nProfile saved locally: {path}")
    print(f"Active profile set to: {profile_id}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--id",
        default="user",
        help="profile ID to create or edit (default: user)",
    )
    args = parser.parse_args()
    try:
        create_profile(args.id)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
