import json
import logging
import subprocess
import time
import os
import urllib.parse
import re
from pathlib import PurePosixPath, Path
from typing import List, Dict, Any, Optional, Tuple

from .manifest import Manifest
from .errors import format_error, QMDError

logger = logging.getLogger(__name__)

class BoundedExecutionError(Exception):
    pass

class BoundedTimeoutError(BoundedExecutionError):
    pass

class BoundedOverflowError(BoundedExecutionError):
    pass

def _run_bounded(cmd: List[str], timeout: float, max_bytes: int = 5_000_000) -> Tuple[int, str, str]:
    """
    Run a subprocess, non-blocking stream capture, bounded by size and timeout.
    Raises BoundedTimeoutError or BoundedOverflowError. Returns (returncode, stdout, stderr).
    """
    import select
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False
    )

    stdout_chunks = []
    stderr_chunks = []
    stdout_len = 0
    stderr_len = 0

    start_time = time.monotonic()

    try:
        os.set_blocking(proc.stdout.fileno(), False)
        os.set_blocking(proc.stderr.fileno(), False)

        while True:
            if time.monotonic() - start_time > timeout:
                raise BoundedTimeoutError()

            reads, _, _ = select.select([proc.stdout, proc.stderr], [], [], 0.5)

            for fd in reads:
                data = fd.read(65536)
                if data:
                    if fd is proc.stdout:
                        stdout_chunks.append(data)
                        stdout_len += len(data)
                        if stdout_len > max_bytes:
                            raise BoundedOverflowError()
                    else:
                        stderr_chunks.append(data)
                        stderr_len += len(data)
                        if stderr_len > max_bytes:
                            raise BoundedOverflowError()

            if proc.poll() is not None:
                for fd in [proc.stdout, proc.stderr]:
                    while True:
                        data = fd.read(65536)
                        if not data:
                            break
                        if fd is proc.stdout:
                            stdout_chunks.append(data)
                            stdout_len += len(data)
                        else:
                            stderr_chunks.append(data)
                            stderr_len += len(data)

                        if stdout_len > max_bytes or stderr_len > max_bytes:
                            raise BoundedOverflowError()
                break

        stdout = b"".join(stdout_chunks).decode("utf-8", errors="replace")
        stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")
        return proc.returncode, stdout, stderr

    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

def _normalize_qmd_path(uri: str, index_name: str, collection_name: str) -> Optional[str]:
    """
    Safely extract a relative manifest path from a QMD result path or URI.
    Returns None if malformed, insecure, or from wrong index/collection.
    """
    # Reject any URI scheme other than qmd
    if "://" in uri and not uri.startswith("qmd://"):
        return None

    if uri.startswith("qmd://"):
        parsed = urllib.parse.urlparse(uri)
        if parsed.scheme != "qmd":
            return None

        if parsed.netloc != collection_name:
            return None

        qs = urllib.parse.parse_qs(parsed.query)
        if "index" in qs:
            if len(qs["index"]) != 1 or qs["index"][0] != index_name:
                return None

        raw_path = parsed.path
        if not raw_path.startswith("/"):
            return None

        # Reject malformed percent escapes
        if re.search(r'%(?![a-fA-F0-9]{2})', raw_path):
            return None

        # Only URL-decode the path component
        decoded_path = urllib.parse.unquote(raw_path)
        norm_path = decoded_path[1:]
    else:
        # Do not URL-decode plain relative paths
        norm_path = uri

    # Use PurePosixPath to check traversal and absolute safely
    if "\\" in norm_path:
        return None

    try:
        p = PurePosixPath(norm_path)
    except Exception:
        return None

    if p.is_absolute():
        return None

    if ".." in p.parts or "." in p.parts:
        return None

    result = p.as_posix()
    if not result or result == ".":
        return None

    return result

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

    # Check if QMD exists (Bounded)
    try:
        rc, _, _ = _run_bounded([qmd_executable, "--version"], timeout=5.0)
        if rc != 0:
            return format_error("qmd_missing", "qmd executable not found or failed.")
    except BoundedTimeoutError:
        return format_error("qmd_timeout", "QMD version check timed out.")
    except BoundedOverflowError:
        return format_error("qmd_error", "QMD version check exceeded safe limit.")
    except FileNotFoundError:
        return format_error("qmd_missing", "qmd executable not found. Install QMD and run build.")
    except Exception as e:
        return format_error("qmd_error", f"Failed checking qmd version: {e}")

    # Check if collection exists (Bounded)
    try:
        rc, out, _ = _run_bounded(
            [qmd_executable, "--index", index_name, "collection", "list"],
            timeout=10.0
        )
        if rc == 0 and collection_name not in out:
            return format_error("collection_not_initialized", f"Collection {collection_name} not found. Rebuild index.")
    except BoundedTimeoutError:
        return format_error("qmd_timeout", "QMD collection list timed out.")
    except BoundedOverflowError:
        return format_error("qmd_error", "QMD collection list exceeded safe limit.")
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
        rc, stdout, stderr = _run_bounded(cmd, timeout=30.0)
    except BoundedTimeoutError:
        return format_error("qmd_timeout", "QMD search timed out.")
    except BoundedOverflowError:
        return format_error("qmd_error", "QMD output exceeded safe limit.")
    except Exception as e:
        return format_error("qmd_error", f"Failed to execute qmd: {e}")

    if rc != 0:
        err_msg = stderr.lower() if stderr else ""
        if "model" in err_msg and ("not found" in err_msg or "load" in err_msg or "unavailable" in err_msg):
            return format_error("search_unavailable", f"QMD embedding model unavailable: {stderr.strip()[:200]}")
        return format_error("qmd_error", f"QMD exited with code {rc}: {stderr.strip()[:200]}")

    try:
        qmd_output = json.loads(stdout)
    except Exception:
        return format_error("qmd_error", "Malformed JSON from QMD.")

    if isinstance(qmd_output, list):
        qmd_results = qmd_output
    elif isinstance(qmd_output, dict) and "results" in qmd_output and isinstance(qmd_output["results"], list):
        qmd_results = qmd_output["results"]
    else:
        return format_error("qmd_error", "Unexpected JSON shape from QMD (must be an array or object containing 'results' array).")

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

        norm_path = _normalize_qmd_path(file_path, index_name, collection_name)
        if not norm_path:
            logger.warning(f"Unknown/invalid result path discarded: {file_path}")
            continue

        entry = manifest.get_entry_by_path(norm_path)
        if not entry:
            logger.warning(f"Unknown manifest path discarded: {norm_path}")
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
