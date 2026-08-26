import json
import tempfile
import subprocess
from pathlib import Path

from hermes_semantic_skills.corpus import build_corpus
from hermes_semantic_skills.qmd import run_qmd_search

def test_exchange_admin_recall():
    """
    Test demonstrating that a skill is discoverable when the terminology
    exists only in references/**/*.md
    """
    mock_qmd = str(Path(__file__).parent.parent / "fixtures" / "mock_qmd.sh")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # 1. Create a mock Exchange Admin skill
        skill_dir = base / "exchange-admin"
        skill_dir.mkdir()

        # Skill metadata mentions only basic description
        with open(skill_dir / "SKILL.md", "w") as f:
            f.write("---\nname: exchange-admin\ndescription: Microsoft Exchange administration\n---\n\n# Exchange Admin Skill\n\nBasic administration tasks.\n")

        # Reference content contains the specific terms
        refs = skill_dir / "references"
        refs.mkdir()
        with open(refs / "mailbox.md", "w") as f:
            f.write("# Mailbox Management\n\nCommands for mailbox management:\n- Disable-RemoteMailbox\n- RemoteRecipientType\n\nUse these for unintended Exchange Online mailbox remediation.")

        # Create a second decoy skill just in case
        skill2_dir = base / "linux-admin"
        skill2_dir.mkdir()
        with open(skill2_dir / "SKILL.md", "w") as f:
            f.write("---\nname: linux-admin\ndescription: Linux administration\n---\n\n# Linux Admin Skill\n\nManage bash and ssh.\n")

        skills = [
            {
                "skill_id": "exchange123",
                "load_name": "exchange-admin",
                "source_dir": str(skill_dir),
                "provenance": "profile",
                "category": None
            },
            {
                "skill_id": "linux123",
                "load_name": "linux-admin",
                "source_dir": str(skill2_dir),
                "provenance": "profile",
                "category": None
            }
        ]

        out_dir = base / "qmd_test"
        out_dir.mkdir()
        manifest = build_corpus(skills, str(out_dir))

        manifest_path = out_dir / "current" / "manifest.json"

        idx_name = "test-hermes-skills"

        # 3. Query using terms ONLY present in the reference file
        query_str = "unintended Exchange Online mailbox"

        result_json = run_qmd_search(
            query=query_str,
            limit=5,
            qmd_executable=mock_qmd,
            index_name=idx_name,
            collection_name=idx_name,
            manifest_path=str(manifest_path)
        )

        result = json.loads(result_json)
        assert result.get("success") is True, f"Search failed: {result}"

        candidates = result.get("candidates", [])
        assert len(candidates) > 0, "No candidates returned."

        top_candidate = candidates[0]
        assert top_candidate["name"] == "exchange-admin", "Exchange admin skill was not retrieved."
        assert "score" in top_candidate
        assert "matched_files" in top_candidate
        assert "path" not in top_candidate
        assert "file" not in top_candidate
        assert "content" not in top_candidate
