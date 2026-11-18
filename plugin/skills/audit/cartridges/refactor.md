# Audit cartridge: code-health (refactor signals)

## Purpose

Catch code-health problems before they compound. Runs the stack's complexity and duplication tools, plus the FFFlow-specific signals (test slowness, redundancy, hot spots).

Absorbs the former `test-optimization` skill — test health is a code-health signal at the same level as cyclomatic complexity.

Invoked by `/audit`. Findings can convert directly to a plan via `audit --plan`.

## Inputs

- `.ffflow/config.yaml` for thresholds (or defaults).
- Source + test trees. **In a polyglot monorepo these are per-subproject** — see "Scope" below; do not assume a single `src/`.
- Stack skill for tool commands (the `dimensions:` block is canonical; this cartridge defers to it rather than hardcoding per-language invocations).

## Outputs

- Findings.
- Stage findings sorted by `impact / (complexity + 1)` for the plan-generation path.

## Thresholds

Defaults (overrideable in config):

```yaml
audit_refactor:
  complexity_limit: 10               # cyclomatic
  file_loc_warn: 250
  file_loc_block: 500
  duplication_threshold: 0.3         # 30% identical lines
  hot_spot_lookback_commits: 50
  hot_spot_sweep_share: 0.2          # commits touching > 20% of files don't count as churn
  test_unit_max_ms: 50
  test_spec_max_ms: 200
  test_suite_max_seconds: 30
```

`complexity_limit` is cyclomatic. Rust's clippy uses **cognitive** complexity (a different metric; the Rust stack cartridge defaults it to 25, tunable in `clippy.toml`). Don't apply the cyclomatic `10` to Rust findings — read the threshold from the active stack's `dimensions:` block.

## Scope (single-tree vs polyglot)

Determine the scan scope before running any step.

- **Single-tree project** — one stack, one source root. Scan it directly.
- **Polyglot monorepo** — multiple subprojects, each with its own stack (e.g. `provable-ts/`, `provablecode-py/`, a Rust crate). There is no top-level `src/`. Run every step **per subproject**, resolving each subproject's stack from its own stack cartridge / justfile, then aggregate findings with their subproject path. Never scan the repo root as if it were one tree — `jscpd src/` against a polyglot root finds nothing or the wrong thing.
- **Explicit target** — when `/refactor <path>` (or `/audit --type refactor <path>`) names a path, scan only that subtree and use the stack that owns it. This is the recommended invocation for large polyglot repos: scope to one subproject's hotspot, get one reviewable PR.

