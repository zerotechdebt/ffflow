# Changelog

All notable changes to the **fff** plugin. Versions track `plugin/.claude-plugin/plugin.json`. The `ppp` plugin keeps its own [ppp/CHANGELOG.md](ppp/CHANGELOG.md).

This file is for humans. Its machine-readable sibling — [`plugin/docs/migrations.md`](plugin/docs/migrations.md) — is what `/fff:upgrade-ffflow` actually reads: same releases, but each entry carries a detection heuristic and a remediation for repo-affecting changes. **When a release changes what a project's files should look like, it needs an entry in both.**

The format is loosely [Keep a Changelog](https://keepachangelog.com/); versioning is [semver as defined in the root `CLAUDE.md`](CLAUDE.md#how-we-version).

> **Marketplace catalog** (`metadata.version` in `.claude-plugin/marketplace.json`): **0.5.0** (2026-10-13) adds `ppp` (ships at 0.2.0) and moves plugin versions out of the catalog entries into each plugin.json. `fff` unchanged at 0.4.2.

---

## [0.5.0] — 2026-11-10

### Added
- **`/fff:pipeline-status`: the delivery view after capture.** `plan-status` stops once a plan is captured; nothing showed every roadmap's progress at once. The new skill joins `docs/roadmap/<slug>/` (working tree, default ref, and branches with an open PR or citing epic) to the tracker's `ffflow-epic` and `epic-<N>` issues and open PRs, and reports each root, phase and epic as done, in progress, captured or not started, which phases are next by their `Depends on:` lines, epics with no plan root, and open issues outside every epic. Gaps in the trail (an epic with no `Roadmap:` link, a plan file citing an issue that isn't an epic, a root no ref holds) are reported as findings. `--format text` for people; JSON (`schema_version: 1`, documented in the skill) for visualization tools; `--format html` for a self-contained viewer (`viewer.html`, also usable standalone on any saved JSON); `--snapshot-out`/`--snapshot-in` to save and replay a view offline. Progress counts task issue state, not checklist ticks. Read-only; `github-issues` only for now. PRDs: ppp bundles (found by ppp's own rule, read directly with no dependency on the ppp plugin) appear above roadmaps with their negotiation state, outcomes, metrics, increments and planning items; a roadmap whose `Source:` points into a bundle links to it, and converged PRDs no roadmap cites are listed as ready for planning. **`/fff:pipeline-next`** says what to do next per roadmap, in two lanes that run side by side: build (review an open PR, finish the epic in progress, start an unblocked epic) and plan (the next phase without an epic, planned while earlier phases are built), each with its FFFlow command; the same `next_actions` lead the viewer's overview (project-wide, most urgent first, above one row per roadmap showing what it's on now) and each roadmap's page (above tabs for phases with their task issues, increments with what each contains and unlocks, and data gaps). Roadmaps and PRDs list done first, so what's upcoming sits at the bottom. References to other repositories are recognized: an epic citing another repository's roadmap shows under an external root, and a plan file's `Epic: owner/repo#N` is not mistaken for a local issue.

## [0.4.3] — 2026-10-14

