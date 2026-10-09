
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = (
    PROJECT_ROOT / "config" / "local" / "user_profile.json"
)


DEFAULT_PROFILE = {
    "identity": {
        "preferred_name": "Amartya",
        "role": "B.Tech AIML student"
    },
    "interests": [
        "Artificial Intelligence",
        "Machine Learning",
        "Linux",
        "Operating Systems",
        "Anime",
        "AI companion development"
    ],
    "current_goals": [
        "Prepare for GATE DA 2027",
        "Develop the RIKO major project",
        "Improve programming fundamentals"
    ],
    "learning_preferences": {
        "explanation_style": "step-by-step, beginner-friendly",
        "pace": "slow and understandable",
        "code_explanations": True
    }
}


def ask_text(label, default):
    while True:
        answer = input(f"{label} [{default}]: ").strip()

        if answer:
            return answer

        if default.strip():
            return default

        print("This field cannot be empty.")


def ask_list(label, defaults):
    print(f"\n{label}")
    print("Current values:", ", ".join(defaults))
    print("Enter comma-separated values.")
    print("Press Enter to keep the current values.")

    while True:
        answer = input("> ").strip()

        if not answer:
            return defaults.copy()

        items = [item.strip() for item in answer.split(",")]

        if any(not item for item in items):
            print("Please remove empty items and try again.")
            continue

        # Remove duplicates while preserving the original order.
        return list(dict.fromkeys(items))


def validate_profile(profile):
    identity = profile.get("identity", {})
    preferences = profile.get("learning_preferences", {})

    if not isinstance(identity.get("preferred_name"), str):
        raise ValueError("Preferred name must be text.")

    if not identity["preferred_name"].strip():
        raise ValueError("Preferred name cannot be empty.")

    if not isinstance(identity.get("role"), str):
        raise ValueError("Role must be text.")

    if not identity["role"].strip():
        raise ValueError("Role cannot be empty.")

    for field in ("interests", "current_goals"):
        values = profile.get(field)

        if not isinstance(values, list):
            raise ValueError(f"{field} must be a list.")

        if any(
            not isinstance(value, str) or not value.strip()
            for value in values
        ):
            raise ValueError(f"{field} contains an invalid item.")

    if not isinstance(preferences.get("code_explanations"), bool):
        raise ValueError("code_explanations must be true or false.")

    return profile


def create_profile():
    profile = json.loads(json.dumps(DEFAULT_PROFILE))

    if PROFILE_PATH.exists():
        try:
            existing_profile = json.loads(
                PROFILE_PATH.read_text(encoding="utf-8")
            )
            validate_profile(existing_profile)
            profile = existing_profile
            print("Loaded your existing profile as the starting point.")
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            print(f"Existing profile could not be loaded: {error}")
            print("Starting with the default profile instead.")

    print("\n=== RIKO User Profile Setup ===")
    print("Press Enter to keep the displayed values.\n")

    profile["identity"]["preferred_name"] = ask_text(
        "Preferred name",
        profile["identity"]["preferred_name"]
    )

    profile["identity"]["role"] = ask_text(
        "Role or occupation",
        profile["identity"]["role"]
    )

    profile["interests"] = ask_list(
        "Interests",
        profile["interests"]
    )

    profile["current_goals"] = ask_list(
        "Current goals",
        profile["current_goals"]
    )

    try:
        validate_profile(profile)
    except ValueError as error:
        print(f"Profile validation failed: {error}")
        print("Your existing profile has not been changed.")
        return

    print("\n=== Profile Preview ===")
    print(json.dumps(profile, indent=4, ensure_ascii=False))

    if PROFILE_PATH.exists():
        confirm = input(
            "\nReplace the existing profile? Type yes to confirm: "
        ).strip().lower()
    else:
        confirm = input(
            "\nSave this profile? Type yes to confirm: "
        ).strip().lower()

    if confirm != "yes":
        print("Profile not saved.")
        return

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = PROFILE_PATH.with_suffix(".tmp")

    temporary_path.write_text(
        json.dumps(profile, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )

    temporary_path.replace(PROFILE_PATH)

    print(f"\nProfile saved to: {PROFILE_PATH}")


if __name__ == "__main__":
    create_profile()
