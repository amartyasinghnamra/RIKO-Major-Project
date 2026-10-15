"""Validation and prompt formatting for RIKO's adjustable behavior controls."""

from __future__ import annotations

import json
import math
import re
from typing import Any


BEHAVIOR_CONTROLS = (
    ("cuteness", "personality", "Cuteness"),
    ("playfulness", "personality", "Playfulness"),
    ("teasing", "personality", "Teasing"),
    ("warmth", "personality", "Affection / warmth"),
    ("energy", "personality", "Energy"),
    ("talkativeness", "personality", "Talkativeness"),
    ("spontaneity", "conversation", "Spontaneity"),
    ("initiative", "conversation", "Conversation initiative"),
    ("emotional_awareness", "conversation", "Emotional awareness"),
    ("reassurance", "conversation", "Reassurance"),
)

RESPONSE_STYLE_OPTIONS = {
    "Balanced": "natural, attentive, honest, and clear; concise for simple exchanges",
    "Concise": "concise and direct while retaining the detail needed to answer well",
    "Detailed": "thorough and explanatory when useful, without repeating points",
    "Structured": "well-organized with clear steps or sections when the topic benefits",
    "Expressive": "warm, lively, and conversational while staying grounded and clear",
    "Study companion": "patient, structured, and learning-focused; explain ideas step by step when useful",
}

_LEVEL_DESCRIPTIONS = (
    (2, "very subtle"),
    (4, "subtle"),
    (6, "balanced"),
    (8, "noticeable"),
    (10, "strong"),
)
_STYLE_CLEANER = re.compile(r"[\x00-\x1f\x7f]")


def validate_behavior_preferences(values: Any) -> dict[str, Any]:
    """Validate the complete local behavior-preference payload."""
    if not isinstance(values, dict):
        raise TypeError("Behavior preferences must be a dictionary.")

    result: dict[str, Any] = {"personality": {}, "conversation": {}}
    for key, section, _label in BEHAVIOR_CONTROLS:
        if key not in values:
            raise ValueError(f"Missing behavior preference: {key}")
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a whole number from 0 to 10.")
        if not math.isfinite(float(value)) or int(value) != value or not 0 <= value <= 10:
            raise ValueError(f"{key} must be a whole number from 0 to 10.")
        result[section][key] = int(value)

    style = values.get("response_style")
    if not isinstance(style, str):
        raise ValueError("response_style must be text.")
    if _STYLE_CLEANER.search(style):
        raise ValueError("response_style must be a single line without control characters.")
    style = style.strip()
    if not style or len(style) > 160:
        raise ValueError("response_style must contain 1 to 160 characters.")
    result["conversation"]["response_style"] = style
    return result


def extract_behavior_preferences(behavior: dict[str, Any]) -> dict[str, Any]:
    """Flatten effective behavior settings into the GUI's editable values."""
    personality = behavior.get("personality", {})
    conversation = behavior.get("conversation", {})
    if not isinstance(personality, dict):
        personality = {}
    if not isinstance(conversation, dict):
        conversation = {}

    values: dict[str, Any] = {}
    for key, section, _label in BEHAVIOR_CONTROLS:
        source = personality if section == "personality" else conversation
        fallback = 5
        value = source.get(key, fallback)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            value = fallback
        values[key] = max(0, min(10, int(value)))

    style = conversation.get("response_style", RESPONSE_STYLE_OPTIONS["Balanced"])
    if not isinstance(style, str) or not style.strip():
        style = RESPONSE_STYLE_OPTIONS["Balanced"]
    values["response_style"] = style.strip()[:160]
    return values


def format_behavior_instructions(behavior: dict[str, Any]) -> str:
    """Turn numeric preferences into short, interpretable model guidance."""
    values = extract_behavior_preferences(behavior)
    lines = [
        "These are soft style preferences on a scale from 0 (very subtle) to 10 (strong).",
    ]
    for key, _section, label in BEHAVIOR_CONTROLS:
        value = values[key]
        if value == 0:
            description = "keep this quality minimal"
        else:
            level = next((name for maximum, name in _LEVEL_DESCRIPTIONS if value <= maximum), "strong")
            description = f"use a {level} amount when it suits the conversation"
        lines.append(f"- {label}: {value}/10 — {description}.")

    lines.append(
        "- Response style preference: "
        + json.dumps(values["response_style"], ensure_ascii=False)
        + "."
    )
    lines.extend(
        (
            "- Keep teasing gentle and never demeaning; affection stays non-romantic unless the user clearly asks for a different fictional tone.",
            "- Notice emotional cues without diagnosing the user; keep reassurance honest and never promise outcomes.",
            "- Follow the user's present request and tone first. These preferences never require extra questions, forced cuteness, or a playful tone during serious moments.",
        )
    )

    recognized = {
        "personality": {key for key, section, _label in BEHAVIOR_CONTROLS if section == "personality"},
        "conversation": {key for key, section, _label in BEHAVIOR_CONTROLS if section == "conversation"}
        | {"response_style"},
    }
    additional = {}
    for section, value in behavior.items():
        if section in recognized and isinstance(value, dict):
            extras = {
                key: item for key, item in value.items()
                if key not in recognized[section]
            }
            if extras:
                additional[section] = extras
        elif section not in recognized:
            additional[section] = value
    if additional:
        lines.append(
            "- Additional persona configuration (style context only):\n"
            + json.dumps(additional, indent=2, ensure_ascii=False)
        )
    return "\n".join(lines)
