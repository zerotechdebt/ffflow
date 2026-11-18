---
name: stack-init
description: Bootstrap a stack into a project — install deps, write configs, justfile, git hooks, CI. Level-aware, idempotent, non-destructive on existing projects.
---

# stack-init

## Purpose

Install the toolchain a project needs to operate at its declared level. Two modes:

- **Fresh** — empty or near-empty project; full setup.
- **Adopt** — existing project; identify gaps and fill them, preserving working setup.

Absorbs the former `justfile-init` skill — justfile bootstrapping happens here as part of the install.

## Inputs

- `.ffflow/config.yaml` — read for level, stack. If absent, run `init-ffflow` first.
- Optional `--stack <name>` to override the configured stack.
- Optional `--check` — dry-run, report-only. Compute the plan and print it without writing anything. Useful for "what would change?" preview.
- Optional `--yes` — skip per-item confirmation. The skill still computes and reports the plan; it just applies without asking. Useful for refresh re-runs after the user has already vetted the diff.

`--check` and `--yes` are mutually exclusive. If both are passed, `--check` wins (read-only is safer than write-without-asking).

## Outputs

- Stack config files (`pyproject.toml`, `tsconfig.json`, etc.).
- `justfile` with level-appropriate recipes (`justfile` baseline + level patterns).
- `.git/hooks/pre-commit` and `pre-push` (via `git-hooks` skill).
- `.github/workflows/ffflow-ci.yml` (via `ci-gates` skill).
- Initial spec directory structure.
- Updated `.ffflow/config.yaml` if anything was inferred.

## Dependencies

- The `stack` skill (specifically the cartridge matching `.ffflow/config.yaml stack:`).
- The `justfile` skill (baseline + a cartridge per tier up to `justfile_maturity` in `.ffflow/stack.yaml`).
- `git-hooks` and `ci-gates` for hooks and CI workflow.

## Idempotency

Hard rule: re-running must be safe.

- Detect existing configs. If present and divergent, **ask** before changing — never silently overwrite working setup.
- Detect existing justfile. Merge level-appropriate recipes in if missing; never overwrite user-customized recipes.
- Detect existing git hooks. Install only if missing; otherwise report and ask.
- Detect existing CI workflow. Install only if no `ffflow-ci.yml` exists; merge with other workflows fine.

## Flow

### 1. Detect state

- Read `.ffflow/config.yaml`. If absent, halt with `Run /init-ffflow first.`
- Read stack skill's dimension YAML.
- Probe filesystem:
  - Stack config files (per stack)
  - `justfile`
  - `.git/hooks/`
  - `.github/workflows/`
  - Spec directory (per stack convention)

### 2. Compute plan

Build a list of actions, each marked `create | update | skip`:

```
- create pyproject.toml (stack config, level-aware baseline)
- update justfile (add Tier 1 patterns: complexity, loc, duplicates)
- create .git/hooks/pre-commit
- skip .github/workflows/ci.yml (existing custom workflow)
- create specs/ directory
```

### 3. Confirm

Present the plan. Ask for confirmation or per-item override:

```
Proposed changes:
  [+] pyproject.toml         (new)
  [~] justfile               (add 4 recipes from Tier 1 cartridge)
  [+] .git/hooks/pre-commit  (new)
  [-] .github/workflows/ci   (existing custom workflow — skip)
  [+] specs/                 (new)

Apply (a), edit per-item (e), abort (x)?
```

### 4. Execute

Apply in this order:

1. Stack config files (so language tooling can find its config).
2. Install dependencies (`uv pip install -e ".[dev]"` or `pnpm install`).
   - **At L3, also verify `npx` is on PATH** (`npx --version`). specdrive — the RID-traceability CLI — is a language-agnostic tool distributed on npm and run via `npx specdrive`, regardless of the project's stack. It audits the Gherkin specs + JUnit XML, not the source, so a Python/Java/Rust project needs Node/npm available *only* to run specdrive. If `npx` is missing, surface:

     ```
     L3 needs specdrive for the RID-traceability gate. specdrive is a
     language-agnostic CLI run via `npx specdrive` — it audits your .feature
     specs, not your <stack> source — so it needs Node.js/npm on PATH.

     Install Node (e.g. via your package manager or nvm), then re-run.
     This is the only Node dependency L3 adds to a non-JS project.
     ```

     Do not treat this as a reason to drop the project below L3 — install Node instead. (For TypeScript projects `npx`/`pnpm` is already present.)
