"""Tests for persona loading, merging, and fallback behaviour."""

import json
import tempfile
from pathlib import Path

from prompt_manager import PromptManager, deep_merge


def make_project(tmp):
    root = Path(tmp)

    (root / "config" / "defaults").mkdir(parents=True)
    (root / "config" / "personas").mkdir(parents=True)
    (root / "config" / "examples").mkdir(parents=True)
    (root / "config" / "local").mkdir(parents=True)
    (root / "prompts").mkdir(parents=True)

    (root / "config" / "defaults" / "behavior.default.json").write_text(
        json.dumps(
            {
                "personality": {"warmth": 5, "playfulness": 4},
                "boundaries": {"allow_serious_mode": True},
            }
        ),
        encoding="utf-8",
    )

    (root / "config" / "personas" / "assistant.json").write_text(
        json.dumps(
            {
                "name": "Riko",
                "description": "Neutral assistant.",
                "greeting": "Hello!",
                "behavior": {"personality": {"playfulness": 2}},
            }
        ),
        encoding="utf-8",
    )

    (root / "config" / "examples" / "user_profile.example.json").write_text(
        json.dumps({"identity": {"preferred_name": "User"}}),
        encoding="utf-8",
    )

    (root / "prompts" / "system_prompt.txt").write_text(
        "{persona_name}|{persona_description}|{user_profile}|"
        "{behavior_instructions}",
        encoding="utf-8",
    )

    return root


def test_deep_merge_is_recursive():
    base = {"a": {"x": 1, "y": 2}, "b": 1}
    override = {"a": {"y": 9}, "c": 3}
    assert deep_merge(base, override) == {
        "a": {"x": 1, "y": 9},
        "b": 1,
        "c": 3,
    }
    print("test_deep_merge_is_recursive: ok")


def test_default_persona_is_assistant():
    with tempfile.TemporaryDirectory() as tmp:
        manager = PromptManager(make_project(tmp))
        assert manager.resolve_persona_name() == "assistant"
    print("test_default_persona_is_assistant: ok")


def test_local_config_selects_persona():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_project(tmp)
        (root / "config" / "local" / "config.json").write_text(
            json.dumps({"persona": "tutor"}), encoding="utf-8"
        )
        (root / "config" / "personas" / "tutor.json").write_text(
            json.dumps({"name": "Riko", "description": "Tutor."}),
            encoding="utf-8",
        )
        manager = PromptManager(root)
        assert manager.resolve_persona_name() == "tutor"
        assert manager.get_persona()["description"] == "Tutor."
    print("test_local_config_selects_persona: ok")


def test_missing_persona_falls_back():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_project(tmp)
        (root / "config" / "local" / "config.json").write_text(
            json.dumps({"persona": "does-not-exist"}), encoding="utf-8"
        )
        manager = PromptManager(root)
        assert manager.get_persona()["name"] == "Riko"
    print("test_missing_persona_falls_back: ok")


def test_persona_behavior_overrides_defaults():
    with tempfile.TemporaryDirectory() as tmp:
        manager = PromptManager(make_project(tmp))
        behavior = manager.load_behavior(manager.get_persona())
        assert behavior["personality"]["playfulness"] == 2
        assert behavior["personality"]["warmth"] == 5
    print("test_persona_behavior_overrides_defaults: ok")


def test_prompt_has_no_unfilled_placeholders():
    with tempfile.TemporaryDirectory() as tmp:
        manager = PromptManager(make_project(tmp))
        prompt = manager.build_prompt()
        for placeholder in (
            "{persona_name}",
            "{persona_description}",
            "{user_profile}",
            "{behavior_instructions}",
        ):
            assert placeholder not in prompt
    print("test_prompt_has_no_unfilled_placeholders: ok")


if __name__ == "__main__":
    test_deep_merge_is_recursive()
    test_default_persona_is_assistant()
    test_local_config_selects_persona()
    test_missing_persona_falls_back()
    test_persona_behavior_overrides_defaults()
    test_prompt_has_no_unfilled_placeholders()
    print("\nAll persona tests passed.")
