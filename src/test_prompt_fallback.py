
import json
import tempfile
from pathlib import Path

from prompt_manager import PromptManager


def test_missing_profile_uses_example():
    project_root = Path(__file__).resolve().parent.parent

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        config_dir = temp_root / "config"

        (config_dir / "defaults").mkdir(parents=True)
        (config_dir / "examples").mkdir(parents=True)
        (config_dir / "local").mkdir(parents=True)
        (temp_root / "prompts").mkdir()

        default_behavior = {
            "tone": "friendly"
        }
        example_profile = {
            "identity": {
                "preferred_name": "ExampleUser",
                "role": "Student"
            },
            "interests": ["Programming"],
            "current_goals": ["Learn"],
            "learning_preferences": {
                "explanation_style": "step-by-step",
                "pace": "adapt to the user's needs",
                "code_explanations": True
            }
        }

        (config_dir / "defaults" / "behavior.default.json").write_text(
            json.dumps(default_behavior), encoding="utf-8"
        )
        (config_dir / "examples" / "user_profile.example.json").write_text(
            json.dumps(example_profile), encoding="utf-8"
        )
        (temp_root / "prompts" / "system_prompt.txt").write_text(
            "Profile: {user_profile}\nBehavior: {behavior_instructions}",
            encoding="utf-8"
        )

        manager = PromptManager(temp_root)
        prompt = manager.build_prompt()

        assert "ExampleUser" in prompt
        assert "friendly" in prompt
        assert not (config_dir / "local" / "user_profile.json").exists()

    print("Prompt fallback test passed!")


if __name__ == "__main__":
    test_missing_profile_uses_example()
