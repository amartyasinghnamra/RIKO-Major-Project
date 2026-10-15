from pathlib import Path
import tools.codebase_explorer as explorer


def test_read_file_returns_source_and_line_numbers(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / "example.py").write_text("first\nsecond\n", encoding="utf-8")
    monkeypatch.setattr(explorer, "PROJECT_ROOT", root)
    result = explorer.read_file("example.py")
    assert "Source: example.py" in result
    assert "1: first" in result and "2: second" in result


def test_read_file_blocks_path_traversal(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (tmp_path / "outside.txt").write_text("do not reveal", encoding="utf-8")
    monkeypatch.setattr(explorer, "PROJECT_ROOT", root)
    result = explorer.read_file("../outside.txt")
    assert "unavailable" in result.lower()
    assert "do not reveal" not in result


def test_search_code_finds_line_numbers(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / "sample.py").write_text("alpha\nunique_symbol = 42\n", encoding="utf-8")
    monkeypatch.setattr(explorer, "PROJECT_ROOT", root)
    result = explorer.search_code("unique_symbol")
    assert "sample.py:2:" in result
    assert "unique_symbol = 42" in result


def test_sensitive_and_generated_paths_are_excluded(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / ".env").write_text("API_KEY=private", encoding="utf-8")
    (root / "password_notes.txt").write_text("private", encoding="utf-8")
    cache = root / "__pycache__"
    cache.mkdir()
    (cache / "cached.py").write_text("not source", encoding="utf-8")
    monkeypatch.setattr(explorer, "PROJECT_ROOT", root)
    files = explorer.list_files()
    assert ".env" not in files
    assert "password_notes.txt" not in files
    assert "cached.py" not in files


def test_dispatch_rejects_unknown_operation():
    result = explorer.execute_codebase_tool("explore_codebase", {"operation": "delete"})
    assert "Invalid operation" in result
