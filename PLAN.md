# Implementation plan

No phase below has been implemented. Each phase is independently reviewable and keeps `skill_view` as the only loader.

## Phase 0 — Contract fixtures and compatibility spike

Create a test matrix from pinned Hermes and QMD sources before writing the plugin.

Work:

- capture representative Hermes layouts: profile, external, project override, categorized names, frontmatter aliases, collisions, disabled/platform-filtered skills, quarantined project skills, plugin-qualified skills, nested references, malformed frontmatter, and symlinks;
- capture real QMD JSON for lexical/vector/hybrid results, no collection, empty collection, missing embeddings, stale files, and malformed invocation;
- document the minimum supported Hermes and QMD versions;
- prototype source resolution only in tests to prove canonical load targets against actual `skill_view` results.

Acceptance criteria:

- every fixture expected to be indexed has exactly one canonical `load_name` that `skill_view` accepts;
- ambiguous/unloadable fixtures are excluded with a reason;
- no production package or model-facing tool exists yet;
- contract tests cite/lock Hermes commit `86ae906e...` and QMD commit `dbfd0b47...`.

## Phase 1 — Read-only Hermes compatibility adapter

Implement the smallest isolated adapter that produces resolved skill records.

Work:

- consume `skills_list()` as the visible canonical-name set;
- enumerate profile/project/external/plugin sources using the pinned Hermes behavior;
- reproduce only the necessary precedence, qualification, and ambiguity rules;
- expose an internal record: `skill_id`, `load_name`, `source_dir`, `provenance`, and allowed Markdown files;
- put every import of a private Hermes helper behind one module and version guard.

Acceptance criteria:

- record names equal the visible/explicitly loadable Hermes surface;
- project overrides win exactly where current Hermes makes them win;
- disabled, incompatible, quarantined, excluded-support, and ambiguous entries do not enter the corpus;
- resolving records does not call the registered `skill_view` wrapper, bump skill usage, preprocess skill content, prompt for setup, or mutate files;
- plugin-qualified names remain qualified.

Tests:

- unit tests for path/name normalization and collision cases;
- integration tests against a temporary `HERMES_HOME` and real Hermes imports;
- differential test: for every emitted record, direct `skill_view(load_name, preprocess=False)` resolves the expected source; perform this only in the test suite.

## Phase 2 — Deterministic corpus and manifest builder

Implement operator-controlled corpus generation without invoking QMD yet.

Work:

- copy `SKILL.md` and `references/**/*.md` only;
- reject symlinks, traversal, non-regular files, non-Markdown references, and files outside the resolved skill root;
- generate stable IDs and a versioned manifest with hashes/provenance;
- use private permissions, generation directories, and atomic promotion;
- add stale-generation detection.

Acceptance criteria:

- templates, assets, scripts, unrelated Markdown, and nested preserved skill packages are absent;
- every corpus file has one manifest entry and every manifest entry has one corpus file;
- no absolute source path appears inside indexed documents or model-facing metadata;
- interrupted builds leave the prior valid generation readable;
- identical inputs produce identical IDs, paths, and manifest content.

Tests:

- property tests for arbitrary nested reference paths;
- symlink/path traversal and permission tests;
- snapshot only the manifest schema shape, while asserting behavioral invariants for values;
- fault-injection tests at each atomic-build boundary.

## Phase 3 — QMD lifecycle CLI

Add human/operator commands for doctor, build/refresh, status, and remove.

Work:

- detect QMD executable/version;
- create named index `hermes-skills` and collection `hermes-skills` over the generated corpus with mask `**/SKILL.md,**/references/**/*.md`;
- run update/embed explicitly during build;
- record extension, Hermes, QMD, manifest, and index generation metadata;
- ensure removal targets only validated extension-owned paths and the dedicated named index.

Acceptance criteria:

- build never modifies QMD's default index/config;
- a normal knowledge query cannot see skill-corpus documents;
- a dedicated skill query cannot see a sentinel document from the default knowledge index;
- doctor distinguishes missing executable, incompatible version, missing index, missing collection, missing embeddings, stale corpus, and healthy state;
- build is idempotent; remove is explicit and bounded to resolved targets.

Tests:

- subprocess contract tests with a fake QMD executable;
- end-to-end tests with a real QMD install, tiny local model fixtures where feasible, and temporary XDG/Hermes directories;
- two-way isolation test using unique sentinel terms;
- paths with spaces, Unicode, long paths, and multiple profiles.

## Phase 4 — Retrieval and skill-level ranking library

Implement the read-only query adapter and aggregation before exposing it as a tool.

