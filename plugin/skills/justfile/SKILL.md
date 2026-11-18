---
name: justfile
description: Justfile interface and maturity model for FFFlow — baseline recipes every project implements (test, lint, format, check-all, etc.) plus tier cartridges (Tier 1 quality, Tier 2 security, Tier 3 advanced, Tier 4 polyglot orchestration).
---

# justfile

## Purpose

The shared build interface every FFFlow project implements, plus the maturity model for adding tier-specific patterns over time.

Two concerns combined into one skill:
1. **Baseline interface** — the recipes every project has, under exact names so people and tooling can call them.
2. **Maturity model** — when and why to add Tier 1–4 patterns. Cartridges under `cartridges/` carry the recipes for each tier.

## Terminology: Level vs. Tier

- **Level (L0–L3)** = FFFlow methodology rigor (declared in `.ffflow/config.yaml`). Affects spec discipline.
- **Tier (0–4)** = justfile maturity (orthogonal to level). Affects build-interface completeness. Declared as `justfile_maturity: <0–4>` in `.ffflow/stack.yaml`; absent means 0.

A project at FFFlow L1 might be at justfile Tier 0 (just bootstrapped) or Tier 3 (production). Pick each independently.

## Baseline (Tier 0) — every project

```just
set shell := ["bash", "-uc"]

# Show all available commands
default:
    @just --list

# Install dependencies and setup development environment
dev-install:
    <install deps, create venvs, download tools>

# Format code (auto-fix)
format:
    <auto-fix whitespace/style>

# Lint code (auto-fix, complexity threshold=10)
lint:
    <auto-fix linting, complexity=10>

# Type check code
typecheck:
    <static type checking>

# Run unit tests
test:
    <unit tests only, fast>

# Run unit tests with coverage threshold
coverage:
    <unit tests, 95% threshold, blocks if below>

# Run all quality checks (format, lint, typecheck, coverage - fastest first)
check-all: format lint typecheck coverage
    @echo "All checks passed"

# Remove generated files and artifacts
clean:
    <remove build artifacts, caches>
```

Stub what you can't implement: `@echo "not implemented"`. Stubs signal intent and pass the interface check.

## FFFlow additions

These engage based on FFFlow level (not justfile tier):

**L2+ recipes:**

```just
# Run BDD spec tests
spec-test:
    <run Gherkin scenarios only>

# Run spec tests with coverage threshold (80%)
spec-coverage:
    <spec tests, 80% threshold>
```

When present, `check-all` extends:
```just
check-all: format lint typecheck coverage spec-coverage
```

**L3 recipes:**

```just
# Run spec traceability audit (RID/specdrive).
# specdrive is a language-agnostic CLI on npm — same invocation on every stack.
# TypeScript projects may use `pnpm specdrive audit`; all others use `npx specdrive audit`.
spec-audit:
    <npx specdrive audit  (or `pnpm specdrive audit` on TypeScript)>

# Run mutation testing
mutate:
    <stryker / mutmut / PIT>
```

At L3, `check-all` includes `spec-audit` (but NOT `mutate` — slow gates kill the loop):
```just
check-all: format lint typecheck coverage spec-coverage spec-audit
```

## Rules

- **Exact names, true comments.** Recipe names must match; tooling calls them. Every recipe carries a one-line comment saying what it does in this project. A cartridge's comment is the default wording for the default recipe. When your recipe differs (a severity, a threshold, an allow-list in place of a deny-list), its comment says what it really does.
- **All required recipes present (per tier and level).** Stub missing ones.
- **`check-all` order**: format, lint, typecheck, coverage, spec-coverage, spec-audit. Fastest first.
- **`test` vs `spec-test`.** `test` runs unit tests. `spec-test` runs BDD scenarios. They do not overlap. `coverage` measures unit coverage. `spec-coverage` measures spec coverage.
- **`mutate` is NOT in `check-all`.** Mutation testing is slow. Run it explicitly or on a schedule (e.g., weekly via CI cron). This rule is the single source of truth — other skills reference it rather than restating.

## The tier ladder

Five tiers. Start at 0. Add tiers when needed. YAGNI applies at every step.

| Tier | Theme | Cartridge | When |
|---|---|---|---|
| 0 | Baseline (above) | — | All projects, no exceptions |
| 1 | Quality patterns: test-watch, integration-test, complexity, loc, duplicates, slowtests | `cartridges/tier-1-quality.md` | Setting up CI/CD; multi-developer; fast feedback wanted |
| 2 | Security: vulns, lic, sbom, doctor | `cartridges/tier-2-security.md` | Deploying to production; compliance |
| 3 | Production: test-smart, deploy, migrate, logs, status | `cartridges/tier-3-advanced.md` | Production deployment; database-backed |
| 4 | Polyglot: multi-language orchestration | `cartridges/tier-4-polyglot.md` | Monorepo / multiple languages |

Cartridges are markdown files under `cartridges/`. Load only the cartridge(s) for tiers you're activating.

## Progression

**Typical paths:**
- Web app: 0 → 1 → 2 → 3
- Library: 0 → 1 → 2 (no deployment)
- Monorepo: 0 → 1 → 4 → 2
- Solo project: 0 → 2 (skip quality overhead)

**Non-linear allowed.** Add specific recipes without completing a full tier:
```bash
/stack-init upgrade vulns       # Add vulns from Tier 2, skip rest
```

**When to stop.** Do not add a tier you will not use. No CI? Skip Tier 1. No deployment? Skip Tier 3. Single language? Skip Tier 4.

## Per-level interface check

`stack-assess` runs the interface check:

| Level | Required recipes (Tier 0 baseline) |
|---|---|
| L0/L1 | default, dev-install, format, lint, typecheck, test, coverage, check-all, clean |
| L2 | above + spec-test, spec-coverage |
| L3 | above + spec-audit, mutate |

Missing required recipes are a finding. Stubs satisfy the requirement.

Plus the recipes of every tier up to the declared `justfile_maturity`.

## Stack implementations

See the `stack` skill's cartridges (`python.md`, `typescript.md`, `java.md`, `polyglot.md`) for the per-stack recipe content (which tool implements each recipe).

## Anti-patterns

- Renaming recipes (`format` → `fmt`, `test` → `t`). Tooling expects exact names.
- A recipe with no comment, or a comment describing something other than what it runs.
- Putting integration tests in `test`. Use a separate recipe (`integration-test`, from Tier 1).
- Adding `mutate` to `check-all`. Slow gates kill the loop.
- Skipping Tier 0. Baseline is non-negotiable.
- Adding all tiers upfront. YAGNI.
- Blocking on `spec-audit` failures in local dev. CI-only gate.
