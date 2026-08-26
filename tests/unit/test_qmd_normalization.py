from hermes_semantic_skills.qmd import _normalize_qmd_path

def test_normalize_qmd_path_valid_uri():
    uri = "qmd://hermes-skills/2cd243b751409a4b/references/optimization.md?index=hermes-skills"
    res = _normalize_qmd_path(uri, "hermes-skills", "hermes-skills")
    assert res == "2cd243b751409a4b/references/optimization.md"

def test_normalize_qmd_path_plain_relative():
    uri = "2cd243b751409a4b/references/optimization.md"
    res = _normalize_qmd_path(uri, "hermes-skills", "hermes-skills")
    assert res == "2cd243b751409a4b/references/optimization.md"

def test_normalize_qmd_path_wrong_collection():
    uri = "qmd://wrong-collection/2cd243b751409a4b/references/optimization.md?index=hermes-skills"
    res = _normalize_qmd_path(uri, "hermes-skills", "hermes-skills")
    assert res is None

def test_normalize_qmd_path_wrong_index():
    uri = "qmd://hermes-skills/2cd243b751409a4b/references/optimization.md?index=wrong-index"
    res = _normalize_qmd_path(uri, "hermes-skills", "hermes-skills")
    assert res is None

def test_normalize_qmd_path_traversal():
    uri = "qmd://hermes-skills/../../etc/passwd?index=hermes-skills"
    res = _normalize_qmd_path(uri, "hermes-skills", "hermes-skills")
    assert res is None

def test_normalize_qmd_path_encoded_traversal():
    uri = "qmd://hermes-skills/%2e%2e/%2e%2e/etc/passwd?index=hermes-skills"
    res = _normalize_qmd_path(uri, "hermes-skills", "hermes-skills")
    assert res is None

def test_normalize_qmd_path_absolute():
    uri = "qmd://hermes-skills//etc/passwd?index=hermes-skills"
    res = _normalize_qmd_path(uri, "hermes-skills", "hermes-skills")
    assert res is None
