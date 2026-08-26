# Hermes Semantic Skills with QMD

Design for an optional Hermes Agent extension that adds full-content skill discovery backed by [QMD](https://github.com/tobi/qmd), without changing how Hermes loads skills.

> Status: architecture and implementation plan only. This repository does not yet provide a working `skill_search` tool.

## Problem

Hermes currently gives the model a compact index of skill names and descriptions and exposes `skills_list` for the same metadata. That progressive-disclosure design is intentionally token-efficient, but a relevant skill can be missed when the user's wording appears only in the body of `SKILL.md` or in `references/**/*.md`.

This project proposes one additional discovery step:

```text
user task -> skill_search(query) -> QMD -> candidate Hermes skill names
                                      |
                                      +-- never returns or loads skill content

candidate name -> existing skill_view(name) -> authoritative load and checks
```

The MVP indexes the full textual content of active Hermes skills in a dedicated QMD index, searches it, groups file/chunk hits by skill, and returns a short ranked list of candidate names. Hermes' existing `skill_view` remains the only component responsible for resolving and loading a selected skill.

## Why this fits Hermes

Hermes already uses three progressive-disclosure levels: compact metadata, full `SKILL.md`, and an individual linked file. `skills_list(category=None, task_id=None)` returns JSON containing `name`, `description`, and `category`; `skill_view(name, file_path=None, task_id=None, preprocess=True)` returns the main skill or a file below its directory. Their schemas and registrations are in [`tools/skills_tool.py`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L818-L888) and [`tools/skills_tool.py`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L1978-L2026).

The proposed tool supplements the first level; it does not introduce a second loader.

## Intended usage

After installation and an explicit index build:

```text
skill_search({"query": "review a migration that must preserve prompt caching"})
```

would return a bounded result such as:

```json
{
  "success": true,
  "candidates": [
    {"name": "hermes-agent", "score": 0.91, "matched_files": 2},
    {"name": "code-review", "score": 0.67, "matched_files": 1}
  ]
}
```

The agent then calls `skill_view(name="hermes-agent")` in the normal way. Scores are discovery hints, not authorization or proof that a skill can load.

Index administration is deliberately outside the model-facing search call. A future CLI command supplied by this project will initialize, rebuild, inspect, and remove only the dedicated skills index.

## Scope and non-goals

The narrow MVP will:

- expose one read-only `skill_search(query, limit?)` tool;
- search `SKILL.md` plus Markdown files under `references/`;
- return candidate load targets, aggregate scores, and small diagnostic counts—not document bodies or snippets;
- use the active Hermes profile's discoverable skill roots and preserve Hermes naming/collision semantics;
- keep the QMD skills corpus separate from the user's ordinary knowledge-base index;
- fail explicitly when QMD or the skills index is unavailable.

It will not:

- replace or wrap `skill_view`;
- auto-load the top result;
- search templates, assets, scripts, arbitrary Markdown, normal QMD knowledge collections, or hub skills that are not installed;
- modify Hermes' system prompt or replace its compact skill index;
- silently install QMD, download models, initialize collections, or rebuild an index during an agent call;
- manage skills, bypass disabled/platform/project-quarantine rules, or resolve plugin-specific behavior independently;
- become a general-purpose knowledge RAG tool.

## Source baseline

This design was audited against:

- NousResearch/hermes-agent commit [`86ae906e88b280215067c5f9726f2f8cec6178b3`](https://github.com/NousResearch/hermes-agent/tree/86ae906e88b280215067c5f9726f2f8cec6178b3) (2026-08-26);
- tobi/qmd commit [`dbfd0b4736aeaf761d1a16ca8e424f071df8feb9`](https://github.com/tobi/qmd/tree/dbfd0b4736aeaf761d1a16ca8e424f071df8feb9) (2026-08-18).

All Hermes API claims in this repository refer to that pinned source baseline. Private helpers are described as implementation details, not promised extension APIs.
