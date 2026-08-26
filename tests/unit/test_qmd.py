from hermes_semantic_skills.qmd import run_qmd_search
import tempfile
import json
import os
from pathlib import Path

def test_qmd_handling_malformed_json(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        manifest_path = base / "current" / "manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text('{"version": 1, "entries": []}')

        # mock qmd to return garbage but pass collection test
        mock_qmd = base / "mock_qmd.sh"
        mock_qmd.write_text("#!/bin/bash\nif [[ \"$*\" == *\"collection list\"* ]]; then echo 'hermes-skills'; else echo '{{garbage'; fi")
        mock_qmd.chmod(0o755)

        result_json = run_qmd_search("test", qmd_executable=str(mock_qmd), manifest_path=str(manifest_path))
        result = json.loads(result_json)
        assert result["success"] is False
        assert result["code"] == "qmd_error"
        assert "Malformed JSON" in result["message"]

def test_qmd_handling_unexpected_shape(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        manifest_path = base / "current" / "manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text('{"version": 1, "entries": []}')

        mock_qmd = base / "mock_qmd.sh"
        mock_qmd.write_text("#!/bin/bash\nif [[ \"$*\" == *\"collection list\"* ]]; then echo 'hermes-skills'; else echo '{\"wrong_key\": []}'; fi")
        mock_qmd.chmod(0o755)

        result_json = run_qmd_search("test", qmd_executable=str(mock_qmd), manifest_path=str(manifest_path))
        result = json.loads(result_json)
        assert result["success"] is False
        assert result["code"] == "qmd_error"
        assert "Unexpected JSON shape" in result["message"]

def test_qmd_handling_invalid_types(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        manifest_path = base / "current" / "manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text('{"version": 1, "entries": [{"corpus_relative_path": "path/doc.md", "load_name": "x", "skill_id": "y"}]}')

        mock_qmd = base / "mock_qmd.sh"
        # Return invalid types for score and file.
        # Now our strict requirements dictate that if ANY object fails it throws a structured error.
        mock_qmd.write_text("#!/bin/bash\nif [[ \"$*\" == *\"collection list\"* ]]; then echo 'hermes-skills'; else echo '{\"results\": [{\"file\": 123, \"score\": \"high\"}]}'; fi")
        mock_qmd.chmod(0o755)

        result_json = run_qmd_search("test", qmd_executable=str(mock_qmd), manifest_path=str(manifest_path))
        result = json.loads(result_json)
        # Should throw qmd_error due to invalid type
        assert result["success"] is False
        assert result["code"] == "qmd_error"
