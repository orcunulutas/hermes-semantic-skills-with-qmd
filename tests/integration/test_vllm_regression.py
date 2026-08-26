import json
import tempfile
from pathlib import Path
from hermes_semantic_skills.qmd import run_qmd_search
from hermes_semantic_skills.corpus import build_corpus

def test_vllm_regression_search():
    """
    Test the live E2E case exactly:
    query: speculative decoding draft model verification
    expected candidate: serving-llms-vllm

    QMD returns a top-level list and a qmd:// URI.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # 1. Create a mock serving-llms-vllm skill
        skill_dir = base / "serving-llms-vllm"
        skill_dir.mkdir()

        with open(skill_dir / "SKILL.md", "w") as f:
            f.write("---\nname: serving-llms-vllm\ndescription: vLLM Server\n---\n")

        refs = skill_dir / "references"
        refs.mkdir()
        with open(refs / "optimization.md", "w") as f:
            f.write("speculative decoding draft model verification")

        skills = [{
            "skill_id": "2cd243b751409a4b", # mock ID to match QMD path
            "load_name": "serving-llms-vllm",
            "source_dir": str(skill_dir),
            "provenance": "profile",
            "category": None
        }]

        out_dir = base / "qmd_test"
        out_dir.mkdir()
        build_corpus(skills, str(out_dir))

        manifest_path = out_dir / "current" / "manifest.json"

        # We need a mock QMD returning the exact live format
        mock_qmd = base / "mock_qmd.sh"
        mock_qmd.write_text("""#!/bin/bash
if [[ "$*" == *"--version"* ]]; then
    echo "qmd mock version"
elif [[ "$*" == *"collection list"* ]]; then
    echo "hermes-skills"
elif [[ "$*" == *"query"* && "$*" == *"--format json"* ]]; then
    cat << 'JSON'
[
  {
    "score": 0.41,
    "file": "qmd://hermes-skills/2cd243b751409a4b/references/optimization.md?index=hermes-skills"
  }
]
JSON
fi
""")
        mock_qmd.chmod(0o755)

        result_json = run_qmd_search(
            query="speculative decoding draft model verification",
            limit=5,
            qmd_executable=str(mock_qmd),
            index_name="hermes-skills",
            collection_name="hermes-skills",
            manifest_path=str(manifest_path)
        )

        result = json.loads(result_json)
        assert result.get("success") is True, f"Search failed: {result}"

        candidates = result.get("candidates", [])
        assert len(candidates) > 0, "No candidates returned."

        names = [c["name"] for c in candidates]
        assert "serving-llms-vllm" in names

        # Verify no snippets, URIs, or absolute paths leak
        top = candidates[0]
        assert "score" in top
        assert "qmd://" not in str(top)
        assert "content" not in top
        assert "file" not in top
