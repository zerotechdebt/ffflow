---
name: pipeline-status
description: Show the whole delivery pipeline for this project — PRDs (ppp bundles), every roadmap and captured plan, its phases, their epics and task progress, what's done, in flight and next — as text, JSON for visualization, or a self-contained HTML viewer. Reads committed plan roots and the tracker; read-only.
---

# pipeline-status

## Purpose

`plan-status` stops at capture: it reports plans being designed. This skill picks up from there. It joins the durable record (`docs/roadmap/<slug>/`) to the tracker and answers, across every roadmap at once: what's complete, what's in flight, what's next, and what isn't attached to any plan.

Above the roadmaps it reads PRDs: any ppp bundle in the repository, its negotiation state, outcomes, metrics and increments, and which roadmaps were planned from it. It reads the bundle's files directly and never needs the ppp plugin installed.

It also emits the same view as JSON (`schema_version: 1`) so a tool can visualize it, and ships a self-contained HTML viewer for that JSON.

## Inputs

- Current working directory (a git repository).
- `.ffflow/config.yaml` for the capture backend. No config → `github-issues`.
- Flags (all optional): `--format text|json|html` (default `json`), `--out <file>`, `--remote <name>` (default `origin`), `--repo <owner/name>`, `--no-worktree`, `--snapshot-out <file>`, `--snapshot-in <file>`.

## Outputs

Console report, or JSON on stdout / `--out`. No side effects: it never fetches, commits, or edits issues.

## Flow

### 1. Run the script

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/pipeline-status/pipeline.py" --format text
```

For JSON, drop `--format text` and add `--out <file>` if the user wants a file. To visualize:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/pipeline-status/pipeline.py" --format html --out pipeline.html && open pipeline.html
``` Remote refs are read as they are locally; if they look stale, suggest `git fetch` — don't run it unasked.

### 2. Present

Show the text view. Then, in at most five lines, say:

- **Done** — roots and phases complete.
- **In flight** — epics in progress, with open PRs.
- **Next** — phases whose dependencies are done and that haven't started (`summary.next`). If none, say what's blocking the front of each roadmap.
- **Unattached** — epics with no plan root, and the count of open issues outside every epic.
- **Data gaps** — the `warn` findings, grouped. Name the fix (e.g. "add `Roadmap: docs/roadmap/<slug>/…` to #18's body") but don't apply it.

## Where the data comes from

| Fact | Source |
|---|---|
| Plan roots | `docs/roadmap/<slug>/` holding `roadmap.md` or `plan.md`, in the working tree, on the default ref, or on a remote branch |
| Phases | `phases/phase-N.md`: heading, `Status:`, `Depends on:`, `## Captured tasks` |
| Root source | the `Source:` line in the root's header (a design doc or PRD) |
| PRDs | ppp's rule: any folder holding both `medium.md` and `state.json`, on the same refs as plan roots. Bundles whose `state.json` slug is still a `<slug>` placeholder are templates and skipped |
| PRD state | `state.json`: `status`, `round`, `round_cap`, `next`, `signoff`, `links` |
| PRD content | `<slug>-prd.md` (or legacy `prd.md`): title, §3 Outcomes, §7 Metrics table, §8 Increments, §11 Open questions by status, `[provisional]` count; `parking-lot.md` entries of kind `planning` |
| PRD → roadmap | a root's `Source:` line names a path inside the bundle (the PRD file or the folder) |
| Epics | issues labelled `ffflow-epic` |
| Epic → root/phase | `docs/roadmap/<slug>[/phases/phase-N.md]` in the epic body, and `Epic: #N` under a plan file's `## Captured tasks` |
| Other repositories | A roadmap path written right after another repository's name (`owner/repo docs/roadmap/<slug>/…`) or inside a GitHub URL to it links the epic to that repository's roadmap, reported as an `external` root (its files are not read). A plan file's `Epic: owner/repo#N` is tracked in that repository: recorded as `external_epics`, never looked up locally |
| Tasks | issues labelled `epic-<N>`, plus issues in the epic's checklist |
| In progress | an open epic with a closed task, or an open PR whose branch is `epic/<N>` / `issue/<N>`, whose title says `Epic <N>`, or whose body closes `#<N>` |

