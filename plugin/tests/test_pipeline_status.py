"""Tests for plugin/skills/pipeline-status/pipeline.py.

    python3 -m unittest discover -s plugin/tests -v

Builds models from in-memory snapshots; never calls git or gh.
"""

import importlib.util
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "pipeline-status", "pipeline.py")
spec = importlib.util.spec_from_file_location("pipeline", SCRIPT)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def issue(n, title, state="OPEN", labels=(), body=""):
    return {"number": n, "title": title, "state": state, "labels": list(labels), "body": body, "url": f"u/{n}"}


def phase_file(n, title, status=None, depends=None, epic=None, tasks=()):
    lines = [f"# Phase {n}: {title}", ""]
    if status:
        lines.append(f"**Status:** {status}")
    if depends is not None:
        lines.append(f"**Depends on:** {depends}")
    if epic:
        lines += ["", "## Captured tasks", f"Epic: #{epic}", ""] + [f"- #{t} — task" for t in tasks]
    return "\n".join(lines) + "\n"


def snapshot(**over):
    snap = {
        "generated_at": "2026-11-10T00:00:00+00:00",
        "repo": "o/r",
        "default_ref": "origin/main",
        "refs_scanned": ["origin/main"],
        "capture": "github-issues",
        "tracker_error": None,
        "pulls": [],
        "plan_roots": {
            "archive": {
                "found_on": ["origin/main"],
                "files": {
                    "roadmap.md": "# Roadmap: archive\n\nLevel: L1 · Source: docs/designs/archive.md @ abc · Tracker: #1\n",
                    "phases/phase-0.md": phase_file(0, "Spike", status="complete", depends="none."),
                    "phases/phase-1.md": phase_file(1, "Storage", status="captured", depends="Phase 0. Not epic #50 (D10).",
                                                    epic=10, tasks=(11, 12)),
                    "phases/phase-2.md": phase_file(2, "Collector", status="not-started", depends="Phase 1; all of epic #50 (D5)."),
                    "phases/phase-3.md": phase_file(3, "Reader", status="not-started", depends="Phases 1 and 2."),
                },
            },
            "solo": {"found_on": ["origin/main"], "files": {"plan.md": "# Plan: solo\n\n## Captured tasks\n\nEpic #50.\n"}},
            "stale": {"found_on": ["origin/old-branch"], "files": {"plan.md": "# Plan: stale\n"}},
        },
        "issues": [
            issue(10, "Epic: Storage", "CLOSED", ["epic", "ffflow-epic"],
                  "Roadmap: docs/roadmap/archive/phases/phase-1.md\n\n- [ ] #11 T1\n- [x] #12 T2\n"),
            issue(11, "T1 — a", "CLOSED", ["ffflow-task", "epic-10"]),
            issue(12, "T2 — b", "CLOSED", ["ffflow-task", "epic-10"]),
            issue(50, "Epic: Solo", "OPEN", ["epic", "ffflow-epic"], "Design is in docs/roadmap/solo/plan.md\n"),
            issue(51, "T1 — c", "CLOSED", ["ffflow-task", "epic-50"]),
            issue(52, "T2 — d", "OPEN", ["ffflow-task", "epic-50"]),
            issue(60, "Epic: Orphan", "OPEN", ["epic", "ffflow-epic"], "No link here."),
            issue(70, "Epic: Gone", "CLOSED", ["epic", "ffflow-epic"], "See docs/roadmap/gone/prereqs.md."),
            issue(80, "Loose bug", "OPEN", ["bug"]),
            issue(81, "Closed loose bug", "CLOSED", ["bug"]),
        ],
    }
    snap.update(over)
    return snap