### Changed
- **The repo moved to [`zerotechdebt/ffflow`](https://github.com/zerotechdebt/ffflow).** It was transferred from `bryonjacob/ffflow`, so stars, forks, and issues came with it, and GitHub redirects the old URL. Existing marketplace installs keep updating with no action needed; `/plugin marketplace add zerotechdebt/ffflow` is the install command going forward. The marketplace name (`ffflow`) and plugin names (`fff`, `ppp`) are unchanged.

### Fixed
- **The beliefs block linked to a repo that never existed.** `init-ffflow`'s canonical block stamped `This project runs [FFFlow](https://github.com/bryonjacob/ffflow-plugin)` into every adopted project's root CLAUDE.md — a 404. It now links `https://github.com/zerotechdebt/ffflow`, and the block's marker moves to `v0.4.3` so `beliefs-block` sees older blocks as stale. New migration entry `ffflow-repo-url` finds the old link in existing projects and replaces it.
- README install instructions now use `/plugin marketplace add zerotechdebt/ffflow` instead of a local-path placeholder. Repo-layout trees in the design docs name the root `ffflow/`.

## [0.4.2] — 2026-10-07

### Fixed
- **`work-epic` now queries the task label format emitted by `plan-capture`.** Task discovery uses `epic-<epic-id>` instead of the mismatched `epic:<epic-id>`, so captured tasks are found correctly.
- **`plan-capture` now burns the execution ordinal into generated task-issue titles, honoring `work-epic`'s ordering invariant.** `work-epic` treats issue *titles* as the ground truth for execution order (sort by the `T<N>` prefix, never by issue number), but the GitHub capture cartridge created tasks with `--title "<task title>"` — no ordinal — so a real `/fff:work-epic` run found no `T<N>` to sort on and had to reconstruct the order by hand. The producer was never honoring the invariant. Task titles now carry the ordinal as `T<N> — <title>` for both roadmap and single-slice plans. `<N>` is the task's 1-based position in the phase's dependency-ordered list.
- **Capture-time guardrail.** `plan-capture` (and the github-issues cartridge) now verify every created/updated task title matches `^T\d+ — ` and refuse — reporting the offenders — if any lack it, so generation can't silently regress to unordered titles.
- **`work-epic` legacy fallback.** If any task title lacks a `T<N>` ordinal — whether the whole epic predates the scheme or it was only partially recaptured — `work-epic` falls back to the epic issue's checklist order for every task and warns, instead of mixing ordering schemes or guessing. The ordering invariant and epic-title handling are otherwise unchanged.

## [0.4.1] — 2026-09-06

### Fixed
- **`work-issue` no longer instructs agents to stamp `.ffflow/audit.yaml`.** The skill's Outputs list said to update the file "if any audited file is touched" — but a stamp means an auditor validated the file, not that its editor touched it. Since `work-issue` runs on nearly every leaf task, that line meant every ordinary PR was self-certifying its own changes into the one record that's supposed to be independent of the author. Reported from a downstream project where 9 of 10 `audit.yaml`-touching commits were self-stamps and only 1 was a real audit run. The invariant — "`audit.yaml` is written by auditors only; an editor never stamps its own work" — is now stated explicitly in `audit/SKILL.md`. `characterize` writing `characterized: true` for spec entries it just authored remains the one sanctioned exception (that's an auditor-shaped act, not self-certification of a code change).

## [0.4.0] — 2026-08-23

### Added
- **Invariant §2.10 — Hierarchical CLAUDE.md is how the codebase explains itself.** Promotes per-module CLAUDE.md from an audit-cartridge coverage rule to a professed, first-class FFFlow belief. Explains the mechanism (proximity loading is the only context-routing that fires before the model chooses what to read) and the four consequences: locality beats volume, root stays a map, freshness becomes scopeable, and it's the spec's habitat at L0/L1.
- **Invariant §2.11 — Beliefs are stamped into the project, not just professed by the plugin.** A downstream session reads *that project's* CLAUDE.md, never the plugin's design docs. Beliefs now ship into the repo as a managed, versioned marker block.
- **`/fff:upgrade-ffflow`** — new skill. Reconciles a project against the current plugin version: reads the stamp, walks the migration ledger, duck-types unstamped repos, applies remediations with per-entry confirmation, re-stamps.
- **`ffflow_version` / `ffflow_upgraded`** in `.ffflow/config.yaml` — records which plugin version a repo was last reconciled against, distinct from the config's own schema `version`.
- **`plugin/docs/migrations.md`** — the migration ledger. Per-version, repo-affecting changes with detection heuristics and remediations.
- **`CHANGELOG.md`** — this file.
- **Managed beliefs block** written by `init-ffflow` into the project's root CLAUDE.md, delimited by `<!-- ffflow:beliefs ... -->` markers and refreshed by `upgrade-ffflow`.

### Changed
- `init-ffflow` now writes the beliefs block and the version stamp in addition to `.ffflow/config.yaml`. This is a deliberate narrowing of its long-standing "don't write project-level files outside `.ffflow/config.yaml`" anti-pattern — the beliefs block is the one exception, and it's confined to a marker-delimited region.
- `work-issue` gains a module-CLAUDE.md step: creating a new module means creating its CLAUDE.md in the same PR, the same way a behavior change ships its spec update.
- `stack-init` seeds CLAUDE.md for scaffolding directories it creates.
- The `claude-md` audit cartridge's root template now names hierarchical CLAUDE.md in its Conventions block, so the convention propagates into every generated root file.

### Fixed
- **`notetoself` no longer advises committing session notes.** The skill told users to copy notes into `.ffflow/notes/` for durability past `/tmp` cleanup, while its own state table two sections later classified the note as the one piece of state scoped to a single session rather than the project. On any team past one developer the advice is actively harmful: the working-directory hash that prevents *project* collisions guarantees *person* collisions once the file is shared, producing overwrites, merge conflicts in a file nobody meant to co-author, and stale notes that read to a teammate as project truth. Durability is now answered by gitignoring, not committing. Reported by a user who got bitten by it.
- **`/fff:autopilot --decision-log` carries the same warning.** Writing a per-session decision log to a repo path had the identical trampling failure mode with no gitignore guidance.
- New migration entry `uncommit-session-notes` untracks (never deletes) already-committed notes and logs, after confirmation, offering to promote genuinely project-level content first.

### Notes
- **Backward compatible.** A repo with no `ffflow_version` still works exactly as before; it duck-types on first `/fff:upgrade-ffflow` run.

---

## [0.3.0] — 2026-08

### Added
- **Invariant §2.9 — View-layer purity**, the frontend sibling of hexagonal: the component layer is the frontend's domain, dependencies point view ← app, decompose → story → test → *then* integrate.
- `component-driven-ui` rulebook skill.
- `typescript-ui` stack cartridge (Storybook + design tokens + component triple scaffolding), with a `ui_baseline` lane of `react` or `web-components`.
- `/audit --type ui` gate.
- `adopt-ffflow --ui` for retrofitting view-layer purity onto an already-adopted project.

---

## [0.2.3] — 2026-08

### Fixed
- Four `/fff:refactor` confusion points surfaced by a real run.

---

## [0.2.2] — 2026-08

### Changed
- Audit refactor cartridge defers tool commands to the stack cartridge rather than hardcoding them.

### Added
- Rust and polyglot support in the refactor cartridge.

---

## [0.2.1] — 2026-08

### Changed
- Justfile cartridges split into per-language files.

### Added
- Rust justfile cartridge.

---

## [0.2.0] — 2026-08

### Fixed
- **specdrive is language-agnostic** — npm is its install channel, not a language constraint. Unlocked L3 for Python, Java, and Rust; all stacks now declare `max_level: L3`. (#1)

---

## [0.1.0] — 2026-08

### Added
- Initial release: plan / work / audit lifecycle, the L0–L3 dial, stack cartridges for TypeScript / Python / Java, capture backends for GitHub Issues / Linear / Jira / markdown.
- Apache 2.0 license.
