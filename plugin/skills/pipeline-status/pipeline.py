#!/usr/bin/env python3
"""pipeline-status: roll FFFlow plan roots and tracker state up into one view.

Collects (git refs + working tree + `gh`) into a raw snapshot, builds a model from
it with pure functions, and prints the model as JSON (schema_version 1) or text.

    python3 pipeline.py                        # JSON on stdout
    python3 pipeline.py --format text
    python3 pipeline.py --format html --out pipeline.html   # viewer.html with the model embedded
    python3 pipeline.py --snapshot-out raw.json --out model.json
    python3 pipeline.py --snapshot-in raw.json --format text   # rebuild offline

Stdlib only. Read-only: never fetches, writes to git, or edits issues.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

SCHEMA_VERSION = 1
ROADMAP_DIR = "docs/roadmap"

DONE_WORDS = {"complete", "completed", "done", "shipped", "delivered"}
BUNDLE_FILES = {"state.json", "medium.md", "parking-lot.md", "prd.md"}

ROOT_LINK = re.compile(r"docs/roadmap/([A-Za-z0-9._-]+?)(?:/phases/phase-(\d+)\.md|/|`|\s|$)")
PHASE_FILE = re.compile(r"^phases/phase-(\d+)\.md$")
CHECKLIST = re.compile(r"^\s*[-*] \[([ xX])\] #(\d+)", re.M)
EPIC_LABEL = re.compile(r"^epic-(\d+)$")
PR_BRANCH = re.compile(r"(?:^|/)(?:epic|issue)[-/]?(\d+)\b")
PR_CLOSES = re.compile(r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)")
PR_TITLE_EPIC = re.compile(r"(?i)\bepic\s+#?(\d+)")


# ---------------------------------------------------------------- parsing (pure)

def _field(text: str, name: str) -> str | None:
    """Value of a `Name:` or `**Name:**` line, or None."""
    m = re.search(rf"(?im)^\s*(?:\*\*)?{name}:(?:\*\*)?\s*(.+?)\s*$", text)
    return m.group(1).strip() if m else None


def parse_depends(text: str | None) -> tuple[list[int] | None, list[int]]:
    """`Depends on:` text -> (phase numbers or None if unstated, issue numbers).

    Clauses starting with "not" are ignored ("Not epic #94" is not a dependency).
    """
    if text is None:
        return None, []
    phases: list[int] = []
    issues: list[int] = []
    for clause in re.split(r";|\.(?:\s|$)", text):
        clause = clause.strip()
        if not clause or re.match(r"(?i)not\b", clause):
            continue
        for m in re.finditer(r"(?i)phases?[\s-]*((?:\d+(?:\s*(?:,|and|&)\s*)?)+)", clause):
            phases += [int(n) for n in re.findall(r"\d+", m.group(1))]
        issues += [int(n) for n in re.findall(r"#(\d+)", clause)]
    return sorted(set(phases)), sorted(set(issues))


def parse_captured(text: str) -> tuple[list[int], list[int], list[str]]:
    """`## Captured tasks` section -> (local epic numbers, local task numbers, external epic refs).

    `Epic: #85` is this repository's issue; `Epic: owner/repo#85` is tracked elsewhere and
    never looked up locally.
    """
    m = re.search(r"(?ims)^##\s+Captured tasks\s*$(.*?)(?=^##\s|\Z)", text)
    if not m:
        return [], [], []
    body = m.group(1)
    epics, external = [], []
    for repo, num in re.findall(r"(?i)\bepic:?\s*([\w.-]+/[\w.-]+)?#(\d+)", body):
        if repo:
            external.append(f"{repo}#{num}")
        else:
            epics.append(int(num))
    tasks = [int(n) for n in re.findall(r"(?m)^\s*[-*]\s+(?:\[[ xX]\]\s+)?#(\d+)", body)]
    return epics, tasks, external


def parse_source(text: str) -> dict | None:
    """The `Source:` line from a root's header -> {text, paths}."""
    lines = text.splitlines()[:15]
    for i, line in enumerate(lines):
        m = re.search(r"(?:^|·\s*|\s)Source:\s*(.+?)(?=\s+·\s+|$)", line)
        if m:
            src = m.group(1).strip()
            if m.end() == len(line.rstrip()):
                # A Source: that ends its line may wrap; take lines until a blank, a heading or another field.
                for nxt in lines[i + 1:]:
                    if not nxt.strip() or re.match(r"\s*(?:#|[-*]\s|\*{0,2}[A-Z][\w ]*:)", nxt):
                        break
                    src += " " + nxt.strip()
            return {"text": src, "paths": re.findall(r"[\w./-]+\.(?:md|ya?ml|json)", src)}
    return None


def _title(text: str) -> str | None:
    m = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    if not m:
        return None
    return re.sub(r"^(?:Plan|Roadmap):\s*", "", m.group(1))


def parse_phase(number: int, path: str, text: str) -> dict:
    heading = _title(text) or ""
    title = re.sub(rf"(?i)^phase\s+{number}\s*[:—–-]*\s*", "", heading) or None
    dep_text = _field(text, "Depends on")
    depends, dep_issues = parse_depends(dep_text)
    epics, tasks, external = parse_captured(text)
    status = _field(text, "Status")
    kind = _field(text, "Kind")
    return {
        "number": number,
        "title": title,
        "path": path,
        "kind": kind.split()[0].lower() if kind else None,
        "declared_status": status.lower() if status else None,
        "depends_on": depends,
        "depends_on_text": dep_text,
        "depends_on_issues": dep_issues,
        "captured_epics": epics,
        "captured_tasks": tasks,
        "external_epics": external,
    }


