# FFFlow Plugin — Implementable Specification and Roadmap

A self-contained Claude Code plugin that provides a complete development lifecycle: plan, work, and audit, scaling from informal prose specs (L0) to full FFFlow rigor (L3).

This document is the build spec. It captures architecture, naming conventions, skill catalog, dependencies, build phases, and the discipline FFFlow encodes.

---

## 1. Plugin Identity

**Name:** `ffflow`
**Type:** Claude Code plugin
**Marketplace:** ffflow marketplace, single plugin
**Architecture:** Skills only — no commands, no agents, no MCP servers
**Standalone:** Requires no other plugins. Reads no aug-* skills. Performs no cross-plugin lookups. Source material from aug-dev / aug-core / aug-just is reference only.

**Replaces (for users who adopt it):**
- `aug-dev` entirely
- `aug-core:automate`, `aug-core:notetoself`, `aug-core:hemingway`, `aug-core:learn`, `aug-core:patterns`, `aug-core:suggest`
- `aug-just` (justfile patterns folded in)
- Standalone `docsaudit` command (folded into the audit subsystem)

**Coexists with (but does not depend on):** Any other plugin. FFFlow defines its own state, its own conventions, its own commands-as-skills.

---

## 2. Architectural Invariants

These shape every skill. Listed first because they govern review and design decisions throughout implementation.

### 2.1 Three artifacts, three roles, three locations

| Artifact | Tense | Lifespan | Location | Owns |
|---|---|---|---|---|
| **Spec** | Present | Evergreen | Codebase (`docs/specs/`, `specs/`, or per-module CLAUDE.md) | Behavioral contract |
| **Plan** | Future | Transient | `/tmp/ffflow-plans/<project-hash>/<slug>/` | Design decisions for one change |
| **Issues** | Imperative | Transactional | Issue tracker (GH/Linear/Jira/markdown) | Work-to-be-done |

The spec describes end state. The plan describes the path. The issues are the chess moves.

### 2.2 Specs and tests move together

A spec entry without a test is documentation. A test without a spec entry is opaque. At every level, both move together — the formality varies, the pairing doesn't.

### 2.3 Two-tier planning, one downstream

Planning is tiered.

**Tier 1 — `plan-roadmap`.** Phase-level. Reads a vision (project.md / README / prompt) or surveys an existing codebase, produces an ordered, dependency-aware list of independently shippable phases. Used when starting a green-field project, adding a multi-phase capability, or re-orienting around a new direction.

**Tier 2 — three entries, each handling one phase of a roadmap (or operating standalone for single-slice work):**

- `characterize` — when a phase needs spec extraction from existing code (brownfield surface).
- `plan-chat` — when a phase is a design slice (single chess move or small cluster).
- `audit` with `--plan` — when a phase is drift cleanup.

All four converge on `plan-breakdown → plan-capture → work-*`.

Single-slice changes can skip Tier 1 and go straight to Tier 2 (typically `plan-chat`). Drift cleanup goes straight to `audit --plan`. The roadmap exists for scopes larger than one slice.

### 2.4 Methodology dial (L0–L3) shapes formality, not workflow

Same skills at every level. What changes:
- Artifact format (prose vs. structured prose vs. Gherkin vs. full FFFlow)
- Required test conventions
- Audit gates enforced

A project declares its level in `.ffflow/config.yaml`. No config = L0.

### 2.5 Audit is the keep-honest layer

Anything worth keeping aligned with reality gets an auditor. Per-type auditors are small and focused. The `audit` skill is coordinator-only. Audits can run interactively, as CI checks, or on schedules. Findings can convert to plans.

### 2.6 Red/Green TDD is the execution discipline

Every chess move executed by `work-issue` follows this loop:
1. Read the current spec and the chess move's acceptance criteria
2. Write or update the test(s) that will pin the new behavior
3. Run them. They must fail. (Red.)
4. Write the minimum code to make them pass. (Green.)
5. Refactor under green if needed
6. Update the spec to reflect the new behavior, in the same PR
7. Run all gates appropriate for the project's level
8. Open the PR

At L0/L1 this is standard TDD. At L2 the test is a Gherkin scenario. At L3 the audit verifies the loop's completeness. The loop is the same; the artifacts scale.

**Wherever it's practical — and the exceptions are named, not silent.** Red-then-green is the default and the overwhelming majority case, but some work genuinely resists a failing-test-first opening:

- **Exploratory spikes**, where the point is to learn what the behavior should even be. Spike, then throw it away and do it properly red-first.
- **Config, scaffolding, and pure wiring** with no behavior of its own to pin.
- **I/O that can't be harnessed yet** — the test needs a seam that doesn't exist. Often the honest move is a chess move that builds the seam first.
- **A defect you can't reproduce yet.** Reproduce first if you possibly can (`defect-driven-specification` exists for exactly this); when you truly can't, characterize what you *can* observe.

When a step lands on one of these edges, **say so and say what you did instead** — in the PR description, and in the spec entry if the gap is durable. The discipline doesn't erode because someone skipped red once with a reason; it erodes because skipping stopped being remarkable. An acknowledged exception is a data point. A silent one is decay.

This is the one place where "wherever practical" is a real qualifier rather than a hedge — it does *not* license reaching for the exception when the test is merely inconvenient to write. A test that's hard to write is usually telling you something true about the design (§ `refactor`), and that signal is most of TDD's value.

### 2.7 Naming convention: memorable prefix first

Skill names are typeahead-friendly. The most distinctive word comes first.

- ✅ `python-stack`, `/audit --type claude-md`, `plan-chat`, `work-fanout`
- ❌ `configuring-python-stack`, `documenting-with-audit`

When in doubt, optimize for: what would a tired developer type when they want this thing?

### 2.8 Skills only

No commands. No agents. No MCP servers. Every entry point is a skill. Skills can call other skills via the Skill tool. Skills can launch agents via the Agent tool for parallel work — but the agent is invoked by the skill, not defined as part of the plugin's API.

### 2.9 View-layer purity — the frontend sibling of hexagonal

The hexagonal dependency rule (§ the `hexagonal-architecture` rulebook) is not a backend-only idea. Rotated onto the view, it becomes FFFlow's UI philosophy:

**The component layer is the frontend's domain.** It is pure and presentational — built, storied, and tested in complete isolation, with **zero dependency on model, logic, or backend**. The app wiring (data fetching, state, routing, use-case calls) is the *adapter*: it plugs data into components that were already proven on their own. Dependencies point **view ← app**, never the reverse. A presentational component that imports from `app/`, `api/`, or `store/` is the frontend equivalent of a `PostgresConnection` leaking into a domain entity — forbidden.

Four consequences, which the `component-driven-ui` rulebook makes concrete:

1. **A design language of components.** Components consume design tokens (color, spacing, type), never raw literals. FFFlow prescribes a default baseline (Radix headless primitives + a token layer + shadcn-style *owned* components), overridable in `.ffflow/stack.yaml`.
2. **Stories as vignettes of state.** Every atom, molecule, organism, and layout gets Storybook stories covering its *reasonable states* — empty, loading, error, populated, edge, disabled, dark/RTL, overflow, long-i18n. A component's stories are the visual catalog of every state we expect it to reach.
3. **Fast tests, near-total coverage.** Storybook interaction tests plus fast component unit tests run on every build. The bar rises with level, reaching near-100% at L3.
4. **Decompose → story → test → *then* integrate.** A feature is decomposed into components; each is storied and tested in isolation; they are assembled upward to the point of app assembly and tested there; **only then** does anything touch the app's own TS files. This ordering forces UI to be designed divorced from the backend — the whole point of the rule.

