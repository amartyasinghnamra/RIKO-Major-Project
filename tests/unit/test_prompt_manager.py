import json
import tempfile
from pathlib import Path

from prompt_manager import PromptManager


def test_build_prompt_uses_persona_profile_and_behavior():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        (root / "config" / "defaults").mkdir(parents=True)
        (root / "config" / "examples").mkdir(parents=True)
        (root / "config" / "personas").mkdir(parents=True)
        (root / "prompts").mkdir(parents=True)

        (root / "config" / "defaults" / "behavior.default.json").write_text(
            json.dumps({"personality": {"warmth": 5}}),
            encoding="utf-8",
        )

        (root / "config" / "personas" / "assistant.json").write_text(
            json.dumps({
                "name": "Riko",
                "description": "Neutral assistant.",
                "greeting": "Hello!",
                "behavior": {},
            }),
            encoding="utf-8",
        )

        (root / "config" / "examples" / "user_profile.example.json").write_text(
            json.dumps({
                "identity": {"preferred_name": "User"},
                "interests": ["Programming"],
            }),
            encoding="utf-8",
        )

        (root / "prompts" / "system_prompt.txt").write_text(
            "You are {persona_name}. "
            "Persona: {persona_description}. "
            "Profile: {user_profile}. "
            "Behaviour: {behavior_instructions}",
            encoding="utf-8",
        )

        prompt = PromptManager(root).build_prompt()

        assert "You are Riko" in prompt
        assert "Neutral assistant." in prompt
        assert "User" in prompt
        assert "warmth" in prompt

        for placeholder in (
            "{user_profile}",
            "{behavior_instructions}",
            "{persona_name}",
            "{persona_description}",
        ):
            assert placeholder not in prompt, (
                f"Unfilled placeholder: {placeholder}"
            )
