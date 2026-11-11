# FFFlow Plugin

A Claude Code plugin providing a complete development lifecycle — plan, work, audit — scaling from informal prose specs (L0) to full FFFlow rigor (L3).

**Build spec:** [`docs/architecture.md`](docs/architecture.md). That document is authoritative for this plugin's design. Skill design, naming, and review decisions are anchored to it.

## What FFFlow is

Three artifacts, three roles, three locations:

| Artifact | Tense | Lifespan | Location | Owns |
|---|---|---|---|---|
| **Spec** | Present | Evergreen | Codebase (`docs/specs/`, `specs/`, or per-module CLAUDE.md) | Behavioral contract |
| **Plan** | Future | Transient | `/tmp/ffflow-plans/<project-hash>/<slug>/` | Design decisions for one change |
| **Issues** | Imperative | Transactional | Issue tracker (GH/Linear/Jira/markdown) | Work-to-be-done |

The spec describes end state. The plan describes the path. The issues are the chess moves.

## The L0–L3 dial

Same skills at every level. What changes:

- **L0** — informal prose specs, standard TDD, lint+test gates
- **L1** — structured prose, hexagonal layering, defect-driven specs
- **L2** — Gherkin scenarios, spec-first development, contract enforcement
- **L3** — full FFFlow: RID traceability, mutation testing, four quality gates

A project declares its level in `.ffflow/config.yaml`. No config = L0.

## Architectural invariants

These shape every skill. Full text in [`docs/architecture.md`](docs/architecture.md) §2.

1. **Three artifacts, three roles, three locations** (above).
2. **Specs and tests move together.** A spec entry without a test is documentation. A test without a spec entry is opaque.
3. **Three planning entry points, one downstream.** `characterize`, `plan-chat`, and `audit --plan` all produce plans. They converge on `plan-breakdown → plan-capture → work`.
4. **Methodology dial shapes formality, not workflow.** Same skills, different artifact format and gate strictness per level.
5. **Audit is the keep-honest layer.** Per-type auditors are small and focused. The `audit` skill coordinates only.
6. **Red/Green TDD is the execution discipline.** Spec → red → green → refactor → spec update → gates → PR. Same loop at every level — wherever it's practical. A few edges genuinely resist a failing test first (spikes, scaffolding, unharnessed I/O, an unreproducible defect); those exceptions get *named* in the PR, never taken silently. "Hard to test" isn't one of them — that's design feedback. Full text in `docs/architecture.md` §2.6.
7. **Naming convention: memorable prefix first.** `/audit --type claude-md`, not `claude-md-audit`. `plan-chat`, not `chat-for-planning`. Optimize for what a tired developer types.
8. **Skills only.** No commands. No agents. No MCP servers. Every entry point is a skill.
9. **View-layer purity — hexagonal, rotated onto the view.** The component layer is the frontend's domain: pure, presentational, storied and tested in isolation with zero model/logic/backend dependency. The app is the adapter. Dependencies point view ← app, never the reverse. Decompose → story → test → *then* integrate. Rulebook: `component-driven-ui`; toolchain: `typescript-ui` stack cartridge; gate: `/audit --type ui`. Full text in `docs/architecture.md` §2.9.
10. **Hierarchical CLAUDE.md is how the codebase explains itself.** Every significant module carries its own CLAUDE.md — a tree mirroring the module tree, not the root file alone. Claude Code loads them by proximity to the work, making them the only context-routing mechanism that fires *before* the model decides what to look at. Locality beats volume; the root stays a map; freshness becomes scopeable; at L0/L1 it's often where the spec lives. A 2-line CLAUDE.md is better than none. Enforced by `/audit --type claude-md` (high severity for a missing top-level module doc). Full text in `docs/architecture.md` §2.10.
11. **Beliefs are stamped into the project, not just professed by the plugin.** A downstream session reads *that project's* CLAUDE.md, never this one. So `init-ffflow` writes a managed, versioned beliefs block into the project root CLAUDE.md (`<!-- ffflow:beliefs ... -->`), and `upgrade-ffflow` keeps it current. Machine-owned inside the markers, human-owned everywhere else. Every belief names its enforcing skill. Full text in `docs/architecture.md` §2.11.

## Plugin layout