Like hexagonal, this is a **dial, not an absolute** (§2.4): encouraged at L0, recommended at L1, CI-enforced at L2, blocking with coverage + token-conformance gates at L3. Enforced by `/audit --type ui`; the ordering gate lives in `work-issue`.

### 2.10 Hierarchical CLAUDE.md is how the codebase explains itself

**Every significant module carries its own CLAUDE.md.** Not the root file alone — a tree of them, mirroring the module tree. This is not a stylistic preference or an emergent precedent that a repo may or may not have set. It is load-bearing infrastructure, and it is the single highest-leverage thing an FFFlow project does for the sessions that work in it.

The reasoning is mechanical, not aesthetic. Claude Code loads CLAUDE.md files by proximity to the work: a session editing `src/payment/refund.ts` gets `src/payment/CLAUDE.md` in context automatically, without searching, without being told, without spending a single tool call. That is a **context-routing mechanism**, and it is the only one that operates before the model has decided what to look at. Conventions that live in a module's CLAUDE.md are enforced by default. The same conventions written as prose in the root file are diluted by everything else in that file; written in a skill, they load only when someone invokes the skill; written in a code comment, they are found only by whoever already opened the right file.

So the hierarchy is what converts documentation from *retrievable* into *unavoidable*:

1. **Locality beats volume.** A 40-line module CLAUDE.md next to the code outperforms 400 lines in the root, because it arrives without being asked for and carries no unrelated noise.
2. **The root file stays a map, not an encyclopedia.** Root owns purpose, architecture overview, module index, stack, and the beliefs block (§2.11). Module-specific rules belong to the module. Without the hierarchy, the root file grows until it is too big to be read carefully — and the audit cartridge's 500-line sanity check starts firing.
3. **Scoped freshness becomes possible.** `.ffflow/audit.yaml` pins each CLAUDE.md to a commit and a path scope. Drift on `src/auth/**` invalidates `src/auth/CLAUDE.md` and nothing else. One monolithic root file has one scope — `**/*` — so *every* change makes it stale, which makes staleness meaningless.
4. **It is the spec's habitat at L0/L1.** §2.1 names per-module CLAUDE.md as a legitimate spec location. At lower levels it is often the *only* one. No hierarchy, no place for the spec to live.

**A 2-line CLAUDE.md is better than none.** Context is cheap; a session guessing at conventions is expensive. The failure mode this invariant exists to prevent is not an under-documented module — it is a session declaring a convention "unprecedented" because the repo never told it otherwise, and then setting a *different* precedent.

Enforced by `/audit --type claude-md` (coverage gaps in a top-level module are **high** severity). Seeded by `init-ffflow`, extended by `stack-init` and `work-issue` when they create new modules, and retrofitted by `upgrade-ffflow`. Like every FFFlow rule it scales with the dial (§2.4) — advisory at L0, expected at L1, audited in CI at L2, blocking at L3 — but unlike most, its *floor* is non-zero at every level: the root CLAUDE.md and the beliefs block are required even at L0.

### 2.11 Beliefs are stamped into the project, not just professed by the plugin

A methodology the plugin believes in but the repo never states is **not in effect**. Sessions working in a downstream project read *that project's* CLAUDE.md; they do not read this plugin's design docs. Every invariant above is therefore invisible at the moment it matters unless the project itself says it out loud.

So `init-ffflow` stamps a **managed beliefs block** into the project's root CLAUDE.md, delimited by markers:

```markdown
<!-- ffflow:beliefs v0.4.0 — managed by /fff:upgrade-ffflow. Edits inside this block are overwritten. -->
## FFFlow beliefs
...
<!-- ffflow:beliefs end -->
```

Three properties make this work:

- **Machine-owned, idempotent region.** `upgrade-ffflow` rewrites what is between the markers and never touches a byte outside them. The rest of the root CLAUDE.md belongs entirely to the humans and to `/audit --type claude-md`.
- **Versioned.** The marker carries the FFFlow version that wrote it, so drift between a repo's stated beliefs and the current methodology is detectable by string comparison, not inference.
- **Named enforcement.** Every belief names the skill that enforces it. A belief with no enforcer is a slogan; a belief with an enforcer is a contract the session can act on.

The block states the non-negotiables only — the rules a session must not have to discover. It is deliberately short. A beliefs block that grows into a second architecture document defeats its own purpose, because it stops being read.

---

## 3. Plugin Layout

```
ffflow/                                # repo root (also the marketplace)
├── .claude-plugin/
│   └── marketplace.json               # marketplace entry; source: "./plugin"
├── README.md                          # User-facing intro (marketplace level)
└── plugin/                            # the actual plugin
    ├── .claude-plugin/
    │   └── plugin.json
    ├── CLAUDE.md                      # Plugin docs for Claude
    ├── docs/
    │   ├── architecture.md            # Build spec (this file)
    │   ├── levels.md                  # The L0–L3 dial explained
    │   ├── workflows.md               # Lifecycle flows
    │   ├── audit.md                   # Audit subsystem
    │   └── migrations.md              # Migration ledger read by upgrade-ffflow
    └── skills/
        ├── init-ffflow/               # Setup
        ├── upgrade-ffflow/            # Reconcile a project against the current plugin version
        ├── plan-roadmap/              # Tier-1 planning: phase out a vision or large capability
        ├── plan-chat/                 # Tier-2 planning: design one slice (resolves all open decisions inline)
        ├── plan-breakdown/            # Cut plans into chess moves
        ├── plan-capture/              # Write issues to tracker (cartridges: github-issues, linear, jira, markdown)
        ├── plan-status/               # Show in-flight plans
        ├── pipeline-status/           # Roll every roadmap and its epics up into one view (text or JSON)
        ├── pipeline-next/             # What to do next per roadmap, from pipeline-status's data
        ├── characterize/              # Planning entry: brownfield bootstrap
        ├── work-issue/                # Execute one issue → one PR
        ├── work-epic/                 # Execute an epic's issues → one PR per epic (sequential, squashed per task)
        ├── work-fanout/               # Parallel multi-issue execution (one PR per issue)
        ├── autopilot/                 # Meta: run any skill unattended
        ├── audit/                     # Audit coordinator (cartridges: claude-md, spec, char-tests, architecture, refactor, rid)
        ├── tdd-loop/                  # The red/green/refactor discipline
        ├── writing-specs/             # L2+ Gherkin conventions
        ├── hexagonal-architecture/    # L1+ architectural reference
        ├── component-driven-ui/       # L1+ view-layer purity reference (UI sibling of hexagonal)
        ├── spec-first-development/    # L2+ TDD-with-specs discipline
        ├── defect-driven-specification/ # L1+ bug-becomes-spec discipline
        ├── contract-enforcement/      # L2+ mocks-vs-real-contracts
        ├── rid-traceability/          # L3 RID format and lifecycle
        ├── total-specification/       # L3 full FFFlow methodology
        ├── quality-gates/             # L3 four-gate model
        ├── stack/                     # Stack reference (cartridges: python, typescript, java, polyglot)
        ├── stack-init/                # Bootstrap stack into project
        ├── stack-assess/              # Compare project to declared stack
        ├── justfile/                  # Justfile interface + maturity (cartridges: Tier 1–4 patterns)
        ├── refactor/                  # Coverage/complexity-driven refactoring
        ├── debugging/                 # Hypothesis-driven debugging
        ├── self-review/               # Pre-PR self-review
        ├── worktrees/                 # Isolated worktree management
        ├── git-hooks/                 # Pre-commit/pre-push setup
        ├── ci-gates/                  # GitHub Actions integration
        ├── notetoself/                # Context save/resume
        ├── hemingway/                 # Concision discipline for prompts
        ├── zero-tech-debt/            # Review-time: fix nits in-flight
        ├── yagni/                     # Tension partner: TODO-with-trigger for legit deferrals
        └── adopt-ffflow/              # Greenfield/brownfield onboarding
```

