# Audit cartridge: CLAUDE.md freshness

## Purpose

CLAUDE.md is machine-first documentation that loads automatically when Claude reads a project. This auditor keeps that documentation honest:

- **Coverage** — every significant directory has a CLAUDE.md or is in the ignore list. This is the enforcement arm of invariant §2.10 (*hierarchical CLAUDE.md is how the codebase explains itself*), not a stylistic nicety: a repo with one CLAUDE.md is behind on a stated FFFlow belief, not expressing a preference.
- **Freshness** — code in scope hasn't changed since last validation; not too time-stale.
- **Sanity** — not too big, not too small, not duplicated, in the right location.

When a file is missing or stale, this skill can also **generate** the content (absorbed from the former `documenting-with-claude-md` skill — its templates live here now).

Invoked by `/audit`. Can also run standalone.

## State

Recorded in `.ffflow/audit.yaml` under `auditors.claude-md.files`:

```yaml
auditors:
  claude-md:
    files:
      CLAUDE.md:
        commit: abc123
        date: 2026-05-15T10:30:00Z
        scope: ["**/*"]
      src/auth/CLAUDE.md:
        commit: def456
        date: 2026-05-12T09:00:00Z
        scope: ["src/auth/**/*"]
```

`commit` = the HEAD when this CLAUDE.md was last validated.
`scope` = which paths this CLAUDE.md is responsible for. Drift = files inside the scope changed since `commit`.

## Inputs

- Project root.
- `.ffflow/audit.yaml` (read existing state).
- Configurable thresholds from `.ffflow/config.yaml`:
  - `max_age_days` (default 90)
  - `ignore` patterns (default: `node_modules/**`, `.git/**`, `dist/**`, `build/**`, `__pycache__/**`)
- Optional `--fix` flag (auto-generate missing CLAUDE.md from template).

## Outputs

