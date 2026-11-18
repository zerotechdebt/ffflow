# Justfile cartridge: Tier 1 — quality patterns

## Purpose

Add Tier 1 justfile recipes — quality reporting and dev-loop convenience. Non-blocking by default (informational). Loaded by `stack-init` when the project's `justfile_maturity` reaches 1.

## Recipes

```just
# Continuous test execution on file changes
test-watch:
    <stack-specific watcher>

# Integration tests (slower, may hit DB/network) — not in check-all
integration-test:
    <runs tests tagged @integration or under tests/integration/>

# Detailed complexity report (informational, does not block)
complexity:
    <stack-specific report>

# Largest files by lines of code
loc:
    <stack-specific report>

# Duplication report (informational)
duplicates:
    <stack-specific tool>

# Find slow tests (>50ms unit, >200ms spec)
slowtests:
    <run with duration profiling>
```

## Per-language implementations

The recipe bodies live in one file per stack under `tier-1-quality/`. Load only the file for the stack you're activating — the concept (this file) stays language-agnostic.

| Stack | Detail file |
|---|---|
| Python | [`tier-1-quality/python.md`](tier-1-quality/python.md) |
| TypeScript | [`tier-1-quality/typescript.md`](tier-1-quality/typescript.md) |
| Java | [`tier-1-quality/java.md`](tier-1-quality/java.md) |
| Rust | [`tier-1-quality/rust.md`](tier-1-quality/rust.md) |

Adding a stack = add one file in `tier-1-quality/`; do not edit this concept file.

## Rules

- **None of these go in `check-all`**. They're reporting / dev convenience.
- **Integration tests are tagged**, never auto-included.
- **Watch mode is per-developer**, not CI.
- **Slow-test signals** are inputs to `/audit --type refactor`, not blocking gates.

## Anti-patterns

- Adding `complexity` to `check-all` and gating PRs on it. Use the lint complexity rule (in `lint`) for blocking; this recipe is for the detailed report.
- Running `integration-test` in `check-all`. Will block on slow external systems.
- Treating `loc` output as a blocker. It's a signal; let `/audit --type refactor` decide what's actionable.

## Friction addressed

- Dev loop without watch mode collapses to "save → manually rerun tests" pattern.
- Integration tests bleeding into unit-test runs.
- Code-health signals living in tools nobody runs.