37 skills total (cartridges fold variants like capture backends, stack languages, and audit types into one entry per family). Built in phases (see §10). `component-driven-ui` is the view-layer sibling of `hexagonal-architecture`; its toolchain lives in the `typescript-ui` stack cartridge and its keep-honest gate in the `ui` audit cartridge.

---

## 4. Configuration

### 4.1 `.ffflow/config.yaml`

Created by `init-ffflow`. Single source of truth for project-level FFFlow state.

```yaml
version: 1                             # config *schema* version (not the plugin version)
ffflow_version: 0.4.0                  # plugin version this repo was last reconciled against
ffflow_upgraded: 2026-08-23            # date of that reconciliation
level: L1                              # L0 | L1 | L2 | L3
stack: typescript                      # references stack skill
capture: github-issues                 # references capture skill

# Optional overrides
spec_location: docs/specs              # where evergreen spec lives
test_location: tests                   # where tests live
audit_state_file: .ffflow/audit.yaml

# Level-specific
features:
  property_based_testing: false        # L2+
  mutation_testing: false              # L3
  rid_traceability: false              # L3
  four_quality_gates: false            # L3
```

**Two version fields, deliberately distinct.** `version` is the schema version of this file — bump it only when the config's *shape* changes in a way that needs migration logic. `ffflow_version` is the **plugin version the repo was last reconciled against**, written by `init-ffflow` on bootstrap and re-written by `upgrade-ffflow` after a successful upgrade run. They move independently: most plugin releases change methodology without changing the config shape.

**A missing `ffflow_version` means "pre-0.4.0, exact version unknown."** Stamping began in 0.4.0, so any repo adopted before it has no stamp. This is not an error state — `upgrade-ffflow` handles it by duck-typing (§ the `upgrade-ffflow` skill): it walks every migration entry from 0.1.0 forward, runs each entry's detection heuristic against the repo, infers which changes already landed, and applies only the genuine gaps. The unstamped case is expected, supported, and self-healing — it happens exactly once per repo.

### 4.2 `.ffflow/audit.yaml`

Maintained by `audit` and its sub-auditors. Tracks state for everything keep-honest.

```yaml
version: 1
max_age_days: 90
ignore:
  - node_modules/**
  - .git/**

auditors:
  claude-md:
    files:
      README.md:
        commit: abc123
        date: 2026-05-15T10:30:00Z
        scope: ["**/*"]
  spec:
    files:
      docs/specs/auth.md:
        commit: abc123
        date: 2026-05-15T11:00:00Z
        scope: ["src/auth/**/*"]
        characterized: true
        characterized_by_session: <opt session id>
  char-tests:
    files:
      tests/characterization/test_auth.py:
        pins_spec: docs/specs/auth.md
        last_passed: 2026-05-15T11:00:00Z
  # ...
```

### 4.3 `.ffflow/stack.yaml` (optional override)

```yaml
extends: typescript-stack
dimensions:
  test_runner: { tool: jest }
  coverage_threshold_line: 90
```

### 4.4 Plan working directory

Plans are transient. They live outside the project tree, addressed by working-directory hash so two projects never collide:

```
/tmp/ffflow-plans/<project-hash>/<slug>/
├── roadmap.md          # (plan-roadmap only) phase-level plan
├── plan.md             # (plan-chat only) slice-level plan: path from spec A to spec B
├── decisions.md        # Decisions made + open ones (?-marked)
├── chat-log.md         # Raw conversation (optional, for chatlake-style archaeology)
├── metadata.json       # Phase, slug, level, source (vision-doc / prompt / characterize / audit), timestamps
├── captured.json       # Populated by plan-capture (issue IDs)
├── phases/             # (plan-roadmap only) placeholders read by tier-2 sessions
│   ├── phase-1.md
│   └── phase-2.md
└── tasks/              # Populated by plan-breakdown
    ├── task-1.md
    └── task-2.md
```

A given `<plan-dir>` contains **either** a `roadmap.md` (tier-1 roadmap) **or** a `plan.md` (tier-2 plan), not both. Tier-2 plans created from a roadmap phase reference their parent roadmap's `<plan-dir>` in `metadata.json`.

The `<project-hash>` is `sha256(pwd) | head -c 16` — same scheme as `notetoself`. One project = one hash; two checkouts of the same repo at the same path collide intentionally (the plan dir is the same one).

**Why `/tmp` rather than `plan/` in the project:**
- Plans are *future tense* and *transient* — they don't belong in the project tree any more than scratch notes do.
- Captured plans live durably as issues in the tracker; the plan dir is just the workshop floor.
- `/tmp` cleanup at reboot is correct behavior — by then, the plan should have been captured.
- No `.gitignore` pollution. No accidental commits.
- Same machinery as `notetoself` — one persistence pattern across the plugin.

### 4.5 Durable roadmap layer (in the repo)

When `plan-capture` runs against a sealed roadmap, the roadmap rationale lands in the repo regardless of which task backend is configured:

```
docs/
├── specs/                    # evergreen behavioral contract
├── roadmap/                  # roadmap rationale (this section)
│   └── <slug>/
│       ├── roadmap.md        # copied from /tmp by plan-capture
│       ├── decisions.md      # copied from /tmp by plan-capture
│       └── phases/
│           ├── phase-1.md    # placeholder + post-capture "## Captured tasks" section
│           └── phase-2.md
└── tasks/                    # task work items (markdown backend only)
    └── <slug>/
        ├── EPIC-phase-1.md
        ├── task-1.md
        └── ...
```

Why the roadmap layer is durable while the plan dir is transient:

| Artifact | Lifetime | Where |
|---|---|---|
| Rationale (roadmap.md + decisions.md) | Forever | `docs/roadmap/<slug>/` |
| Phase placeholders | Forever (write-once-then-update-once) | `docs/roadmap/<slug>/phases/` |
| Tasks | Transactional | Issue tracker, or `docs/tasks/<slug>/` for markdown backend |
| Session state (`metadata.json`, `chat-log.md`, `tasks/*.md` pre-capture) | Until captured | `/tmp/ffflow-plans/<hash>/<slug>/` |

`plan-status` re-hydrates the `/tmp` cache from `docs/roadmap/<slug>/` when the cache is missing — making roadmap durability complete across machine reboots, container clears, and fresh checkouts.

For single-slice plans (`plan-chat` → `plan-breakdown` → `plan-capture` without a `plan-roadmap` upstream), no `docs/roadmap/` entry is written. The rationale isn't durable for one-off slices, which is the right asymmetry.

**Durability escape hatch (pre-capture):** if you need an *uncaptured* plan to survive `/tmp` cleanup, copy the dir into `.ffflow/plan-archive/<slug>/` explicitly via `plan-status --archive`. This is rare — almost always the right answer is to capture instead.