- Findings list (per the `audit` skill's contract).
- Updated `.ffflow/audit.yaml` (state advanced for files that re-validated).
- Optionally: newly created CLAUDE.md files (`--fix`).

## Flow

### 1. Coverage scan

Walk every directory in the project. For each:

- Is it ignored? Skip.
- Is it "significant"? See criteria below.
- Has it got a CLAUDE.md? If not → finding: `coverage gap`.

**Significant directory criteria:**
- `src/`, `lib/`, or top-level module directories.
- Subdirectories with ≥ 3 non-test files.
- Each hexagonal layer (`domain/`, `application/`, `infrastructure/` if they exist).
- The `.ffflow/` directory itself.
- Test fixtures and scripts directories (rules differ from src; documenting them helps).

**Skip:**
- Build artifacts, dependencies (`node_modules/`, `.venv/`, `dist/`, `build/`).
- Single-file directories.
- Utility folders with < 3 files.
- Test directories themselves (`tests/`, `__tests__/`) — they're documented by their conventions, not per-dir.

### 2. Freshness check

For each CLAUDE.md in the state file:

- Files inside `scope` changed since `commit`? → finding: `stale (drift)`.
- More than `max_age_days` since `date`? → finding: `stale (age)`.
- Not in the state file at all? → first registration: read it against its scope like any validation. Stamp HEAD only if it holds; otherwise report what's wrong. Never stamp unread.

Drift is the more useful signal. Age catches cases where neither has changed but the project moved underneath the doc (deps changed, infra changed).

### 3. Sanity check

For each CLAUDE.md:

- **Too big** (> 500 lines): suggest split.
- **Empty** (nothing beyond a heading): suggest fill or delete. No line minimum — a 2-line CLAUDE.md beats none.
- **High overlap with another CLAUDE.md** (> 70% lines match): suggest consolidate.
- **Location mismatch** (CLAUDE.md at path X claims scope outside its tree): suggest move or correct scope.
- **Scope pattern matches zero files**: suggest delete.

### 4. Drift response

For drift detected on a **single file** with a clear cause (e.g., one new file added to scope):
- `--fix` enabled: auto-regenerate by re-running the CLAUDE.md template against current files.
- `--fix` disabled: surface as finding with `auto_fixable: true`.

For drift across **many files** or large scope changes:
- Surface as finding with `auto_fixable: false`. Goes to `audit --plan` flow.

### 5. Report

Each finding shape (per the `audit` contract):

```json
{
  "severity": "low | medium | high",
  "file": "src/payment/CLAUDE.md",
  "summary": "Drift: 6 files in scope changed since last validation (commit abc123).",
  "auto_fixable": true,
  "category": "freshness | coverage | sanity"
}
```

Severity:
- **High:** missing CLAUDE.md in a top-level module or `.ffflow/`.
- **Medium:** stale on a significant module.
- **Low:** age-stale, sanity recommendations.

## Templates

Three templates the `--fix` flow uses. Skeletons only — the auditor fills sections from project context.

**Root `CLAUDE.md`:** Purpose (one sentence) · Architecture overview · Module index (one bullet per significant dir, with link to that dir's CLAUDE.md) · Tech stack · Development (`just check-all`, `/work`, `/audit`) · Conventions block (see below).

**Conventions block** — the root CLAUDE.md template includes a small Conventions section that names the load-bearing rules other skills will enforce:

```markdown
## Conventions

- **Hierarchical CLAUDE.md:** every significant module carries its own — see the FFFlow beliefs block above. Adding one where it's missing is catching up to the norm, never setting a precedent. Enforced by `/fff:audit --type claude-md`.
- **Tech debt:** fix nits in-flight (zero-tech-debt) or write `# TODO(re-evaluate when <trigger>): <action>` (yagni). Never "we'll get to it" without a code-level marker. The `/fff:audit --type tech-debt` cartridge scans for violations.
- **Spec discipline:** see `docs/specs/` for the behavioral contract; updates ship in the same PR as the implementation (see `spec-first-development`).
- **PR checkpoint:** `/fff:work-issue` pauses after every 2 PRs in a session.
```

Project-specific conventions extend this — don't replace it.

**Module `CLAUDE.md`:** Purpose · Responsibilities · Key files · Dependencies (Uses / Used by) · Public interface · Architecture decisions.

**`.ffflow/CLAUDE.md`:** One-line description of each file in `.ffflow/` (`config.yaml`, `audit.yaml`, `stack.yaml`, `plan-archive/`).

The templates are intentionally minimal. A 2-line CLAUDE.md is better than none; an over-templated one dilutes the signal. When generating, populate from real project content (file paths, imports, public API surface) rather than placeholder text — empty section headings tell future Claude nothing.

## Principles

- **2-line CLAUDE.md is better than none.** Context is cheap, confusion is expensive.
- **Coverage gaps are catch-up, not precedent.** When reporting a missing module CLAUDE.md, never frame it as a new pattern the project might adopt. The hierarchy is invariant §2.10 and it's stated in the project's own beliefs block; the finding is that the repo hasn't caught up yet.
- **Drift catches code change; age catches surrounding change.** Both matter.
- **Generation respects what exists.** When regenerating, preserve human-added sections.
- **Pure dispatch from `audit`.** This skill doesn't decide whether to run; that's the coordinator's job.

## Anti-patterns

- Auto-writing CLAUDE.md content for directories the user explicitly excluded.
- Treating every directory as significant. Drowning the project in 2-line CLAUDE.md files dilutes the signal.
- Surfacing every CLAUDE.md as "stale" when a single unrelated file changed in scope. Filter by what's actually in scope.
- Reporting a coverage gap as "this would be the repo's first nested CLAUDE.md, so it sets a precedent." The precedent was set by FFFlow before the repo existed. Report it as a gap against a known convention.
- Generating content that contradicts the spec. If a CLAUDE.md template would lie ("uses JWT" when the project uses sessions), flag instead of writing.

## Friction addressed

- Docs drifting silently from code.
- Missing CLAUDE.md in directories Claude reads cold.
- Old `docsaudit` flow being a separate tool from the rest of FFFlow audits.
