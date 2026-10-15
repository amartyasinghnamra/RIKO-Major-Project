"""Read-only, bounded inspection of RIKO's local source tree."""
from pathlib import Path
import json
import re
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_FILE_BYTES = 200_000
MAX_RESULTS = 30
MAX_SNIPPET_CHARS = 900
SKIP_DIRS = {".git", ".venv", ".venv-tts", "venv", "venv-tts", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache", "models", "logs", "audio", "cleanup_quarantine", "dist", "build"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".wav", ".mp3", ".onnx", ".pt", ".pth", ".safetensors", ".db", ".sqlite", ".zip", ".7z", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
SKIP_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "credentials.json", "secrets.json", "token.json"}
SECRET_WORDS = ("secret", "credential", "password", "token", "private_key")

CODEBASE_TOOL = {
    "type": "function",
    "function": {
        "name": "explore_codebase",
        "description": ("Read-only inspection of the CURRENT LOCAL RIKO project source tree. Use when asked how a specific function/class/module is implemented, where something is defined, how files connect, or to verify behavior from actual source rather than architecture notes. Operations: list_files, search_code, read_file. This tool only reads text files and never executes code."),
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["list_files", "search_code", "read_file"]},
                "query": {"type": "string", "description": "For search_code: text or regex; for list_files: optional repository-relative folder filter (defaults to src; use . for repository root)."},
                "path": {"type": "string", "description": "For read_file: repository-relative path only."},
            },
            "required": ["operation"],
        },
    },
}


def _safe_path(relative: str) -> Path | None:
    if not isinstance(relative, str) or not relative.strip():
        return None
    root = PROJECT_ROOT.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if candidate == root:
        return candidate
    parts = candidate.relative_to(root).parts
    if any(part.lower() in SKIP_DIRS for part in parts):
        return None
    name = candidate.name.lower()
    if name in SKIP_NAMES or any(word in name for word in SECRET_WORDS):
        return None
    if candidate.suffix.lower() in SKIP_SUFFIXES:
        return None
    return candidate


def _eligible(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size <= MAX_FILE_BYTES
    except OSError:
        return False


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT.resolve()).as_posix()


def list_files(query: str = "") -> str:
    # Default to source code; use query="." to inspect the repository root.
    folder = _safe_path(query.strip()) if query.strip() else (PROJECT_ROOT / "src").resolve()
    if folder is None or not folder.is_dir():
        return "Folder unavailable or outside the allowed project tree."
    results = []
    try:
        for path in sorted(folder.rglob("*")):
            safe = _safe_path(_relative(path))
            if safe is None or not _eligible(safe):
                continue
            results.append(_relative(safe))
            if len(results) >= MAX_RESULTS:
                break
    except OSError:
        return "Could not list that project folder."
    suffix = "\n[Results capped at 30 files; narrow the folder query.]" if len(results) >= MAX_RESULTS else ""
    return "Project-relative files:\n" + ("\n".join(results) if results else "(no eligible text files found)") + suffix


def search_code(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        return "Provide a non-empty search query."
    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(query), re.IGNORECASE)
    matches = []
    try:
        for path in sorted(PROJECT_ROOT.rglob("*")):
            safe = _safe_path(_relative(path))
            if safe is None or not _eligible(safe):
                continue
            try:
                lines = safe.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            for number, line in enumerate(lines, 1):
                if pattern.search(line):
                    matches.append(f"{_relative(safe)}:{number}: {line[:MAX_SNIPPET_CHARS]}")
                    if len(matches) >= MAX_RESULTS:
                        return "Code search results:\n" + "\n".join(matches) + "\n[Results capped at 30 matches.]"
    except OSError:
        pass
    return "Code search results:\n" + ("\n".join(matches) if matches else "(no matches found)")


def read_file(relative: str) -> str:
    path = _safe_path(relative)
    if path is None or not _eligible(path):
        return "File unavailable, excluded for safety, too large, or outside the project tree."
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return "File could not be read as UTF-8 text."
    limit = 240
    result = "\n".join(f"{i}: {line}" for i, line in enumerate(lines[:limit], 1))
    if len(lines) > limit:
        result += f"\n[Truncated: showing first {limit} of {len(lines)} lines.]"
    return f"Source: {_relative(path)}\n" + result


def execute_codebase_tool(name: str, arguments: Any) -> str:
    if name != "explore_codebase":
        return f"Tool '{name}' is not available."
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return "Invalid tool arguments. Expected a JSON object."
    if not isinstance(arguments, dict):
        return "Invalid tool arguments. Expected a JSON object."
    operation = arguments.get("operation")
    if operation == "list_files":
        query = arguments.get("query", "")
        return list_files(query if isinstance(query, str) else "")
    if operation == "search_code":
        query = arguments.get("query", "")
        return search_code(query) if isinstance(query, str) else "Provide a text search query."
    if operation == "read_file":
        path = arguments.get("path", "")
        return read_file(path) if isinstance(path, str) else "Provide a project-relative file path."
    return "Invalid operation. Available operations: list_files, search_code, read_file."
