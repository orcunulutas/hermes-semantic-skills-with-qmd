import sys
import os
import json
import tempfile
from pathlib import Path

# Provide hermes-agent path
hermes_path = "/tmp/hermes-agent"
if os.path.exists(hermes_path):
    sys.path.append(hermes_path)

import pytest

@pytest.mark.skipif(not os.path.exists("/tmp/hermes-agent"), reason="hermes-agent not available in /tmp/hermes-agent")
def test_hermes_compatibility(monkeypatch):
    """
    Test that the load targets emitted by hermes_adapter are genuinely
    accepted by the pinned version of skill_view(name, preprocess=False).
    """
    try:
        import yaml
        import tools.skills_tool
        import agent.skill_utils
        from hermes_semantic_skills.hermes_adapter import iter_resolved_skills
    except ImportError:
        pytest.skip("Failed to import hermes modules despite /tmp/hermes-agent existing. Maybe pyyaml missing.")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # Create a real test skill
        skill_dir = base / "test-skill-xyz"
        skill_dir.mkdir()
        with open(skill_dir / "SKILL.md", "w") as f:
            f.write("---\nname: test-skill-xyz\ndescription: Test skill\n---\n\n# XYZ\nContent.")

        monkeypatch.setattr(agent.skill_utils, "get_project_skills_dirs", lambda *args, **kwargs: [base])
        monkeypatch.setattr(agent.skill_utils, "get_external_skills_dirs", lambda *args, **kwargs: [])
        monkeypatch.setattr(tools.skills_tool, "_skills_dir", lambda: base)

        skills = iter_resolved_skills()
        assert len(skills) > 0, "Adapter failed to discover the mocked test skill"

        found = False
        for skill in skills:
            if skill["load_name"] == "test-skill-xyz":
                found = True
                load_name = skill["load_name"]

                result_json = tools.skills_tool.skill_view(load_name, preprocess=False)
                result = json.loads(result_json)

                assert result.get("success") is True, f"skill_view rejected valid canonical name '{load_name}': {result}"
                assert result.get("name") == "test-skill-xyz"

        assert found, "The specific test skill was not discovered by adapter"