class ParseTests(unittest.TestCase):
    def test_depends_ignores_negated_clauses(self):
        self.assertEqual(pipeline.parse_depends("Phase 0. Not epic #94 (D10)."), ([0], []))
        self.assertEqual(pipeline.parse_depends("Phase 1; all of epic #94 (D5)."), ([1], [94]))
        self.assertEqual(pipeline.parse_depends("Phases 2 and 3 (D3)."), ([2, 3], []))
        self.assertEqual(pipeline.parse_depends("phase-2"), ([2], []))
        self.assertEqual(pipeline.parse_depends("none."), ([], []))
        self.assertEqual(pipeline.parse_depends(None), (None, []))

    def test_source_from_dotted_header(self):
        src = pipeline.parse_source("# Plan: x\n\nLevel: L1 · Source: docs/designs/v2.md @ d813dee (main) · Tracker: #80\n")
        self.assertEqual(src["text"], "docs/designs/v2.md @ d813dee (main)")
        self.assertEqual(src["paths"], ["docs/designs/v2.md"])

    def test_source_wraps_onto_following_lines(self):
        src = pipeline.parse_source("# Roadmap: x\n\nLevel: L1\nSource: docs/designs/x.md (approved), with\n"
                                    "docs/research/spike.md as evidence.\n\n## Phase 0\n")
        self.assertEqual(src["text"], "docs/designs/x.md (approved), with docs/research/spike.md as evidence.")
        self.assertEqual(src["paths"], ["docs/designs/x.md", "docs/research/spike.md"])

    def test_epic_link(self):
        self.assertEqual(pipeline.epic_link("Roadmap: docs/roadmap/a-b/phases/phase-2.md"), ("a-b", 2, None))
        self.assertEqual(pipeline.epic_link("see `docs/roadmap/first-run/prerequisites.md`."), ("first-run", None, None))
        self.assertIsNone(pipeline.epic_link("nothing"))

    def test_epic_link_to_another_repositorys_roadmap(self):
        body = "Tracked in yaunder/fffactory-verification `docs/roadmap/first-run/prerequisites.md`."
        self.assertEqual(pipeline.epic_link(body, "yaunder/fffactory"), ("first-run", None, "yaunder/fffactory-verification"))
        url = "See https://github.com/o/other/blob/main/docs/roadmap/x/phases/phase-1.md"
        self.assertEqual(pipeline.epic_link(url, "o/r"), ("x", 1, "o/other"))
        self.assertEqual(pipeline.epic_link("o/r docs/roadmap/x/", "o/r"), ("x", None, None))

    def test_captured_refs_to_another_tracker_are_external(self):
        text = "## Captured tasks\nEpic: yaunder/factory#85\n\n- yaunder/factory#88 — a\n"
        self.assertEqual(pipeline.parse_captured(text), ([], [], ["yaunder/factory#85"]))


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.m = pipeline.build(snapshot())
        self.roots = {r["slug"]: r for r in self.m["roots"]}
        self.epics = {e["number"]: e for e in self.m["epics"]}
        self.codes = [f["code"] for f in self.m["findings"]]

    def phase(self, n):
        return next(p for p in self.roots["archive"]["phases"] if p["number"] == n)

    def test_roadmap_phases_roll_up(self):
        self.assertEqual(self.phase(0)["status"], "done")
        self.assertEqual(self.phase(0)["status_basis"], "declared")
        self.assertEqual(self.phase(1)["status"], "done")
        self.assertEqual(self.phase(1)["epics"], [10])
        self.assertEqual(self.roots["archive"]["status"], "in_progress")
        self.assertEqual(self.roots["archive"]["source"]["paths"], ["docs/designs/archive.md"])
        self.assertEqual(self.roots["archive"]["progress"]["tasks_closed"], 2)

    def test_next_waits_for_phase_and_issue_dependencies(self):
        self.assertFalse(self.phase(2)["next"])  # epic #50 is still open
        self.assertFalse(self.phase(3)["next"])  # phase 2 not done
        m = pipeline.build(snapshot(issues=[i if i["number"] != 50 else {**i, "state": "CLOSED"}
                                            for i in snapshot()["issues"]]))
        archive = next(r for r in m["roots"] if r["slug"] == "archive")
        self.assertTrue(archive["phases"][2]["next"])
        self.assertEqual(m["summary"]["next"], [{"root": "archive", "phase": 2}])

    def test_roots_are_listed_done_first_upcoming_last(self):
        snap = snapshot()
        snap["plan_roots"]["later"] = {"found_on": ["origin/main"], "files": {
            "roadmap.md": "# Roadmap: later\n", "phases/phase-1.md": phase_file(1, "Someday")}}
        snap["issues"] = [i if i["number"] != 50 else {**i, "state": "CLOSED"} for i in snap["issues"]]
        order = [(r["slug"], r["status"]) for r in pipeline.build(snap)["roots"]]
        self.assertEqual(order, [("solo", "done"), ("gone", "done"), ("archive", "in_progress"), ("later", "not_started")])

    def test_tasks_count_issue_state_not_checklist_ticks(self):
        self.assertEqual(self.epics[10]["tasks"], {"total": 2, "closed": 2, "open": []})
        self.assertEqual(self.epics[10]["checklist"], {"total": 2, "ticked": 1})
        self.assertEqual([(x["number"], x["title"], x["state"]) for x in self.epics[10]["task_list"]],
                         [(11, "T1 — a", "closed"), (12, "T2 — b", "closed")])
        self.assertIn("checklist-stale", self.codes)

    def test_single_plan_links_from_both_sides(self):
        e = self.epics[50]
        self.assertEqual((e["root"], e["phase"]), ("solo", None))
        self.assertEqual(sorted(e["link_sources"]), ["issue_body", "plan_file"])
        self.assertEqual(e["status"], "in_progress")
        self.assertEqual(self.roots["solo"]["epics"], [50])

    def test_orphans_missing_roots_and_loose_issues(self):
        self.assertIsNone(self.epics[60]["root"])
        self.assertIn("epic-unlinked", self.codes)
        self.assertEqual(self.roots["gone"]["kind"], "missing")
        self.assertIn("root-missing", self.codes)
        self.assertEqual([i["number"] for i in self.m["unlinked_open_issues"]], [80])

    def test_epics_citing_another_repositorys_roadmap(self):
        snap = snapshot()
        snap["issues"].append(issue(71, "Epic: Prereq", "CLOSED", ["epic", "ffflow-epic"],
                                    "Tracked in o/verify `docs/roadmap/first-run/prerequisites.md`."))
        snap["plan_roots"]["archive"]["files"]["phases/phase-2.md"] = phase_file(2, "Collector", status="complete") + "\n## Captured tasks\nEpic: o/old#85\n"
        m = pipeline.build(snap)
        roots = {r["slug"]: r for r in m["roots"]}
        self.assertEqual((roots["verify/first-run"]["kind"], roots["verify/first-run"]["repo"]), ("external", "o/verify"))
        self.assertEqual(roots["verify/first-run"]["epics"], [71])
        codes = [f["code"] for f in m["findings"]]
        self.assertNotIn("captured-epic-unknown", codes)
        p2 = roots["archive"]["phases"][2]
        self.assertEqual((p2["status"], p2["external_epics"]), ("done", ["o/old#85"]))

    def actions(self, snap):
        m = pipeline.build(snap)
        return m, {r["slug"]: r["next_actions"] for r in m["roots"]}

    def test_build_and_plan_lanes_run_side_by_side(self):
        snap = snapshot()
        snap["issues"] += [issue(30, "Epic: Collector", "OPEN", ["epic", "ffflow-epic"], "Roadmap: docs/roadmap/archive/phases/phase-2.md"),
                           issue(31, "T1 — a", "CLOSED", ["ffflow-task", "epic-30"]),
                           issue(32, "T2 — b", "OPEN", ["ffflow-task", "epic-30"])]
        m, acts = self.actions(snap)
        kinds = [(a["lane"], a["kind"]) for a in acts["archive"]]
        self.assertEqual(kinds[:2], [("build", "finish-epic"), ("plan", "plan-phase")])
        finish, plan = acts["archive"][:2]
        self.assertEqual((finish["epic"], finish["command"]), (30, "/fff:work-epic 30"))
        self.assertIn("#32", finish["reason"])
        self.assertEqual((plan["phase"], plan["buildable"]), (3, False))  # phase 3 waits on phase 2, still planned now
        self.assertEqual(plan["command"], '/fff:plan-chat roadmap archive, phase 3 "Reader" (docs/roadmap/archive/phases/phase-3.md)')

    def test_phase_kind_picks_the_planning_skill(self):
        snap = snapshot()
        snap["plan_roots"]["archive"]["files"]["phases/phase-2.md"] = phase_file(2, "Collector", depends="Phase 1.") + "**Kind:** roadmap\n"
        _, acts = self.actions(snap)
        plan = next(a for a in acts["archive"] if a["kind"] == "plan-phase")
        self.assertTrue(plan["command"].startswith('/fff:plan-roadmap --phase 2 roadmap archive, phase 2 "Collector"'))
        snap["plan_roots"]["archive"]["files"]["phases/phase-2.md"] = phase_file(2, "Collector", depends="Phase 1.") + "Kind: research\n"
        _, acts = self.actions(snap)
        plan = next(a for a in acts["archive"] if a["kind"] == "plan-phase")
        self.assertIsNone(plan["command"])

    def test_open_pr_comes_first_and_global_list_is_by_urgency(self):
        snap = snapshot(pulls=[{"number": 99, "title": "x", "headRefName": "epic/50", "body": "", "url": "p"}])
        m, acts = self.actions(snap)
        self.assertEqual(acts["solo"][0]["kind"], "review-pr")
        self.assertEqual(m["next_actions"][0]["kind"], "review-pr")

    def test_captured_epic_on_an_unblocked_phase_can_start(self):
        snap = snapshot()
        snap["issues"].append(issue(30, "Epic: Collector", "OPEN", ["epic", "ffflow-epic"], "Roadmap: docs/roadmap/archive/phases/phase-2.md"))
        snap["issues"] = [i if i["number"] != 50 else {**i, "state": "CLOSED"} for i in snap["issues"]]
        _, acts = self.actions(snap)
        start = [a for a in acts["archive"] if a["kind"] == "start-epic"]
        self.assertEqual([(a["epic"], a["command"]) for a in start], [(30, "/fff:work-epic 30")])

    def test_blocked_and_done_roots(self):
        snap = snapshot()
        files = snap["plan_roots"]["archive"]["files"]
        files["phases/phase-2.md"] = phase_file(2, "Collector", depends="Phase 9.")
        files["phases/phase-3.md"] = phase_file(3, "Reader", depends="Phase 2.")
        _, acts = self.actions(snap)
        self.assertIn("plan-phase", [a["kind"] for a in acts["archive"]])  # phase 9 doesn't exist, so P2 plans
        snap["issues"] = [i if i["number"] != 50 else {**i, "state": "CLOSED"} for i in snap["issues"]]
        snap["plan_roots"]["solo"]["files"]["plan.md"] = "# Plan: solo\n\n## Captured tasks\n\nEpic #50.\n"
        _, acts = self.actions(snap)
        self.assertEqual(acts["solo"], [])

    def test_body_and_plan_file_naming_different_roots_conflict(self):
        snap = snapshot()
        snap["plan_roots"]["archive"]["files"]["phases/phase-2.md"] = phase_file(2, "Collector", epic=50)
        m = pipeline.build(snap)
        e = next(e for e in m["epics"] if e["number"] == 50)
        self.assertEqual((e["root"], e["phase"]), ("solo", None))
        self.assertIn("epic-link-conflict", [f["code"] for f in m["findings"]])

    def test_stale_branch_roots_are_omitted(self):
        self.assertNotIn("stale", self.roots)
        self.assertIn("root-stale-branch", self.codes)

    def test_branch_root_kept_when_its_branch_has_an_open_pr(self):
        pulls = [{"number": 9, "title": "x", "headRefName": "old-branch", "body": "", "url": "p"}]
        m = pipeline.build(snapshot(pulls=pulls))
        stale = next(r for r in m["roots"] if r["slug"] == "stale")
        self.assertFalse(stale["on_default_ref"])

    def test_phase_file_citing_unknown_epic(self):
        snap = snapshot()
        snap["plan_roots"]["archive"]["files"]["phases/phase-2.md"] = phase_file(2, "Collector", epic=999)
        m = pipeline.build(snap)
        self.assertIn("captured-epic-unknown", [f["code"] for f in m["findings"]])
        archive = next(r for r in m["roots"] if r["slug"] == "archive")
        self.assertEqual(archive["phases"][2]["status"], "unknown")

    def test_blank_task_title_is_a_gap(self):
        snap = snapshot()
        snap["issues"] = [i if i["number"] != 11 else {**i, "title": "T1 — "} for i in snap["issues"]]
        self.assertIn("task-title-blank", [f["code"] for f in pipeline.build(snap)["findings"]])

    def test_open_pr_marks_epic_in_progress(self):
        snap = snapshot(pulls=[{"number": 99, "title": "Epic 60 — x", "headRefName": "epic/60", "body": "", "url": "p"}])
        e = next(e for e in pipeline.build(snap)["epics"] if e["number"] == 60)
        self.assertEqual((e["status"], e["open_pulls"]), ("in_progress", [99]))

    def test_tracker_unavailable_still_reports_plan_files(self):
        m = pipeline.build(snapshot(issues=[], tracker_error="gh failed"))
        self.assertFalse(m["tracker"]["ok"])
        archive = next(r for r in m["roots"] if r["slug"] == "archive")
        self.assertEqual(archive["phases"][0]["status"], "done")
        self.assertNotIn("captured-epic-unknown", [f["code"] for f in m["findings"]])

    def test_html_embeds_model_and_cannot_close_the_script_tag(self):
        snap = snapshot()
        snap["issues"].append(issue(90, "</script><script>alert(1)</script>", "OPEN", ["bug"]))
        with open(pipeline.VIEWER, encoding="utf-8") as fh:
            html = pipeline.render_html(pipeline.build(snap), fh.read())
        self.assertNotIn(pipeline.PLACEHOLDER, html)
        data = html.split('id="pipeline-data" type="application/json">', 1)[1].split("</script>", 1)[0]
        self.assertEqual(json.loads(data)["unlinked_open_issues"][-1]["number"], 90)

    def test_model_is_json_with_schema_version(self):
        self.assertEqual(json.loads(json.dumps(self.m))["schema_version"], 1)
        self.assertIn("archive", pipeline.render_text(self.m))


