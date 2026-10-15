"""Profile selection, validation, persistence, and system-prompt coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from create_user_profile import create_profile
from prompt_manager import PromptManager
from settings_manager import SettingsManager
from user_profile import default_profile, normalize_profile


def make_project(root: Path) -> Path:
    (root / "config" / "defaults").mkdir(parents=True)
    (root / "config" / "examples" / "profiles").mkdir(parents=True)
    (root / "config" / "personas").mkdir(parents=True)
    (root / "prompts").mkdir(parents=True)
    (root / "config" / "defaults" / "behavior.default.json").write_text(
        "{}", encoding="utf-8"
    )
    (root / "config" / "personas" / "assistant.json").write_text(
        json.dumps({"name": "Riko", "description": "Helpful companion."}),
        encoding="utf-8",
    )
    (root / "config" / "examples" / "user_profile.example.json").write_text(
        json.dumps(default_profile()), encoding="utf-8"
    )
    (root / "config" / "examples" / "profiles" / "demo.json").write_text(
        json.dumps(
            {
                "_meta": {"name": "Demo learner", "description": "Fictional."},
                "identity": {"preferred_name": "Alex", "role": "Learner"},
                "interests": ["Python"],
                "current_goals": ["Build a project"],
                "learning_preferences": {
                    "explanation_style": "small examples",
                    "pace": "steady",
                    "code_explanations": True,
                },
                "communication_preferences": {
                    "response_language": "English",
                    "response_length": "balanced",
                    "tone": "direct",
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "prompts" / "system_prompt.txt").write_text(
        "Core {persona_name}. Profile context: {user_profile}. "
        "Behavior: {behavior_instructions}.",
        encoding="utf-8",
    )
    return root


def test_demo_and_personal_profiles_are_added_through_prompt_placeholder(tmp_path):
    root = make_project(tmp_path)
    manager = PromptManager(root)

    assert {item["id"] for item in manager.list_profiles()} == {"user", "demo"}
    personal_path = manager.profile_storage_path("user")
    personal_path.parent.mkdir(parents=True, exist_ok=True)
    personal_path.write_text(
        json.dumps(
            {
                "identity": {"preferred_name": "Casey", "role": "Designer"},
                "interests": ["Typography"],
            }
        ),
        encoding="utf-8",
    )

    personal_prompt = manager.build_prompt()
    assert "Casey" in personal_prompt
    assert "Typography" in personal_prompt
    assert "schema_version" in personal_prompt

    manager.select_profile("demo")
    demo_prompt = manager.build_prompt(mode="voice")
    assert "Alex" in demo_prompt
    assert "Build a project" in demo_prompt
    assert "Fictional." not in demo_prompt
    assert "_meta" not in demo_prompt


def test_named_local_profile_can_be_selected_and_used_in_prompt(tmp_path):
    root = make_project(tmp_path)
    manager = PromptManager(root)
    local_profile = manager.profile_storage_path("study")
    local_profile.parent.mkdir(parents=True, exist_ok=True)
    local_profile.write_text(
        json.dumps({"identity": {"preferred_name": "Taylor"}}),
        encoding="utf-8",
    )

    assert any(item["id"] == "study" for item in manager.list_profiles())
    manager.select_profile("study")
    assert "Taylor" in manager.build_prompt()
    assert manager.settings.get_profile() == "study"


def test_profile_selection_rejects_unknown_ids_and_path_traversal(tmp_path):
    manager = PromptManager(make_project(tmp_path))

    with pytest.raises(ValueError, match="Unknown profile"):
        manager.select_profile("missing")
    assert manager.load_profile("../secrets")["identity"]["preferred_name"] == ""


def test_profile_schema_validates_limits_and_normalizes_legacy_data():
    profile = normalize_profile(
        {
            "identity": {"preferred_name": "  Morgan  "},
            "interests": ["Python", "python", "Local AI"],
            "private_unknown_field": "not injected into the prompt",
        }
    )

    assert profile["identity"]["preferred_name"] == "Morgan"
    assert profile["interests"] == ["Python", "Local AI"]
    assert "private_unknown_field" not in profile
    with pytest.raises(ValueError, match="characters or shorter"):
        normalize_profile({"identity": {"role": "x" * 121}})
    with pytest.raises(ValueError, match="response_length"):
        normalize_profile(
            {"communication_preferences": {"response_length": "random"}}
        )


def test_bundled_demo_profile_matches_the_supported_schema():
    demo_path = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "examples"
        / "profiles"
        / "demo.json"
    )
    profile = normalize_profile(json.loads(demo_path.read_text(encoding="utf-8")))

    assert profile["identity"]["preferred_name"] == "Alex"
    assert profile["communication_preferences"]["response_length"] == "balanced"


def test_interactive_profile_creation_saves_and_selects_named_profile(
    tmp_path, monkeypatch
):
    root = make_project(tmp_path)
    answers = iter(
        [
            "Sam",
            "Learner",
            "Python, Systems",
            "Build a local assistant",
            "Small examples",
            "Steady",
            "n",
            "English",
            "1",
            "Direct",
            "yes",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    assert create_profile("study", root) is True
    manager = PromptManager(root)
    assert manager.settings.get_profile() == "study"
    assert manager.resolve_profile()["identity"]["preferred_name"] == "Sam"
    assert "Build a local assistant" in manager.build_prompt()


def test_settings_profile_updates_preserve_other_values(tmp_path):
    settings = SettingsManager(tmp_path)
    settings.set_persona("tutor")
    settings.set_tts_speed(1.25)
    settings.set_profile("demo")

    loaded = settings.load()
    assert loaded["persona"] == "tutor"
    assert loaded["tts"]["speed"] == 1.25
    assert loaded["profile"] == "demo"
