import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from .manifest import Manifest
from .errors import format_error, QMDError

logger = logging.getLogger(__name__)

def run_qmd_search(
    query: str,
    limit: int = 5,
    qmd_executable: str = "qmd",
    index_name: str = "hermes-skills",
    collection_name: str = "hermes-skills",
    manifest_path: Optional[str] = None
) -> str:
    """
    Run QMD search, parse output, validate against manifest, and return JSON.
    """
    # Fetch more file results than requested skills
    fetch_limit = min(50, max(20, limit * 5))

    cmd = [
        qmd_executable,
        "--index", index_name,
        "query", query,
        "--collection", collection_name,
        "--format", "json",
        "-n", str(fetch_limit)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False
        )
    except subprocess.TimeoutExpired:
        return format_error("qmd_timeout", "QMD search timed out.")
    except FileNotFoundError:
        return format_error("qmd_missing", "qmd executable not found. Install QMD and run build.")

    if result.returncode != 0:
        return format_error("qmd_error", f"QMD exited with code {result.returncode}")

    try:
        qmd_output = json.loads(result.stdout)
    except json.JSONDecodeError:
        return format_error("qmd_error", "Malformed JSON from QMD.")

    # QMD JSON shape typically:
    # {"results": [{"file": "path/to/file.md", "score": 0.9, ...}, ...]}
    # Check shape
    if not isinstance(qmd_output, dict) or "results" not in qmd_output:
        return format_error("qmd_error", "Unexpected JSON shape from QMD.")

    qmd_results = qmd_output["results"]

    if not manifest_path:
        from .cli import get_base_dir
        manifest_path = str(get_base_dir() / "manifest.json")

    if not Path(manifest_path).exists():
        return format_error("index_not_initialized", "Manifest not found. Run build.")

    try:
        manifest = Manifest.load(manifest_path)
    except Exception as e:
        return format_error("index_inconsistent", f"Failed to load manifest: {e}")

    valid_hits = []
    for r in qmd_results:
        file_path = r.get("file")
        if not file_path:
            continue

        entry = manifest.get_entry_by_path(file_path)
        if not entry:
            logger.warning(f"Unknown result path discarded: {file_path}")
            continue

        valid_hits.append({
            "skill_id": entry["skill_id"],
            "load_name": entry["load_name"],
            "corpus_relative_path": entry["corpus_relative_path"],
            "score": r.get("score", 0.0)
        })

    if not valid_hits and qmd_results:
        # All invalid?
        return format_error("index_inconsistent", "All results were unknown. Rebuild required.")

    from .ranking import rank_skills
    candidates = rank_skills(valid_hits, limit)

    return json.dumps({
        "success": True,
        "candidates": candidates
    })