def parse_root(slug: str, files: dict[str, str]) -> dict:
    """A plan root's files (paths relative to the root) -> parsed root."""
    head_name = "roadmap.md" if "roadmap.md" in files else "plan.md" if "plan.md" in files else None
    head = files.get(head_name, "") if head_name else ""
    phases = []
    for rel, text in files.items():
        m = PHASE_FILE.match(rel)
        if m:
            phases.append(parse_phase(int(m.group(1)), f"{ROADMAP_DIR}/{slug}/{rel}", text))
    phases.sort(key=lambda p: p["number"])
    epics, tasks, external = parse_captured(head)
    return {
        "slug": slug,
        "kind": "roadmap" if head_name == "roadmap.md" else "plan" if head_name else "unknown",
        "title": _title(head),
        "path": f"{ROADMAP_DIR}/{slug}/",
        "source": parse_source(head),
        "phases": phases,
        "captured_epics": epics,
        "captured_tasks": tasks,
        "external_epics": external,
    }


REPO_BEFORE = re.compile(r"(?:github\.com/([\w.-]+/[\w.-]+)/(?:blob|tree)/[^/\s]+/|\b([\w.-]+/[\w.-]+)\s*[`'\"]?\s*)$")


def epic_link(body: str, repo: str | None = None) -> tuple[str, int | None, str | None] | None:
    """First `docs/roadmap/<slug>[/phases/phase-N.md]` in an epic body -> (slug, phase, other repo).

    A path written right after another repository's name (`owner/repo docs/roadmap/…`, or a
    GitHub URL into another repository) belongs to that repository's roadmap.
    """
    body = body or ""
    m = ROOT_LINK.search(body)
    if not m:
        return None
    line_start = body.rfind("\n", 0, m.start()) + 1
    q = REPO_BEFORE.search(body[line_start:m.start()])
    other = (q.group(1) or q.group(2)) if q else None
    if other and repo and other.lower() == repo.lower():
        other = None
    return m.group(1).rstrip("."), int(m.group(2)) if m.group(2) else None, other


def pr_targets(pr: dict) -> set[int]:
    nums = {int(n) for n in PR_BRANCH.findall(pr.get("headRefName") or "")}
    nums |= {int(n) for n in PR_CLOSES.findall(pr.get("body") or "")}
    nums |= {int(n) for n in PR_TITLE_EPIC.findall(pr.get("title") or "")}
    return nums


# ---------------------------------------------------------------- PRDs (pure)

PRD_STAGES = ("drafting", "converged", "ratified", "planned", "delivering", "delivered", "unknown")
QUESTION_STATES = ("open", "answered", "deferred", "dropped")


def _sections(text: str) -> dict[str, str]:
    """`## N. Name` sections -> {name, lowercased and unnumbered: body}."""
    return {m.group(1).strip().lower(): m.group(2)
            for m in re.finditer(r"(?ms)^##\s+(?:\d+\.\s*)?(.+?)\s*$(.*?)(?=^##\s|\Z)", text)}


def _section(secs: dict[str, str], name: str) -> str:
    return next((body for k, body in secs.items() if k.startswith(name)), "")


def _table(text: str) -> list[dict]:
    """First markdown table in text -> rows keyed by lowercased header."""
    lines = [l.strip() for l in text.splitlines() if l.strip().startswith("|")]
    if len(lines) < 2:
        return []
    split = lambda l: [c.strip() for c in l.strip("|").split("|")]  # noqa: E731
    head = [c.lower() for c in split(lines[0])]
    rows = []
    for line in lines[1:]:
        cells = split(line)
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c) or not any(cells):
            continue
        rows.append(dict(zip(head, cells + [""] * (len(head) - len(cells)))))
    return rows


def _plain(text: str) -> str:
    """Markdown links -> their text."""
    return re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text).strip()


def _bullets(text: str) -> list[str]:
    """Bullet items, each joined with its wrapped continuation lines; else one paragraph."""
    items: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^\s*[-*]\s+(.+)$", line)
        if m:
            items.append(m.group(1).strip())
        elif items and line.startswith((" ", "\t")) and line.strip():
            items[-1] += " " + line.strip()
        elif items and not line.strip():
            continue
    if items:
        return [_plain(i) for i in items]
    para = " ".join(l.strip() for l in text.splitlines() if l.strip())
    return [_plain(para)] if para else []


def _split_unlocks(text: str) -> tuple[str, str | None]:
    """'contents; unlocks X.' -> ('contents', 'X')."""
    m = re.search(r"(?i)(?:^|[;,.]\s*|\s)unlocks?\s+(.+?)\.?$", text)
    if not m:
        return text.strip().rstrip("."), None
    return text[:m.start()].strip().rstrip(";,.") , m.group(1).strip()


def parse_increments(text: str) -> list[dict]:
    """Numbered §8 entries -> [{number, name, size, text, contains, unlocks}].

    `number` is the entry's position in the PRD, for display only: increments have no stable IDs.
    Continuation lines join their entry.
    """
    entries: list[str] = []
    for line in text.splitlines():
        if re.match(r"^\s*\d+\.\s+", line):
            entries.append(re.sub(r"^\s*\d+\.\s+", "", line).strip())
        elif entries and line.strip():
            entries[-1] += " " + line.strip()
    out = []
    for n, e in enumerate(entries, 1):
        parts = [x.strip() for x in e.split("·")]
        if len(parts) >= 4 and re.fullmatch(r"XL|S|M|L", parts[1]):
            # Template form: name · size · what it contains · what it unlocks
            name, size, contains, unlocks = parts[0].strip("*: "), parts[1], parts[2], " · ".join(parts[3:])
            out.append({"number": n, "name": name, "size": size, "text": f"{contains}; unlocks {unlocks}",
                        "contains": contains, "unlocks": re.sub(r"(?i)^unlocks?\s+", "", unlocks).rstrip(".")})
            continue
        bold = re.match(r"\*\*(.+?)\*\*:?\s*(.*)", e)
        head, rest = (bold.group(1), bold.group(2)) if bold else (e.split(":", 1)[0], e.split(":", 1)[-1])
        size = re.search(r"\b(XL|S|M|L)\b(?=[^()]*\))", head) or re.search(r"·\s*(XL|S|M|L)\s*·", e)
        contains, unlocks = _split_unlocks(rest.strip())
        out.append({
            "number": n,
            "name": re.sub(r"\s*\([^)]*\)\s*:?$", "", head).strip().rstrip(":"),
            "size": size.group(1) if size else None,
            "text": rest.strip(),
            "contains": contains,
            "unlocks": unlocks,
        })
    return out


