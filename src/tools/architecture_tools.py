"""Safe, allow-listed retrieval from RIKO's architecture knowledge files."""

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge" / "architecture"

TOPIC_FILES = {
    "overview": ("overview.md", "Project purpose and high-level architecture."),
    "models": ("models.json", "LLM, speech recognition, and speech synthesis inventory."),
    "voice_pipeline": ("voice_pipeline.md", "Voice input-to-output flow and audio components."),
    "modules": ("modules.md", "Python modules and their responsibilities."),
    "configuration": ("configuration.md", "Prompt and configuration management."),
    "capabilities": ("capabilities.md", "Documented capabilities and limitations."),
    "development_status": ("development_status.md", "Implemented, in-development, and planned features."),
}

ARCHITECTURE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_architecture_info",
        "description": (
            "Retrieve documented facts about RIKO's own architecture, models, "
            "modules, configuration, voice pipeline, capabilities, or development status. "
            "Use for questions about how RIKO itself is built, not unrelated general questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": list(TOPIC_FILES),
                    "description": "The most relevant knowledge topic.",
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "full"],
                    "description": "Use summary for simple questions and full for detailed questions.",
                },
            },
            "required": ["topic"],
        },
    },
}


def get_architecture_info(topic: str, detail: str = "summary") -> str:
    """Read one allow-listed file. The model cannot supply an arbitrary path."""
    if topic not in TOPIC_FILES:
        return "Topic unavailable. Available topics: " + ", ".join(TOPIC_FILES)

    filename, description = TOPIC_FILES[topic]
    path = KNOWLEDGE_DIR / filename
    if not path.is_file():
        return (
            f"Architecture record '{filename}' is missing from "
            f"knowledge/architecture. Do not guess its contents."
        )

    try:
        raw = path.read_text(encoding="utf-8").strip()
        if filename.endswith(".json"):
            parsed: Any = json.loads(raw)
            return json.dumps(
                parsed,
                ensure_ascii=False,
                indent=2 if detail == "full" else None,
                separators=None if detail == "full" else (",", ":"),
            )

        if detail != "full":
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
            lines = [line for line in lines if not line.startswith("#")]
            raw = "\n".join(lines[:12])

        return (
            f"Topic: {topic}\nSource: knowledge/architecture/{filename}\n"
            f"Purpose: {description}\n\n{raw}"
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return (
            f"Could not read architecture record '{filename}' "
            f"({type(error).__name__}). Do not invent the missing details."
        )


def execute_architecture_tool(name: str, arguments: Any) -> str:
    """Validate and execute a model-requested function call."""
    if name != "get_architecture_info":
        return f"Tool '{name}' is not available."

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return "Invalid tool arguments. Expected a JSON object with a topic."

    if not isinstance(arguments, dict):
        return "Invalid tool arguments. Expected a JSON object with a topic."

    topic = arguments.get("topic", "overview")
    detail = arguments.get("detail", "summary")
    if not isinstance(topic, str) or topic not in TOPIC_FILES:
        return "Invalid topic. Available topics: " + ", ".join(TOPIC_FILES)
    if not isinstance(detail, str) or detail not in {"summary", "full"}:
        detail = "summary"

    return get_architecture_info(topic, detail)


_ARCHITECTURE_TERMS = (
    "riko's architecture", "your architecture", "project architecture",
    "system architecture", "how are you built", "how were you built",
    "how do you work", "how does riko work", "your model", "which model",
    "what model", "models do you use", "llm", "ollama", "qwen",
    "faster-whisper", "whisper model", "kokoro", "tts model", "stt model",
    "speech recognition", "speech synthesis", "voice pipeline", "voice mode",
    "source file", "python module", "modules do", "configuration", "config file",
    "data flow", "components", "implementation", "implemented features",
    "development status", "technical details", "project demo", "offline",
    "persistent memory", "barge-in",
)
_FOLLOWUP_TERMS = (
    "that detail", "more detail", "what about the model", "which version",
    "what version", "explain the pipeline", "explain that", "how exactly",
    "internally", "the components",
)


def should_offer_architecture_tool(
    user_message: str, recent_messages: list[dict] | None = None
) -> bool:
    """Keep the tool schema off ordinary turns; route architecture questions to it."""
    text = (user_message or "").lower().strip()
    if any(term in text for term in _ARCHITECTURE_TERMS):
        return True
    if len(text.split()) <= 12 and any(term in text for term in _FOLLOWUP_TERMS):
        return True
    if len(text.split()) <= 10 and recent_messages:
        context = " ".join(
            str(message.get("content", ""))
            for message in recent_messages[-4:]
            if message.get("role") in {"user", "assistant"}
        ).lower()
        if any(term in context for term in (
            "riko's architecture", "your architecture", "voice pipeline",
            "qwen3:4b-instruct", "faster-whisper", "kokoro onnx",
            "knowledge/architecture", "project architecture",
        )):
            return True
    return False
