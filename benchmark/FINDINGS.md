# Code quality as a lever — preliminary benchmark

**Question.** Holding the model (Claude Opus 4.8) and the tool (Claude Code)
constant, does *code quality / structure* change how correctly an agent adds a
feature? We repurpose **VulcanBench** as the runner and vary only the codebase.

**Arms** (same RealWorld/Conduit Django app, same feature, same hidden tests):
- **A** — raw repo, naive prompt ("implement it").
- **C** — the same app after FFFlow adoption (cleaner code, specs, per-module
  CLAUDE.md) + the FFFlow plugin skills, driven through its spec-first
  `plan-chat → plan-breakdown → work-issue` pipeline.

Everything else is identical. Hidden tests are **arm-neutral**: they drive public
URLs and the public ORM, assert only spec-level behavior, and are calibrated so a
correct reference implementation scores full marks while the unbuilt feature
scores 0. Scoring mirrors VulcanBench (net working-tree diff → hidden tests).

This is a **deliberately hand-picked, directional** probe, not a representative
suite. We chose one easy feature and one hard feature to find where — if
anywhere — the arms separate. B-arm (hygiene-only) and a broad suite are future
work.

---

## Task 1 — `article-drafts` (easy: single-model feature, ~5 visibility surfaces)

| Arm | Runs | Score |
|-----|------|-------|
| A (naive) | 2 | **2/2 perfect (8/8 each)** |

**Result: tie (as far as measured).** Opus 4.8, even naive-prompted on the raw
repo, reliably finds all draft-visibility surfaces. On a feature this size,
structure did not change the outcome. *This is a real, reported result* — not
every feature is hard enough to separate the arms, and that itself is worth
knowing.

---

## Task 2 — `user-blocking` (hard: `system`-complexity, 8 invariants across 4 apps)

"A blocks B" must sever follows both directions, block B from following /
commenting / favoriting A, remove A's content from B's feed, fix follower
counts, and leave everyone else untouched.

| Arm | Runs | Score | Consistent miss |
|-----|------|-------|-----------------|
| A (naive) | 3 | **7/8 every run** | feed-visibility filter |
| C (FFFlow) | in progress | — | — |

**The finding (A):** across **3 independent runs**, the naive agent wrote a
genuinely competent implementation — it even abstracted a `can_interact_with()`
check and guarded follow, comment, and favorite — but **every single time failed
the same invariant:** a blocked user still sees the blocker's articles in their
feed. The agent's mental model is "blocking gates *actions*" (endpoints); it
never extends to "blocking gates *content*" (the feed queryset), because the feed
is the one surface that isn't an interaction endpoint — and the issue text never
names it. This is verified real (traced: comment/favorite return 403; the feed
genuinely leaks), reproducible 3/3, and specific.

**Why this is the interesting class of bug:** it's not a crash or an obvious
omission. It's *silent incompleteness* — clean, plausible code that ships a
feature missing one cross-cutting invariant. Exactly the failure a documented
codebase (C's specs + centralized `_feed_queryset` + module CLAUDE.md telling the
agent where visibility is decided) is positioned to prevent.

**C result:** _[pending — this run tests whether the structured arm catches the
feed surface the naive arm misses 3/3]_

---

## Honest caveats
- Hand-picked tasks; N is small (2–3 per arm); one model, one tool.
- C differs from A in several ways at once (cleaner code **and** specs **and**
  plugin skills). This measures the *whole package* — "quality vs none" — not
  which dimension matters. Isolating dimensions (a hygiene-only B arm) is the
  next experiment.
- Environment: runs scored host-side in clean venvs (the Docker sandbox has an
  amd64/arm64 mount issue on this box); scoring logic mirrors VulcanBench's.

## What this suggests
A blunt, directional data point consistent with the hypothesis: **on features
hard enough to have non-obvious cross-cutting invariants, the naive approach
consistently ships silent incompleteness.** Whether structure fixes *this
specific* miss is what the C run measures. The framework now exists to ask that
question repeatably — and to iterate on FFFlow by measuring which parts move the
number.