**Progress is task issue state, never checklist ticks.** Checklists are rarely ticked in practice; when they disagree, a `checklist-stale` info finding says so.

**Branch roots and PRDs.** A root or PRD bundle that exists only on a branch (drafting PRDs live on `prd/<slug>` in ppp's worked example) is reported when an open PR heads that branch, an epic cites it, or it is in the working tree. Otherwise it is omitted with a `root-stale-branch` finding.

**Dependencies.** `Depends on:` is parsed for phase numbers (`Phase 1`, `Phases 2 and 3`, `phase-2`) and issue numbers; clauses starting with "Not" are ignored. With no `Depends on:` line, a phase depends on the phase before it (`depends_inferred: true`).

## Statuses

| Level | Values | Rule |
|---|---|---|
| Epic | `done` · `in_progress` · `captured` | closed · open with progress or an open PR · open, untouched |
| Phase | `done` · `in_progress` · `captured` · `not_started` · `unknown` | rolled up from its epics; with none, `done` if the phase file declares it complete (`status_basis: declared`), `unknown` if it cites epics the tracker doesn't have, else `not_started` |
| Root | same as phase | rolled up from its phases and directly linked epics |

PRD **stage**: before any roadmap cites it, the `state.json` status (`drafting`, `converged`, `ratified`); after, it follows the citing roadmaps: `planned` (none started), `delivering`, `delivered` (all done). A PRD is **ready for planning** when it is converged or ratified and no roadmap cites it. Increments are shown beside a roadmap's phases but not linked to them; nothing records which increment became which phase. Metrics show baseline and target only: nothing measures current values yet.

A phase is **next** when it is `not_started` or `captured`, every phase it depends on is `done`, and every issue it depends on is closed.

## JSON (schema_version 1)

```jsonc
{
  "schema_version": 1,
  "generated_at": "2026-11-10T16:21:18+00:00",
  "repo": "owner/name",
  "default_ref": "origin/main",
  "refs_scanned": ["origin/main", "origin/epic/136"],
  "tracker": { "backend": "github-issues", "ok": true, "error": null, "issues": 114, "open_pulls": 3 },
  "summary": {
    "roots": 6, "roots_done": 3, "roots_in_progress": 2,
    "epics": 13, "epics_done": 9, "epics_in_progress": 2, "epics_unlinked": 7,
    "unlinked_open_issues": 16,
    "next": [],                        // [{ "root": "<slug>", "phase": 3 }] for each unblocked phase
    "prds": 1, "prds_by_stage": { "delivering": 1 }, "ready_for_planning": [], "roots_without_prd": 5
  },
  "prds": [{
    "slug": "refunds", "path": "docs/prds/refunds", "prd_file": "docs/prds/refunds/refunds-prd.md",
    "title": "Faster refunds", "found_on": ["origin/main"], "on_default_ref": true,
    "state": { "status": "ratified", "round": 2, "round_cap": 3, "next": "product",
               "signoff": { "builder": "yes", "product": "yes" }, "links": { "parent": null, "children": [] } },
    "stage": "delivering",             // drafting | converged | ratified | planned | delivering | delivered | unknown
    "ready_for_planning": false,
    "roots": ["worker-log-archive"],   // roadmaps whose Source: points into this bundle
    "outcomes": ["…"],
    "metrics": [{ "metric": "…", "definition": "…", "source": "…", "baseline": "48", "target": "4" }],
    "increments": [{ "number": 1, "name": "Decision API", "size": "M", "text": "…",
                     "contains": "the rules as a service", "unlocks": "the agent screen" }],  // number = PRD order, not an ID
    "questions": { "open": 1, "answered": 1, "deferred": 0, "dropped": 0, "total": 2 },
    "provisional": 0,
    "planning_items": [{ "id": "P-1", "item": "…" }]
  }],
  "roots": [{
    "slug": "worker-log-archive",
    "kind": "roadmap",                 // roadmap | plan | external (another repository's) | missing (cited, found nowhere)
    "title": "worker-log-archive",
    "path": "docs/roadmap/worker-log-archive/",
    "found_on": ["worktree", "origin/main", "origin/epic/136"],
    "on_default_ref": true,
    "source": { "text": "docs/designs/worker-log-archive.md (…)", "paths": ["docs/designs/worker-log-archive.md"] },
    "status": "in_progress",
    "progress": { "phases_total": 5, "phases_done": 2, "epics_total": 2, "epics_done": 1, "tasks_total": 12, "tasks_closed": 11 },
    "phases": [{
      "number": 2, "title": "Collector", "path": "docs/roadmap/worker-log-archive/phases/phase-2.md",
      "declared_status": "not-started",
      "depends_on": [1], "depends_inferred": false, "depends_on_text": "Phase 1; all of epic #94 (D5).", "depends_on_issues": [94],
      "epics": [117], "external_epics": [],  // "owner/repo#N" captured in another tracker
      "status": "in_progress", "status_basis": "tracker", "next": false
    }],
    "next_actions": [{                 // see /fff:pipeline-next; lanes: build | plan | data | blocked
      "lane": "build", "kind": "finish-epic", "title": "Finish epic #117", "reason": "1 task open (#124)",
      "command": "/fff:work-epic 117", "epic": 117, "phase": 2
    }],
    "epics": [],                       // epics linked to the root but no phase (single plans)
    "prds": ["refunds"]                // PRDs this root was planned from
  }],
  "epics": [{
    "number": 117, "title": "…", "state": "open", "url": "…", "labels": ["epic", "ffflow-epic", "ready"],
    "root": "worker-log-archive", "phase": 2, "link_sources": ["issue_body"],   // issue_body | plan_file
    "tasks": { "total": 7, "closed": 6, "open": [124] },
    "task_list": [{ "number": 118, "title": "T1 — …", "state": "closed", "url": "…" }],  // execution order (T<N>), then number
    "checklist": { "total": 7, "ticked": 0 },
    "open_pulls": [], "status": "in_progress"
  }],
  "next_actions": [],                // build and plan actions across roots and ready PRDs, most urgent first
  "unlinked_open_issues": [{ "number": 12, "title": "…", "url": "…", "labels": ["bug"] }],
  "findings": [{ "code": "epic-unlinked", "severity": "warn", "subject": { "type": "epic", "number": 18 }, "message": "…" }]
}
```

Graph edges for a visualizer: PRD → root (`prds[].roots`), root → phase (`phases`), phase → epic (`phases[].epics`), root → epic (`roots[].epics`), phase → phase (`depends_on`), phase → issue (`depends_on_issues`), root → source document (`source.paths`). Additive fields don't bump `schema_version`; renamed or removed ones do.

### Finding codes

| Code | Severity | Meaning |
|---|---|---|
| `epic-unlinked` | warn | an epic names no plan root and no plan file cites it |
| `root-missing` | warn | an epic cites a plan root that no scanned ref holds |
| `captured-epic-unknown` | warn | a plan file's `Captured tasks` cites an issue that isn't an `ffflow-epic` (often stale numbering after a repo move) |
| `epic-link-conflict` | warn | issue body and plan file place an epic in different phases |
| `phase-missing` | warn | an epic cites a phase with no phase file |
| `roadmap-without-phase-files` | warn | `roadmap.md` with no `phases/phase-N.md` |
| `declared-status-disagrees` | warn / info | a phase file's `Status:` contradicts its epics (warn when it claims done) |
| `task-title-blank` | warn | a task issue's title is only its ordinal (`T1 — `) |
| `checklist-stale` | info | closed tasks left unticked in the epic checklist |
| `phase-capture-unrecorded` | info | the tracker links an epic to a phase whose file doesn't record it |
| `root-off-default-ref` | info | a root read from a branch or the working tree, not the default ref |
| `root-stale-branch` | info | a branch-only root nothing live points at; omitted |
| `prd-planned-before-converged` | warn | a roadmap cites a PRD whose `state.json` is not converged or ratified |
| `prd-file-missing` / `prd-file-ambiguous` | warn | a bundle with no `<slug>-prd.md`, or more than one |
| `prd-state-unreadable` | warn | `state.json` is not valid JSON |
| `prd-off-default-ref` | info | a PRD read from a branch or the working tree |
| `prd-stale-branch` | info | a branch-only PRD with no open PR and no roadmap citing it; omitted |

## Viewer

`viewer.html` (beside this file) is a template: one file, no network, no build. `--format html` writes it with the model embedded in `<script id="pipeline-data" type="application/json">` (the `__PIPELINE_JSON__` placeholder, `</` escaped). Opened as-is, it asks for a pipeline-status JSON file by picker or drag-and-drop, so any saved model can be viewed.

The repository's name, with a home icon, tops the left nav and leads back to the Overview. Below it the nav lists PRDs first, when the repository has any, delivered first (stage, round while drafting, a **ready** marker when ready for planning; each expands to the roadmaps planned from it), then every roadmap and plan (status and task count), done first and upcoming last. A roadmap expands to its phases, each with its status, task count and a **now** (in progress) or **next** (unblocked) marker; unfinished roadmaps start expanded, and a phase links to its place in the detail view (`#/root/<slug>/<phase>`). Below the roots is a catch-all section: **Unattached work** (epics with no plan root, open issues outside every epic), **Data gaps** (findings by code) and **All epics** (a table). The main pane shows the selection: the **Overview** (a one-line summary, the project-wide next actions, and one row per PRD and roadmap with what it's on now, a phase strip, status and task progress; an About panel links to what needs attention), or one roadmap: its **next actions** at the top (build and plan lanes, each with a copyable command), then tabs for **Phases** (one row per phase with status and task progress, expanding to dependencies, epics and each epic's task issues; the phase in progress or linked to opens), **Increments** (from the PRD it came from: number, size, what each contains and unlocks, not linked to phases; without a PRD, says how a roadmap gets one), and **Data gaps**, with an **About** panel beside them (progress, source, PRD, increments by size, location), or a PRD's detail (negotiation state and sign-offs, the roadmaps it feeds, outcomes, metrics with baseline → target, increments, items parked for planning). Views live in the URL hash (`#/root/<slug>`, `#/unattached`, …), so back, forward and bookmarks work. Status is always icon + label: ✓ done (green), ▶ in progress (blue), ○ captured / not started (grey), ? unknown (amber, a data gap). The next phase is outlined. Light and dark themes follow the OS, with a toggle. All data is inserted as text, never as HTML.

The viewer reads only the JSON contract above; it has no logic of its own about plans or trackers. Change the model in `pipeline.py`, the picture in `viewer.html`.

## Offline and replay

`--snapshot-out raw.json` saves what was collected (plan files and tracker data); `--snapshot-in raw.json` rebuilds the view from it with no git or network access. Use it to share a view, or to compare two points in time.

## Scope

- **Tracker:** `github-issues` only. Other backends report plan files with `tracker.ok: false`.
- **One repository.** No cross-repo portfolio yet.
- **Above PRDs:** goals are not read yet. Metrics have no current value; measuring them belongs to the goals layer.

## Anti-patterns

- Don't edit issues or plan files to fix findings — report them. Fixing is a separate, confirmed step.
- Don't infer status from prose. If the data says `unknown`, say `unknown` and name the gap.
- Don't re-implement readiness. `next` is dependency order only; the executor (e.g. a dispatcher) decides what can actually start.