def parse_prd(path: str, files: dict[str, str], findings: list) -> dict:
    """A ppp bundle's files -> PRD summary. Reads files only; never calls ppp."""
    subject = {"type": "prd", "path": path}
    state = None
    try:
        state = json.loads(files.get("state.json", ""))
    except ValueError:
        _finding(findings, "prd-state-unreadable", "warn", subject, f"{path}/state.json is not valid JSON")
    prd_names = [n for n in files if n.endswith("-prd.md")] or [n for n in files if n == "prd.md"]
    if len(prd_names) != 1:
        _finding(findings, "prd-file-missing" if not prd_names else "prd-file-ambiguous", "warn", subject,
                 f"{path} holds {len(prd_names)} PRD files; expected one <slug>-prd.md")
    text = files.get(prd_names[0], "") if len(prd_names) == 1 else ""
    secs = _sections(text)
    outcomes_text = _section(secs, "outcomes")
    outcomes_text = re.split(r"(?i)\*\*non-goals", outcomes_text)[0]
    outcomes_text = re.sub(r"(?i)\*\*outcomes:?\*\*:?", "", outcomes_text)
    metrics = [{k: _plain(r.get(k, "")) for k in ("metric", "definition", "source", "baseline", "target")}
               for r in _table(_section(secs, "metrics")) if r.get("metric")]
    qrows = [r for r in _table(_section(secs, "open questions")) if r.get("id")]
    questions = {k: sum(1 for r in qrows if r.get("status", "").lower() == k) for k in QUESTION_STATES}
    questions["total"] = len(qrows)
    planning = [{"id": r.get("id", ""), "item": r.get("item", "")}
                for r in _table(files.get("parking-lot.md", "")) if r.get("kind", "").lower() == "planning"]
    st = state if isinstance(state, dict) else {}
    return {
        "slug": st.get("slug") or path.rsplit("/", 1)[-1] or path,
        "path": path,
        "prd_file": f"{path}/{prd_names[0]}".lstrip("/") if len(prd_names) == 1 else None,
        "title": _title(text),
        "state": {k: st.get(k) for k in ("status", "round", "round_cap", "next", "signoff", "links")},
        "outcomes": _bullets(outcomes_text),
        "metrics": metrics,
        "increments": parse_increments(_section(secs, "increments")),
        "questions": questions,
        "provisional": len(re.findall(r"\[provisional(?::[^\]]*)?\]", text)),
        "planning_items": planning,
    }


def _cites(path: str, source: dict | None) -> bool:
    if not source:
        return False
    return any(p == path or p.startswith(path + "/") for p in source["paths"]) or (path + "/") in source["text"]


# ---------------------------------------------------------------- next actions (pure)

LANES = ("build", "plan", "data", "blocked")
# A phase's Kind: picks the skill that plans it (plan-roadmap's handoff table). Unknown kinds plan with plan-chat.
PLAN_HANDOFF = {"design-slice": "/fff:plan-chat", "plan-chat": "/fff:plan-chat", "characterize": "/fff:characterize",
                "cleanup": "/fff:audit --plan", "roadmap": "/fff:plan-roadmap --phase {n}"}
# Across roots, the most urgent first: unblock review, finish what's started, start, then plan.
ACTION_ORDER = ("review-pr", "finish-epic", "start-epic", "plan-phase", "plan-roadmap")


def _action(lane, kind, title, reason, command=None, **ref):
    return {"lane": lane, "kind": kind, "title": title, "reason": reason, "command": command, **ref}


def next_actions(root: dict, epics: dict[int, dict], findings: list[dict]) -> list[dict]:
    """What to do next on one root, in two lanes that run side by side.

    build: review an open PR, finish an epic in progress, start a captured epic whose phase is unblocked.
    plan:  the next phase with no epic, once every phase it depends on is at least planned. Planning
           runs ahead of building: dependencies gate starting the build, not planning.
    data:  warnings on this root's trail. blocked: when neither lane has anything, what's in the way.
    Suggestions only; the executor decides what actually starts.
    """
    if root["kind"] == "external" or root["status"] == "done":
        return []
    acts: list[dict] = []
    phases = {p["number"]: p for p in root["phases"]}
    mine = [(n, p) for p in root["phases"] for n in p["epics"]] + [(n, None) for n in root["epics"]]
    mine = [(epics[n], p) for n, p in mine if n in epics]

    for e, p in mine:
        if e["status"] != "done" and e["open_pulls"]:
            prs = ", ".join(f"#{x}" for x in e["open_pulls"])
            acts.append(_action("build", "review-pr", f"Review and merge PR {prs}", f"epic #{e['number']} has an open pull request",
                                epic=e["number"], phase=p["number"] if p else None, pulls=e["open_pulls"]))
    for e, p in mine:
        if e["status"] == "in_progress" and not e["open_pulls"]:
            left = e["tasks"]["open"]
            what = f"{len(left)} task{'s' if len(left) != 1 else ''} open ({', '.join(f'#{t}' for t in left[:5])})" if left else "no open tasks; close the epic"
            acts.append(_action("build", "finish-epic", f"Finish epic #{e['number']}", what,
                                command=f"/fff:work-epic {e['number']}", epic=e["number"], phase=p["number"] if p else None))
    for e, p in mine:
        if e["status"] == "captured" and (p is None or p["next"] or p["status"] == "in_progress"):
            acts.append(_action("build", "start-epic", f"Start epic #{e['number']}",
                                f"phase {p['number']} is unblocked" if p else "captured and not started",
                                command=f"/fff:work-epic {e['number']}", epic=e["number"], phase=p["number"] if p else None))

    planned = {"done", "in_progress", "captured"}
    for p in root["phases"]:
        if p["epics"] or p["status"] in ("done", "in_progress", "unknown"):
            continue
        if all(phases[d]["status"] in planned for d in p["depends_on"] if d in phases):
            ready = all(phases[d]["status"] == "done" for d in p["depends_on"] if d in phases)
            name = p["title"] or "(untitled)"
            skill = PLAN_HANDOFF.get(p.get("kind") or "design-slice")
            # Name the roadmap, the phase and its file, so the planner can't pick up a similarly named phase.
            command = (f'{skill.format(n=p["number"])} roadmap {root["slug"]}, phase {p["number"]} "{name}" ({p["path"]})'
                       if skill else None)
            reason = ("its dependencies are done, so it can be built once planned" if ready
                      else "its dependencies are planned; plan it while they are built")
            if not skill:
                reason += f"; its kind ({p['kind']}) has no planning skill"
            acts.append(_action("plan", "plan-phase", f"Plan phase {p['number']}: {name}", reason, command=command,
                                phase=p["number"], path=p["path"], phase_kind=p.get("kind"), buildable=ready))
        break  # plan one phase ahead at a time

    gaps = [f for f in findings if f["severity"] == "warn" and f["subject"].get("slug") == root["slug"]]
    if gaps:
        acts.append(_action("data", "fix-data", f"Fix {len(gaps)} data gap{'s' if len(gaps) != 1 else ''}",
                            gaps[0]["message"], count=len(gaps)))

    if not any(a["lane"] in ("build", "plan") for a in acts):
        waiting = next((p for p in root["phases"] if p["status"] not in ("done",)), None)
        if waiting is not None:
            deps = [f"phase {d}" for d in waiting["depends_on"] if d in phases and phases[d]["status"] != "done"]
            deps += [f"#{i}" for i in waiting["depends_on_issues"]]
            why = (f"waiting on {', '.join(deps)}" if deps else
                   "its status is unknown (see data gaps)" if waiting["status"] == "unknown" else "nothing is unblocked")
            acts.append(_action("blocked", "blocked", f"Phase {waiting['number']} is blocked", why, phase=waiting["number"]))
        elif not root["phases"] and not mine:
            acts.append(_action("blocked", "nothing-linked", "Nothing is linked to this plan",
                                "no epic cites it and it has no phase files"))
    return acts


