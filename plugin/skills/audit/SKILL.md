---
name: audit
description: Run the FFFlow keep-honest auditors against this project. Coordinator with per-type cartridges (CLAUDE.md freshness, spec drift, characterization tests, architecture conformance, complexity/refactor signals, and L3 RID traceability). Use --type to target one; --plan to convert findings into work.
---

# audit

## Purpose

Dispatch + aggregate + render. Runs the per-type auditors that apply to this project's level, aggregates their findings into the unified `.ffflow/audit.yaml` state, and renders a single report. With `--plan`, above-threshold findings become a plan that flows through `plan-breakdown → plan-capture → work`.

The coordinator does no auditing itself — every finding originates from a per-type auditor. Aggregation and report rendering are the only logic this skill owns.

**Invariant: `audit.yaml` is written by auditors only. An editor never stamps its own work.** A stamp means an auditor read the file at commit X and found it true — that's what makes it worth more than the author's own say-so. Any other skill that touches an audited file leaves the stamp alone; going stale is the correct, visible state until the next `/fff:audit` re-validates it. The one sanctioned exception is `characterize`, which registers `characterized: true` for spec entries it just wrote — that's an auditor-shaped act (declaring new audit surface), not self-certification of a code change.

## Inputs

- `.ffflow/config.yaml` — level, stack, audit config file path.
- `.ffflow/audit.yaml` — per-auditor state (validated commits, scope, last-passed timestamps).
- Optional `--type <auditor>` to run a subset (`--type claude-md,spec`).
- Optional `--plan` to convert findings to a plan in `plan/audit-<slug>/`.
- Optional `--ci` for machine-readable output (JSON) instead of human report.
- Optional `--fix` to authorize small auto-fixes (per-auditor decision; not all support it).

## Outputs

- Console report (or JSON if `--ci`).
- Updated `.ffflow/audit.yaml` (each auditor writes its own section).
- Optionally `plan/audit-<slug>/` populated as if `plan-chat` had run.
- Exit code: 0 if all auditors pass, non-zero if any above-threshold finding (gates CI use).

## Cartridges

Per-type auditors live as cartridges under `cartridges/`. The coordinator loads them on demand based on `--type` and project level:

| Cartridge | When it runs | Notes |
|---|---|---|
| `cartridges/claude-md.md` | any level, if any CLAUDE.md files exist | always available |
| `cartridges/spec.md` | any level, if a spec directory exists | mechanism varies by level (prose re-read at L0/L1, scenario run at L2, RID delegation at L3) |
| `cartridges/char-tests.md` | any level, if characterization tests registered | strict-block on failure |
| `cartridges/architecture.md` | L1+ | uses `hexagonal-architecture` defaults for hex projects |
| `cartridges/refactor.md` | any level | complexity, LoC, duplication, hot spots, test health |
| `cartridges/tech-debt.md` | any level | bare TODOs, vague triggers, "we should..." patterns, PR-body "future work" prose. Enforces `zero-tech-debt` + `yagni` |
| `cartridges/rid.md` | L3 only | wraps `specdrive audit` |

Cartridges aren't separate skills — they're reference files. The LLM doesn't see them in its skill index; this skill loads them when needed.

## Flow

### 1. Resolve which cartridges to run

| Flag | Cartridges loaded |
|---|---|
| `--type <list>` | exactly those (e.g., `--type spec,refactor`) |
| (default) | every cartridge applicable to the project's level |

Applicability rules are in the table above.

### 2. Run cartridges in parallel where safe

