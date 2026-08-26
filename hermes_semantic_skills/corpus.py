import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Set, Any
import hashlib

from .hermes_adapter import ResolvedSkill

logger = logging.getLogger(__name__)

def is_subpath(child: Path, parent: Path) -> bool:
    """Check if child is securely a subpath of parent (resolves symlinks and prevents traversal)."""
    try:
        resolved_child = child.resolve()
        resolved_parent = parent.resolve()
        return resolved_parent in resolved_child.parents
    except Exception:
        return False

def discover_markdown_files(source_dir: str) -> List[str]:
    """
    Discover all allowed markdown files for a skill.
    Must ONLY include SKILL.md and references/**/*.md.
    """
    allowed_files = []
    base_path = Path(source_dir)

    skill_md = base_path / "SKILL.md"
    if skill_md.is_file() and not skill_md.is_symlink():
        allowed_files.append("SKILL.md")

    references_dir = base_path / "references"
    if references_dir.is_dir() and not references_dir.is_symlink():
        for md_file in references_dir.rglob("*.md"):
            if md_file.is_file() and not md_file.is_symlink():
                # Enforce resolved-path containment
                if is_subpath(md_file, base_path):
                    rel_path = md_file.relative_to(base_path).as_posix()
                    allowed_files.append(rel_path)

    return allowed_files

def calculate_file_hash(filepath: Path) -> str:
    """Calculate SHA256 fingerprint for a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            sha256.update(data)
    return f"sha256:{sha256.hexdigest()}"

def build_corpus(
    skills: List[ResolvedSkill],
    output_dir: str,
) -> Dict[str, Any]:
    """
    Build the deterministic corpus and generate the manifest atomically.
    Returns the manifest dictionary.
    """
    base_output = Path(output_dir)

    # We will build into a temporary directory first.
    temp_dir = base_output / "corpus.tmp"
    final_dir = base_output / "corpus"

    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    temp_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []

    for skill in skills:
        skill_id = skill["skill_id"]
        source_dir = Path(skill["source_dir"])

        allowed_files = discover_markdown_files(str(source_dir))
        if not allowed_files:
            continue

        skill_corpus_dir = temp_dir / skill_id
        skill_corpus_dir.mkdir(parents=True, exist_ok=True)

        for rel_path in allowed_files:
            src_file = source_dir / rel_path
            dst_file = skill_corpus_dir / rel_path

            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)

            fingerprint = calculate_file_hash(src_file)

            corpus_relative = Path(skill_id) / rel_path

            manifest_entries.append({
                "schema_version": 1,
                "skill_id": skill_id,
                "load_name": skill["load_name"],
                "source_relative_path": rel_path,
                "corpus_relative_path": corpus_relative.as_posix(),
                "source_fingerprint": fingerprint,
                "provenance": skill["provenance"]
            })

    manifest = {
        "version": 1,
        "entries": manifest_entries
    }

    manifest_path_tmp = base_output / "manifest.json.tmp"
    manifest_path_final = base_output / "manifest.json"

    with open(manifest_path_tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Atomic promotion
    # First, handle the directory.
    # POSIX rename allows overwriting an empty directory, but usually not a full one.
    # To swap a full directory atomically (or close to it) without failing, we can move the old one out of the way.
    if final_dir.exists():
        old_dir = base_output / "corpus.old"
        if old_dir.exists():
            shutil.rmtree(old_dir)
        os.rename(final_dir, old_dir)
        os.rename(temp_dir, final_dir)
        shutil.rmtree(old_dir)
    else:
        os.rename(temp_dir, final_dir)

    # Promote manifest atomically
    os.replace(manifest_path_tmp, manifest_path_final)

    return manifest
