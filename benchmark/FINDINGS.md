# Code quality as a lever — a benchmark instrument and preliminary findings

**Question.** Holding model (Claude Opus 4.8) and tool (Claude Code) constant,
does *code quality / structure* change how correctly an agent adds a feature?

**Method.** Repurpose **VulcanBench** as a runner. Same RealWorld/Conduit Django
app in two states:
- **A** — raw repo, naive prompt ("implement it").
- **C** — same app after FFFlow adoption (cleaner code, specs, per-module
  CLAUDE.md) + the FFFlow plugin skills, driven through its spec-first
  `plan-chat → plan-breakdown → work-issue` pipeline.

Everything else identical. `claude -p` runs host-side with `--setting-sources
project`, so C's in-repo `.claude/` loads the FFFlow plugin (v0.3.0) and A's does
not — the arms differ exactly by (repo state) + (plugin skills).

Grading is **behavioral** and, where possible, **implementation-neutral**: drive
public URLs / ORM, assert observable behavior. For the flagship task we grade two
axes, mirroring VulcanBench's split:
- **new behavior works** (fail_to_pass)
- **existing behavior intact** (pass_to_pass) — overlay C's own 107-test suite
  onto BOTH arms' final trees; a single pre-existing failure is deselected.

---

## Results

### Task 4 — `notifications` (flagship: real 10-file feature, 3 apps)
Notification model + migration, three trigger integrations (follow / favorite /
comment), self-action exclusion, no-fire-on-unfollow, nav unread badge,
notifications page, mark-read.

| Arm | Model | New behavior | Regression |
|-----|-------|--------------|------------|
| A (naive) | Opus 4.8 | **8/8** | **107/107** |
| A (naive) | Opus 4.8 | **8/8** | **107/107** |
| A (naive) | Haiku 4.5 | **8/8** | **107/107** |
| C (FFFlow pipeline) | Opus 4.8 | **8/8** | **107/107** |

Every arm shipped a complete, non-regressing feature. C used a cleaner
architecture (signal-driven creation; 4 disciplined one-per-move commits) vs.
A's inline trigger calls — a real *qualitative* difference — but behavioral
correctness was identical.

### Earlier tasks (escalating difficulty)
- `drafts` (easy): A 2/2 clean.
- `blocking` (4 apps, 8 invariants): A 7/8 — the 1 "miss" was an **unstated,
  debatable requirement in the test**, not a defect (feed-visibility was never
  specified; blocking-gates-interaction is a legitimate design).
- `comment-counts` (ORM cartesian-join trap): A used `distinct=True`
  proactively — knew the trap cold.

---

## Honest conclusions

1. **No separation at single-feature granularity.** Across four tasks escalating
   to a genuine 10-file feature, the naive arm kept succeeding — and so did
   **Haiku 4.5**, a much smaller model. On single, well-scoped feature-additions,
   baseline model competence is high enough that structure did not change the
   *behavioral* outcome. This is a real, falsifiable result — not the one we
   expected.

2. **Structure changed *how*, not *whether*.** C consistently produced cleaner
   architecture (signals, spec-first decomposition, disciplined commits). The
   benchmark measured behavior, so this shows up as a qualitative note, not a
   score. A quality-focused metric (maintainability, diff hygiene, spec
   conformance) would be needed to capture it.

3. **Implementation-neutral behavioral testing is HARD.** Our first-draft hidden
   tests produced false failures on *every* task by coupling to a specific
   implementation shape (a feed filter, a `.with_comments()` method, a mark-read
   URL name). Each was the test's fault, not the agent's. **Treat every number
   as provisional until tests are hardened** — this is itself a finding about how
   to build these benchmarks.

## Where the quality lever likely lives (next experiments)
- **Accumulation over many changes** — drift across 20 features, not 1. Specs
  prevent slow erosion; a single-feature design structurally cannot test this.
- **Genuinely unfamiliar / idiosyncratic domains** — where the model can't lean
  on training priors and the spec is the only source of a constraint.
- **A quality/architecture metric**, not just pass/fail — to capture the "C is
  cleaner" difference that behavior grading misses.

## The durable deliverable
A working, reproducible harness on top of VulcanBench that varies codebase
quality while holding model+tool constant, runs real Claude Code (with FFFlow
loading correctly per-arm), and scores new-behavior + regression on both arms —
across models (Opus, Haiku). The instrument works; it is ready to ask the
sharper questions above.
