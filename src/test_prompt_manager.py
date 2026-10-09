
from pathlib import Path

from prompt_manager import PromptManager


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    manager = PromptManager(PROJECT_ROOT)
    prompt = manager.build_prompt()

    assert "{user_profile}" not in prompt
    assert "{behavior_instructions}" not in prompt
    assert "Amartya" in prompt
    assert "teasing" in prompt
    assert "You are Riko" in prompt

    print("PromptManager test passed!")
    print("\n--- Prompt preview ---\n")
    print(prompt[:1000])


if __name__ == "__main__":
    main()
