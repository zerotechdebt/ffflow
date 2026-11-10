# FFFlow marketplace for Claude Code

Two independent plugins: **fff** — plan, work, audit, at the level of rigor your project actually needs; **ppp** — product ping-pong: builder and product negotiate a PRD to convergence. Install either or both.

## Install

```bash
/plugin marketplace add zerotechdebt/ffflow
/plugin install fff@ffflow
/plugin install ppp@ffflow
```

Commands are namespaced per plugin: `/fff:…` (e.g., `/fff:plan-chat`, `/fff:work-issue`) and `/ppp:…` (e.g., `/ppp:prd-start`, `/ppp:prd-turn`).

## fff — FFFlow

**Plan, work, audit — at the level of rigor your project actually needs.**

FFFlow is a complete development lifecycle in a single Claude Code plugin. It scales from informal prose specs (L0) to full spec-driven development with mutation testing and RID traceability (L3). Same workflow at every level; what changes is the formality of the artifacts and strictness of the gates.

The plugin's invocation prefix is `/fff:` — short, distinctive, won't collide.

### The shape

Three artifacts. Three roles. Three locations.

- **Spec** (present tense, evergreen) — your codebase's behavioral contract. Lives in `docs/specs/`, `specs/`, or per-module CLAUDE.md.
- **Plan** (future tense, transient) — the path from current spec to next spec. Lives in `/tmp/ffflow-plans/<project-hash>/<slug>/`, never in the project tree.
- **Issues** (imperative, transactional) — the chess moves. Lives in your issue tracker.

### Workflows

**Bootstrap a new project (from `project.md`, README, or just an idea):**
```
/fff:adopt-ffflow   Detects greenfield vs. brownfield. Runs init + stack setup,
                    then hands off to /fff:plan-roadmap.
/fff:plan-roadmap   Reads your vision; produces ordered phases with dependencies.
                    Per phase: design-slice (→ plan-chat), characterize, cleanup,
                    or recursive sub-roadmap.
```

**Steady-state feature work (after bootstrap):**
```
/fff:plan-chat        Design one slice. Open decisions resolved inline before sealing.
/fff:plan-breakdown   Cut the plan into 3–8 independently shippable chess moves.
/fff:plan-capture     Write the chess moves to your issue tracker.
/fff:work-issue       Execute one chess move end-to-end: red → green → spec → PR.
/fff:work-fanout      Or run several in parallel across worktrees (one PR per issue).
/fff:work-epic        Or run an epic's issues sequentially into one PR.
/fff:audit            Periodically: check that specs, CLAUDE.md, tests still match reality.
/fff:pipeline-status  Every roadmap at once: done, in flight, next. --format text, or JSON to visualize.
/fff:pipeline-next    What to do next, per roadmap: build and plan lanes, each with its FFFlow command.
```

**Maintenance loop:**
```
/fff:audit            Find drift. Find gaps.
/fff:audit --plan     Convert findings into a plan. Then breakdown → capture → work.
/fff:upgrade-ffflow   After updating the plugin: catch this repo up to the new version.
```

Updating the plugin changes what FFFlow *believes*; it doesn't change what your repo *contains*. `/fff:upgrade-ffflow` closes that gap — it reads the `ffflow_version` stamped in `.ffflow/config.yaml`, walks the migration ledger, and applies whatever your project is missing. Projects adopted before 0.4.0 have no stamp; the skill infers their effective version from what's actually in the tree, then stamps it so it never has to guess again.

### Two-tier planning

- **Tier 1** — `/fff:plan-roadmap` (phase-level). Used for new projects, big features, or new directions.
- **Tier 2** — three entries, each handling one phase:
  - `/fff:plan-chat` — design a slice.
  - `/fff:characterize` — extract specs from existing code.
  - `/fff:audit --plan` — convert drift into a plan.

All four converge on `plan-breakdown → plan-capture → work-*`.

Single-slice changes skip tier 1; bug fixes go through `plan-chat` directly.

### The L0–L3 dial

Pick the level your project needs. You can change levels later.

| Level | Spec format | Tests | Gates |
|---|---|---|---|
| **L0** | Informal prose | Standard unit/integration | Lint + tests pass |
| **L1** | Structured prose, hexagonal layering | + defect-driven spec entries | + CLAUDE.md audit |
| **L2** | Gherkin 6 scenarios | + spec-first TDD | + spec audit, contract enforcement |
| **L3** | Gherkin + RIDs + property-based | + mutation testing | + four quality gates, RID audit |

