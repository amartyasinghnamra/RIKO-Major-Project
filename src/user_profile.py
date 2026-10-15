"""Validation and normalization for RIKO user-profile data."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


PROFILE_SCHEMA_VERSION = 1
MAX_PROFILE_ITEMS = 20
MAX_PROFILE_ITEM_LENGTH = 120

DEFAULT_PROFILE: dict[str, Any] = {
    "schema_version": PROFILE_SCHEMA_VERSION,
    "identity": {
        "preferred_name": "",
        "role": "",
    },
    "interests": [],
    "current_goals": [],
    "learning_preferences": {
        "explanation_style": "step-by-step, beginner-friendly",
        "pace": "adapt to the user's needs",
        "code_explanations": True,
    },
    "communication_preferences": {
        "response_language": "",
        "response_length": "balanced",
        "tone": "",
    },
}

RESPONSE_LENGTHS = {"", "concise", "balanced", "detailed"}


def _text(section: dict[str, Any], key: str, default: str, limit: int) -> str:
    value = section.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text.")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"{key} must be {limit} characters or shorter.")
    return value


def _list(section: dict[str, Any], key: str) -> list[str]:
    values = section.get(key, [])
    if not isinstance(values, list):
        raise ValueError(f"{key} must be a list.")
    if len(values) > MAX_PROFILE_ITEMS:
        raise ValueError(f"Use no more than {MAX_PROFILE_ITEMS} {key.replace('_', ' ')}.")

    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"{key} entries must be text.")
        value = value.strip()
        if not value:
            raise ValueError(f"{key} entries cannot be empty.")
        if len(value) > MAX_PROFILE_ITEM_LENGTH:
            raise ValueError(
                f"Each {key.replace('_', ' ')} entry must be "
                f"{MAX_PROFILE_ITEM_LENGTH} characters or shorter."
            )
        if value.casefold() not in {item.casefold() for item in cleaned}:
            cleaned.append(value)
    return cleaned


def normalize_profile(profile: Any) -> dict[str, Any]:
    """Return the supported profile fields with defaults and validation.

    Older profiles remain compatible: missing optional fields are filled from
    the current defaults, while unsupported keys are kept out of model context.
    """
    if not isinstance(profile, dict):
        raise ValueError("A user profile must be a JSON object.")

    version = profile.get("schema_version", PROFILE_SCHEMA_VERSION)
    if isinstance(version, bool) or version != PROFILE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported profile schema version: {version!r}.")

    identity = profile.get("identity", {})
    learning = profile.get("learning_preferences", {})
    communication = profile.get("communication_preferences", {})
    for name, section in (
        ("identity", identity),
        ("learning_preferences", learning),
        ("communication_preferences", communication),
    ):
        if not isinstance(section, dict):
            raise ValueError(f"{name} must be a JSON object.")

    code_explanations = learning.get(
        "code_explanations",
        DEFAULT_PROFILE["learning_preferences"]["code_explanations"],
    )
    if not isinstance(code_explanations, bool):
        raise ValueError("code_explanations must be true or false.")

    response_length = _text(
        communication,
        "response_length",
        DEFAULT_PROFILE["communication_preferences"]["response_length"],
        20,
    ).lower()
    if response_length not in RESPONSE_LENGTHS:
        raise ValueError(
            "response_length must be concise, balanced, or detailed."
        )

    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "identity": {
            "preferred_name": _text(identity, "preferred_name", "", 80),
            "role": _text(identity, "role", "", 120),
        },
        "interests": _list(profile, "interests"),
        "current_goals": _list(profile, "current_goals"),
        "learning_preferences": {
            "explanation_style": _text(learning, "explanation_style", "", 160),
            "pace": _text(learning, "pace", "", 120),
            "code_explanations": code_explanations,
        },
        "communication_preferences": {
            "response_language": _text(communication, "response_language", "", 80),
            "response_length": response_length,
            "tone": _text(communication, "tone", "", 100),
        },
    }


def default_profile() -> dict[str, Any]:
    """Return a fresh copy suitable for an empty personal profile."""
    return deepcopy(DEFAULT_PROFILE)