3. Spec directory.
4. Justfile (sourced from the `justfile` skill — baseline + tier cartridges).
5. Git hooks (via `git-hooks`).
6. CI workflow (via `ci-gates`).

After each step, run a smoke verification — for stack config, run `<tool> --version`; for justfile, run `just --list`; for hooks, run `pre-commit --version` or stat the file.

### 4a. Network failure handling

The dependency-install step is the most common failure point — `pnpm install`, `uv pip install`, `cargo install`, `mvn install` all reach the network. When this step fails:

1. Look for telltale network errors in the tool's output (`ENOTFOUND`, `ECONNREFUSED`, `Could not resolve host`, `Failed to fetch`, DNS errors, TLS errors, `proxy` mentioned).
2. If found, **before** showing the tool's failure verbatim, surface a hint:

```
Dependency install failed at the network step.

If you're in a container, corporate network, or behind a proxy, check:
  - HTTPS_PROXY / HTTP_PROXY / ALL_PROXY (and their lowercase forms)
  - NO_PROXY allowlists
  - Registry-specific config (npm: ~/.npmrc; pip: ~/.config/pip/pip.conf; cargo: ~/.cargo/config.toml)

A common trap: a proxy env var set in a parent shell that points at an
unreachable host (`*.internal`, `localhost:N`, container-only addresses).
Try `env | grep -i proxy` to see what's set, then unset what's wrong.

If you're not behind a proxy, this is probably an actual network issue.
The underlying error follows:
```

Then show the tool's actual output. The hint short-circuits 30 minutes of debugging for users who don't know to check env vars.

### 4b. Seed CLAUDE.md for scaffolding it created

When this run created a directory that meets the `claude-md` cartridge's significance criteria — a spec directory, a `.storybook/`, a new source-layout skeleton, `.ffflow/` itself — seed a short CLAUDE.md in it. Two or three lines is the target: what lives here, and the rule that governs it.

This is invariant §2.10 applied at the moment of creation. A directory scaffolded without its CLAUDE.md becomes an audit finding on the very next `/fff:audit --type claude-md` run; writing it now costs nothing and closes the loop.

Don't seed for directories that already have one, and don't seed for directories this run didn't create — retrofitting existing coverage gaps belongs to `/fff:audit --type claude-md --fix`, not here.

### 5. Verify

Run `just check-all`. Report results. If it fails, surface the failure clearly — don't claim success.

### 6. Report

```
✓ stack-init complete (level=L1, stack=python)
  pyproject.toml       written
  justfile             updated (added: complexity, loc, duplicates, slowtests)
  pre-commit hook      installed
  pre-push hook        installed
  .github/workflows/ffflow-ci.yml  written
  specs/               created (+ CLAUDE.md)
  .ffflow/CLAUDE.md    seeded

Verification: just check-all → PASS

Next:
  /plan-chat          # start designing a change
  /characterize       # (brownfield) extract specs from existing code
```

## Upgrade mode

When level is being raised (e.g., L1 → L2), invoke `stack-init` again:

- Detects new level from `.ffflow/config.yaml`.
- Computes the diff: which additional recipes / configs / dependencies are needed.
- Same confirm-and-execute flow, but only for the delta.

Replaces the former `/justfile-init upgrade <pattern>` flow:

```bash
/stack-init                     # apply current level fully
/stack-init upgrade <pattern>   # add one specific pattern without full upgrade
```

`<pattern>` is one of the justfile tier cartridges: `quality` (Tier 1), `security` (Tier 2), `advanced` (Tier 3), `polyglot` (Tier 4). Each loads its cartridge from the `justfile` skill. Adding a whole tier raises `justfile_maturity` in `.ffflow/stack.yaml` to that tier; adding single recipes does not.

## Anti-patterns

- Overwriting custom justfile recipes. Always merge.
- Installing CI workflows without confirming they don't conflict with existing CI.
- Installing dependencies without running `dev-install`-style verification.
- Treating missing `.ffflow/config.yaml` as a license to assume defaults. Tell the user to `init-ffflow` first.
- Creating a significant directory and leaving it undocumented. Scaffolding a dir without seeding its CLAUDE.md just manufactures an audit finding for later (§2.10).
- Retrofitting CLAUDE.md across directories this run didn't create. That's `/fff:audit --type claude-md --fix`.

## Friction addressed

- Multi-step manual setup (deps, configs, hooks, CI, justfile) collapsed into one command.
- Inconsistent setup across team members.
- Drift between declared stack and actual tooling.
