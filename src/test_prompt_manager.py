from pathlib import Path

from prompt_manager import PromptManager


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    manager = PromptManager(PROJECT_ROOT)
    prompt = manager.build_prompt()

    # No unfilled placeholders should survive formatting.
    assert "{user_profile}" not in prompt
    assert "{behavior_instructions}" not in prompt
    assert "{persona_name}" not in prompt
    assert "{persona_description}" not in prompt

    # The persona drives the identity line.
    assert "You are Riko" in prompt

    # Neutral defaults are present.
    assert "warmth" in prompt

    # The published example profile is used when no local profile exists.
    assert "User" in prompt

    print("PromptManager test passed!")
    print("\n--- Prompt preview ---\n")
    print(prompt[:1000])


if __name__ == "__main__":
    main()