# ---------------------------------------------------------------- build (pure)

def _finding(findings, code, severity, subject, message):
    findings.append({"code": code, "severity": severity, "subject": subject, "message": message})


def _rollup(statuses: list[str]) -> str:
    if not statuses:
        return "unknown"
    if all(s == "done" for s in statuses):
        return "done"
    if any(s in ("done", "in_progress") for s in statuses):
        return "in_progress"
    if any(s == "captured" for s in statuses):
        return "captured"
    if any(s == "unknown" for s in statuses):
        return "unknown"
    return "not_started"


def build(snap: dict) -> dict:
    findings: list[dict] = []
    default_ref = snap.get("default_ref")
    issues = {i["number"]: i for i in snap.get("issues", [])}
    pulls = snap.get("pulls", [])
    tracker_ok = not snap.get("tracker_error")

    def labels(i):
        return [l if isinstance(l, str) else l["name"] for l in i.get("labels", [])]

    def closed(n):
        return n in issues and issues[n]["state"].upper() == "CLOSED"

    epic_nums = sorted(n for n, i in issues.items() if "ffflow-epic" in labels(i))
    pr_heads = {pr.get("headRefName") for pr in pulls}

    # Tasks per epic: epic-<n> labels, plus checklist entries that are real non-epic issues.
    tasks: dict[int, set[int]] = {n: set() for n in epic_nums}
    for n, i in issues.items():
        for l in labels(i):
            m = EPIC_LABEL.match(l)
            if m and int(m.group(1)) in tasks:
                tasks[int(m.group(1))].add(n)
    checklists: dict[int, list[tuple[int, bool]]] = {}
    for n in epic_nums:
        items = [(int(num), mark != " ") for mark, num in CHECKLIST.findall(issues[n].get("body") or "")]
        checklists[n] = items
        tasks[n] |= {num for num, _ in items if num in issues and num not in epic_nums}

    epic_prs: dict[int, list[int]] = {n: [] for n in epic_nums}
    for pr in pulls:
        for t in pr_targets(pr):
            if t in epic_prs:
                epic_prs[t].append(pr["number"])

    # Plan roots, filtered: off-default roots only when something live points at them.
    raw_roots = snap.get("plan_roots", {})
    repo = snap.get("repo")
    cited = {lnk[0] for n in epic_nums if (lnk := epic_link(issues[n].get("body"), repo)) and not lnk[2]}
    roots: dict[str, dict] = {}
    for slug, raw in raw_roots.items():
        found_on = raw.get("found_on", [])
        on_default = default_ref in found_on
        live_branch = any(r.split("/", 1)[-1] in pr_heads for r in found_on)
        if not (on_default or "worktree" in found_on or live_branch or slug in cited):
            _finding(findings, "root-stale-branch", "info", {"type": "root", "slug": slug},
                     f"{slug} exists only on {', '.join(found_on)} with no open PR or epic citing it; omitted")
            continue
        root = parse_root(slug, raw.get("files", {}))
        root.update(found_on=found_on, on_default_ref=on_default, epics=[], prds=[])
        if not on_default:
            _finding(findings, "root-off-default-ref", "info", {"type": "root", "slug": slug},
                     f"{slug} is not on {default_ref}; read from {found_on[0]}")
        if root["kind"] == "roadmap" and not root["phases"]:
            _finding(findings, "roadmap-without-phase-files", "warn", {"type": "root", "slug": slug},
                     f"{slug}/roadmap.md has no phases/phase-N.md files to report on")
        for p in root["phases"]:
            p["epics"] = []
        roots[slug] = root

    # Link epics -> roots/phases from both sides.
    epics: dict[int, dict] = {}
    external_roots: dict[str, tuple[str, str]] = {}
    for n in epic_nums:
        i = issues[n]
        lnk = epic_link(i.get("body"), repo)
        if lnk and lnk[2]:
            # Another repository's roadmap: keyed "<repo name>/<slug>" so it can't collide with a local slug.
            lnk = (f"{lnk[2].split('/')[-1]}/{lnk[0]}", lnk[1], lnk[2])
            external_roots[lnk[0]] = (lnk[2], lnk[0].split("/", 1)[1])
        epics[n] = {
            "number": n,
            "title": i["title"],
            "state": i["state"].lower(),
            "url": i.get("url"),
            "labels": labels(i),
            "root": lnk[0] if lnk else None,
            "phase": lnk[1] if lnk else None,
            "link_sources": ["issue_body"] if lnk else [],
        }

    def cite(slug, phase_no, nums, where):
        for e in nums:
            if e not in epics:
                what = "not an ffflow-epic issue" if e in issues else "not found in the tracker"
                if tracker_ok:
                    _finding(findings, "captured-epic-unknown", "warn",
                             {"type": "phase" if phase_no is not None else "root", "slug": slug, "phase": phase_no},
                             f"{where} cites epic #{e}, which is {what} (stale numbering?)")
                continue
            ep = epics[e]
            if ep["root"] is None:
                ep["root"], ep["phase"] = slug, phase_no
            elif ep["root"] != slug or (None not in (ep["phase"], phase_no) and ep["phase"] != phase_no):
                said = f"{ep['root']}" + (f" phase {ep['phase']}" if ep["phase"] is not None else "")
                _finding(findings, "epic-link-conflict", "warn", {"type": "epic", "number": e},
                         f"#{e} body says {said}; {where} also claims it")
                continue
            elif ep["phase"] is None:
                ep["phase"] = phase_no
            if "plan_file" not in ep["link_sources"]:
                ep["link_sources"].append("plan_file")

    for slug, root in roots.items():
        cite(slug, None, root["captured_epics"], f"{root['path']}")
        for p in root["phases"]:
            cite(slug, p["number"], p["captured_epics"], p["path"])

    # External roots: another repository's roadmap that epics here serve.
    for key, (other, slug) in external_roots.items():
        roots[key] = {"slug": key, "kind": "external", "repo": other, "title": None,
                      "path": f"{other}:{ROADMAP_DIR}/{slug}/", "url": f"https://github.com/{other}/tree/HEAD/{ROADMAP_DIR}/{slug}",
                      "source": None, "phases": [], "found_on": [], "on_default_ref": False, "epics": [], "prds": [],
                      "captured_epics": [], "captured_tasks": [], "external_epics": []}

    # Missing roots: epics cite a slug no scanned ref holds.
    for ep in epics.values():
        if ep["root"] and ep["root"] not in roots:
            slug = ep["root"]
            roots[slug] = {"slug": slug, "kind": "missing", "title": None, "path": f"{ROADMAP_DIR}/{slug}/",
                           "source": None, "phases": [], "found_on": [], "on_default_ref": False, "epics": [], "prds": [],
                           "captured_epics": [], "captured_tasks": [], "external_epics": []}
            _finding(findings, "root-missing", "warn", {"type": "root", "slug": slug},
                     f"epics cite {slug}, but no scanned ref or the working tree holds it")

    # Epic status.
    for n, ep in epics.items():
        ts = sorted(tasks[n])
        done_ts = [t for t in ts if closed(t)]
        ep["tasks"] = {"total": len(ts), "closed": len(done_ts), "open": [t for t in ts if not closed(t)]}
        # Execution order: the T<N> ordinal in the title when present, else the issue number.
        ordinal = lambda t: (int(m.group(1)) if (m := re.match(r"T(\d+)\b", issues[t]["title"])) else 10**6, t)  # noqa: E731
        ep["task_list"] = [{"number": t, "title": issues[t]["title"], "state": issues[t]["state"].lower(),
                            "url": issues[t].get("url")} for t in sorted(ts, key=ordinal)]
        for t in ep["task_list"]:
            if re.fullmatch(r"\s*(?:T\d+\s*[—–-]?)?\s*", t["title"]):
                _finding(findings, "task-title-blank", "warn", {"type": "epic", "number": n},
                         f"task #{t['number']} of epic #{n} has no title beyond its ordinal ({t['title'].strip()!r})")
        ep["checklist"] = {"total": len(checklists[n]), "ticked": sum(1 for _, x in checklists[n] if x)}
        ep["open_pulls"] = sorted(set(epic_prs[n]))
        if ep["state"] == "closed":
            ep["status"] = "done"
        elif done_ts or ep["open_pulls"]:
            ep["status"] = "in_progress"
        else:
            ep["status"] = "captured"
        closed_listed = sum(1 for num, x in checklists[n] if closed(num) and not x)
        if closed_listed:
            _finding(findings, "checklist-stale", "info", {"type": "epic", "number": n},
                     f"#{n} checklist leaves {closed_listed} closed task(s) unticked; status uses issue state")
        if ep["root"] is None:
            _finding(findings, "epic-unlinked", "warn", {"type": "epic", "number": n},
                     f"#{n} names no docs/roadmap/<slug>, and no plan file cites it")

    # Attach epics; phase and root status.
    for ep in epics.values():
        root = roots.get(ep["root"])
        if not root:
            continue
        phase = next((p for p in root["phases"] if p["number"] == ep["phase"]), None)
        if phase is not None:
            phase["epics"].append(ep["number"])
            if "plan_file" not in ep["link_sources"]:
                _finding(findings, "phase-capture-unrecorded", "info",
                         {"type": "phase", "slug": root["slug"], "phase": phase["number"]},
                         f"{phase['path']} has no Captured tasks entry for #{ep['number']}")
        else:
            if ep["phase"] is not None and root["kind"] not in ("missing", "external"):
                _finding(findings, "phase-missing", "warn", {"type": "epic", "number": ep["number"]},
                         f"#{ep['number']} cites {root['slug']} phase {ep['phase']}, which has no phase file")
            root["epics"].append(ep["number"])

    for root in roots.values():
        numbers = {p["number"] for p in root["phases"]}
        for p in root["phases"]:
            sts = [epics[e]["status"] for e in p["epics"]]
            if sts:
                p["status"], p["status_basis"] = _rollup(sts), "tracker"
                if p["declared_status"] in DONE_WORDS and p["status"] != "done":
                    _finding(findings, "declared-status-disagrees", "warn",
                             {"type": "phase", "slug": root["slug"], "phase": p["number"]},
                             f"{p['path']} says {p['declared_status']}; its epics say {p['status']}")
                elif p["declared_status"] in ("not-started", "not started", "planned") and p["status"] != "not_started":
                    _finding(findings, "declared-status-disagrees", "info",
                             {"type": "phase", "slug": root["slug"], "phase": p["number"]},
                             f"{p['path']} says {p['declared_status']}; its epics say {p['status']}")
            elif p["declared_status"] in DONE_WORDS:
                p["status"], p["status_basis"] = "done", "declared"
            elif p["captured_epics"] or p["external_epics"]:
                p["status"], p["status_basis"] = "unknown", "none"
            else:
                p["status"], p["status_basis"] = "not_started", "none"
            p["depends_inferred"] = p["depends_on"] is None
            if p["depends_on"] is None:
                prior = [x for x in numbers if x < p["number"]]
                p["depends_on"] = [max(prior)] if prior else []
        by_no = {p["number"]: p for p in root["phases"]}
        for p in root["phases"]:
            deps_done = all(by_no[d]["status"] == "done" for d in p["depends_on"] if d in by_no)
            issues_done = all(closed(i) or i not in issues for i in p["depends_on_issues"])
            p["next"] = p["status"] in ("not_started", "captured") and deps_done and issues_done

        sts = [p["status"] for p in root["phases"]] + [epics[e]["status"] for e in root["epics"]]
        root["status"] = _rollup(sts)
        all_epics = [e for p in root["phases"] for e in p["epics"]] + root["epics"]
        root["progress"] = {
            "phases_total": len(root["phases"]),
            "phases_done": sum(1 for p in root["phases"] if p["status"] == "done"),
            "epics_total": len(all_epics),
            "epics_done": sum(1 for e in all_epics if epics[e]["status"] == "done"),
            "tasks_total": sum(epics[e]["tasks"]["total"] for e in all_epics),
            "tasks_closed": sum(epics[e]["tasks"]["closed"] for e in all_epics),
        }
        for k in ("captured_epics", "captured_tasks"):
            root.pop(k, None)
            for p in root["phases"]:
                p.pop(k, None)
        root["epics"].sort()
        for p in root["phases"]:
            p["epics"].sort()

    # PRDs: ppp bundles, linked to the roots whose Source: line points into them.
    prds: list[dict] = []
    seen: set[str] = set()
    for path, raw in sorted(snap.get("prd_bundles", {}).items()):
        found_on = raw.get("found_on", [])
        on_default = default_ref in found_on
        live_branch = any(r.split("/", 1)[-1] in pr_heads for r in found_on)
        cited_by = [r["slug"] for r in roots.values() if _cites(path, r["source"])]
        if not (on_default or "worktree" in found_on or live_branch or cited_by):
            _finding(findings, "prd-stale-branch", "info", {"type": "prd", "path": path},
                     f"PRD bundle {path} exists only on {', '.join(found_on)} with no open PR or roadmap citing it; omitted")
            continue
        prd = parse_prd(path, raw.get("files", {}), findings)
        if prd["slug"].startswith("<"):
            continue  # an unfilled template (state.json slug is still "<slug>"), not a PRD
        if prd["slug"] in seen:
            prd["slug"] = path
        seen.add(prd["slug"])
        prd.update(found_on=found_on, on_default_ref=on_default, roots=sorted(cited_by))
        for slug in cited_by:
            roots[slug]["prds"].append(prd["slug"])
        status = prd["state"]["status"]
        if cited_by:
            sts = [roots[s]["status"] for s in cited_by]
            prd["stage"] = ("delivered" if all(x == "done" for x in sts)
                            else "delivering" if any(x in ("done", "in_progress") for x in sts) else "planned")
        else:
            prd["stage"] = status if status in ("drafting", "converged", "ratified") else "unknown"
        prd["ready_for_planning"] = not cited_by and status in ("converged", "ratified")
        if cited_by and status not in ("converged", "ratified"):
            _finding(findings, "prd-planned-before-converged", "warn", {"type": "prd", "path": path},
                     f"{', '.join(cited_by)} cites PRD {prd['slug']}, which is still {status or 'without a status'}")
        if not on_default:
            _finding(findings, "prd-off-default-ref", "info", {"type": "prd", "path": path},
                     f"PRD {prd['slug']} is not on {default_ref}; read from {found_on[0]}")
        prds.append(prd)
    # Same reading order as roots: delivered first, the earliest-stage PRDs last.
    prd_rank = ("delivered", "delivering", "planned", "ratified", "converged", "drafting", "unknown")
    prds.sort(key=lambda p: (prd_rank.index(p["stage"]), p["slug"]))

    for r in roots.values():
        r["next_actions"] = next_actions(r, epics, findings)
    product = [_action("plan", "plan-roadmap", f"Plan a roadmap from PRD {p['slug']}",
                       f"the PRD is {p['state']['status']} and no roadmap cites it", command="/fff:plan-roadmap",
                       prd=p["slug"], path=p["prd_file"]) for p in prds if p["ready_for_planning"]]

    # Open issues outside every epic.
    in_epic = {t for ts in tasks.values() for t in ts}
    unlinked = []
    for n, i in sorted(issues.items()):
        ls = labels(i)
        if (i["state"].upper() == "OPEN" and n not in epics and n not in in_epic
                and "ffflow-task" not in ls and not any(EPIC_LABEL.match(l) for l in ls)):
            unlinked.append({"number": n, "title": i["title"], "url": i.get("url"), "labels": ls})

    # Done first, then in progress, then what's still to come, so the end of the list is what's upcoming.
    rank = {"done": 0, "in_progress": 1, "captured": 2, "not_started": 3, "unknown": 4}
    order = sorted(roots.values(), key=lambda r: (rank.get(r["status"], 4), r["kind"] == "missing", r["slug"]))
    ep_list = sorted(epics.values(), key=lambda e: e["number"])
    count = lambda xs, s: sum(1 for x in xs if x["status"] == s)  # noqa: E731
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": snap.get("generated_at"),
        "repo": snap.get("repo"),
        "default_ref": default_ref,
        "refs_scanned": snap.get("refs_scanned", []),
        "tracker": {
            "backend": snap.get("capture"),
            "ok": tracker_ok,
            "error": snap.get("tracker_error"),
            "issues": len(issues),
            "open_pulls": len(pulls),
        },
        "summary": {
            "roots": len(order),
            "roots_done": count(order, "done"),
            "roots_in_progress": count(order, "in_progress"),
            "epics": len(ep_list),
            "epics_done": count(ep_list, "done"),
            "epics_in_progress": count(ep_list, "in_progress"),
            "epics_unlinked": sum(1 for e in ep_list if e["root"] is None),
            "unlinked_open_issues": len(unlinked),
            "next": [{"root": r["slug"], "phase": p["number"]} for r in order for p in r["phases"] if p["next"]],
            "prds": len(prds),
            "prds_by_stage": {k: sum(1 for p in prds if p["stage"] == k) for k in PRD_STAGES if any(p["stage"] == k for p in prds)},
            "ready_for_planning": [p["slug"] for p in prds if p["ready_for_planning"]],
            "roots_without_prd": sum(1 for r in order if r["kind"] != "missing" and not r["prds"]),
        },
        "prds": prds,
        "next_actions": sorted(product + [{**a, "root": r["slug"]} for r in order for a in r["next_actions"]
                                          if a["lane"] in ("build", "plan")],
                               key=lambda a: ACTION_ORDER.index(a["kind"])),
        "roots": order,
        "epics": ep_list,
        "unlinked_open_issues": unlinked,
        "findings": findings,
    }


