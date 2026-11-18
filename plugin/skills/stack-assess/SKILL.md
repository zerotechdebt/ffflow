---
name: stack-assess
description: Compare the current project to its declared stack and level — identify missing tools, version mismatches, configuration gaps, level upgrade readiness.
---

# stack-assess

## Purpose

Read-only audit. Compares what's installed and configured against what the declared stack + level requires. Produces a report; modifies nothing.

Used standalone, or invoked by `stack-init` to compute the upgrade plan.

## Inputs

- `.ffflow/config.yaml` — level, stack.
- Optional `--target-level <L0|L1|L2|L3>` to assess against a level different from the configured one (useful for "what would I need to upgrade to L2?").

## Outputs

Console report.

## Flow

### 1. Read config

- Level (default L0).
- Stack (one of `python`, `typescript`, `java`, `polyglot` — resolves to a cartridge under `stack/`).
- `.ffflow/stack.yaml` overrides if present, including `justfile_maturity` (0–4; absent means 0).

If no config: report "no FFFlow config; run /init-ffflow first" and exit.

### 2. Load stack skill

Read the stack skill's dimensions YAML. This is the canonical "what should be in place at level N."

### 3. Probe project

For each dimension active at the configured level:

- **package_manager**: lockfile present? `<tool> --version` returns OK?
- **formatter / linter / type_checker / test_runner**: tool installed? config in expected location? recipe in justfile?
- **coverage_tool + threshold**: configured at the right floor?
- **complexity_limit**: enforced (lint rule present)?
- **bdd_runner (L2+)**: installed? `specs/` directory exists?
- **property_runner (L2+)**: installed? any `@property-based` scenarios?
- **mutation_tool (L3)**: installed? `mutate` recipe in justfile?
- **spec_audit_cli (L3)**: `npx specdrive` resolvable (Node/npm present)? `spec-audit` recipe in justfile? specdrive is a language-agnostic CLI run via npx on every stack — a missing-specdrive gap is "install Node," never "this stack can't do L3."

Mark each as `OK`, `missing`, `misconfigured`, or `lower-than-floor`.

### 4. Justfile & infra checks

- Baseline `justfile` recipes present (`test`, `lint`, `format`, `typecheck`, `coverage`, `check-all`)?
- Pattern groups present for every tier up to `justfile_maturity` (orthogonal to FFFlow level). Recipes from a higher tier are fine; report them, don't demand the rest. Cartridges live under `skills/justfile/cartridges/`:
  - Tier 1: `tier-1-quality.md` (test-watch, integration-test, complexity, loc, duplicates, slowtests)
  - Tier 2: `tier-2-security.md` (vulns, lic, sbom, doctor)
  - Tier 3: `tier-3-advanced.md` (deploy, migrate, logs, status)
  - Tier 4 (polyglot only): `tier-4-polyglot.md`
- Git hooks installed?
- CI workflow installed (`ffflow-ci.yml`)?

### 5. FFFlow adoption checks

- `.ffflow/config.yaml` present and parseable.
- `.ffflow/audit.yaml` present.
- Spec directory exists per stack convention (`docs/specs/` at L0/L1, `specs/` at L2+).
- At L3: RID tags found in any `.feature` file? Mutation runs configured?

### 6. Report

```
Stack assessment: python (cartridge) @ L1
=====================================

Toolchain
  uv (package_manager)         ✓ 0.4.18
  ruff format                  ✓ 0.4.1
  ruff check (linter)          ✓ 0.4.1
  mypy strict                  ✓ 1.10.0
  pytest                       ✓ 8.2.0
  coverage.py @ 95             ✓ configured
  complexity ≤ 10              ✗ ruff config missing C90 rule

Justfile
  Baseline interface           ✓
  Tier 1 patterns (quality)        partial — missing slowtests, duplicates

Infrastructure
  pre-commit hook              ✓
  pre-push hook                ✓
  ffflow-ci.yml                ✗ missing

FFFlow adoption
  .ffflow/config.yaml          ✓
  .ffflow/audit.yaml           ✓
  docs/specs/                  ✓ (8 spec files)

Summary: 3 gaps at L1.
Next: /stack-init                                # apply missing pieces
      /stack-init upgrade quality                # add just the Tier 1 patterns
      /stack-assess --target-level L2            # see what L2 would require
```

## Symbols

- `✓` present and correct
- `✗` missing
- `~` present but misconfigured
- `partial` present but incomplete

## YAGNI guidance

Don't push every project to L3. Recommendations should match the project's needs:

- Library with no business rules → L0 or L1 is fine.
- Prototype → L0.
- Internal tool with a stakeholder team → L1.
- Customer-facing core with regulated behavior → L2 or L3.

When `--target-level` would imply a level the project doesn't need, flag it explicitly:

> Note: target L3 is high overhead for a project of this size. Consider whether L2 meets your needs.

## Anti-patterns

- Recommending level upgrades the user didn't ask for.
- Writing files. This skill is read-only.
- Conflating "level" with "stack maturity." They're orthogonal — a TypeScript project can be at L0 with a full Stryker setup, or at L3 without it.