PRD = """# Faster refunds

## 1. Problem
Refunds are slow.

## 3. Outcomes and non-goals
**Outcomes**
- Customers see a refund decision
  within one visit ([E-01](evidence/01-x.md)).
- Agents stop re-keying orders.

**Non-goals:** chargebacks.

## 7. Metrics
| Metric | Definition | Source | Baseline | Target |
|---|---|---|---|---|
| Time to decision | hours from request to decision | [facts](../_shared/facts.md) | 48 | 4 [provisional] |

## 8. Increments
1. **Decision API (M):** the rules as a service;
   unlocks the agent screen.
2. **Agent screen (S):** one form.

## 11. Open questions
| ID | ? | Question | Raised by | Owner (role) | Status | Resolution |
|---|---|---|---|---|---|---|
| Q-1 | ? | Which currencies? | builder | product | open | |
| Q-2 | | Who approves? | product | product | answered | → R-3 |
"""

PARKING = """| ID | Kind | Item | Why parked | Raised by | Round |
|---|---|---|---|---|---|
| P-1 | planning | Ship after the payments freeze | sequencing | builder | 1 |
| P-2 | idea | Refund chatbot | not this PRD | product | 1 |
"""


def bundle(slug, status, found_on=("origin/main",)):
    state = {"slug": slug, "round": 2, "round_cap": 3, "next": "product", "status": status,
             "signoff": {"builder": None, "product": None}, "links": {"parent": None, "children": []}}
    return {"found_on": list(found_on), "files": {"state.json": json.dumps(state), "medium.md": "# Medium\n",
                                                   "parking-lot.md": PARKING, f"{slug}-prd.md": PRD}}


