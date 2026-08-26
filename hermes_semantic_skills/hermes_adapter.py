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
    # Isolate imports to avoid requiring hermes-agent to load this module.
    try:
        from tools.skills_tool import skills_list, _find_all_skills
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
        all_skills_list = _find_all_skills(skip_disabled=True)
        seen_names = set()

        for skill_info in all_skills_list:
            if not isinstance(skill_info, dict):
                continue

            load_name = skill_info.get("name")
            if not load_name or load_name not in canonical_names:
                continue

            if load_name in seen_names:
                continue
            seen_names.add(load_name)

            source_path_str = skill_info.get("original_path") or skill_info.get("path")
            if not source_path_str:
                continue

            source_dir = str(Path(source_path_str).parent)

            is_project = skill_info.get("is_project_skill", False)
            source_type = skill_info.get("source", "")

            if is_project or source_type == "project":
                provenance = "project"
            elif source_type == "external":
                provenance = "external"
            elif source_type == "plugin" or load_name.startswith("plugin:"):
                provenance = "plugin"
            else:
                provenance = "profile"

            skill_id_str = f"{provenance}:{source_dir}:{load_name}"
            skill_id = hashlib.sha256(skill_id_str.encode("utf-8")).hexdigest()[:16]

            resolved.append({
                "skill_id": skill_id,
                "load_name": load_name,
                "source_dir": source_dir,
                "provenance": provenance,
                "category": skill_info.get("category")
            })

    except Exception as e:
        logger.error(f"Failed to scan skills via _find_all_skills: {e}")

    return resolved
