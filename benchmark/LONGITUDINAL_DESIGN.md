# Longitudinal benchmark design — does quality compound?

**Status:** design only, not yet run. Successor to the single-feature experiment
(see FINDINGS.md), which found no behavioral separation between arms on any one
feature. Hypothesis for THIS design: the quality lever is **longitudinal** — it
shows up as changes accumulate, not within a single change.

---

## The core reframe

Single-feature grading asks "does feature N work?" Every arm passed that. The
longitudinal design asks three questions a single feature cannot:

1. **Regression accumulation** — as you add features 1→N on top of each other,
   do *earlier* features silently break? (Tech debt = later changes eroding
   earlier behavior.)
2. **Velocity decay** — does feature N get *harder* (more turns, more cost, more
   failed attempts) as the codebase degrades under an arm that doesn't maintain
   quality?
3. **Divergence** — do the two arms' codebases drift apart in quality over time,
   even when both keep passing behavioral tests?

The thesis "zero tech debt compounds" predicts: **arm A degrades across the
sequence (rising regressions, rising cost, falling maintainability) while arm C
holds the line — and the gap widens with each feature.**

---

## Design

### Arms
Same two as before — A (raw + naive) and C (FFFlowed + pipeline) — but now each
arm carries its OWN tree forward across the whole sequence. Feature N is built on
the arm's own output from features 1..N-1, NOT on a fresh checkout. This is the
critical difference: **the codebase is allowed to degrade (or not) under its own
accumulated history.**

For C specifically, "carry forward" means the specs, CLAUDE.md, and RID maps also
evolve — the arm maintains its own quality artifacts as it goes (that's the whole
point of FFFlow; the pipeline updates specs per feature).

### The feature sequence (ordered, interdependent — order matters)
A chain where later features build on and stress earlier ones. Draft candidates
on the RealWorld app (each already partly scoped from this repo's work):

1. **drafts** — `is_published` on articles; hidden from public listings.
2. **comment-counts** — counts on listings (interacts with the favorites Count).
3. **user-blocking** — block gates interaction (touches follow/comment/favorite).
4. **notifications** — follow/favorite/comment triggers (touches same 3 sites).
5. **tag-following** — users follow tags; feed composition changes.
6. **reading-list / bookmarks** — another per-user M2M on articles.
7. **article-revisions** — editing creates revisions; every read path changes.
8. **moderation/report** — report → hide; interacts with drafts + blocking + feed.

The ordering is deliberate: 3,4 both touch the follow/favorite/comment sites; 7
forces every earlier read path (drafts, blocking, notifications) to stay correct
through a model redesign; 8 composes with 1,3,5. By feature 8, a naive arm has
many chances to have quietly broken features 1–5.

### Scoring — three layers, per feature step
For each feature N, on each arm:

- **New-behavior gate** (fail_to_pass): feature N's own behavioral tests pass.
- **Cumulative regression gate** (pass_to_pass, THE KEY METRIC): the behavioral
  tests for **features 1..N-1** all still pass. This is where accumulation shows.
  Plot "cumulative passing tests" vs feature index per arm — divergence here is
  the headline.
- **Cost/effort telemetry**: turns, wall-clock, tokens, cost for feature N.
  Plot per arm; a rising A curve vs flat C curve = velocity decay.

Plus a **quality snapshot** after each step (not pass/fail — a measured number):
- maintainability index / cyclomatic complexity (radon) on the app package,
- diff churn (lines touched per feature — is A rewriting vs C extending),
- optional LLM-judge on architecture conformance vs the spec.

### The output artifact
Two curves per metric (A vs C) over feature index 1→8:
- cumulative regressions (expect A to rise, C flat),
- cost per feature (expect A to rise, C flat),
- maintainability (expect A to fall, C flat/rise).
**The claim is proven if and only if the curves diverge.** A tie here (both flat)
is still a real, reportable result: quality doesn't compound at this horizon.

---

## What makes this hard (and how to handle it)

1. **Test-authoring is the bottleneck.** Single-feature already showed
   implementation-neutral behavioral tests are hard and my first drafts produced
   false failures 4/4 times. Eight features × ~8 tests = ~64 hidden tests, each
   of which must be impl-neutral AND survive being run against a tree that later
   features have mutated. **Mitigation:** write tests against a stable public
   contract (URLs, ORM, rendered output), calibrate EACH against a reference impl
   AND against later features' reference trees before trusting any number. Budget
   most of the effort here.

2. **The regression suite must be arm-fair.** Reuse the approach that worked:
   maintain ONE canonical behavioral suite per feature (not per arm), overlay it
   onto whichever arm's tree is being scored, run with an explicit
   `--ds=config.settings` via a venv that has pytest. Deselect any test that was
   red on the base repo.

3. **Cascading failure ambiguity.** If feature 3 breaks feature 1, does the arm
   "continue" with broken feature 1, or is the run dead? **Decision:** the arm
   continues (mirrors reality — you don't stop shipping because something
   regressed). Cumulative-regression is a running score, not a halt condition.
   This is exactly the tech-debt dynamic we want to measure.

4. **Cost.** 8 features × 2 arms × N repeats × (C runs ~20-35 min) is real spend.
   **Mitigation:** N=1 for a first directional pass (the sequence itself provides
   8 data points per arm — divergence is visible at N=1); add repeats only on
   steps that look decisive. Consider running the cheaper arm (A, naive) at
   higher N since it's fast.

5. **Model choice.** Run the WHOLE sequence at two model tiers (Opus, Haiku).
   The single-feature result suggests Haiku may show divergence sooner (structure
   compensates for capability). This is arguably the most likely place to see the
   effect — prioritize the Haiku sequence.

---

## Reuses what already exists
- `run_notif_model.sh` — already model-parameterized; generalize its
  task/probe/regression args to accept a *carried-forward workspace* instead of a
  fresh checkout (add a `--continue-from <ws>` mode; skip the clean checkout,
  keep the base-commit snapshot per step for per-feature diffing).
- The regression-overlay mechanism (C-suite pytest with `--ds`) — extend from
  "one suite" to "accumulate suites 1..N-1".
- FINDINGS.md format for the writeup.

## First concrete step when picking this up
1. Lock the feature sequence + ordering (8 above, or trim to 5 for a first run).
2. Build feature 1's task + tests + reference (drafts — already exists).
3. Build the `--continue-from` harness mode + cumulative-regression scorer.
4. Dry-run the reference impls chained 1→3 to prove the cumulative gate works
   before spending on agents.
5. Run arm A (Haiku) through the full sequence first — cheapest path to first
   signal.
