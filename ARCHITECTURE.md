# Architecture

## Decision summary

Build this first as a standalone Hermes plugin/extension with one service-gated Python tool named `skill_search`. Its handler invokes the QMD CLI against a dedicated named index, maps hits through an extension-owned manifest, aggregates them by canonical Hermes load target, and returns names only. `skill_view` stays untouched and authoritative.

The extension boundary is preferred for the MVP because Hermes' own contribution guide says capability should live at the edges and third-party product integrations should ship as standalone plugin repositories ([`AGENTS.md`, “The Footprint Ladder” and third-party integrations](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/AGENTS.md)). If the experiment proves broadly useful, the small generic discovery contract—not QMD-specific lifecycle code—can be proposed upstream later.

## Current Hermes skill architecture

### Discovery roots and precedence

Hermes' local source of truth is the active profile's `<HERMES_HOME>/skills`; `_skills_dir()` resolves it at call time so long-lived processes follow profile changes ([`tools.skills_tool._skills_dir`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L148-L161)). `_find_all_skills()` scans, in order:

1. trusted project skill directories from `get_project_skills_dirs()`;
2. the active profile skills directory;
3. configured `skills.external_dirs`.

Project entries are scanned through `iter_project_skill_files`, other roots through `iter_skill_index_files`. First-seen names win in the metadata list; disabled, platform-incompatible, environment-irrelevant, excluded-support, and quarantined project entries are filtered ([`tools.skills_tool._find_all_skills`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L687-L810)). The shared scanner deliberately treats `references`, `templates`, `assets`, and `scripts` below an actual skill root as support content rather than nested skills ([`agent.skill_utils.is_skill_support_path`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/agent/skill_utils.py#L123-L149)).

Plugin-provided skills are a separate namespace. `skills_list` asks the plugin manager for metadata after the filesystem scan; `skill_view` routes names containing `:` through plugin lookup ([`tools.skills_tool.skills_list`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L837-L851), [`tools.skills_tool.skill_view`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L1107-L1205)). Plugin skills therefore need an explicit adapter in the index builder; they must not be guessed from the flat filesystem roots.

### How skills reach the model

At prompt construction, Hermes builds a compact, categorized list from the same roots. It filters by compatibility, disabled state, and available tools/toolsets, gives project-local names precedence, and scans external directories ([`agent.prompt_builder.build_skills_system_prompt`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/agent/prompt_builder.py#L1739-L2105)). The resulting prompt tells the model to call `skill_view(name)` when a skill is relevant. This prompt is a stable per-conversation component; this project will not mutate it mid-session.

Slash commands use the same loader rather than a parallel file reader: `agent.skill_commands._load_skill_payload` calls `skill_view(..., preprocess=False)` and returns the resolved payload for skill-message rendering ([`agent.skill_commands._load_skill_payload`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/agent/skill_commands.py#L232-L269)).

### Exact role and API of `skills_list`

Python API:

```python
skills_list(category: str | None = None, task_id: str | None = None) -> str
```

It returns a JSON string, normally with `success`, `skills`, `categories`, `count`, and a hint. Each skill record is minimal metadata: `name`, `description`, and `category`. `category` filters exact category equality. `task_id` is passed by the registered handler but is not otherwise used by the current function. Errors use Hermes' JSON tool-error form ([`tools.skills_tool.skills_list`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L818-L888)).

Model-tool API:

```json
{
  "name": "skills_list",
  "parameters": {
    "type": "object",
    "properties": {"category": {"type": "string"}},
    "required": []
  }
}
```

It is registered in toolset `skills`, with `check_skills_requirements` (currently always true), and delegates to `skills_list(category=..., task_id=...)` ([`SKILLS_LIST_SCHEMA` and registration](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L1983-L2026)). It is a metadata enumeration endpoint, not full-text search and not a loader.

### Exact role and API of `skill_view`

Python API:

```python
skill_view(
    name: str,
    file_path: str | None = None,
    task_id: str | None = None,
    preprocess: bool = True,
) -> str
```

`name` can be a bare/frontmatter name, a relative categorized path, or a plugin-qualified `plugin:skill`. `file_path` selects a linked file below the resolved skill directory. The function returns a JSON string containing success/content metadata or a structured error ([`tools.skills_tool.skill_view`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L1086-L1106)).

The loader performs behavior that `skill_search` must not copy:

- validates the skill name before path/namespace dispatch;
- resolves project/profile/external roots and frontmatter names;
- detects ambiguous matches and refuses to guess;
- enforces project-skill quarantine, platform compatibility, and disabled state;
- confines `file_path` within the selected skill root;
- preprocesses main content and reports linked files/readiness.

The resolution/collision path is in [`skill_view`, candidates and quarantine](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L1242-L1431); linked-file confinement is in [`skill_view`, `file_path`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L1517-L1594). The model schema requires only `name` and optionally accepts `file_path` ([`SKILL_VIEW_SCHEMA`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L1998-L2015)). Its registered wrapper also deduplicates unchanged repeat views and records usage; the underlying loader remains the authority ([`_skill_view_with_bump` and registration](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/tools/skills_tool.py#L2136-L2187)).

## Proposed components and data flow

```text
Index lifecycle (operator/CLI)                 Retrieval lifecycle (agent)

Hermes active roots + plugin metadata          skill_search(query, limit)
              |                                           |
              v                                           v
      eligibility/resolution adapter             validate/bound arguments
              |                                           |
              v                                           v
 deterministic corpus + manifest       qmd --index hermes-skills query ...
              |                              --format json --collection ...
              v                                           |
 qmd --index hermes-skills update/embed                    v
                                                  parse paths + scores
                                                            |
                                                            v
                                                manifest lookup + group/rank
                                                            |
                                                            v
                                              candidate skill names only
                                                            |
                                                            v
                                               existing skill_view(name)
```

### 1. Hermes adapter

The adapter discovers eligible installed skills using public behavior wherever possible. `skills_list()` supplies the canonical visible name set. The MVP must not import `_find_all_skills` as if it were stable API: the leading underscore and its evolving root/security rules make that high coupling.

Reliable source resolution is the one missing public API. Until Hermes exposes a read-only resolver, the external extension should isolate a thin, version-tested compatibility adapter that mirrors only the pinned resolution required at index-build time. It will enumerate roots through `agent.skill_utils` and plugin metadata, apply the same precedence/eligibility rules, and fail closed on ambiguity. All dependencies on private Hermes symbols live in this single module. Runtime retrieval uses only the extension manifest and does not touch those internals.

An upstream follow-up should propose a small generic API such as `iter_resolved_skills() -> {load_name, source_path, root, provenance}`. That would remove the compatibility adapter without adding a QMD dependency to Hermes core.

### 2. Deterministic corpus and manifest

QMD search results identify documents by `displayPath`; CLI JSON emits this as `file` along with score/title/snippet ([`src.cli.formatter.searchResultsToJson`](https://github.com/tobi/qmd/blob/dbfd0b4736aeaf761d1a16ca8e424f071df8feb9/src/cli/formatter.ts#L94-L127)). Depending on a user's original absolute directory layout would be brittle and could expose paths. Instead, the builder creates an extension-owned corpus:

```text
<profile-cache>/semantic-skills/
  corpus/
    <stable-skill-id>/
      SKILL.md
      references/
        .../*.md
  manifest.json
```

`stable-skill-id` is a non-secret deterministic digest of `(provenance, resolved source root, relative skill directory, canonical load target)`. The manifest maps every indexed relative document path to:

```json
{
  "schema_version": 1,
  "skill_id": "...",
  "load_name": "hermes-agent",
  "source_relative_path": "references/config.md",
  "source_fingerprint": "sha256:...",
  "provenance": "profile"
}
```

Files are copied atomically, not symlinked. This gives QMD one controlled root, prevents symlink traversal after validation, makes returned paths unambiguous, and avoids leaking absolute source paths into results. A generation directory plus atomic pointer/rename prevents queries from observing a half-built corpus.

Canonical `load_name` is decided at build time:

- use the frontmatter name that Hermes exposes when it is uniquely loadable;
- use the relative categorized path when Hermes requires it to disambiguate a filesystem collision;
- plugin skills are explicitly unsupported in this MVP;
- omit any entry whose load target cannot be proven to resolve under the pinned Hermes rules.

Never derive a skill name at query time by taking `Path(file).parent.name`; references can be nested, frontmatter names can differ from directory names, and plugin/collision names are qualified.

### 3. QMD index model and isolation

Use a dedicated QMD **named index** `hermes-skills`, not QMD's default index. QMD resolves `--index <name>` separately; named indexes use distinct YAML and SQLite state, while project-local indexes are another independent mode ([`src.cli.qmd` index selection](https://github.com/tobi/qmd/blob/dbfd0b4736aeaf761d1a16ca8e424f071df8feb9/src/cli/qmd.ts#L3085-L3101), [QMD index locations](https://github.com/tobi/qmd/blob/dbfd0b4736aeaf761d1a16ca8e424f071df8feb9/README.md#L700-L713)). Within it, create exactly one collection, also named `hermes-skills`, rooted at the generated corpus.

Its mask is the union:

```text
**/SKILL.md,**/references/**/*.md
```

QMD supports comma-separated masks as a union and defaults to Markdown globbing ([collection CLI](https://github.com/tobi/qmd/blob/dbfd0b4736aeaf761d1a16ca8e424f071df8feb9/src/cli/qmd.ts#L4438-L4475), [mask documentation](https://github.com/tobi/qmd/blob/dbfd0b4736aeaf761d1a16ca8e424f071df8feb9/README.md#L733-L758)). Do not index `templates`, `scripts`, `assets`, category `DESCRIPTION.md`, generated website docs, or any file outside a resolved skill root.

Every query supplies both:

```text
--index hermes-skills --collection hermes-skills
```

The double scope is intentional defense in depth. No unscoped QMD call is permitted. The extension does not add the corpus to the user's default QMD config, and normal knowledge collections are never added to the named skills index. Tests assert both directions of isolation.

### 4. Search adapter

Recommended internal invocation:

```text
qmd --index hermes-skills query <query>
    --collection hermes-skills
    --format json
    -n <candidate-file-limit>
```

QMD's current CLI supports hybrid `query`, collection filtering, JSON output, result limits, and named indexes ([search options](https://github.com/tobi/qmd/blob/dbfd0b4736aeaf761d1a16ca8e424f071df8feb9/README.md#L840-L900)). Arguments are passed as a subprocess argv array with `shell=False`; the query is never interpolated into a shell command.

The model-facing schema should stay small:

```json
{
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
```

Register it from the plugin via `PluginContext.register_tool`, which delegates to the central registry ([`hermes_cli.plugins.PluginContext.register_tool`](https://github.com/NousResearch/hermes-agent/blob/86ae906e88b280215067c5f9726f2f8cec6178b3/hermes_cli/plugins.py#L1720-L1778)). Put it in a plugin-owned toolset and use a cheap `check_fn` that checks configured enablement plus executable presence without running models or network calls. It should not override `skills_list` or `skill_view` and should not require changes to `toolsets.py`.

## CLI versus Hermes MCP infrastructure

QMD's MCP server is real and Hermes supports it. QMD registers `query`, `get`, and `status`; `query` accepts collection filters and returns `structuredContent.results` with file, score, line, and snippet ([`src.mcp.server.createMcpServer`](https://github.com/tobi/qmd/blob/dbfd0b4736aeaf761d1a16ca8e424f071df8feb9/src/mcp/server.ts#L170-L398)). Hermes dynamically registers MCP tools into server-specific toolsets.

Nevertheless, direct QMD MCP configuration is not the right MVP boundary:

- it exposes generic knowledge-search and document-read tools rather than one names-only skills contract;
- collection restriction remains a model-supplied argument, so accidental cross-corpus queries are possible if other collections share the server/index;
- it gives the model snippets/content that this MVP deliberately withholds;
- the extension would need to call another registered model tool or implement an MCP client merely to post-process it;
- users would pay the schema footprint of QMD's generic tools in addition to `skill_search`.

The CLI is preferable because it provides machine-readable JSON and lets the adapter force `--index` and `--collection`. It also makes missing executable, timeout, exit code, stdout size, and malformed JSON behavior straightforward to test. QMD's MCP mode remains a valid alternative for a later warm daemon optimization, but only behind the same adapter contract and with an extension-owned, skills-only server/index.

## Retrieval, deduplication, and ranking

QMD already deduplicates hybrid results by file and reranks chunks rather than whole bodies ([`src.store.hybridSearchQuery`](https://github.com/tobi/qmd/blob/dbfd0b4736aeaf761d1a16ca8e424f071df8feb9/src/store.ts#L5668-L5743)). The extension must add a second, skill-level aggregation because several files can map to one skill.

For each valid QMD result:

1. normalize the result path as a POSIX relative path; reject absolute paths, traversal, unknown files, and entries absent from the manifest;
2. map it to `skill_id` and `load_name` through the manifest;
3. retain only the best hit per `(skill_id, source_relative_path)` (defensive against repeated result rows);
4. rank each skill with reciprocal-rank fusion over distinct file hits:

```text
skill_score = max(normalized_qmd_score)
              + 0.10 * sum(1 / (60 + result_rank)) for other distinct files
```

5. cap the corroboration bonus at `0.05`, sort by `(skill_score desc, best_result_rank asc, load_name asc)`, and return at most `limit` skills.

The max score preserves QMD's primary ranking; the small capped RRF bonus rewards independent evidence without allowing a skill with many reference files to swamp a better match. Multiple chunks from one file contribute once. `SKILL.md` and reference hits receive no arbitrary fixed boost in the first MVP; relevance should be measured before adding one. Return rounded adapter scores, `matched_files`, and whether the best hit came from `SKILL.md`, but no snippet or source path.

Fetch more file results than requested skills—initially `min(50, max(20, limit * 5))`—so grouping does not collapse a requested top five into one skill. Make this internal and benchmark-driven.

## Index lifecycle

Index mutation is operator-driven:

1. **doctor** checks Hermes compatibility, QMD version/executable, named-index state, corpus/manifest schema, and stale fingerprints;
2. **build** resolves active skills, validates paths, copies only allowed Markdown, writes the manifest/corpus atomically, creates or repairs the `hermes-skills` collection, runs QMD update and embed, then records the Hermes/QMD versions and generation fingerprint;
3. **search** is read-only and refuses a missing, incomplete, incompatible, or stale-enough-to-be-unsafe generation; ordinary content staleness can be reported as a warning according to a configured policy;
4. **refresh** repeats build after skills are installed, removed, enabled/disabled, or edited;
5. **remove** deletes only extension-owned corpus state and the dedicated QMD named index after explicit operator confirmation.

The MVP does not rebuild during `skill_search`: model calls must have bounded latency and must not trigger model downloads or index mutations.

## Failure behavior

All expected failures return bounded structured JSON and never fall back to ordinary knowledge RAG or `skills_list` search.

| Condition | Tool behavior | Operator hint |
|---|---|---|
| QMD executable absent | `success:false`, `code:"qmd_missing"` | Install QMD, then run project doctor/build command |
| Dedicated named index/config absent | `code:"index_not_initialized"` | Run explicit init/build command |
| Collection absent or empty | `code:"collection_not_initialized"` | Rebuild `hermes-skills` |
| Embeddings absent/model unavailable | `code:"search_unavailable"`; include bounded QMD stderr | Run embed/doctor; no lexical fallback in semantic MVP |
| QMD timeout | terminate child, `code:"qmd_timeout"` | Retry after models are warm or run doctor |
| Non-zero exit/malformed/oversize JSON | `code:"qmd_error"` | Include exit status and a redacted, truncated diagnostic |
| Unknown result path/manifest mismatch | discard hit; if all invalid, `code:"index_inconsistent"` | Rebuild; log rejected paths |
| No hits | `success:true`, empty `candidates` | Agent may use compact list or proceed without a skill |
| Candidate later rejected by `skill_view` | surface `skill_view` result unchanged | Search is advisory; never retry another loader path automatically |

The `check_fn` may hide the tool when QMD is not configured, but the handler must still defend every call because executable/index state can change after registry availability caching.

## Security and privacy

- Treat skill text and QMD output as untrusted data. Search returns names and numeric metadata only, preventing snippets from becoming a new prompt-injection channel.
- Validate source files with resolved-path containment, reject symlinks for the MVP, and copy only regular `.md` files matching the allowlist.
- Reuse Hermes eligibility/quarantine decisions at build time. Never use QMD membership as proof a skill is safe or enabled.
- Invoke QMD with an argv array, a minimal inherited environment, fixed index/collection names, timeout, output cap, and `shell=False`.
- Store corpus/index state in profile-scoped private directories with restrictive permissions. Do not print absolute source paths in model-facing results.
- Verify the manifest schema and corpus paths before trusting a hit. Atomic generations prevent time-of-check/time-of-use mixing during rebuilds.
- QMD is local software but model downloads and optional collection update commands can cause network/process activity. Search never runs `qmd update`, collection update hooks, installation, or downloads.
- Plugin skills may be third-party content. Index only skills that Hermes currently exposes and preserve namespace/provenance in the manifest.

## Alternatives considered

### Extend `skills_list(query=...)`

Rejected for the external MVP. It would change a core tool's stable metadata role, couple core Hermes to QMD, and make a normally cheap call depend on an external index. A future upstream generic search-provider hook could reuse the name, but only with demonstrated demand.

### Add `skill_search` directly to Hermes core

Rejected initially. It adds permanent schema footprint and a third-party dependency. A service-gated upstream tool could be revisited if semantic discovery becomes broadly expected and a provider-neutral interface exists.

### Configure QMD only as a generic MCP server

Rejected for this contract because it exposes generic search/read tools and cannot guarantee names-only output or mandatory corpus scoping without an adapter.

### Search raw skill roots directly with QMD

Rejected. Multiple roots, frontmatter aliases, project precedence, plugin namespaces, collisions, nested references, and absolute path disclosure make query-time path inference unreliable.

### Index only `SKILL.md`

Too narrow for the stated problem: reference documents contain the detailed vocabulary that metadata and even the main skill file may omit. The allowlist stops at Markdown references to avoid turning executable/support assets into RAG content.

### Return snippets or automatically call `skill_view`

Rejected. Snippets expand the injection and token surface, while automatic loading conflates advisory retrieval with Hermes' authoritative, security-aware loader. The MVP returns candidates only.

## Maintenance direction

Maintain the working QMD integration externally first. Pin supported Hermes and QMD ranges, keep all private-Hermes compatibility logic in one adapter, and run contract tests against both pinned commits and latest upstream CI.

The best upstream proposal is small and provider-neutral:

1. a public read-only resolved-skill iterator containing canonical load target and source path;
2. optionally, a plugin-visible way to attach discovery tools to the existing `skills` toolset without editing static `toolsets.py`;
3. no QMD dependency, corpus manager, or ranking policy in Hermes core.

If upstream later wants first-class semantic discovery, this extension becomes the QMD provider/reference implementation rather than being copied wholesale into core.