```
ffflow/                                # repo root (also the marketplace)
├── .claude-plugin/
│   └── marketplace.json               # marketplace entry; source: "./plugin"
├── README.md                          # User-facing intro (marketplace level)
└── plugin/                            # the actual plugin
    ├── .claude-plugin/
    │   └── plugin.json
    ├── CLAUDE.md                      # This file
    ├── tests/                         # unittest suite for skill scripts (see Tests)
    ├── docs/
    │   ├── architecture.md            # Build spec (authoritative)
    │   ├── levels.md                  # The L0–L3 dial explained
    │   ├── workflows.md               # Lifecycle flows
    │   └── audit.md                   # Audit subsystem
    └── skills/
        └── <skills>                   # See docs/architecture.md §5 for the full catalog
```

## Build order

The plugin is large. Built in phases — see [`docs/architecture.md`](docs/architecture.md) §10.

- **Phase 1** — L0/L1 planning spine (`init-ffflow`, `plan-roadmap`, `plan-chat`, `plan-breakdown`, `plan-capture` (with `github-issues` cartridge), `plan-status`).
- **Phase 2** — Execution (`work-issue`, `work-epic`, `work-fanout`, `autopilot`, `tdd-loop`, `self-review`, `worktrees`, `stack` (with python + typescript cartridges), `stack-init`, `stack-assess`).
- **Phase 3** — Audit foundation (`audit` skill with `claude-md` cartridge active; `ci-gates`).
- **Phase 4** — Brownfield + characterize (`characterize`, `adopt-ffflow`, `defect-driven-specification`).
- **Phase 5** — Spec-level rigor (additional `audit` cartridges: `spec`, `char-tests`, `architecture`, `refactor`; `hexagonal-architecture`, `refactor` skill).
- **Phase 6** — L2/L3 methodology (`writing-specs`, `spec-first-development`, `contract-enforcement`, `rid-traceability`, `total-specification`, `quality-gates`, `audit`'s `rid` cartridge).
- **Phase 7** — Breadth (remaining capture backends, stacks, justfile patterns, dev tools, `zero-tech-debt`, `yagni`, `audit`'s `tech-debt` cartridge).

## Cross-cutting conventions

When authoring or editing skills, enforce these. Full text in `docs/architecture.md` §7.

- **Plan Mode discipline.** Skills that interact about future actions must NOT invoke `EnterPlanMode`. State this explicitly at the top of the skill body. Required for: `plan-chat`, `plan-breakdown`, `characterize`, `work-issue`, `work-fanout`.
- **Decision-marker convention.** Open decisions in plans/specs are marked with `?` at the start of the line, or in a `## Open decisions (?)` section. Resolving a decision **removes** the marker (rewrite `## ? D1` → `## D1 (resolved)`); don't leave archival `## ?` headings — the `plan-breakdown` gate keys on open markers and stale ones trip it. Full rule: `docs/architecture.md` §7.2.
- **PR-checkpoint protocol.** `work-issue`/`work-fanout` post a one-line summary after every PR; pause for confirmation after every 2 PRs in an unattended session.
- **Local-validation gate.** `work-issue` does not push a non-spec-only PR without either a local repro/smoke pass, or an explicit statement in the PR body explaining why local validation wasn't possible.
- **Idempotency.** Every state-writing skill detects existing state and updates rather than duplicating.
- **Resume-ability.** Long-running skills persist state to disk between meaningful steps.
- **Memorable typeahead names.** Distinctive word first.

## Tests

```
python3 -m unittest discover -s plugin/tests -v
```

Run from the repo root; stdlib only. Run it whenever `plugin/` changes; it must pass before a release.

Skills are prose. When a skill needs deterministic logic (parsing, joining, rendering), it ships a stdlib-only Python script in its own folder (`skills/<skill>/<script>.py`) and invokes it via `${CLAUDE_PLUGIN_ROOT}`. Each script has one test module here, `test_<skill>.py` (hyphens become underscores), which loads the script by path. Keep the logic a pure function of its inputs, with git, `gh` and the filesystem at the edges, so tests feed it data instead of calling them.

## Related projects

- **ffflow** — Methodology documentation and examples
- **specdrive** — [language-agnostic CLI](https://github.com/bryonjacob/specdrive) for Gherkin behavioral contract management (used by `/audit --type rid` at L3). Distributed on npm and run via `npx specdrive`; audits `.feature` files + JUnit XML, so it works for any stack (Python, Java, Rust, TypeScript) — npm is its install channel, not a language constraint.
- **quickpickle-property** — BDD+PBT plugin for TypeScript (L2+ TypeScript stacks)
- **pytest-bdd-property** — BDD+PBT plugin for Python (L2+ Python stacks)
