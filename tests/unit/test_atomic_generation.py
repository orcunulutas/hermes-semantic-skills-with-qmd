import tempfile
import os
from pathlib import Path
from hermes_semantic_skills.corpus import build_corpus

def test_atomic_generation_symlinks():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        out_dir = base / "out"

        # Build first generation
        skill_dir = base / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").touch()
        skills = [{"skill_id": "1", "load_name": "s1", "source_dir": str(skill_dir), "provenance": "test", "category": None}]

        manifest1 = build_corpus(skills, str(out_dir))
        gen1 = manifest1["generation"]

        current_dir = out_dir / "current"

        assert current_dir.is_symlink()
        assert (current_dir / "corpus").exists()
        assert (current_dir / "manifest.json").exists()

        assert str(gen1) in str(current_dir.resolve())

        # Build second generation
        manifest2 = build_corpus(skills, str(out_dir))
        gen2 = manifest2["generation"]

        assert gen1 != gen2
        assert str(gen2) in str(current_dir.resolve())

        # old generation is untouched
        assert (out_dir / "generations" / gen1).exists()
