# Hermes Semantic Skills with QMD

An optional Hermes Agent extension that adds full-content skill discovery backed by [QMD](https://github.com/tobi/qmd).

## Problem

Hermes gives the model a compact index of skill names and descriptions. This is token-efficient, but a relevant skill can be missed when the user's wording appears only in the body of `SKILL.md` or in `references/**/*.md`.

This extension adds one discovery step:
```text
skill_search(query) -> QMD -> candidate Hermes skill names
```
The model can then load the relevant skill using the core `skill_view(name)` tool.

## Installation

### Prerequisites

* Hermes Agent >= 0.20.5
* [QMD](https://github.com/tobi/qmd) executable in your PATH.

### Install the plugin

```bash
hermes plugins install orcunulutas/hermes-semantic-skills-with-qmd --enable
```

## Setup & Index Build

Before the model can search, you must build the dedicated skills index:

```bash
python -m hermes_semantic_skills.cli build
```

This will safely copy `SKILL.md` and `references/**/*.md` of your active skills into a dedicated corpus, generate a deterministic manifest, and invoke QMD to update/embed the corpus under a dedicated named index `hermes-skills`.

You can also use:
```bash
python -m hermes_semantic_skills.cli doctor   # Check status
python -m hermes_semantic_skills.cli refresh  # Rebuild index after adding skills
python -m hermes_semantic_skills.cli remove   # Clean up the semantic index
```

## Usage

Once enabled, the model will have access to the `skill_search` tool:

```json
{
  "name": "skill_search",
  "parameters": {
    "query": "unintended Exchange Online mailbox",
    "limit": 5
  }
}
```

It returns candidate skill names which the model should follow up with using `skill_view`.

## Security

This plugin respects the boundaries set by Hermes:
* Only explicit files (`SKILL.md`, `references/**/*.md`) are indexed.
* Search results never leak path information, QMD snippets, or full text.
* Execution is bounded to the `hermes-skills` QMD index ensuring absolute isolation from generic RAG or local knowledge bases.
* Requires manual index builds; no automatic indexing or downloads occur during search.

## Versions
* Developed and tested against Hermes Agent `86ae906e88b280215067c5f9726f2f8cec6178b3`
* QMD `dbfd0b4736aeaf761d1a16ca8e424f071df8feb9`
