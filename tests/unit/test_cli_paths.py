import sys
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from hermes_semantic_skills.cli import command_build, command_doctor, get_base_dir

@patch("hermes_semantic_skills.cli.check_qmd_executable", return_value=True)
@patch("hermes_semantic_skills.cli.iter_resolved_skills", return_value=[])
@patch("hermes_semantic_skills.cli.build_corpus")
@patch("hermes_semantic_skills.cli.subprocess.run")
def test_build_corpus_uses_current_dir(mock_run, mock_build, mock_skills, mock_check, monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        monkeypatch.setattr("hermes_semantic_skills.cli.get_base_dir", lambda: base)

        # Create a mock layout mimicking an atomic generation to prove it doesn't resolve symlinks
        gen_dir = base / "generations" / "12345"
        gen_dir.mkdir(parents=True)
        (gen_dir / "corpus").mkdir()

        current_symlink = base / "current"
        os.symlink(gen_dir, current_symlink)

        # Call build
        command_build(MagicMock())

        # Verify collection add was called on current/corpus
        add_call = [call for call in mock_run.call_args_list if "collection" in call.args[0] and "add" in call.args[0]]
        assert len(add_call) == 1

        cmd_args = add_call[0].args[0]
        cmd_str = " ".join(cmd_args)

        # The argument should strictly be current/corpus without resolving to generations/12345
        assert "current/corpus" in cmd_str
        assert "generations" not in cmd_str

@patch("hermes_semantic_skills.cli.check_qmd_executable", return_value=True)
def test_doctor_checks_current_manifest(mock_check, monkeypatch, capsys):
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        monkeypatch.setattr("hermes_semantic_skills.cli.get_base_dir", lambda: base)

        command_doctor(MagicMock())
        captured = capsys.readouterr()
        assert "Manifest: MISSING" in captured.out

        # Now create the manifest and check
        manifest_path = base / "current" / "manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.touch()

        command_doctor(MagicMock())
        captured = capsys.readouterr()
        assert "Manifest: PRESENT" in captured.out
