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
    fetch_limit = min(50, max(20, limit * 5))

    if not manifest_path:
        from .cli import get_base_dir
        manifest_path = str(get_base_dir() / "manifest.json")

    if not Path(manifest_path).exists():
        return format_error("index_not_initialized", "Manifest not found. Run build.")

    try:
        manifest = Manifest.load(manifest_path)
    except Exception as e:
        return format_error("index_inconsistent", f"Failed to load manifest: {e}")

    # Check if QMD exists
    try:
        subprocess.run([qmd_executable, "--version"], capture_output=True, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        return format_error("qmd_missing", "qmd executable not found. Install QMD and run build.")

    # Check if collection exists
    try:
        col_res = subprocess.run([qmd_executable, "--index", index_name, "collection", "list"], capture_output=True, text=True)
        if collection_name not in col_res.stdout:
            return format_error("collection_not_initialized", f"Collection {collection_name} not found. Rebuild index.")
    except Exception:
        # If this fails, we will catch the query error later, but we try to provide a specific error first.
        pass

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

    if result.returncode != 0:
        err_msg = result.stderr.lower() if result.stderr else ""
        if "model" in err_msg and ("not found" in err_msg or "load" in err_msg or "unavailable" in err_msg):
            return format_error("search_unavailable", f"QMD embedding model unavailable: {result.stderr.strip()[:200]}")
        return format_error("qmd_error", f"QMD exited with code {result.returncode}: {result.stderr.strip()[:200]}")

    try:
        qmd_output = json.loads(result.stdout)
    except json.JSONDecodeError:
        return format_error("qmd_error", "Malformed JSON from QMD.")

    if not isinstance(qmd_output, dict) or "results" not in qmd_output:
        return format_error("qmd_error", "Unexpected JSON shape from QMD.")

    qmd_results = qmd_output["results"]

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
        return format_error("index_inconsistent", "All results were unknown. Rebuild required.")

    from .ranking import rank_skills
    candidates = rank_skills(valid_hits, limit)

    return json.dumps({
        "success": True,
        "candidates": candidates
    })