---

## 5. Skill Catalog

For each skill: purpose, inputs, outputs, dependencies (other skills it loads), the friction it addresses, and implementation notes.

### 5.1 Setup

#### `init-ffflow`
**Purpose:** Bootstrap a project for FFFlow.
**Inputs:** Current working directory (project root).
**Outputs:** `.ffflow/config.yaml`. (No `.gitignore` edits, no eager directory creation — lazy-init everywhere else.)
**Dependencies:** Stack skills (consulted for defaults), `stack-init`.
**Implementation notes:**
- Detects existing language (Python, TS, etc.) and proposes a stack.
- Detects existing test/coverage tooling.
- Asks user for level. Defaults to L1.
- Asks user for capture backend. Defaults to github-issues if `gh` is configured.
- Idempotent. Re-running upgrades the config rather than overwriting.

### 5.2 Planning

#### `plan-roadmap` (tier 1)
**Purpose:** Phase-level planning above `plan-chat`. Reads a vision (project.md / README / prompt) or surveys an existing codebase; produces an ordered, dependency-aware roadmap of independently shippable phases. Each phase becomes a tier-2 session.
**Inputs:** A vision (file path or free-form description); optional `--phase <N>` for recursion; optional `--vision-doc <path>`.
**Outputs:** `<plan-dir>/roadmap.md`, `<plan-dir>/decisions.md`, `<plan-dir>/phases/phase-N.md` placeholders.
**Dependencies:** Stack and methodology context per level; `.ffflow/audit.yaml` for what's already characterized.
**Friction addressed:** Vision docs that never become plans; brownfield features that fail because nobody characterized first; the adopt→first-slice cliff; roadmaps living in slide decks instead of versioned artifacts.
**Implementation notes:**
- **Hard rule:** never invokes Claude Code's Plan Mode.
- **Hard gate:** does not seal with any open `?` markers (same discipline as `plan-chat`).
- Greenfield default phasing: Foundation → smallest end-to-end slice → expansion in dependency order.
- Brownfield default phasing: characterize the touched surface as phase 1; build phases on top; optional deprecation/cleanup as final phase.
- Each phase has a `Kind:` (`design-slice` → handoff to `plan-chat`, `characterize` → handoff to `/characterize`, `cleanup` → handoff to `/audit --plan`, `roadmap` → recursive `/plan-roadmap --phase N`).
- Each phase has `Scope:`, `Out of scope:`, `Success:`, `Depends on:`, `Estimated tasks:`. Independent shippability check before sealing.
- Recursion: `/plan-roadmap --phase N` opens an existing roadmap and produces a sub-roadmap for that phase. Recursion past two levels signals the original roadmap was too ambitious.
- After sealing, the user invokes the first phase's tier-2 handoff manually (or via `autopilot`).

#### `plan-chat` (tier 2)
**Purpose:** Interactive design of a behavior change. Produces a plan describing the path from current spec to target spec, with **every open decision resolved before sealing**.
**Inputs:** A description of the change to plan (free-form).
**Outputs:** `<plan-dir>/plan.md`, `<plan-dir>/decisions.md`, optionally a draft spec delta.
**Dependencies:** Level-appropriate methodology skills (`writing-specs` at L2+, etc.).
**Friction addressed:** Plan Mode misfires; 200+ turn bloated chats; lost context after `/clear`; hand-pasted "walk me through alternatives" templates; plans that seal with open questions.
**Implementation notes:**
- **Hard rule:** never invokes Claude Code's Plan Mode. State this explicitly at the top of the skill body.
- First action: create `<plan-dir>/` directory and write initial `plan.md` skeleton.
- Three phases: Understanding → Architecture/Approach → Path. Confirms user signoff between phases.
- Uses `?`-marker convention for open decisions. Decisions accumulate during Phases 1–3; a dedicated decision-walk step resolves all of them before sealing.
- For each open decision: restate the question, present 2–3 alternatives with concrete tradeoffs, name a recommendation, ask for confirmation. Record rejected alternatives in `decisions.md`.
- Continuously updates `plan.md` and `decisions.md` as the conversation progresses.
- Phase 3 (the path) describes which parts of the spec change, in what order, with explicit dependencies.
- **Hard gate:** does not seal until `decisions.md` has zero open `?` markers (deferred markers count as open) AND user confirms "ready to break this down."

