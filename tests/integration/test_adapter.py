import os
import sys
import tempfile
import pytest
from pathlib import Path

hermes_path = "/tmp/hermes-agent"
if os.path.exists(hermes_path):
    sys.path.append(hermes_path)

@pytest.mark.skipif(not os.path.exists("/tmp/hermes-agent"), reason="hermes-agent not available")
def test_adapter_discovery_and_precedence(monkeypatch):
    """
    Test that the adapter discovers project, profile, and external skills,
    respects the canonical name from `skills_list`, and enforces precedence.
    """
    try:
        import agent.skill_utils
        import tools.skills_tool
        from hermes_semantic_skills.hermes_adapter import iter_resolved_skills
    except ImportError:
        pytest.skip("Could not import hermes-agent internals")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        proj_dir = base / "project_skills"
        prof_dir = base / "profile_skills"
        ext_dir = base / "external_skills"

        for d in [proj_dir, prof_dir, ext_dir]:
            d.mkdir()

        s1 = proj_dir / "skill-proj"
        s1.mkdir()
        with open(s1 / "SKILL.md", "w") as f:
            f.write("---\nname: skill-proj\n---\ncontent")

        s2 = prof_dir / "skill-proj"
        s2.mkdir()
        with open(s2 / "SKILL.md", "w") as f:
            f.write("---\nname: skill-proj\n---\ncontent")

        s3 = ext_dir / "skill-ext"
        s3.mkdir()
        with open(s3 / "SKILL.md", "w") as f:
            f.write("---\nname: skill-ext\n---\ncontent")

        monkeypatch.setattr(agent.skill_utils, "get_project_skills_dirs", lambda *args, **kwargs: [proj_dir])
        monkeypatch.setattr(agent.skill_utils, "get_external_skills_dirs", lambda *args, **kwargs: [ext_dir])
        monkeypatch.setattr(tools.skills_tool, "_skills_dir", lambda: prof_dir)

        skills = iter_resolved_skills()

        load_names = {s["load_name"] for s in skills}
        assert "skill-proj" in load_names
        assert "skill-ext" in load_names
        assert len(skills) == 2

        proj_skill = next(s for s in skills if s["load_name"] == "skill-proj")
        assert proj_skill["provenance"] == "project"
        assert str(proj_dir) in proj_skill["source_dir"]

        ext_skill = next(s for s in skills if s["load_name"] == "skill-ext")
        assert ext_skill["provenance"] == "external"
        assert str(ext_dir) in ext_skill["source_dir"]