No config = L0. Declare your level in `.ffflow/config.yaml` to enable more.

### Cartridge architecture

Several skills carry their family of variants as on-demand cartridges, keeping the LLM's skill index uncluttered:

- `/fff:plan-capture` — cartridges for `github-issues` (default), `linear`, `jira`, `markdown`.
- `/fff:stack` — cartridges for `python`, `typescript`, `java`, `rust`, `polyglot`.
- `/fff:justfile` — Tier 1–4 pattern cartridges (quality, security, advanced, polyglot).
- `/fff:audit` — cartridges for `claude-md`, `spec`, `char-tests`, `architecture`, `refactor`, `tech-debt`, `rid`.

Configure once in `.ffflow/config.yaml`; the right cartridge loads when needed.

### What FFFlow doesn't do

- It doesn't lock you to one stack. Pluggable via cartridges; override any tool via `.ffflow/stack.yaml`.
- It doesn't lock you to GitHub. Capture backends are pluggable (Linear, Jira, markdown).
- It doesn't replace your tests. Spec tests are additive — both unit and spec tests have independent coverage thresholds.
- It doesn't force L3 on you. L0 is a valid forever-state for projects that want lightweight discipline.

## ppp — product ping-pong

A builder seat and a product seat take turns revising one PRD, and every turn must pass a mechanical check (no names, no estimates, no history, no bloat) before it lands. What doesn't belong goes to a parking lot, an analyst seat answers data requests neutrally, and each round ends with a retro on the record. The PRD converges when a seat hands it back unchanged with no question open, and is ratified when every seat signs off `yes` with nothing provisional left.

```
/ppp:prd-start [<medium>]               Agree the medium, seat the parties, create the bundle.
/ppp:prd-turn --seat builder|product    Take one turn: respond, revise, park, ask, memo, check.
/ppp:prd-data                           Analyst seat: answer open data requests with evidence.
/ppp:prd-retro                          Close the round: retro, tidy the lot, summary, findings; converge, ratify.
/ppp:prd-check                          The mechanical rules (also run inside every turn).
/ppp:prd-split                          Carve a growing thread into its own PRD.
/ppp:prd-status                         Where one PRD, or the whole portfolio, stands.
```

**Any medium.** A PRD bundle is a handful of text documents; they can live anywhere that meets the requirements in [`ppp/media.md`](ppp/media.md) — every seat can read and write them, a version is kept per turn, and the seats agree how hand-off, sign-off and the final commit work. The repo + draft-PR worked example is offered by default; bring your own by pointing `/ppp:prd-start` at a medium document. The agreement is recorded in each bundle's `medium.md`.

PPP doesn't depend on fff; a converged PRD can feed any planning step, including `/fff:plan-roadmap`.

## Documentation

- [Build spec & architecture](plugin/docs/architecture.md) — what the plugin is and why
- [Levels explained](plugin/docs/levels.md) — the L0–L3 dial in detail
- [Workflows](plugin/docs/workflows.md) — the lifecycle flows
- [Audit subsystem](plugin/docs/audit.md) — the keep-honest layer
- [Migration ledger](plugin/docs/migrations.md) — what `/fff:upgrade-ffflow` reads
- [Changelog](CHANGELOG.md) — fff release history and catalog notes
- [PPP design](ppp/CLAUDE.md) — what the ppp plugin is and its invariants
- [PPP process](ppp/process.md) — the process contract every `/ppp:` skill implements
- [PPP media](ppp/media.md) — where a bundle can live; the worked example
- [PPP design PRD](ppp/docs/prds/ppp/ppp-prd.md) — PPP's own PRD, as a PPP bundle
- [PPP changelog](ppp/CHANGELOG.md) — ppp release history

## Status

Active development. See [`plugin/CLAUDE.md`](plugin/CLAUDE.md) for the build phase status.

## License

Apache License 2.0 — see [LICENSE](LICENSE). Copyright 2026 Bryon Jacob.

Contributions welcome. New stack cartridges (Go, Elixir, …), capture backends, and audit cartridges are the easiest ways to extend FFFlow without touching the core.