# ---------------------------------------------------------------- render

MARK = {"done": "✓", "in_progress": "▶", "captured": "·", "not_started": "·", "unknown": "?"}


def render_text(m: dict) -> str:
    epics = {e["number"]: e for e in m["epics"]}
    out = [f"Pipeline: {m['repo'] or '(no tracker repo)'} @ {m['default_ref']}  ({m['generated_at']})"]
    if not m["tracker"]["ok"]:
        out.append(f"  tracker unavailable: {m['tracker']['error']}")
    out.append("")

    def epic_line(n, indent):
        e = epics[n]
        prs = f"  PR {' '.join('#%d' % p for p in e['open_pulls'])}" if e["open_pulls"] else ""
        return (f"{indent}#{n} {e['state']:<6} {e['tasks']['closed']}/{e['tasks']['total']} tasks  "
                f"{MARK[e['status']]} {e['status']}{prs}  {e['title'][:60]}")

    if m.get("prds"):
        out.append("PRDs")
        for p in m["prds"]:
            st = p["state"]
            rnd = f"round {st['round']}/{st['round_cap']}, next {st['next']}" if st.get("round") else ""
            feeds = f" → {', '.join(p['roots'])}" if p["roots"] else (" · ready for planning" if p["ready_for_planning"] else "")
            out.append(f"  {p['slug']:<28} {p['stage']:<10} {rnd}{feeds}")
        out.append("")

    for r in m["roots"]:
        where = ("" if r["on_default_ref"] else f"  [in {r['repo']}]" if r["kind"] == "external"
                 else f"  [{', '.join(r['found_on']) or 'not found'}]")
        out.append(f"{r['slug']}  ({r['kind']}) {MARK.get(r['status'], '?')} {r['status']}{where}")
        if r["source"]:
            out.append(f"  source: {r['source']['text']}")
        if r.get("prds"):
            out.append(f"  from PRD: {', '.join(r['prds'])}")
        for p in r["phases"]:
            nxt = "  ⏭ next" if p["next"] else ""
            basis = " (declared)" if p["status_basis"] == "declared" else ""
            out.append(f"  phase {p['number']} {(p['title'] or '')[:44]:<44} {MARK[p['status']]} {p['status']}{basis}{nxt}")
            for n in p["epics"]:
                out.append(epic_line(n, "      "))
        for n in r["epics"]:
            out.append(epic_line(n, "    "))
        out.append("")

    loose = [e for e in m["epics"] if e["root"] is None]
    if loose:
        out.append("epics with no plan root")
        out += [epic_line(e["number"], "    ") for e in loose]
        out.append("")
    if m["unlinked_open_issues"]:
        nums = " ".join(f"#{i['number']}" for i in m["unlinked_open_issues"])
        out.append(f"open issues outside any epic ({len(m['unlinked_open_issues'])}): {nums}")
        out.append("")
    if m["findings"]:
        out.append(f"findings ({len(m['findings'])})")
        out += [f"  {f['severity']:<4} {f['code']}: {f['message']}" for f in m["findings"] if f["severity"] != "info"]
        info: dict[str, int] = {}
        for f in m["findings"]:
            if f["severity"] == "info":
                info[f["code"]] = info.get(f["code"], 0) + 1
        out += [f"  info {code} ×{n} (see JSON)" for code, n in info.items()]
    return "\n".join(out).rstrip() + "\n"


