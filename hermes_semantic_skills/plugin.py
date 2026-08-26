import logging
from typing import Dict, Any

from .qmd import run_qmd_search
from .cli import check_qmd_executable

logger = logging.getLogger(__name__)

SKILL_SEARCH_SCHEMA = {
    "name": "skill_search",
    "description": "Search full installed-skill content and return candidate skill names. Load a candidate with skill_view.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 2000},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5}
        },
        "required": ["query"]
    }
}

def skill_search_handler(args: Dict[str, Any], **kw: Any) -> str:
    query = args.get("query", "")
    limit = args.get("limit", 5)

    if not isinstance(limit, int):
        try:
            limit = int(limit)
        except ValueError:
            limit = 5

    limit = max(1, min(10, limit))
    return run_qmd_search(query, limit=limit)

def _check_fn(*args, **kw) -> bool:
    """Cheap availability check without running models."""
    # Only expose tool if qmd is installed.
    return check_qmd_executable()

def register(ctx: Any) -> None:
    """
    Register the skill_search tool into the Hermes plugin context.
    Do not touch skills_list or skill_view.
    """
    try:
        ctx.register_tool(
            name="skill_search",
            toolset="semantic_skills",
            schema=SKILL_SEARCH_SCHEMA,
            handler=skill_search_handler,
            check_fn=_check_fn,
            emoji="🔍"
        )
        logger.info("Registered skill_search tool.")
    except Exception as e:
        logger.error(f"Failed to register skill_search tool: {e}")
