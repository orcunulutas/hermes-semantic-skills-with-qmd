from pathlib import Path
from hermes_semantic_skills.corpus import build_corpus, discover_markdown_files
import tempfile

def test_discover_markdown_files():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # Valid files
        (base / "SKILL.md").touch()
        (base / "references").mkdir()
        (base / "references" / "valid.md").touch()
        (base / "references" / "nested").mkdir()
        (base / "references" / "nested" / "deep.md").touch()

        # Invalid files
        (base / "templates").mkdir()
        (base / "templates" / "tmpl.md").touch()
        (base / "assets").mkdir()
        (base / "assets" / "script.py").touch()
        (base / "README.md").touch()

        allowed = discover_markdown_files(str(base))
        allowed_set = set(allowed)

        assert "SKILL.md" in allowed_set
        assert "references/valid.md" in allowed_set
        assert "references/nested/deep.md" in allowed_set

        assert "templates/tmpl.md" not in allowed_set
        assert "assets/script.py" not in allowed_set
        assert "README.md" not in allowed_set

def test_build_corpus_creates_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        skill_dir = base / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").touch()
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "doc.md").touch()

        skills = [{
            "skill_id": "abcdef",
            "load_name": "skill_a",
            "source_dir": str(skill_dir),
            "provenance": "project",
            "category": None
        }]

        out_dir = base / "out"
        manifest = build_corpus(skills, str(out_dir))

        assert "entries" in manifest
        assert len(manifest["entries"]) == 2

        corpus_relative_paths = {e["corpus_relative_path"] for e in manifest["entries"]}
        assert "abcdef/SKILL.md" in corpus_relative_paths
        assert "abcdef/references/doc.md" in corpus_relative_paths

        # Verify physical files
        assert (out_dir / "corpus" / "abcdef" / "SKILL.md").exists()
        assert (out_dir / "corpus" / "abcdef" / "references" / "doc.md").exists()
