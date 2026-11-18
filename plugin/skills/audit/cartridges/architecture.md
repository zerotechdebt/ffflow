# Audit cartridge: architecture conformance

## Purpose

Architecture decisions are easy to make, easy to violate, hard to detect. This auditor checks that the project still respects its declared architecture by analyzing imports and dependency graphs.

For hexagonal projects, defaults come from the `hexagonal-architecture` skill.

Invoked by `/audit` at L1+.

## Configuration

Architecture rules live in `.ffflow/config.yaml` under an `architecture:` block:

```yaml
architecture:
  style: hexagonal
  rules_from:                  # optional: where the layering is already written down
    - docs/specs/architecture.md
    - eslint.config.js         # e.g. import-restriction rules
  rules:
    - "src/domain/** must not import from src/infrastructure/**"
    - "src/domain/** must not import from src/application/**"
    - "src/application/** must not import from src/infrastructure/**"
    - "src/ui/** must not import from src/data/**"
```

For hex projects, `style: hexagonal` triggers default rules from `hexagonal-architecture`:
- Domain imports nothing from app or infra.
- Application imports from domain only.
- Infrastructure imports from app and domain (one-way).

User can override or extend.

For non-hex projects, the user declares rules explicitly. No defaults are imposed.

`rules_from` points at files that already state the layering (a spec, lint rules). Read the rules there; `rules` adds to them. Layer folders are the project's own (`src/app`, `src/infra/<adapter>`), not fixed names — map the hexagonal defaults onto them.

No `architecture:` block: look for layering rules in the root CLAUDE.md, the specs and the lint config. Audit against what you find and name the source in the report. Nothing found: one low finding, "no declared architecture".

## Inputs

- `.ffflow/config.yaml`.
- Source tree.
- Stack skill (for the import-parsing convention).

## Outputs

- Findings per the `audit` contract.

## Flow

### 1. Build dependency graph

Per stack:
- **Python**: walk imports via the AST (`ast.parse` on each file). Map `from x.y import z` to a graph edge.
- **TypeScript**: walk imports via `tsc --listFiles` or read each file's `import` statements with the TS compiler API.
- **Java**: walk imports in `.java` files (regex is fine for `import x.y.Z;`).

### 2. Apply rules

For each rule:
1. Parse: "X must not import from Y" → `{forbidden: src/domain/**, target: src/infrastructure/**}`.
2. Scan edges in the graph: any edge from a file matching `forbidden` to a file matching `target`?
3. Each match is a finding.

### 3. Finding shape

```json
{
  "severity": "medium",
  "file": "src/domain/auth.py",
  "summary": "src/domain/auth.py imports src/infrastructure/db.py — violates rule 'domain must not import from infrastructure'.",
  "auto_fixable": false,
  "category": "architecture",
  "evidence": {
    "import_line": 14,
    "import_statement": "from src.infrastructure.db import session"
  }
}
```

### 4. Severity ladder

- **Informational**: import cycles made only of type-only imports (TypeScript `import type`). They vanish at build. List them apart from runtime cycles; they never fail the audit.
- **Low**: stylistic (e.g., runtime circular imports within a layer).
- **Medium**: cross-layer violation (the common case).
- **High**: domain importing infra (the architecturally fatal violation).

User can override severity per rule in config.

## Auto-fix scope

Generally not auto-fixable — the right fix is a refactor, not a textual change. Findings convert to plan tasks via `audit --plan`:

```markdown
# Task: Remove infrastructure import from src/domain/auth.py

## Problem
src/domain/auth.py:14 imports src/infrastructure/db.py, violating hexagonal layering.

## Approach
Extract the needed contract into a port in src/application/, then inject the
infrastructure implementation at composition time.

## Out of scope
- Refactoring other domain modules with similar issues (file separate tasks).
- Changing the port's API beyond what's needed to remove this import.
```

## Hexagonal defaults

When `architecture.style: hexagonal`:

Default rule set (loaded from `hexagonal-architecture` skill):
- `src/domain/** must not import from src/application/**`
- `src/domain/** must not import from src/infrastructure/**`
- `src/domain/** must not import from third-party packages` (except std lib)
- `src/application/** must not import from src/infrastructure/**`
- `src/infrastructure/** can import from src/application/** and src/domain/**`

User can append additional rules; the defaults remain unless explicitly overridden.

## Refactor support

When findings would all be addressed by the same refactor pattern (e.g., "extract three ports for db, http, fs"), `audit --plan` groups them into a single plan rather than three tiny ones. The grouping heuristic: same target module, same layer combination, same suggested refactor name.

## Anti-patterns

- Declaring rules the project doesn't actually follow yet. Use `@accepted-risk` style annotations for known violations during a transition.
- Treating "X imports Y" as a violation when Y is a permitted shared library. The rules must be specific.
- Auto-fixing imports by reordering. The fix is a refactor; reordering hides the smell.

## Friction addressed

- Architecture rules written in CLAUDE.md but never enforced.
- Drift discovered six months later when a senior engineer reads the codebase.
- Hexagonal projects slowly leaking infrastructure into domain.
