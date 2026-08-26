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
        manifest_path = str(get_base_dir() / "current" / "manifest.json")

    if not Path(manifest_path).exists():
        return format_error("index_not_initialized", "Manifest not found. Run build.")

    try:
        manifest = Manifest.load(manifest_path)
    except Exception as e:
        return format_error("index_inconsistent", f"Failed to load manifest: {e}")

    # Check if QMD exists
    try:
        subprocess.run([qmd_executable, "--version"], capture_output=True, check=True, timeout=5, shell=False)
    except subprocess.TimeoutExpired:
        return format_error("qmd_timeout", "QMD version check timed out.")
    except (subprocess.SubprocessError, FileNotFoundError):
        return format_error("qmd_missing", "qmd executable not found. Install QMD and run build.")

    # Check if collection exists
    try:
        col_res = subprocess.run(
            [qmd_executable, "--index", index_name, "collection", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False
        )
        if collection_name not in col_res.stdout:
            return format_error("collection_not_initialized", f"Collection {collection_name} not found. Rebuild index.")
    except subprocess.TimeoutExpired:
        return format_error("qmd_timeout", "QMD collection list timed out.")
    except Exception:
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
        # Popen is safer to bound stdout memory size before reading it fully
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False
        )

        try:
            stdout, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return format_error("qmd_timeout", "QMD search timed out.")

    except Exception as e:
        return format_error("qmd_error", f"Failed to execute qmd: {e}")

    if proc.returncode != 0:
        err_msg = stderr.lower() if stderr else ""
        if "model" in err_msg and ("not found" in err_msg or "load" in err_msg or "unavailable" in err_msg):
            return format_error("search_unavailable", f"QMD embedding model unavailable: {stderr.strip()[:200]}")
        return format_error("qmd_error", f"QMD exited with code {proc.returncode}: {stderr.strip()[:200]}")

    if len(stdout) > 5_000_000:
        return format_error("qmd_error", "QMD output exceeded safe limit.")

    try:
        qmd_output = json.loads(stdout)
    except Exception:
        return format_error("qmd_error", "Malformed JSON from QMD.")

    if not isinstance(qmd_output, dict):
        return format_error("qmd_error", "Unexpected JSON shape from QMD (not an object).")

    qmd_results = qmd_output.get("results")
    if not isinstance(qmd_results, list):
        return format_error("qmd_error", "Unexpected JSON shape from QMD ('results' is not a list).")

    valid_hits = []
    for r in qmd_results:
        if not isinstance(r, dict):
            return format_error("qmd_error", "Unexpected JSON shape from QMD (result is not an object).")

        file_path = r.get("file")
        score = r.get("score")

        if not isinstance(file_path, str):
            return format_error("qmd_error", "Unexpected JSON shape from QMD ('file' is not a string).")

        if not isinstance(score, (int, float)):
            return format_error("qmd_error", "Unexpected JSON shape from QMD ('score' is not numeric).")

        import math
        if not math.isfinite(score):
            return format_error("qmd_error", "Unexpected JSON shape from QMD ('score' is not finite).")

        entry = manifest.get_entry_by_path(file_path)
        if not entry:
            logger.warning(f"Unknown result path discarded: {file_path}")
            continue

        valid_hits.append({
            "skill_id": entry["skill_id"],
            "load_name": entry["load_name"],
            "corpus_relative_path": entry["corpus_relative_path"],
            "score": score
        })

    if not valid_hits and qmd_results:
        return format_error("index_inconsistent", "All results were unknown. Rebuild required.")

    from .ranking import rank_skills
    candidates = rank_skills(valid_hits, limit)

    return json.dumps({
        "success": True,
        "candidates": candidates
    })