Work:

- invoke QMD using an argv array, fixed named-index and collection arguments, timeout, minimal environment, and stdout/stderr caps;
- parse JSON and validate every result path through the manifest;
- deduplicate by file, group by skill, apply capped max-plus-RRF scoring, and use deterministic tie-breaks;
- return candidate records without snippets or paths;
- implement structured failure codes from `ARCHITECTURE.md`.

Acceptance criteria:

- multiple chunks from one file count once;
- multiple files from one skill yield one candidate and only a bounded corroboration bonus;
- a skill with many mediocre references cannot outrank a substantially better single hit solely by file count;
- invalid/unknown QMD paths never become skill names;
- output contains no indexed content, snippet, doc ID, or absolute path;
- empty results are successful; operational failures are not reported as empty results.

Tests:

- table-driven ranking/dedup tests, including deterministic ties;
- fuzz malformed JSON, path traversal, unknown paths, extreme scores, duplicate rows, huge output, timeouts, and non-zero exits;
- golden API tests for every structured failure code;
- relevance evaluation set with task-to-expected-skill judgments and recall@5/MRR baseline.

## Phase 5 — Standalone Hermes plugin tool

Register `skill_search` through `PluginContext.register_tool` in a plugin-owned toolset.

Work:

- implement the narrow schema in `ARCHITECTURE.md`;
- add a cheap, profile-scoped availability check without network/model startup;
- make the handler revalidate executable/index state despite cached availability;
- package installation/configuration docs and keep lifecycle commands outside model calls;
- add user guidance that candidates must be loaded through `skill_view`.

Acceptance criteria:

- enabling the plugin adds one model-facing tool; disabling it adds none;
- no core Hermes file or static toolset definition is patched;
- the tool never calls, shadows, or overrides `skill_view`/`skills_list`;
- a returned candidate can be passed verbatim to current `skill_view`;
- missing QMD or an uninitialized index produces the specified actionable failure and never falls back to other QMD collections;
- the system prompt remains byte-stable across searches and index refreshes.

Tests:

- plugin load/unload and profile-scope integration tests;
- real Hermes registry dispatch test with task/session arguments;
- concurrent searches during refresh verify old-or-new atomic generation behavior;
- end-to-end agent test asserts `skill_search` result followed by an ordinary `skill_view` call, with no automatic load.

## Phase 6 — Evaluation and hardening

Evaluate whether full-content search improves discovery enough to justify maintenance.

Work:

- compare compact-description baseline against QMD skill search on a curated, blinded task set;
- measure recall@1/3/5, MRR, false-positive rate, cold/warm latency, index size/build time, and token impact;
- test profile switching, skill edits/install/removal, QMD upgrades, and Hermes latest main;
- security review corpus construction, subprocess boundary, output parsing, and prompt-injection containment.

Acceptance criteria:

- predefined quality/latency thresholds are written before evaluation and met or the feature remains experimental;
- no task leaks normal knowledge documents into skill candidates;
- latest supported Hermes/QMD compatibility CI passes;
- threat-model findings are fixed or explicitly accepted/documented.

## Phase 7 — Upstream proposal decision

Do not propose QMD-specific core code by default. Use evaluation evidence to choose:

1. continue as an external plugin if adoption is niche or QMD-specific;
2. propose a provider-neutral resolved-skill iterator upstream if private-helper compatibility is the main maintenance burden;
3. only propose first-class `skill_search` upstream if usage is broad, measured benefit is material, and it can be service-gated without destabilizing prompt caching or core schemas.

Acceptance criteria:

- an architecture decision record compares measured maintenance cost and discovery benefit;
- any upstream change is independently useful without QMD and includes behavior-contract/E2E tests;
- the external plugin continues working against the last supported Hermes release during upstream review.

## Test strategy summary

The test pyramid is intentionally integration-heavy at security and resolution boundaries:

- **Unit:** normalization, manifest validation, ranking, error mapping, command construction.
- **Property/fuzz:** paths, malformed QMD output, duplicate and adversarial results.
- **Hermes integration:** temporary profiles and real discovery/loading imports; no mocks for precedence/security invariants.
- **QMD contract:** fake executable for exhaustive failures plus real QMD for output and isolation contracts.
- **End to end:** plugin registry -> `skill_search` -> candidate -> existing `skill_view`.
- **Evaluation:** stable judged queries comparing metadata-only discovery with full-content semantic search.

CI should test a pinned known-good pair and a non-blocking/latest-upstream compatibility lane. Failures in the latter become compatibility work, not silent behavior changes.
