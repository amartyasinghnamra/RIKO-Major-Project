from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_STAGE_SCRIPT = PROJECT_ROOT / "packaging" / "stage_project.py"
_SPEC = importlib.util.spec_from_file_location("riko_stage_project", _STAGE_SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
stage_project = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(stage_project)


def test_stage_creates_model_directory_for_clean_checkout_without_local_models(
    tmp_path,
    monkeypatch,
):
    source_root = tmp_path / "source"
    destination = tmp_path / "payload"
    source_root.mkdir()

    for relative in stage_project.ROOT_FILES:
        path = source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source", encoding="utf-8")

    for relative in stage_project.SOURCE_DIRS:
        if relative == "models":
            continue
        (source_root / relative).mkdir(parents=True)

    local_config = source_root / "config" / "local"
    local_config.mkdir()
    (local_config / "private.json").write_text("private", encoding="utf-8")
    setup_script = source_root / "packaging" / "linux" / "setup-and-run.sh"
    setup_script.parent.mkdir(parents=True)
    setup_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    monkeypatch.setattr(stage_project, "PROJECT_ROOT", source_root)
    stage_project.stage_project(destination)

    assert (destination / "models" / "kokoro").is_dir()
    assert (destination / "riko-setup-and-run.sh").is_file()
    assert not (destination / "config" / "local").exists()
