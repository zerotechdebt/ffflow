# Audit cartridge: tech-debt (zero-tech-debt + yagni enforcement)

## Purpose

Scan the codebase for unmarked deferrals — the "we'll get to it" comments that the `zero-tech-debt` and `yagni` skills forbid. Surfaces findings in the standard audit format; findings convert to refactor tasks via `/fff:audit --plan`.

This cartridge encodes the philosophy: every noticed issue should be either fixed (zero-tech-debt) or documented with a concrete trigger (yagni). Anything in between — bare TODOs, vague intentions, "future work" prose — is debt that won't get paid.

## When this runs

- `/fff:audit` (default — runs every applicable cartridge for the project's level).
- `/fff:audit --type tech-debt` (explicit invocation).
- `/fff:ci-gates` on PRs (via the audit CI integration).

Applicable at every level. The convention doesn't depend on whether you're at L0 or L3.

## What it scans for

### 1. Bare TODOs

Comments matching `TODO`, `FIXME`, `XXX`, `HACK`, `BUG` (case-insensitive) **without a trigger condition**.

A trigger condition is text in the form `re-evaluate when <something>` or `re-evaluate after <something>` in the same comment (or, for multi-line forms, in the comment block).

Examples (findings):

```python
# TODO: refactor this
# FIXME: handle the null case
# XXX why is this here
# HACK: works for now
```

Examples (not findings — properly triggered):

```python
# TODO(re-evaluate when 5+ RIDs land): switch to dynamic marker registration
# TODO(re-evaluate when read-load > 1k req/s): caching layer
# FIXME(re-evaluate after v2 schema migration): drop the compatibility shim
```

### 2. Vague triggers

Comments that *try* to defer but use forbidden vague language:

- `eventually`
- `someday`
- `when we have time`
- `if it becomes a problem`
- `at some point`
- `later`

These are deferral-without-deferral. Findings either way — sharpen the trigger or fix now.

Match by meaning, not by word. `later` and `eventually` also describe time order ("the token is checked later in the pipeline"). A comment that defers no work is not a finding.

### 3. "We should..." / "Consider..." patterns

Comments expressing preference without action:

```python
# We should refactor this someday
# Consider extracting this into a port
# Might be worth caching here
```

These are zero-tech-debt failures dressed as casual observations. Either fix or trigger.

### 4. PR-body "future work" sections

When scanning a PR (via CI), look in the PR body for sections labeled:

- `## Future work`
- `## Follow-ups`
- `## TODO`
- `## Polish` / `## Nice to have`

These belong as captured issues (durable, tracked) or code TODOs (with triggers), not as PR-body prose that disappears when the PR closes.

## Finding shape

Per the standard audit result format:

```json
{
  "cartridge": "tech-debt",
  "status": "warn",
  "findings": [
    {
      "severity": "low",
      "file": "src/auth/signup.py",
      "line": 42,
      "summary": "Bare TODO without trigger condition.",
      "snippet": "# TODO: handle the validation case",
      "auto_fixable": false,
      "category": "bare-todo"
    },
    {
      "severity": "low",
      "file": "src/billing/calculator.py",
      "line": 117,
      "summary": "Vague trigger ('eventually'). Sharpen to a concrete inflection or fix now.",
      "snippet": "# TODO: eventually we should batch these queries",
      "auto_fixable": false,
      "category": "vague-trigger"
    }
  ],
  "state_updates": {
    "tech-debt": {
      "last_run_commit": "abc123",
      "bare_todo_count": 4,
      "vague_trigger_count": 2,
      "should_pattern_count": 3,
      "pr_body_future_work_count": 0
    }
  }
}
```

Severity is **low** by default — these are not blockers. They're signals that compound. Project owners can raise severity via config if they want CI to gate on them.

Open findings are recorded in `.ffflow/audit.yaml` per the `audit` skill ("Findings record"), with `category` as `type`.

## Severity rules

By default:
- All findings: **low**.

User can raise via `.ffflow/audit.yaml`:

```yaml
auditors:
  tech-debt:
    severity:
      bare_todo: medium       # raise to medium if bare TODOs should block PRs
      vague_trigger: medium
      should_pattern: low
      pr_future_work: medium  # block PRs with prose follow-ups
```

## Trends matter more than absolute counts

`state_updates` records counts each run. A project at low absolute count but rising trend is doing worse than one at higher absolute count but falling trend. Future reporting could surface trends; for now the state is recorded for downstream tooling.

A single high count isn't necessarily bad — a brownfield project that just adopted FFFlow might have 200 bare TODOs from years of history. The point is the *trajectory* after adoption.

## Auto-fix

Generally not auto-fixable. The whole point of the rule is human judgment: fix now (which requires understanding the code) or write a trigger (which requires naming a concrete inflection). Neither is mechanical.

The cartridge does NOT:

- Delete bare TODOs.
- Replace bare TODOs with synthetic triggers.
- Comment out problematic code.

It only surfaces findings.

## Per-language scanning notes

The cartridge is language-agnostic — it grep-scans comments. Per-language idioms it recognizes:

- **Python**: `# TODO`, `# FIXME`, `"""TODO ..."""` docstrings.
- **TypeScript / JavaScript**: `// TODO`, `/* TODO ... */`, JSDoc `@todo`.
- **Rust**: `// TODO`, `//! TODO` (inner doc), `/// TODO` (outer doc).
- **Java**: `// TODO`, `/* TODO ... */`, Javadoc `@todo`.

Custom comment patterns can be added via `.ffflow/audit.yaml`:

```yaml
auditors:
  tech-debt:
    patterns:
      - "WONTFIX"
      - "DEFERRED"
```

## Configuration

`.ffflow/audit.yaml` extensions for this cartridge:

```yaml
auditors:
  tech-debt:
    ignore_paths:
      - "vendored/**"
      - "third_party/**"
    severity:
      bare_todo: low
      vague_trigger: low
      should_pattern: low
      pr_future_work: low
    patterns:                  # additional comment patterns beyond TODO/FIXME/XXX/HACK/BUG
      - "WONTFIX"
```

## Anti-patterns

- Deleting flagged TODOs without addressing them. The scan would pass; the problem stays.
- Treating "low severity" as "ignore." Low is a signal that compounds.
- Allowing severity bumps to hide work — if you're raising `bare_todo` to `medium` to block PRs, also commit to fixing the existing backlog. The audit isn't a moralizing weapon.

## Related

- **`zero-tech-debt`** — the "fix now" side of the philosophy this cartridge enforces.
- **`yagni`** — the "defer with trigger" side.
- **`/fff:refactor`** — converts findings into actionable refactor tasks via `/fff:audit --plan`.

## Friction addressed

- TODOs that proliferate without dates, owners, or triggers.
- "Future work" that exists only in PR bodies and evaporates when the PR closes.
- Codebases that fail the zero-tech-debt + yagni discipline silently because nothing scans for it.
- Reviewers who can defer issues without committing to a follow-up trigger.