#### `plan-breakdown`
**Purpose:** Cut a sealed plan into independently shippable chess moves.
**Inputs:** Path to a plan directory.
**Outputs:** `<plan-dir>/tasks/task-N.md` files.
**Dependencies:** None.
**Friction addressed:** Plan-then-breakdown loops where breakdown reveals new design questions.
**Implementation notes:**
- **Hard gate:** refuses to run if `decisions.md` has any open `?`s. Tells the user to resume `plan-chat` (which doesn't seal until decisions are resolved).
- Each task is: behavioral scope (which Rules/sections), implementation scope (files, layers), acceptance criteria, dependencies on other tasks.
- 3–8 tasks per plan. Interactive review with the user before committing.
- Each task is reviewed for: freestanding (mergeable alone), bounded (explicit out-of-scope), red/green-able (the test is writable before the code).

#### `plan-capture`
**Purpose:** Write chess moves to the configured issue tracker.
**Inputs:** Path to a plan directory with sealed tasks.
**Outputs:** Issues in the tracker; `<plan-dir>/captured.json` linking task files ↔ issue numbers.
**Dependencies:** One of `capture-github-issues`, `capture-linear`, `capture-jira`, `capture-markdown`.
**Implementation notes:**
- Reads `.ffflow/config.yaml` to pick the capture backend.
- Delegates to the backend skill.
- Idempotent. Re-running updates existing issues rather than duplicating.
- Each issue body includes: link to evergreen spec it advances, acceptance criteria, branch name, dependency references.
- After capture, optionally cleans up `<plan-dir>/`. Default: keep until user confirms or runs `plan-status --cleanup`.

#### `plan-status`
**Purpose:** Show in-flight plans across the working directory.
**Inputs:** Current working directory.
**Outputs:** Report of each plan: phase, what's done, what's next.
**Dependencies:** None.
**Implementation notes:**
- Scans `plan/*/` directories.
- Reads `metadata.json` from each.
- Reports phase (chat-incomplete, chat-complete, breakdown-complete, captured) and next command.

#### `pipeline-status`
**Purpose:** Show delivery across every roadmap after capture: what's done, in flight, next, and unattached.
**Inputs:** Current working directory; `.ffflow/config.yaml` for the capture backend.
**Outputs:** Text view, JSON (`schema_version: 1`) for visualization tools, or HTML: `viewer.html`, a self-contained template that renders the JSON.
**Dependencies:** `git`; `gh` for the `github-issues` backend (the only one supported so far).
**Implementation notes:**
- `pipeline.py` (stdlib Python) collects plan roots from the working tree, the default ref and remote branches, plus tracker issues and open PRs, into a raw snapshot; a pure build step turns it into the model.
- Joins epics to roots and phases from both sides: the `docs/roadmap/<slug>/…` link in the epic body and `Epic: #N` under a plan file's `## Captured tasks`.
- Progress is task issue state, not checklist ticks. Data gaps (unlinked epics, missing roots, stale numbering) are findings, never silently fixed.
- PRDs: ppp bundles (a folder with `medium.md` and `state.json`), read directly — fff never calls ppp. A roadmap's `Source:` line links it to the bundle it was planned from.
- Read-only.

#### `pipeline-next`
**Purpose:** Say what to do next, per roadmap or project-wide, with the FFFlow command for each action.
**Inputs:** Optional roadmap slug.
**Outputs:** Recommendations; runs a command only on confirmation.
**Dependencies:** `pipeline-status` (its `pipeline.py` computes `next_actions`).
**Implementation notes:**
- Two lanes side by side: build (review an open PR, finish an epic in progress, start an unblocked epic) and plan (the next phase without an epic, once its dependencies are planned; planning runs ahead of building). Plus data gaps, and what blocks a roadmap when neither lane has anything.
- The rules live in `pipeline.py` so the viewer and this skill agree. Suggestions only: the executor decides what starts.

### 5.3 Brownfield Entry

#### `characterize`
**Purpose:** Interactive bootstrap of an evergreen spec for an unspec'd codebase. Produces (a) the spec committed immediately, and (b) a plan whose tasks add characterization tests for the spec'd behaviors.
**Inputs:** Optional: target module/directory to focus on.
**Outputs:**
- Spec entries written to project's spec location (committed)
- `plan/characterize-<slug>/` with `plan.md` + `tasks/` for test backfill
- Entries registered in `.ffflow/audit.yaml` under spec auditor
**Dependencies:** `audit` (registers output), `tdd-loop` (referenced for test-writing tasks), level-appropriate methodology skills.
**Implementation notes:**
- Five phases (see §6.5 for the full flow): Survey, Propose shape, Walk module-by-module, Test gap analysis, Hand off plan.
- Resumable across sessions. State written to disk between phases.
- Detects existing test coverage and adapts: rich tests → summarize-into-spec; weak tests → write spec + characterization tests.
- Annotation conventions per level (`<!-- INTENT?: ... -->` at L0/L1; `@known-defect` etc. at L2+).
- Hands off the plan portion to `plan-breakdown` / `plan-capture` like any other plan.
- The spec is committed directly because that's a single mechanical chess move that doesn't need autonomous execution; the tests, by contrast, are queued for `/work-issue`.

### 5.4 Execution

#### `work-issue`
**Purpose:** Execute a single chess move (one captured issue) from cold-start to merged PR.
**Inputs:** An issue ID (or path to a task file for markdown capture).
**Outputs:** A PR; spec updates committed in the same PR; updated audit state if applicable.
**Dependencies:** `tdd-loop`, `self-review`, level-appropriate stack and methodology skills.
**Friction addressed:** Plan Mode misfires; PR-author archaeology after long autonomous runs; PRs shipped without local repro; specs falling behind code.
**Implementation notes:**
- **Hard rule:** never invokes Claude Code's Plan Mode.
- **PR-checkpoint protocol:** When ≥ 2 PRs have been created in the current session, pause with a summary ("created #X, #Y, #Z — author: subagent; status: …") and explicit "continue?" gate.
- **Local-validation gate:** Before pushing, must either run local repro/smoke or state in the PR body why local validation wasn't possible.
- Phase 0: Load task. Idempotent — detects branch/PR state and resumes.
- Phase 1: Read the chess move's spec (the issue body) and the current evergreen spec.
- Phase 2: Run the `tdd-loop` — write tests, watch red, write code, watch green, refactor.
- Phase 3: Update the evergreen spec to reflect new behavior. Same PR.
- Phase 4: Run level-appropriate gates (lint/test at L0/L1; audit at L2+; full quality gates at L3).
- Phase 5: `self-review` skill.
- Phase 6: PR. Body cites the issue, the spec changes, and the test summary.

#### `work-fanout`
**Purpose:** Parallel execution of multiple chess moves across worktrees. **One PR per issue.**
**Inputs:** A list of issue IDs (or "all open issues in epic X").
**Outputs:** N PRs; a final report of done/in-progress/stalled.
**Dependencies:** `work-issue`, `worktrees`.
**Friction addressed:** Weekly hand-typed "have an agent team work on these four in worktrees…" prompts.
**Implementation notes:**
- Spawns N subagents (default cap 2), each in its own worktree branched off the same base.
- Each agent runs `work-issue` for its issue.
- Built-in stall detection: agents silent > 10 min get flagged.
- Resume-aware: re-launch only the stalled ones.
- Final report distinguishes: done (PR open + green), in-progress (PR open, not yet green), stalled (no recent activity), failed (agent gave up with explanation).

#### `work-epic`
**Purpose:** Sequential execution of every open issue under an epic onto **one feature branch** — one squashed commit per task, **one PR per epic**.
**Inputs:** An epic identifier (e.g., `E0.1` or a GitHub umbrella issue number).
**Outputs:** One branch `epic/<id>`, one PR off main, per-task and umbrella issues closed after merge.
**Dependencies:** `work-issue` discipline inside implement subagents; `self-review` discipline inside review subagents.
**Friction addressed:** Hand-typed "have an agent team work on these N under epic X, sequentially, one squashed commit each" prompts.
**Implementation notes:**
- Sorts tasks by title `T<N>` (not issue number — parallel agents create issues out of order).
- Per task: implement subagent → review subagent → squash to one commit. Implementer and reviewer are never the same agent.
- Step 5 runs a holistic epic-level review subagent after the per-task pass.
- Never merges. User approves the merge; cleanup (close child + umbrella issues) runs after merge is confirmed.

#### `autopilot`
**Purpose:** Meta-skill that wraps any interactive skill for unattended execution. Reads project context to stand in for the user on routine decisions.
**Inputs:** A skill name and its arguments.
**Outputs:** Whatever the wrapped skill produces; a decision log of every choice autopilot made.
**Dependencies:** Any skill, dynamically.
**Friction addressed:** Replaces `aug-core:automate`. Reduces typing for routine chains like `plan-breakdown → plan-capture`.
**Implementation notes:**
- Different from `--dangerously-skip-permissions`: provides *contextual judgment*, not just auto-approval.
- Decision principles: consistency over novelty, simplicity when ambiguous, ask on high stakes (destructive operations, architectural choices, ambiguous domain questions), never force-push or delete without explicit prior authorization.
- Every decision cites evidence: a file, a config, a recent commit. Bad autopilot decisions cite convention; good ones cite the codebase.

### 5.5 The TDD Loop (shared discipline)

#### `tdd-loop`
**Purpose:** The red/green/refactor discipline. Loaded by `work-issue` and by characterize's test-backfill tasks.
**Inputs:** A spec entry or acceptance criteria to satisfy.
**Outputs:** Tests written, tests failing (red), code written, tests passing (green), code refactored under green.
**Dependencies:** None (pure discipline).
**Implementation notes:**
- This is a reference rulebook skill, not a standalone workflow.
- The loop:
  1. Read the spec/acceptance to satisfy.
  2. Write the test(s) that pin the new behavior.
  3. Run them. Confirm they fail. (Red — if they pass, the test is wrong or trivial.)
  4. Write the minimum code to make them pass. (Green.)
  5. Refactor for clarity/quality. Tests stay green.
  6. Repeat for the next chunk of acceptance.
- At L0/L1: unit/integration tests in the project's existing framework.
- At L2: a mix — Gherkin scenarios first (acceptance), then unit tests for inner correctness.
- At L3: full spec-first — `.feature` file → step definitions → red → green → audit.
- The loop is the same; the artifacts scale with level.

### 5.6 Audit (keep-honest layer)

#### `audit` (one skill, six cartridges)

**Purpose:** Coordinator for the audit subsystem. Loads applicable cartridges, runs them, aggregates findings, renders a unified report.
**Inputs:** Optional `--type <list>` to run a subset; optional `--plan` to convert findings to a plan; optional `--ci` for machine-readable output; optional `--fix` for conservative auto-fixes.
**Outputs:** A report; updates to `.ffflow/audit.yaml`; optionally a plan under `/tmp/ffflow-plans/<project-hash>/audit-<slug>/`.
**Cartridges:** Per-type audit procedures live under `skills/audit/cartridges/`:

- `cartridges/claude-md.md` — CLAUDE.md coverage, freshness, sanity. Folds in former aug-dev `docsaudit`, `documenting-with-audit`, `documenting-with-claude-md`.
- `cartridges/spec.md` — spec / `.feature` freshness. Per-level mechanism: prose re-read at L0/L1; scenario run at L2; delegates to `rid` cartridge at L3.
- `cartridges/char-tests.md` — characterization test suite results. Failures always block; no auto-classification (strict by design).
- `cartridges/architecture.md` — architectural conformance via static analysis. Hexagonal defaults from `hexagonal-architecture`.
- `cartridges/refactor.md` — complexity, LoC, duplication, hot spots, test health. Folds in parts of aug-just's `justfile-quality-patterns`.
- `cartridges/rid.md` (L3 only) — wraps `specdrive audit` for RID coverage, unbound scenarios, orphaned step definitions, mutation scores.
- `cartridges/ui.md` — view-layer purity (§2.9). Flags components imported into app code without a story, stories without interaction tests, uncovered states/variants, presentational components importing from `app/`/`api/`/`store/`, and raw hex/px literals bypassing design tokens. Advisory at L0/L1, blocking at L2/L3. Applies only when the project's stack includes a UI cartridge.

**Implementation notes:**
- Coordinator does no auditing itself. Dispatch + aggregate + render only.
- Default behavior: run every cartridge applicable to the project's level.
- With `--plan`: above-threshold findings convert into a plan that flows through breakdown/capture/work.
- Designed to also run in CI: each cartridge produces machine-readable output the workflow can act on.
- Cartridges aren't separate skills — they're reference files loaded on demand. The LLM only sees `audit` in its skill index.

### 5.7 Methodology spine (reference rulebooks)

These are loaded as context by the workflow skills based on level. Not invoked directly.

- `writing-specs` — L2+. Gherkin 6 conventions, Rule structure, scenario shape, annotation tags.
- `hexagonal-architecture` — L1+. Layer boundaries, ports/adapters, dependency direction.
- `component-driven-ui` — L1+. View-layer purity (§2.9): presentational vs. connected components, the atoms→molecules→organisms→layouts ladder, story-as-vignette doctrine, design-token layer, and the decompose→story→test→integrate ordering. Loaded by `plan-chat`, `work-issue`, and `/audit --type ui`.
- `spec-first-development` — L2+. The red-green-audit loop with specs.
- `defect-driven-specification` — L1+. Every bug becomes a spec entry before a fix.
- `contract-enforcement` — L2+. Mocks must be anchored to verifiable contracts.
- `rid-traceability` — L3. RID format, uniqueness, lifecycle.
- `total-specification` — L3. The 10 pillars. The full FFFlow methodology.
- `quality-gates` — L3. The four-gate model (Structure, Correctness, Coverage, Maintainability).

### 5.8 Stack defaults

One skill (`stack`) with per-language cartridges, plus two operator skills.

- `stack` — Reference for the FFFlow dimension model + cartridges under `cartridges/` for each language:
  - `cartridges/python.md` — uv, ruff, mypy, pytest, coverage.py thresholds, mutmut for mutation testing.
  - `cartridges/typescript.md` — pnpm, prettier, eslint, vitest, c8/istanbul thresholds, Stryker.
  - `cartridges/typescript-ui.md` — extends `typescript`. The prescriptive web-UI toolchain for view-layer purity (§2.9): design tokens (style-dictionary → CSS vars); Storybook; fast component + interaction tests; a11y and (L3) visual-regression checks; `just storybook` / `test-stories` recipes folded into `check-all`. Blesses **two baselines under one rulebook**, selectable in `.ffflow/stack.yaml`: the **React** lane (prescribed default — Radix headless primitives + shadcn-style *owned* components, concrete templates) and the **Web Components** lane (**Web Awesome**, the Lit-based successor to Shoelace — a natively-themeable kit with a Shadow-DOM purity seal). Both are first-class Storybook renderers. Server-rendered-fragment stacks (htmx) are a *different paradigm*, not this lane: they keep view-layer purity via pure-template + fragment-contract tests, not Storybook, and are scoped out of the story gates (see `component-driven-ui`).
  - `cartridges/java.md` — Maven, JUnit 5, Spotless, SpotBugs, JaCoCo.
  - `cartridges/rust.md` — cargo, rustfmt, clippy, cargo-nextest, cargo-llvm-cov, cucumber-rs + proptest at L2+, cargo-mutants at L3.
  - `cartridges/polyglot.md` — Multi-language orchestration via root justfile; per-subproject `level_override` allowed.

  Each cartridge has its own `templates/` subdir for concrete config files (pyproject.toml, tsconfig.json, pom.xml, Cargo.toml, etc.) that `stack-init` reads from.

- `stack-init` — Bootstrap a stack into a project. Idempotent. `--check` (dry-run) and `--yes` (skip confirmations) supported.
- `stack-assess` — Compare current project to its declared stack. Identify missing tools, version mismatches, configuration gaps.

Each cartridge declares its dimensions in a YAML block. Example shape:

```yaml
# skills/stack/cartridges/python.md embeds:
dimensions:
  package_manager: { tool: uv, version: ">=0.4" }
  formatter: { tool: ruff, command: "ruff format" }
  linter: { tool: ruff, command: "ruff check" }
  type_checker: { tool: mypy }
  test_runner: { tool: pytest }
  coverage_tool: { tool: coverage.py }
  coverage_threshold_line: 95
  mutation_tool: { tool: mutmut }
  mutation_threshold: 80
```

`.ffflow/stack.yaml` can override any dimension.

**Note: the dimensions YAML is documentation, not a machine-parsed schema.** No validator. Skills that act on dimensions (e.g., `stack-init`, `stack-assess`) read the values via grep / hand-parsing. We keep it informal because the alternative — defining a schema and writing a validator — is overhead the plugin doesn't need yet. If a future requirement demands machine parsing, the YAML format is forward-compatible.

### 5.9 Capture backends

Folded into `plan-capture` as cartridges. The skill is one entry; the backend cartridges live under `skills/plan-capture/cartridges/`:

- `cartridges/github-issues.md` — Default. Umbrella epic issue + child task issues, dependency wired via comments.
- `cartridges/linear.md` — Linear Project + Issues with first-class `relation:blocks` dependencies.
- `cartridges/jira.md` — Jira Epic + Stories with `is blocked by` issue links.
- `cartridges/markdown.md` — No external tracker; writes `tasks/EPIC-<slug>.md` + `tasks/task-N.md` + `TASKS.md` index in the repo.

The capture *protocol* (idempotency check, epic creation, task creation, dependency linking, captured.json write, spec back-link requirement) lives in `plan-capture/SKILL.md` once. Cartridges only describe the API-specific differences.

### 5.10 Build interface (justfile patterns)

Folded into one `justfile` skill with tier cartridges. Folds aug-just in as FFFlow's build-interface convention.

- `justfile/SKILL.md` — Baseline interface (test, lint, format, check-all, etc.) + the 5-tier maturity model.
- `cartridges/tier-1-quality.md` — test-watch, integration-test, complexity, loc, duplicates, slowtests.
- `cartridges/tier-2-security.md` — vulns, lic, sbom, doctor.
- `cartridges/tier-3-advanced.md` — deploy, migrate, logs, status.
- `cartridges/tier-4-polyglot.md` — multi-language recipe extensions (the structural shape lives in `stack/cartridges/polyglot.md`).

**Concept/language split.** Each tier file describes the language-agnostic concept (recipe list, rules, anti-patterns) and indexes per-stack recipe bodies under a sibling folder of the same stem — e.g. `cartridges/tier-1-quality/{python,typescript,java,rust}.md`. Adding a language is one new file per tier it touches; the concept file never grows. This keeps the cartridge set O(concepts), not O(concepts × languages), and matches the one-file-per-language axis already used in `stack/cartridges/`. Tier 4 has no per-language bodies (it delegates structure to the polyglot stack cartridge), so it has no folder.

**Terminology:** "Level" (L0–L3) = FFFlow methodology rigor. "Tier" (0–4) = justfile maturity. Orthogonal dials.

### 5.11 Supporting tools

- `refactor` — Coverage/complexity-driven refactoring. Generates plan tasks.
- `debugging` — Hypothesis-driven debugging workflow.
- `self-review` — Pre-PR self-review checklist.
- `worktrees` — Isolated worktree management for parallel work.
- `git-hooks` — Pre-commit/pre-push hook setup.
- `ci-gates` — GitHub Actions workflow templates that run audits as PR checks.
- `notetoself` — Save working context for resumption across sessions.
- `hemingway` — Concision discipline for prompt content; used in skill authoring.
- `zero-tech-debt` — Review-time discipline: fix nits in-flight if <15 min and uncontroversial. Loaded by `self-review` and `work-issue` Phase 5.
- `yagni` — Tension partner with `zero-tech-debt`. Provides the TODO-with-trigger format for legitimate deferrals. Vague triggers forbidden.

### 5.12 Onboarding

- `upgrade-ffflow` — Reconcile an already-adopted project against the current plugin version. Reads `ffflow_version` from `.ffflow/config.yaml`, walks `docs/migrations.md`, duck-types unstamped (pre-0.4.0) repos from repo evidence, applies gaps by delegating to the owning skill, re-stamps last. Complements `adopt-ffflow`: adoption onboards, upgrade catches up.
- `adopt-ffflow` — End-to-end onboarding for a new ffflow project. Greenfield: runs `init-ffflow` then suggests next steps. Brownfield: runs `init-ffflow`, then `characterize`, then helps queue up the test-backfill work.

---

## 6. Workflows

The lifecycle flows the plugin supports.

### 6.1 Brownfield bootstrap

```
init-ffflow             — declare level, stack, capture backend
upgrade-ffflow          — catch an existing project up to the current plugin version
characterize            — interactive walk; produces spec (committed) + plan (for test backfill)
plan-breakdown          — cut test-backfill plan into per-module tasks
plan-capture            — write tasks to issue tracker
work / work-fanout      — fill the safety net autonomously
audit                   — verify net is intact; baseline is locked
```

Resumable. Modules can be characterized one at a time across sessions.

### 6.2 Steady-state feature work

```
plan-chat               — design the change; produce plan
plan-breakdown          — cut plan into chess moves
plan-capture            — write issues
work / work-fanout      — execute; spec advances with code
audit (periodically)    — keep artifacts honest
```

### 6.3 Maintenance loop

```
audit                   — finds drift / gaps / sanity issues
audit --plan            — convert findings into a plan
plan-breakdown          — cut maintenance plan into chess moves
plan-capture            — write issues
work / work-fanout      — execute
```

### 6.4 Single chess move

```
work <issue-id>         — autonomous execution of one task end-to-end
```

### 6.5 Characterize phase detail

`characterize` is the most complex single skill. The phases:

**Phase 1: Survey.** Read codebase structure, existing docs, existing tests, recent git history. Identify architectural shape. Internal notes only.

**Phase 2: Propose shape.** Given the project's level, propose where the spec will live, the bounded contexts, and per-context spec organization. Interactive confirmation before writing anything.

**Phase 3: Walk module-by-module.** For each module: read code → propose behavioral rules in present tense → identify judgment-call points (confirmed/likely-defect/unverified/accepted-risk) → user reviews and confirms → write spec entries to the spec location. Commit each module's spec as it's completed.

**Phase 4: Test gap analysis.** With the spec in hand, analyze coverage of each spec'd behavior. Categorize gaps: behaviors with no test, behaviors with weak test, behaviors well-tested. Propose test-backfill tasks sized appropriately (module / file / function / class as the scope demands).

**Phase 5: Build the plan.** Wrap the test-backfill into a plan with `plan.md` + tasks. Optionally include "research/spec follow-up" tasks for spec gaps the agent couldn't confidently fill. Hand off to `plan-breakdown`.

After Phase 5, the rest of the pipeline (`plan-breakdown → plan-capture → work`) runs as for any plan.

---

## 7. Cross-cutting Conventions

### 7.1 Plan Mode discipline

Skills that interact with the user about future actions explicitly state at the top of their body: **"This skill does NOT use Plan Mode. Do not invoke the EnterPlanMode tool."** Required for: `plan-chat`, `plan-breakdown`, `characterize`, `work-issue`, `work-fanout`.

### 7.2 Decision-marker convention

In any plan or spec artifact, an open decision is marked with `?` at the start of the line or in a `## Open decisions (?)` section. `plan-chat` resolves them inline before sealing; `plan-breakdown` refuses to run if any remain.

**Resolving a marker removes it.** When a decision is answered, rewrite its heading to drop the `?` — `## ? D1 — …` becomes `## D1 — … (resolved)`. Do not preserve the original `## ?` heading in an archival block; the resolution text is the record. The gate detects *open* markers only (line-leading `?`, `## ?` headings, the Open-decisions section) — not every `?` in the file, so prose questions are fine — but a stale `## ?` left as decoration will trip it. Skills that write `decisions.md` (`plan-chat`, `audit --plan`, `characterize`) own keeping resolved markers clean.

### 7.3 PR-checkpoint protocol

`work-issue` and `work-fanout` follow the same protocol: after every PR, post a one-line summary. After every 2 PRs in an unattended session, pause and ask the user to confirm before continuing.

### 7.4 Local-validation gate

`work-issue` will not push a PR for non-spec-only changes without one of:
1. A local repro/smoke that passed
2. An explicit statement in the PR body explaining why local validation was not possible (e.g., needs production credentials, integration with paid third-party service, etc.)

### 7.5 Spec ↔ test linkage

At L0/L1, the link is naming convention or colocation. At L2, the link is the Gherkin step definition binding. At L3, the link is the RID. The audit subsystem verifies the link at every level.

### 7.6 Idempotency

Every skill that writes state (`plan-capture`, `characterize`, `audit`, `init-ffflow`, etc.) is idempotent. Re-running detects existing state and updates rather than duplicating.

### 7.7 Resume-ability

Long-running skills (`characterize`, `work-fanout`) persist state to disk between meaningful steps. Re-invocation detects and resumes.

### 7.8 Memorable typeahead names

Reference §2.7. When in doubt, lead with the distinctive word.

---

## 8. Dependencies Between Skills (Reference)

```
init-ffflow
  └─→ stack-init (consults stack skills for defaults)

characterize
  ├─→ audit (registers output)
  ├─→ tdd-loop (referenced in test-backfill task descriptions)
  └─→ (level-appropriate methodology skills)

plan-chat
  └─→ (level-appropriate methodology skills)

plan-breakdown
  └─→ (none; pure breakdown logic)

plan-capture
  └─→ capture-* (one of)

work
  ├─→ tdd-loop
  ├─→ self-review
  └─→ (stack-* and methodology skills)

work-fanout
  ├─→ work (per-issue)
  └─→ worktrees

autopilot
  └─→ (any skill, dynamically)

audit
  └─→ audit-* (per-type auditors, dynamically per config)

audit-claude-md, audit-spec, audit-char-tests, audit-architecture, audit-refactor, audit-rid
  └─→ (stack-* for tool invocations)

adopt-ffflow
  ├─→ init-ffflow
  └─→ characterize
```

Methodology spine skills (`writing-specs`, `hexagonal-architecture`, etc.) are loaded as references, not invoked directly.

---

## 9. Friction Patterns Addressed (Reference)

Each documented friction pattern from the chat-history analysis maps to a concrete mechanism.

| Friction | Mechanism |
|---|---|
| "I asked you to /plan-chat not go into plan mode" | Plan Mode discipline (§7.1) in plan-chat, work, etc. |
| Hand-pasted "1 - walk me through the alternatives" template | `plan-chat` resolves every open `?` inline before sealing |
| 200+ turn bloated plan-chats re-reading code | On-disk plan artifact + edit-not-rewrite discipline |
| "WTF our session created all these PRs?" | PR-checkpoint protocol (§7.3) |
| "have you tested this shit LOCALLY?" | Local-validation gate (§7.4) |
| Weekly "spin up an agent team in worktrees" retype | `work-fanout` |
| Plans lost after `/clear` | `<plan-dir>/` directory; resumability (§7.7) |
| CLAUDE.md drift | `/audit --type claude-md` |
| Just updated the plugin | `/upgrade-ffflow` |
| Specs falling behind code | `/audit --type spec` + `/audit --type char-tests` |
| Architectural drift | `/audit --type architecture` |
| Refactoring backlog invisibility | `/audit --type refactor` |
| "Renumbered epics based on rebase-related blocking issues" | `plan-breakdown` hard gate on open decisions |
| Lost design rationale between sessions | `decisions.md` capturing rejected alternatives |

---

## 10. Build Phases

The plugin is large. Building it all at once is the trap. Pragmatic order:

### Phase 1: L0/L1 spine (week 1–2)

The minimum to replace aug-dev for daily L0/L1 work.

- `init-ffflow`
- `plan-chat` (with Plan Mode guard, on-disk artifacts, decision markers, inline decision-walk before sealing)
- `plan-breakdown` (with the open-decision gate)
- `plan-capture` (github-issues only)
- `plan-status`
- `capture-github-issues`

**Outcome:** You can use the new plugin for any L0/L1 project's planning. aug-dev's plan-chat/plan-breakdown/plan-create become replaceable.

### Phase 2: Execution (week 3–4)

Closes the loop on autonomous work.

- `work-issue` (with PR-checkpoint + local-validation gates)
- `work-fanout`
- `autopilot`
- `tdd-loop`
- `self-review`
- `worktrees`
- `python-stack`, `typescript-stack` (minimum two stacks to start)
- `stack-init`, `stack-assess`

**Outcome:** Full L0/L1 lifecycle works end-to-end with the new plugin.

### Phase 3: Audit foundation (week 5)

The keep-honest layer; folds in docsaudit.

- `audit` coordinator
- `/audit --type claude-md`
- `ci-gates` (so audits can run as CI checks)

**Outcome:** Drift detection on CLAUDE.md and a working state file. Standalone docsaudit is now replaceable.

### Phase 4: Brownfield + characterize (week 6–7)

`characterize` lands once `audit` exists to register its output.

- `characterize`
- `adopt-ffflow`
- `defect-driven-specification` (reference rulebook, used by characterize at L1+)

**Outcome:** Brownfield ffflow adoption is real. You can run `adopt-ffflow` on a fresh codebase and get to a working baseline.

### Phase 5: Spec-level rigor (week 8)

The maintenance loop becomes real for specs and code-health.

- `/audit --type spec`
- `/audit --type char-tests`
- `/audit --type architecture`
- `/audit --type refactor`
- `hexagonal-architecture` (reference rulebook)
- `refactor`

**Outcome:** Steady-state maintenance is automated. Drift surfaces as plan tasks.

### Phase 6: L2/L3 methodology (week 9–10)

Full FFFlow available for projects that want it.

- `writing-specs`
- `spec-first-development`
- `contract-enforcement`
- `rid-traceability`
- `total-specification`
- `quality-gates`
- `/audit --type rid` (wraps specdrive)

**Outcome:** Projects can promote to L2 or L3 cleanly. Full methodology stack online.

### Phase 7: Breadth (week 11+)

As demand emerges.

- `capture-linear`, `capture-jira`, `capture-markdown`
- `java-stack`, `polyglot-stack`
- `justfile-interface` through `justfile-polyglot`
- `debugging`, `git-hooks`
- `notetoself`, `hemingway`

**Outcome:** Plugin is feature-complete; aug-* fully retired.

---

## 11. Definition of Done

### For Phase 1 (the critical milestone)

- [ ] `init-ffflow` creates `.ffflow/config.yaml` and updates `.gitignore` idempotently
- [ ] `plan-chat` produces `<plan-dir>/plan.md` + `decisions.md`; never invokes Plan Mode
- [ ] `plan-chat` resolves all open `?`-marked decisions inline before sealing
- [ ] `plan-breakdown` refuses to run on a plan with open decisions
- [ ] `plan-capture` creates GH issues idempotently with back-links to the spec
- [ ] `plan-status` correctly reports phase for every plan in the working directory
- [ ] All Phase 1 skills are typeahead-friendly (memorable prefix first)
- [ ] No dependencies on aug-* or any other plugin
- [ ] At least one real-world plan flowed through end-to-end on a live project

### For overall completion

- [ ] All 36 skills implemented per their specs in §5
- [ ] All friction patterns from §9 addressed by concrete mechanisms
- [ ] Plugin standalone — verified by installing in a fresh environment with no other plugins
- [ ] CI templates from `ci-gates` working on at least one real project
- [ ] Brownfield onboarding via `adopt-ffflow` validated on at least one real existing codebase
- [ ] A project running at L3 with full FFFlow audit passing in CI
- [ ] Documentation (`docs/architecture.md`, `docs/levels.md`, `docs/workflows.md`, `docs/audit.md`) complete

---

## 12. What This Spec Is Not

- Not the implementation. Each skill needs its own SKILL.md drafted, reviewed, and tested.
- Not a frozen design. The phases let us learn between them; Phase 2 may inform changes to Phase 1's design.
- Not a wholesale rewrite. Existing aug-* skills are source material; the FFFlow plugin reimplements them with the new conventions, but the conceptual work isn't being thrown out.
- Not L3-prescriptive. L0 is a valid forever-state for projects that want lightweight discipline.

---

This is the build spec. Start with Phase 1. Test it against real projects (chatlake and one client repo would be ideal). Adjust before Phase 2 based on what you learn.
