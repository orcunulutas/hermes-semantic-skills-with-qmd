from hermes_semantic_skills.ranking import rank_skills

def test_rank_skills_deduplication():
    results = [
        {"skill_id": "1", "load_name": "skill_a", "corpus_relative_path": "1/SKILL.md", "score": 0.9},
        {"skill_id": "1", "load_name": "skill_a", "corpus_relative_path": "1/SKILL.md", "score": 0.8},
    ]
    candidates = rank_skills(results, 5)
    assert len(candidates) == 1
    assert candidates[0]["matched_files"] == 1
    assert candidates[0]["score"] == 0.9

def test_rank_skills_rrf_bonus():
    results = [
        {"skill_id": "1", "load_name": "skill_a", "corpus_relative_path": "1/SKILL.md", "score": 0.9},
        {"skill_id": "1", "load_name": "skill_a", "corpus_relative_path": "1/references/a.md", "score": 0.8},
    ]
    candidates = rank_skills(results, 5)
    assert len(candidates) == 1
    assert candidates[0]["matched_files"] == 2
    # Bonus is calculated as 1/(60+1) for the second distinct file
    assert candidates[0]["score"] == round(0.9 + 1/61, 4)

def test_rank_skills_ordering():
    results = [
        {"skill_id": "2", "load_name": "skill_b", "corpus_relative_path": "2/SKILL.md", "score": 0.95},
        {"skill_id": "1", "load_name": "skill_a", "corpus_relative_path": "1/SKILL.md", "score": 0.9},
        {"skill_id": "1", "load_name": "skill_a", "corpus_relative_path": "1/references/a.md", "score": 0.8},
    ]
    candidates = rank_skills(results, 5)
    assert len(candidates) == 2
    assert candidates[0]["name"] == "skill_b"
    assert candidates[1]["name"] == "skill_a"

def test_rank_skills_limit():
    results = [
        {"skill_id": str(i), "load_name": f"skill_{i}", "corpus_relative_path": f"{i}/SKILL.md", "score": 1.0 - (i*0.01)}
        for i in range(10)
    ]
    candidates = rank_skills(results, 3)
    assert len(candidates) == 3
