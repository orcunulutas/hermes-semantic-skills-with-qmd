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
def test_hermes_compatibility():
    """
    Test that the load targets emitted by hermes_adapter are genuinely
    accepted by the pinned version of skill_view(name, preprocess=False).
    """
    try:
        from tools.skills_tool import skill_view
        from hermes_semantic_skills.hermes_adapter import iter_resolved_skills
    except ImportError:
        pytest.skip("Failed to import hermes modules despite /tmp/hermes-agent existing.")

    # iter_resolved_skills uses the current profile/project skills
    # Since we don't have real skills in this temporary environment by default,
    # let's mock one or let hermes discover any built-in ones if they exist.

    skills = iter_resolved_skills()
    if not skills:
        pytest.skip("No skills found in hermes-agent to verify against.")

    for skill in skills:
        load_name = skill["load_name"]

        # In current hermes architecture, skill_view loads without resolving full markdown
        # when preprocess=False.
        result_json = skill_view(load_name, preprocess=False)
        result = json.loads(result_json)

        # skill_view returns {"success": True, "name": "...", "content": "..."}
        # If it's a valid load name, success should be True
        assert result.get("success") is True, f"skill_view rejected valid canonical name '{load_name}': {result}"
