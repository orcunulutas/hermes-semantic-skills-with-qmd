from hermes_semantic_skills.cli import check_qmd_executable
import pytest
from unittest.mock import patch
import subprocess

@patch("subprocess.run")
def test_check_qmd_executable_success(mock_run):
    mock_run.return_value = subprocess.CompletedProcess(args=["qmd", "--version"], returncode=0, stdout=b"")
    assert check_qmd_executable() is True

@patch("subprocess.run")
def test_check_qmd_executable_failure(mock_run):
    mock_run.side_effect = FileNotFoundError()
    assert check_qmd_executable() is False
