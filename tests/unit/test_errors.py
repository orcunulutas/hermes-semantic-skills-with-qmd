from hermes_semantic_skills.errors import format_error, QMDError
import json

def test_format_error():
    err_str = format_error("qmd_error", "test message")
    data = json.loads(err_str)
    assert data["success"] is False
    assert data["code"] == "qmd_error"
    assert data["message"] == "test message"

def test_qmd_error():
    e = QMDError("test_code", "test_msg")
    assert e.code == "test_code"
    assert str(e) == "test_msg"