class PrdTests(unittest.TestCase):
    def test_bundles_follow_ppps_rule(self):
        files = ["docs/prds/a/medium.md", "docs/prds/a/state.json", "docs/prds/a/a-prd.md", "docs/prds/a/evidence/01.md",
                 "docs/prds/b/state.json", "docs/prds/_shared/facts.md"]
        self.assertEqual(pipeline._bundles_in(files), {"docs/prds/a": ["a-prd.md", "medium.md", "state.json"]})

    def test_parse_prd(self):
        p = pipeline.parse_prd("docs/prds/refunds", bundle("refunds", "drafting")["files"], [])
        self.assertEqual(p["title"], "Faster refunds")
        self.assertEqual(p["outcomes"], ["Customers see a refund decision within one visit (E-01).", "Agents stop re-keying orders."])
        self.assertEqual(p["metrics"][0]["source"], "facts")
        self.assertEqual([(i["number"], i["name"], i["size"]) for i in p["increments"]],
                         [(1, "Decision API", "M"), (2, "Agent screen", "S")])
        self.assertEqual((p["increments"][0]["contains"], p["increments"][0]["unlocks"]),
                         ("the rules as a service", "the agent screen"))
        self.assertIsNone(p["increments"][1]["unlocks"])
        self.assertEqual((p["questions"]["open"], p["questions"]["answered"], p["questions"]["total"]), (1, 1, 2))
        self.assertEqual(p["provisional"], 1)
        self.assertEqual(p["planning_items"], [{"id": "P-1", "item": "Ship after the payments freeze"}])

    def test_increments_in_template_form(self):
        inc = pipeline.parse_increments("1. Import · M · a CSV reader · unlocks bulk loads\n")
        self.assertEqual({k: inc[0][k] for k in ("name", "size", "contains", "unlocks")},
                         {"name": "Import", "size": "M", "contains": "a CSV reader", "unlocks": "bulk loads"})

    def build(self, bundles, source=None, pulls=()):
        snap = snapshot(pulls=list(pulls))
        snap["prd_bundles"] = bundles
        if source:
            files = snap["plan_roots"]["archive"]["files"]
            files["roadmap.md"] = files["roadmap.md"].replace("docs/designs/archive.md", source)
        m = pipeline.build(snap)
        return m, {p["slug"]: p for p in m["prds"]}, [f["code"] for f in m["findings"]]

    def test_roadmap_source_links_prd_and_sets_stage(self):
        m, prds, codes = self.build({"docs/prds/refunds": bundle("refunds", "ratified")}, "docs/prds/refunds/refunds-prd.md")
        self.assertEqual(prds["refunds"]["roots"], ["archive"])
        self.assertEqual(prds["refunds"]["stage"], "delivering")
        self.assertFalse(prds["refunds"]["ready_for_planning"])
        self.assertEqual(next(r for r in m["roots"] if r["slug"] == "archive")["prds"], ["refunds"])
        self.assertNotIn("prd-planned-before-converged", codes)

    def test_converged_prd_with_no_roadmap_is_ready_for_planning(self):
        m, prds, _ = self.build({"docs/prds/refunds": bundle("refunds", "converged")})
        self.assertEqual(prds["refunds"]["stage"], "converged")
        self.assertEqual(m["summary"]["ready_for_planning"], ["refunds"])

    def test_prds_are_listed_delivered_first(self):
        m, _, _ = self.build({"docs/prds/a": bundle("a", "drafting"), "docs/prds/b": bundle("b", "ratified")},
                             "docs/prds/b/b-prd.md")
        self.assertEqual([(p["slug"], p["stage"]) for p in m["prds"]], [("b", "delivering"), ("a", "drafting")])

    def test_roadmap_from_unconverged_prd_is_flagged(self):
        _, _, codes = self.build({"docs/prds/refunds": bundle("refunds", "drafting")}, "docs/prds/refunds/refunds-prd.md")
        self.assertIn("prd-planned-before-converged", codes)

    def test_branch_prds_need_an_open_pr_and_templates_are_skipped(self):
        bundles = {"docs/prds/draft": bundle("draft", "drafting", ["origin/prd/draft"]),
                   "docs/prds/stale": bundle("stale", "drafting", ["origin/old"]),
                   "ppp/templates": bundle("<slug>", "drafting")}
        pulls = [{"number": 7, "title": "PRD: draft", "headRefName": "prd/draft", "body": "", "url": "p"}]
        _, prds, codes = self.build(bundles, pulls=pulls)
        self.assertEqual(sorted(prds), ["draft"])
        self.assertIn("prd-stale-branch", codes)


if __name__ == "__main__":
    unittest.main()
