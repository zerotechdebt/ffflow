---
name: pipeline-next
description: Say what to do next — per roadmap or across the project — from pipeline-status's data, in two lanes that run side by side (build: review, finish, start; plan: the next phase or PRD to plan), with the FFFlow command for each. Suggests; never starts work on its own.
---

# pipeline-next

## Plan Mode

This skill does NOT invoke Plan Mode. It reads the pipeline and recommends; any command it offers runs only after the user confirms.

## Purpose

`pipeline-status` shows where everything stands. This skill answers the follow-up: *what should happen next?* The calculation lives in `pipeline-status`'s model (`next_actions`), so the viewer, this skill and any other tool give the same answer.

## Inputs

- Optional: a roadmap or plan slug (e.g. `/fff:pipeline-next worker-log-archive`). With none, the whole project.
- The same flags as `pipeline-status` where they matter: `--repo`, `--remote`, `--no-worktree`.

## Flow

### 1. Get the model

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/pipeline-status/pipeline.py" --format json
```

With a slug, use that root's `next_actions`. Without one, use the top-level `next_actions` (build and plan lanes across every root and ready PRDs, most urgent first), plus each in-progress root's `data` and `blocked` entries.

### 2. Present

Lead with the single most urgent action, then the rest grouped by lane. One line each: title, reason, command.

```
Next on worker-log-archive
  build  Finish epic #117 — 1 task open (#124)              /fff:work-epic 117
  plan   Plan phase 3: fffactory logs reader
         its dependencies are planned; plan it while they are built
         /fff:plan-chat roadmap worker-log-archive, phase 3 "fffactory logs reader" (docs/roadmap/worker-log-archive/phases/phase-3.md)
```

If a root has no build or plan action, show its `blocked` reason. If it has `data` actions, mention them last and point to the data gaps (`/fff:pipeline-status`).

### 3. Offer, don't run

Ask which action, if any, to take. Run its command only on the user's confirmation. Actions with no command (reviewing a PR, fixing data) are described, not performed.

## The rules (computed in `pipeline.py`)

Two lanes run side by side, because planning the next phase can happen while the current one is built:

| Lane | Action | When |
|---|---|---|
| build | **Review and merge PR #N** | an unfinished epic has an open PR |
| build | **Finish epic #N** → `/fff:work-epic N` | an epic is in progress with no open PR; names its open tasks |
| build | **Start epic #N** → `/fff:work-epic N` | an epic is captured and its phase is unblocked (or it belongs to a single plan) |
| plan | **Plan phase N** → the skill for the phase's `Kind:` | the first phase with no epic, once every phase it depends on is at least captured; `buildable` says whether its dependencies are already done |
| plan | **Plan a roadmap from PRD x** → `/fff:plan-roadmap` | a PRD is converged or ratified and no roadmap cites it (project-wide only) |
| data | **Fix N data gaps** | the root has warnings |
| blocked | **Phase N is blocked** | neither lane has anything; says what it waits on |

A plan command follows plan-roadmap's handoff table (`design-slice` → `/fff:plan-chat`, `characterize` → `/fff:characterize`, `cleanup` → `/fff:audit --plan`, `roadmap` → `/fff:plan-roadmap --phase N`; no `Kind:` → `/fff:plan-chat`; other kinds get no command) and always names the roadmap, the phase number and title, and the phase file, e.g. `/fff:plan-chat roadmap worker-log-archive, phase 3 "fffactory logs reader" (docs/roadmap/worker-log-archive/phases/phase-3.md)`. Pass it as given: the path is what keeps the planner from picking up a similarly named phase or roadmap.

Across roots, actions are ordered: review, finish, start, plan phase, plan roadmap. Done and external roots have none.

## Anti-patterns

- Don't start work without confirmation, and don't re-derive readiness from prose: the executor (e.g. a dispatcher) decides what can actually start.
- Don't recompute the rules here. If an action is wrong, fix `next_actions` in `pipeline.py` and its tests.
- Don't hide the plan lane because the build lane is busy; they are meant to run together.