VIEWER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer.html")
PLACEHOLDER = "__PIPELINE_JSON__"


def render_html(m: dict, template: str) -> str:
    """viewer.html with the model embedded; `</` is escaped so data can't close the script tag."""
    data = json.dumps(m, ensure_ascii=False).replace("</", "<\\/")
    return template.replace(PLACEHOLDER, data, 1)


# ---------------------------------------------------------------- collect (adapters)

def _run(args: list[str], cwd: str) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout


def _default_ref(root: str) -> str:
    try:
        return _run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], root).strip()
    except subprocess.CalledProcessError:
        for ref in ("origin/main", "origin/master", "main", "master"):
            if subprocess.run(["git", "rev-parse", "-q", "--verify", ref], cwd=root, capture_output=True).returncode == 0:
                return ref
    return "HEAD"


def _ref_files(root: str, ref: str) -> list[str]:
    try:
        return _run(["git", "ls-tree", "-r", "--name-only", ref], root).splitlines()
    except subprocess.CalledProcessError:
        return []


def _worktree_files(root: str) -> list[str]:
    names = _run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], root).splitlines()
    return [n for n in names if os.path.isfile(os.path.join(root, n))]


def _roots_in(files: list[str]) -> dict[str, list[str]]:
    """Plan roots in a file listing -> {slug: files relative to the root}."""
    found: dict[str, list[str]] = {}
    for name in files:
        if not name.startswith(ROADMAP_DIR + "/"):
            continue
        slug, _, rest = name[len(ROADMAP_DIR) + 1:].partition("/")
        if rest in ("roadmap.md", "plan.md") or PHASE_FILE.match(rest):
            found.setdefault(slug, []).append(rest)
    return {s: fs for s, fs in found.items() if "roadmap.md" in fs or "plan.md" in fs}