If no target is given and the repo is polyglot, enumerate subprojects (the polyglot stack cartridge's subproject list) and iterate; do not silently scan only the root.

### 1. Complexity

Run the stack's complexity tool. **Do not hardcode the per-language command here** — the stack skill's `dimensions:` block is the canonical record of which tool each stack uses (the same tool the justfile `complexity` recipe wraps; see `justfile/cartridges/tier-1-quality/<stack>.md`). Read the active stack's cartridge for the invocation. Across stacks today that resolves to: ruff `C90` (Python), eslint `complexity` (TypeScript), SpotBugs (Java), clippy `cognitive_complexity` (Rust). New stacks work automatically — when a stack cartridge defines the tool, this scan picks it up with no edit here.

The audit reports at `error` severity (every function over `complexity_limit` is a finding), independent of whether the justfile recipe runs the same tool at `warn` for its informational report.

Each function above the limit is a finding (severity = low if just over, medium if 2× over, high if 3× over).

### 2. LoC

Per-file line counts. Files above `file_loc_warn`: low/medium severity (depends on layer — domain has tighter budget than infrastructure).

Files above `file_loc_block`: high.

### 3. Duplication

Run the stack's duplication detector — the same one the justfile `duplicates` recipe wraps (`justfile/cartridges/tier-1-quality/<stack>.md`); don't restate the command per language here. Across stacks today: jscpd (TypeScript), pylint `R0801` or jscpd (Python), CPD (Java).

**Rust has no first-class duplication tool** (no mature CPD/jscpd equivalent). For Rust, this scan produces no findings of its own; lean on clippy's copy-paste lints plus the LoC (step 2) and hot-spot (step 4) signals, and flag candidate clusters for manual review. Do not substitute a weak token-scanner — a misleading duplication signal is worse than an acknowledged gap.

Any duplicate cluster above `duplication_threshold` is a finding. Cite both/all instances.

### 4. Hot spots

Combine complexity with churn:

- For each file with complexity ≥ 8, count its commits in the last `hot_spot_lookback_commits`. Skip sweep commits — ones touching more than `hot_spot_sweep_share` of tracked files (renames, format runs). They inflate every file's churn equally.
- "Hot spots" = complexity ≥ 8 AND churn in top 25%. Surface as high-priority findings.

The idea: a complex file nobody touches is fine; a complex file everyone keeps touching is where bugs accumulate.

### 5. Test health

From the former `test-optimization`:

**Speed analysis:**
- Per-test duration via the stack's profiling run (the justfile `slowtests` recipe wraps it per stack — pytest `--durations`, vitest reporter, surefire, cargo-nextest). Don't hardcode one runner.
- Unit tests over `test_unit_max_ms` → finding (low).
- Spec tests over `test_spec_max_ms` → finding (low).
- Total suite over `test_suite_max_seconds` → finding (medium).

Common causes annotated in the finding:
- DB call: mock with fixtures.
- External API: mock response.
- File I/O: in-memory.
- Sleep/wait: mock time.

**Redundancy:**
- Semantic overlap: tests with > 70% similar assertions → finding with both names, suggest deleting the weaker one.
- Cross-suite overlap: unit test and spec test asserting identical behavior at identical layer → finding, suggest consolidating to the appropriate suite.

**DRY opportunities:**
- Fixture candidates: repeated object creation across tests → finding.
- Parameterization: similar tests with different inputs → finding.

### 6. Prioritize

Sort findings by `impact / (complexity + 1)`:

- Speed fixes on slow tests: high impact, low complexity → top of list.
- Removing redundant tests: medium impact, low complexity.
- DRY refactoring: medium impact, medium complexity.
- Complexity reduction in a hot spot: high impact, high complexity → still high priority because of the impact.

Open findings are recorded in `.ffflow/audit.yaml` per the `audit` skill ("Findings record").

## Plan-generation flow

When `/audit --plan` runs:

1. Filter to medium-or-higher severity findings.
2. Group by file when possible (one refactor task per file makes for cleaner PRs).
3. Generate a plan whose tasks read:

```markdown
# Task: Reduce complexity in src/auth/signup.py

## Problem
src/auth/signup.py contains 3 functions over complexity limit 10:
  - signup_user (complexity 17)
  - validate_signup_request (complexity 14)
  - persist_signup (complexity 12)

## Approach
1. Extract method for input validation phase.
2. Extract method for persistence phase.
3. Use a small DTO to pass data between phases.

## Out of scope
- Behavior change. This is a structural refactor only.
- Touching other files with similar issues.

## Acceptance
- [ ] All complexity warnings on signup.py cleared.
- [ ] Existing tests still pass with no modification.
- [ ] No new public API.
```

## Safeguards

- Never remove tests as part of a finding — only **suggest**. The user decides.
- Never apply complexity refactors automatically. The fix is structural; auto-application produces bad code.
- Re-run after any user-applied fix to confirm the finding is resolved.
- **Report skipped scans; never imply full coverage.** If a scan can't run for the active stack (e.g. duplication on Rust), say so explicitly in the output — "duplication: not run (no first-class Rust tool)" — rather than emitting nothing and reading as "clean." A skipped scan and a clean scan must not look the same.
- **State the scope scanned.** In a polyglot repo, list which subprojects were scanned and which were skipped, so partial runs are visible.

## Anti-patterns

- Treating "high LoC" as inherently bad. Some files (configs, generated code, fixtures) legitimately are large — exclude via config.
- Counting every duplication as a finding. The rule of three: < 3 duplicates is acceptable.
- Recommending refactors that would break the architecture. Cross-check with `audit-architecture` before suggesting.

## Friction addressed

- Test suites drifting from <30s to >5 minutes over time, with no single PR being blamed.
- Complexity creeping into hot files where the cost of refactoring keeps rising.
- "We should refactor this someday" — `audit --plan` turns it into actual tasks.
- Test redundancy hiding behind growing coverage numbers.
