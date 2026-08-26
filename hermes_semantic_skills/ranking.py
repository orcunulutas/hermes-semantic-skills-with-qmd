from typing import List, Dict, Any

def rank_skills(results: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """
    Rank skills based on QMD results and a capped max-plus-RRF scoring.
    """
    # 1. Deduplicate by file: only keep the best hit per (skill_id, corpus_relative_path)
    # The results from QMD are already sorted by score descending.
    best_file_hits = {}

    for rank_idx, result in enumerate(results):
        skill_id = result["skill_id"]
        rel_path = result["corpus_relative_path"]
        key = (skill_id, rel_path)

        if key not in best_file_hits:
            best_file_hits[key] = {
                "score": result["score"],
                "rank": rank_idx,
                "skill_id": skill_id,
                "load_name": result["load_name"],
                "is_main_skill": rel_path.endswith("SKILL.md")
            }

    # 2. Group by skill
    skill_groups = {}
    for hit in best_file_hits.values():
        skill_id = hit["skill_id"]
        if skill_id not in skill_groups:
            skill_groups[skill_id] = {
                "load_name": hit["load_name"],
                "hits": [],
                "best_rank": hit["rank"]
            }
        skill_groups[skill_id]["hits"].append(hit)
        if hit["rank"] < skill_groups[skill_id]["best_rank"]:
            skill_groups[skill_id]["best_rank"] = hit["rank"]

    # 3. Apply capped max-plus-RRF scoring
    candidates = []

    for skill_id, group in skill_groups.items():
        # Sort hits by score descending to get max score first
        hits = sorted(group["hits"], key=lambda x: x["score"], reverse=True)
        max_score = hits[0]["score"]

        # Calculate RRF bonus for OTHER distinct files
        rrf_bonus = 0.0
        for hit in hits[1:]:
            rrf_bonus += 1.0 / (60.0 + hit["rank"])

        capped_bonus = min(0.05, rrf_bonus)
        final_score = max_score + capped_bonus

        has_main = any(h["is_main_skill"] for h in hits)

        candidates.append({
            "name": group["load_name"],
            "score": round(final_score, 4),
            "matched_files": len(hits),
            "main_skill_matched": has_main,
            "best_rank": group["best_rank"] # for tie-breaking
        })

    # 4. Sort and cap
    # Sort by (skill_score desc, best_result_rank asc, load_name asc)
    candidates.sort(key=lambda c: (-c["score"], c["best_rank"], c["name"]))

    # Clean up fields not meant for output
    for c in candidates:
        del c["best_rank"]

    return candidates[:limit]
