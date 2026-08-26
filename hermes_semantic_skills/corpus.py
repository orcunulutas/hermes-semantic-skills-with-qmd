import json
import logging
import os
import shutil
import uuid
import time
from pathlib import Path
from typing import Dict, List, Set, Any
import hashlib

from .hermes_adapter import ResolvedSkill

logger = logging.getLogger(__name__)

def is_subpath(child: Path, parent: Path) -> bool:
    try:
        resolved_child = child.resolve()
        resolved_parent = parent.resolve()
        return resolved_parent in resolved_child.parents
    except Exception:
        return False

def discover_markdown_files(source_dir: str) -> List[str]:
    allowed_files = []
    base_path = Path(source_dir)

    skill_md = base_path / "SKILL.md"
    if skill_md.is_file() and not skill_md.is_symlink():
        allowed_files.append("SKILL.md")

    references_dir = base_path / "references"
    if references_dir.is_dir() and not references_dir.is_symlink():
        for md_file in references_dir.rglob("*.md"):
            if md_file.is_file() and not md_file.is_symlink():
                if is_subpath(md_file, base_path):
                    rel_path = md_file.relative_to(base_path).as_posix()
                    allowed_files.append(rel_path)

    return allowed_files

def calculate_file_hash(filepath: Path) -> str:
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
    We build a complete generation in a temporary directory, and then promote it via symlinks
    or directory renaming so the old generation remains intact if something fails.
    Returns the manifest dictionary.
    """
    base_output = Path(output_dir)

    generation_id = str(uuid.uuid4())
    generation_dir = base_output / "generations" / generation_id
    temp_dir = base_output / "generations" / f"{generation_id}.tmp"

    corpus_dir = temp_dir / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []

    for skill in skills:
        skill_id = skill["skill_id"]
        source_dir = Path(skill["source_dir"])

        allowed_files = discover_markdown_files(str(source_dir))
        if not allowed_files:
            continue

        skill_corpus_dir = corpus_dir / skill_id
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
        "generation": generation_id,
        "entries": manifest_entries
    }

    manifest_path = temp_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Promote temporary generation folder to final generation folder
    os.rename(temp_dir, generation_dir)

    # Update current symlinks atomically
    current_corpus_link = base_output / "corpus"
    current_manifest_link = base_output / "manifest.json"

    tmp_corpus_link = base_output / "corpus.tmp"
    tmp_manifest_link = base_output / "manifest.json.tmp"

    if tmp_corpus_link.exists() or tmp_corpus_link.is_symlink():
        tmp_corpus_link.unlink()
    if tmp_manifest_link.exists() or tmp_manifest_link.is_symlink():
        tmp_manifest_link.unlink()

    # Create symlinks pointing to the new generation
    os.symlink(generation_dir / "corpus", tmp_corpus_link)
    os.symlink(generation_dir / "manifest.json", tmp_manifest_link)

    # Atomically replace the existing current links
    os.replace(tmp_corpus_link, current_corpus_link)
    os.replace(tmp_manifest_link, current_manifest_link)

    return manifest