def _bundles_in(files: list[str]) -> dict[str, list[str]]:
    """PPP bundles (ppp's rule: a folder holding medium.md and state.json) -> {dir: files we read}."""
    by_dir: dict[str, set[str]] = {}
    for name in files:
        d, _, base = name.rpartition("/")
        by_dir.setdefault(d, set()).add(base)
    found = {}
    for d, names in by_dir.items():
        if "medium.md" in names and "state.json" in names:
            found[d] = sorted(n for n in names if n in BUNDLE_FILES or n.endswith("-prd.md"))
    return found


def _github_repo(root: str) -> str | None:
    try:
        url = _run(["git", "remote", "get-url", "origin"], root).strip()
    except subprocess.CalledProcessError:
        return None
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def _capture_backend(root: str) -> str | None:
    try:
        with open(os.path.join(root, ".ffflow", "config.yaml")) as fh:
            m = re.search(r"(?m)^capture:\s*([\w-]+)", fh.read())
            return m.group(1) if m else "github-issues"
    except OSError:
        return None


def collect(root: str, repo: str | None, remote: str, worktree: bool, limit: int) -> dict:
    default_ref = _default_ref(root)
    refs = [default_ref]
    for ref in _run(["git", "for-each-ref", "--format=%(refname:short)", f"refs/remotes/{remote}"], root).split():
        if ref not in refs and not ref.endswith("/HEAD") and "/" in ref:
            refs.append(ref)

    listings = ([("worktree", _worktree_files(root))] if worktree else []) + [(r, _ref_files(root, r)) for r in refs]

    def gather(find, prefix):
        sources: dict[str, list[tuple[str, list[str]]]] = {}
        for where, files in listings:
            for key, rels in find(files).items():
                sources.setdefault(key, []).append((where, rels))
        out = {}
        for key, found in sources.items():
            # Content precedence: working tree, then the default ref, then the first branch.
            found.sort(key=lambda f: (f[0] != "worktree", f[0] != default_ref))
            where, rels = found[0]
            files = {}
            for rel in rels:
                path = f"{prefix(key)}/{rel}" if prefix(key) else rel
                if where == "worktree":
                    with open(os.path.join(root, path), encoding="utf-8") as fh:
                        files[rel] = fh.read()
                else:
                    files[rel] = _run(["git", "show", f"{where}:{path}"], root)
            out[key] = {"found_on": [f[0] for f in found], "files": files}
        return out

    plan_roots = gather(_roots_in, lambda slug: f"{ROADMAP_DIR}/{slug}")
    prd_bundles = gather(_bundles_in, lambda d: d)

    snap = {
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "root": root,
        "default_ref": default_ref,
        "refs_scanned": refs,
        "capture": _capture_backend(root) or "github-issues",
        "repo": repo or _github_repo(root),
        "plan_roots": plan_roots,
        "prd_bundles": prd_bundles,
        "issues": [],
        "pulls": [],
        "tracker_error": None,
    }
    if snap["capture"] != "github-issues":
        snap["tracker_error"] = f"capture backend {snap['capture']} is not supported yet; plan files only"
    elif not snap["repo"]:
        snap["tracker_error"] = "no GitHub repo (pass --repo owner/name)"
    else:
        try:
            snap["issues"] = json.loads(_run(
                ["gh", "issue", "list", "-R", snap["repo"], "--state", "all", "--limit", str(limit),
                 "--json", "number,title,state,labels,body,url"], root))
            snap["pulls"] = json.loads(_run(
                ["gh", "pr", "list", "-R", snap["repo"], "--state", "open", "--limit", "200",
                 "--json", "number,title,headRefName,body,url,isDraft"], root))
            for i in snap["issues"]:
                i["labels"] = [l["name"] for l in i["labels"]]
            if len(snap["issues"]) >= limit:
                snap["tracker_error"] = f"issue limit {limit} reached; raise --limit"
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            detail = getattr(exc, "stderr", "") or str(exc)
            snap["tracker_error"] = f"gh failed: {detail.strip()}"
    return snap


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", help="repository root (default: git toplevel of cwd)")
    ap.add_argument("--repo", help="GitHub owner/name (default: origin remote)")
    ap.add_argument("--remote", default="origin", help="remote whose branches are scanned for plan roots")
    ap.add_argument("--no-worktree", action="store_true", help="ignore uncommitted plan roots in the working tree")
    ap.add_argument("--limit", type=int, default=1000, help="max issues to fetch")
    ap.add_argument("--format", choices=("json", "text", "html"), default="json")
    ap.add_argument("--out", help="write the output here instead of stdout")
    ap.add_argument("--snapshot-in", help="build from a saved raw snapshot instead of collecting")
    ap.add_argument("--snapshot-out", help="also save the raw snapshot here")
    a = ap.parse_args(argv)

    if a.snapshot_in:
        with open(a.snapshot_in, encoding="utf-8") as fh:
            snap = json.load(fh)
    else:
        root = a.root or _run(["git", "rev-parse", "--show-toplevel"], os.getcwd()).strip()
        snap = collect(root, a.repo, a.remote, not a.no_worktree, a.limit)
    if a.snapshot_out:
        with open(a.snapshot_out, "w", encoding="utf-8") as fh:
            json.dump(snap, fh, indent=2)

    model = build(snap)
    if a.format == "json":
        text = json.dumps(model, indent=2, ensure_ascii=False) + "\n"
    elif a.format == "html":
        with open(VIEWER, encoding="utf-8") as fh:
            text = render_html(model, fh.read())
    else:
        text = render_text(model)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