Cartridges are independent. For each: load the cartridge file, follow its procedure (run the stack's tool, scan files, etc.), collect findings.

No audit logic lives in this skill — the cartridges describe the inspection procedures. The coordinator's I/O is limited to: reading `.ffflow/config.yaml` and `.ffflow/audit.yaml`, loading cartridges, executing their procedures (possibly via subagents), merging their results, writing the unified state file, and rendering the report.

### 3. Collect findings

Each cartridge produces a structured result:

```json
{
  "cartridge": "spec",
  "status": "pass | fail | warn",
  "findings": [
    {
      "severity": "low | medium | high",
      "file": "docs/specs/auth.md",
      "summary": "Spec section 'Token refresh' references TokenService.refresh() which was removed in abc123.",
      "auto_fixable": false
    }
  ],
  "state_updates": { ... }   // gets merged into .ffflow/audit.yaml
}
```

### 4. Apply state updates

For each cartridge's `state_updates`, merge into `.ffflow/audit.yaml`. This is the keep-honest record:

- `validated_at` timestamps per file.
- `scope` lists (which files a cartridge covers).
- `last_pass_commit` hashes.

If two cartridges update the same key, last-write-wins is fine — they shouldn't disagree.

**Stamp a commit that survives the merge.** Squash and rebase rewrite hashes, leaving stamps that name commits that no longer exist. Re-stamp after a squash or rebase. The record commits after the code it describes, never with it.

### 4a. Findings record

Open findings live under their auditor, beside `files`:

```yaml
auditors:
  tech-debt:
    findings:
      - file: src/auth/signup.py
        line: 42
        type: bare-todo          # the finding's category
        severity: low
        status: open             # open | fixed
        found: abc123            # commit where first seen
        fixed: def456            # set when closed
```

Each run matches findings by file, type and content (snippet or summary) — lines move. A recorded finding the run no longer sees becomes `status: fixed` with `fixed: <HEAD>`. Only the auditor closes a finding; an editor's fix waits for the next run, like a stamp. Fixed entries may be pruned once their `fixed` commit is on the default branch.

### 5. Render report

Default human-readable:

```
audit report (level=L1):

  claude-md         ✓ pass (12 files validated)
  spec              ⚠ warn (1 finding)
    - docs/specs/auth.md: drift detected, scope `src/auth/**` changed since 2026-05-10
  architecture      ✓ pass
  refactor          ⚠ warn (3 findings)
    - src/auth/signup.py: complexity 14 (limit 10)
    - src/payment/processor.py: 320 LoC (warn threshold 250)
    - src/utils/string_helpers.py + src/web/string_utils.py: 40% duplication

Total: 4 findings (0 high, 1 medium, 3 low).
Run `/audit --plan` to convert these into a plan.
```

`--ci` flag emits JSON:

```json
{
  "level": "L1",
  "status": "warn",
  "exit_code": 1,
  "auditors": { ... }
}
```

### 6. `--plan` mode

When invoked with `--plan`:

1. Filter to findings above the configured threshold (default: `medium` or higher).
2. Create `plan/audit-<YYYY-MM-DD>-<short-hash>/`.
3. Write `plan.md` summarizing the findings as a problem statement.
4. Write `decisions.md` with any open `?` (e.g., scope of refactor).
5. Update `metadata.json`: `phase: chat-complete`, source: `audit`.
6. Print:
   ```
   Plan created: plan/audit-2026-05-20-abc12/
   Next: /plan-breakdown
   ```

### 7. `--fix` mode

For each cartridge that reports `auto_fixable: true` findings:

1. Apply the fix per the cartridge's procedure.
2. Re-run that cartridge on the affected file.
3. Confirm it now passes.
4. Stage the change (don't commit — user reviews).

Cartridges decide what's auto-fixable. By default, conservative.

## CI integration

The CI workflow (`ci-gates`) runs `audit --ci`. Non-zero exit fails the PR check. Findings appear as GitHub Actions annotations via the workflow.

## Idempotency

- Running `audit` repeatedly on the same state: same report.
- State updates are commit-tagged; a cartridge running on the same commit as last time short-circuits to `pass` quickly.

## Anti-patterns

- This skill generating findings directly. Every finding must come from a cartridge. Aggregation and rendering are the limit of this skill's reach.
- Cartridges that side-effect outside their declared scope. Each writes to its own section of `.ffflow/audit.yaml`.
- `--fix` doing anything destructive. Auto-fix is for the obvious cases (whitespace, missing CLAUDE.md from template); risky fixes go to `--plan`.
- Running L3-only cartridges at L0/L1. Skip silently — that's the level dial doing its job.

## Friction addressed

- Multiple disparate audit tools with no unified view.
- Drift between code and spec going unnoticed for sprints.
- "Audit" being a noun (a once-a-quarter event) instead of a verb (a per-PR gate).
