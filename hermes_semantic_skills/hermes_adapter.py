import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, TypedDict
import hashlib

logger = logging.getLogger(__name__)

class ResolvedSkill(TypedDict):
    skill_id: str
    load_name: str
    source_dir: str
    provenance: str
    category: Optional[str]

def iter_resolved_skills() -> List[ResolvedSkill]:
    """
    Enumerate eligible installed skills using the pinned Hermes behavior.
    """
    try:
        from tools.skills_tool import skills_list, _find_all_skills
        from agent.skill_utils import iter_project_skill_files, iter_skill_index_files, get_project_skills_dirs, get_external_skills_dirs
        from tools.skills_tool import _skills_dir
    except ImportError as e:
        raise ImportError("Hermes Agent >=0.20.5 (or pinned version) is required.") from e

    try:
        skills_json = skills_list(category=None, task_id=None)
        skills_data = json.loads(skills_json)
        if not isinstance(skills_data, dict) or not skills_data.get("success"):
            logger.warning(f"skills_list returned success=false: {skills_json}")
            return []
    except Exception as e:
        logger.warning(f"Failed to get skills from skills_list: {e}")
        return []

    canonical_names = {s.get("name") for s in skills_data.get("skills", []) if isinstance(s, dict) and s.get("name")}

    resolved: List[ResolvedSkill] = []

    try:
        seen_names = set()

        def _process_file(skill_md: Path, provenance: str):
            with open(skill_md, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(2048)

            load_name = skill_md.parent.name
            if content.startswith("---"):
                try:
                    import yaml
                    frontmatter = yaml.safe_load(content.split("---")[1])
                    if frontmatter and isinstance(frontmatter, dict) and "name" in frontmatter:
                        load_name = frontmatter["name"]
                except Exception:
                    pass

            if not load_name or load_name not in canonical_names:
                return

            if load_name in seen_names:
                return

            seen_names.add(load_name)

            source_dir = str(skill_md.parent)

            skill_id_str = f"{provenance}:{source_dir}:{load_name}"
            skill_id = hashlib.sha256(skill_id_str.encode("utf-8")).hexdigest()[:16]

            resolved.append({
                "skill_id": skill_id,
                "load_name": load_name,
                "source_dir": source_dir,
                "provenance": provenance,
                "category": None
            })

        for proj_dir in get_project_skills_dirs():
            # _find_all_skills uses iter_project_skill_files which we can mirror safely
            # by looking for SKILL.md under the directory.
            for f in Path(proj_dir).rglob("SKILL.md"):
                _process_file(f, "project")

        active_skills_dir = _skills_dir()
        if hasattr(active_skills_dir, "exists") and active_skills_dir.exists():
            for f in active_skills_dir.rglob("SKILL.md"):
                _process_file(f, "profile")

        for ext_dir in get_external_skills_dirs():
            for f in Path(ext_dir).rglob("SKILL.md"):
                _process_file(f, "external")

    except Exception as e:
        logger.error(f"Failed to scan skills: {e}")

    return resolved
