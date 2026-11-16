#!/usr/bin/env python3
"""Offline checks over a github-reconcile export. Reads files only: no network, no writes
except the report. Run as:  python3 -I check.py EXPORT_DIR [--policy FILE] [--previous REPORT]
                                              [--out REPORT]
                            python3 -I check.py fingerprint ISSUE_JSON_FILE
Exit: 0 nothing to act on (WAIVER rows are listed, never silent); 1 findings (FAIL/MISSING/OWNER); 2 usage, invalid policy or unsupported input (no conclusion); 3 export incomplete (no conclusion).
Informational notes (e.g. what the API does not expose) are printed and kept in the report; they never change the exit.
"""
import hashlib, json, os, re, sys

CLASSES = ("PASS", "FAIL", "RETAINED", "WAIVER", "MISSING", "OWNER")
BOX = re.compile(r"^\s*[-*]\s+\[( |x|X)\]\s+(.*)$")
REF = re.compile(r"#(\d+)")


class Unreadable(Exception):
    """An export file that exists but cannot be read or parsed: the export is incomplete (exit 3)."""


def load(d, name, default=None):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return default
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise Unreadable("%s (%s)" % (name, e.__class__.__name__))


def norm(o):
    """Canonical form: lists of objects that carry an `id` are sorted by it (link sets have no order)."""
    if isinstance(o, dict):
        return {k: norm(v) for k, v in o.items()}
    if isinstance(o, list):
        o = [norm(x) for x in o]
        if o and all(isinstance(x, dict) and "id" in x for x in o):
            o.sort(key=lambda x: str(x["id"]))
    return o


def fingerprint(o):
    """Stale-state hash: sha256 of the canonical JSON of the EXACT re-read target (see SKILL.md, apply mode)."""
    return hashlib.sha256(json.dumps(norm(o), sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def issue_fp(o):
    """What a single-object check read, for RETAINED only (not for stale-state detection)."""
    keep = {k: o.get(k) for k in ("updated_at", "state", "body", "title")}
    keep["labels"] = sorted((x["name"] if isinstance(x, dict) else x) for x in o.get("labels", []))
    keep["milestone"] = (o.get("milestone") or {}).get("title")
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:16]


class Report:
    def __init__(self, previous):
        self.rows, self.passes, self.notes = [], {}, []
        self.prev = (previous or {}).get("passes", {})

    def ok(self, check, obj, fp=None, local=False):
        if local and fp and self.prev.get(check, {}).get(obj) == fp:
            self.rows.append(dict(check=check, cls="RETAINED", object=obj, observed="unchanged since previous run", fp=fp))
        else:
            self.rows.append(dict(check=check, cls="PASS", object=obj, fp=fp))
        self.passes.setdefault(check, {})[obj] = fp

    def add(self, check, cls, obj, observed, evidence="", proposal="", change=None, fp=None):
        """A FAIL/MISSING/OWNER row stays what it is: no policy can turn it into a WAIVER or remove it.
        The only WAIVER rows come from a criterion's exception tag (C5), validated per criterion."""
        self.rows.append(dict(check=check, cls=cls, object=obj, observed=observed,
                              evidence=evidence, proposal=proposal, change=change, fp=fp))


def policy_problems(pol):
    """An invalid policy is rejected (exit 2), never silently ignored."""
    if not isinstance(pol, dict):
        return ["the policy must be a JSON object"]
    out = ["`waivers` is not supported: a waiver exists only as an exception tag on a criterion, "
           "validated against `exception_scopes`"] if "waivers" in pol else []

    def objs(v):
        return isinstance(v, list) and all(isinstance(x, dict) for x in v)

    def obj_of_objs(v):
        return isinstance(v, dict) and all(isinstance(x, dict) for x in v.values())

    def strs(v):
        return isinstance(v, list) and all(isinstance(x, str) for x in v)

    shapes = dict(  # the shape each check reads; a wrong shape is an invalid policy, never a traceback
        hierarchy=(strs, "a list of strings"), no_milestone_types=(strs, "a list of strings"),
        required_roles=(strs, "a list of strings"), builtin_fields=(strs, "a list of strings"),
        board_roles=(lambda v: obj_of_objs(v) and all(strs(x.get("options")) for x in v.values()),
                     'an object: role -> {"options": [option names]}'),
        status_map=(lambda v: isinstance(v, dict) and all(isinstance(x, str) for x in v.values()), "an object: meaning -> option name"),
        plan_edges=(lambda v: isinstance(v, list) and all(isinstance(e, list) and len(e) == 2 and all(type(x) is int for x in e) for e in v),
                    "a list of [blocked, blocker] issue-number pairs"),
        milestone_exits=(lambda v: obj_of_objs(v) and all(
            isinstance(x.get("require_closed", []), list) and all(type(n) is int for n in x.get("require_closed", []))
            and strs(x.get("require_labels_closed", [])) for x in v.values()),
            "an object: milestone title -> {require_closed: [issue numbers], require_labels_closed: [label names]}"),
        exception_scopes=(obj_of_objs, "an object: decision ID -> {prs, issues, waives}"),
        field_aliases=(lambda v: objs(v) and all(isinstance(x.get("old"), str) and isinstance(x.get("role"), str) for x in v),
                       'a list of {"old": name, "role": role}'),
        stale_text=(lambda v: objs(v) and all(isinstance(x.get("regex"), str) and isinstance(x.get("new"), str) for x in v),
                    'a list of {"regex", "new", "why"}'),
        owner_pending=(objs, "a list of {object, match, decision}"))
    for key, (ok, want) in shapes.items():
        if key in pol and not ok(pol[key]):
            out.append("`%s` must be %s" % (key, want))
    for key in ("proof_regex", "exception_regex"):
        if key in pol:
            try:
                rx = re.compile(pol[key])
                if key == "exception_regex" and rx.groups < 1:
                    out.append("`exception_regex` must capture the decision ID in its first group")
            except (re.error, TypeError):
                out.append("`%s` must be a valid regular expression" % key)
    for st in pol.get("stale_text", []) if objs(pol.get("stale_text", [])) else []:
        try:
            re.compile(st.get("regex") or "").sub(st.get("new") or "", "")  # also parses the replacement template
        except (re.error, TypeError, IndexError):
            out.append("`stale_text` holds an invalid regular expression or replacement")
    return out


def completeness(meta, ex):
    """Return reasons the export cannot support an 'absent' conclusion. Empty list = complete."""
    why = []
    if not meta:
        return ["meta.json missing"]
    if not meta.get("complete"):
        why.append("meta.complete is false")
    why += ["fetch error: %s" % e for e in meta.get("errors", [])]
    for key, got in ex.items():
        want = meta.get("expected", {}).get(key)
        if want is None:
            why.append("no expected count recorded for %s" % key)
        elif want != got:
            why.append("%s: expected %s, exported %s" % (key, want, got))
    return why


def find_cycle(edges):
    state, stack = {}, []

    def dfs(n):
        state[n] = 1
        stack.append(n)
        for m in edges.get(n, ()):
            if state.get(m) == 1:
                return stack[stack.index(m):] + [m]
            if state.get(m) is None:
                c = dfs(m)
                if c:
                    return c
        stack.pop()
        state[n] = 2
        return None

    for n in list(edges):
        if state.get(n) is None:
            c = dfs(n)
            if c:
                return c
    return None


def resolve_role(fields, role):
    """Resolve a board role to a field by option set, never by a remembered name."""
    want = {o.lower() for o in role.get("options", [])}
    hit = [f for f in fields if f.get("options") and {o["name"].lower() for o in f["options"]} == want]
    return hit[0] if len(hit) == 1 else None


FILES = ("meta", "issues", "pulls", "milestones", "labels", "sub_issues", "blocked_by", "closing", "project")


def run(d, pol, previous):
    data, why = {}, []
    for f in FILES:  # every export file is required: a missing file is never an empty collection
        data[f] = load(d, f + ".json")
        if data[f] is None:
            why.append("missing export file %s.json" % f)
    if why:
        return None, why
    meta, issues_all, pulls, milestones, labels = (data[k] for k in ("meta", "issues", "pulls", "milestones", "labels"))
    try:
        P = next(iter(next(iter(data["project"]["data"].values())).values()))
        items = P["items"]
        P["fields"]["nodes"], P["views"]["nodes"], items["nodes"]
    except (KeyError, StopIteration, TypeError, AttributeError):
        return None, ["project.json is malformed"]
    nums = {i["number"] for i in issues_all if "pull_request" not in i}
    why = completeness(meta, dict(issues=len(nums), pulls=len(pulls), labels=len(labels), milestones=len(milestones),
                                  project_items=len(items["nodes"])))
    if (items.get("pageInfo") or {}).get("hasNextPage"):
        why.append("project items: hasNextPage is true")
    for fname, key in (("sub_issues", "parent"), ("blocked_by", "issue")):  # explicit per-issue coverage
        miss = sorted(nums - {x[key] for x in data[fname]})
        if miss:
            why.append("%s.json has no entry for %s" % (fname, ["#%d" % m for m in miss]))
    miss = sorted({p["number"] for p in pulls} - {x["pr"] for x in data["closing"]})
    if miss:
        why.append("closing.json has no entry for PR %s" % ["#%d" % m for m in miss])
    noid = [it for it in items["nodes"] if it.get("type") in ("ISSUE", "PULL_REQUEST")
            and not ((it.get("content") or {}).get("repository") or {}).get("nameWithOwner")]
    if noid:
        why.append("%d board item(s) without repository identity: re-export with the repository in the query" % len(noid))
    if why:
        return None, why

    R = Report(previous)
    issues = {i["number"]: i for i in issues_all if "pull_request" not in i}
    prs = {p["number"]: p for p in pulls}
    prefix = pol.get("type_label_prefix", "type:")
    hier = pol.get("hierarchy", [])
    top_types = set(pol.get("no_milestone_types", []))
    children = {x["parent"]: set(x["children"]) for x in data["sub_issues"]}
    parent_of = {c: p for p, cs in children.items() for c in cs}
    blocked_by = {x["issue"]: set(x["blocked_by"]) for x in data["blocked_by"]}
    closes = {x["pr"]: set(x["closes"]) for x in data["closing"]}
    lab = lambda i: [x["name"] for x in i.get("labels", [])]
    typ = lambda i: [l[len(prefix):] for l in lab(i) if l.startswith(prefix)]
    name = lambda n: "#%d" % n
    roles = pol.get("board_roles", {})
    smap = pol.get("status_map", {})
    blabel = pol.get("blocked_label", "status:blocked")

    # Board items are keyed by repository + content type + number; nothing is silently overwritten.
    repo_l = (meta.get("repo") or "").lower()
    by_issue, board_rows, cnt = {}, [], {}
    for it in items["nodes"]:
        c, ty = it.get("content") or {}, it.get("type")
        rp = ((c.get("repository") or {}).get("nameWithOwner") or "").lower()
        num, tag_ = c.get("number"), "%s %s#%s" % (ty, rp, c.get("number"))
        kind = "draft" if ty == "DRAFT_ISSUE" else "archived" if it.get("isArchived") else \
            "other-repo" if rp != repo_l else "pull request" if ty == "PULL_REQUEST" else "issue" if ty == "ISSUE" else "other"
        if kind == "issue" and num in by_issue:
            kind = "duplicate"
        cnt[kind] = cnt.get(kind, 0) + 1
        if kind == "issue":
            by_issue[num] = {v["field"]["name"]: v.get("name") or v.get("text") for v in it["fieldValues"]["nodes"] if v.get("field")}
        elif kind in ("archived", "other-repo", "duplicate", "other"):
            board_rows.append(("OWNER" if kind != "duplicate" else "FAIL", tag_, "board item is %s; it does not count as membership" % kind,
                               "decide: unarchive, remove, or keep it as it is"))
    R.notes.append("board items: " + ", ".join("%s %d" % (k, v) for k, v in sorted(cnt.items())))

    # C1 coverage (object-local)
    for n, i in sorted(issues.items()):
        t, fp, bad = typ(i), issue_fp(i), []
        if len(t) != 1:
            bad.append("type labels: %s" % (t or "none"))
        if t and t[0] not in top_types and not i.get("milestone"):
            bad.append("no milestone")
        if t and hier and t[0] != hier[0] and n not in parent_of:
            bad.append("no native parent")
        if bad:
            R.add("C1-coverage", "FAIL", name(n), "; ".join(bad), "labels/milestone/sub_issues export",
                  "set the missing field after confirming the intended value in the plan", fp=fp)
        else:
            R.ok("C1-coverage", name(n), "%s:%s" % (fp, parent_of.get(n)), local=True)

    # C2 checklist <-> native sub-issues
    for n, i in sorted(issues.items()):
        listed = set()
        for line in (i.get("body") or "").splitlines():
            m = BOX.match(line)
            if m and REF.search(m.group(2)) and m.group(2).lstrip().startswith("#"):
                listed.add(int(REF.search(m.group(2)).group(1)))
        native = children.get(n, set())
        if not listed and not native:
            continue
        if listed != native:
            R.add("C2-checklist", "FAIL", name(n),
                  "checklist-only %s; native-only %s" % (sorted(listed - native), sorted(native - listed)),
                  "body checklist vs sub_issues.json", "align the body list or the native links with the plan")
        else:
            R.ok("C2-checklist", name(n))

    # C3 dependency edges
    for n, bs in sorted(blocked_by.items()):
        for b in bs:
            if b == n:
                R.add("C3-dependencies", "FAIL", name(n), "self-link", "blocked_by.json", "remove the edge")
            elif b not in issues:
                R.add("C3-dependencies", "FAIL", name(n), "blocked by unknown %s" % name(b), "blocked_by.json", "remove or fix")
    cyc = find_cycle({k: {x for x in v if x != k} for k, v in blocked_by.items()})
    R.add("C3-dependencies", "FAIL", "graph", "cycle %s" % " -> ".join(map(name, cyc)), "blocked_by.json", "break the cycle") if cyc else R.ok("C3-dependencies", "graph")
    for blocked, blocker in pol.get("plan_edges", []):
        if blocker not in blocked_by.get(blocked, set()):
            R.add("C3-dependencies", "FAIL", name(blocked), "plan edge on %s missing" % name(blocker),
                  "policy.plan_edges vs blocked_by.json", "add the native dependency",
                  change=dict(op="add_blocked_by", issue=blocked, blocker=blocker))
    planned = {tuple(e) for e in pol.get("plan_edges", [])}
    if planned and pol.get("plan_edges_exhaustive"):
        for n, bs in blocked_by.items():
            for b in bs:
                if (n, b) not in planned:
                    R.add("C3-dependencies", "OWNER", name(n), "edge on %s is not in the plan" % name(b),
                          "blocked_by.json vs policy.plan_edges", "decide: add it to the plan or remove it")

    # C4 status vs state vs PR vs blockers
    status_f = resolve_role(P["fields"]["nodes"], roles["status"]) if "status" in roles else None
    open_pr_for = {}
    for pn, p in prs.items():
        if p["state"] == "open":
            for c in closes.get(pn, ()):
                open_pr_for.setdefault(c, []).append(pn)
    if not (status_f and smap):
        R.add("C4-status", "MISSING", "board", "status role or status_map not resolved", "policy.board_roles/status_map",
              "name the Status options and their meanings in the policy; no status conclusion was drawn")
    else:
        S = status_f["name"]
        have = {k for k in ("done", "blocked", "ready", "in_progress", "in_review") if smap.get(k)}
        for k in ("done", "blocked", "ready", "in_progress", "in_review"):
            if k not in have:
                R.add("C4-status", "MISSING", "status_map:" + k, "meaning %r not given" % k, "policy.status_map",
                      "name the Status option for it; the clauses that need it were skipped")
        for n, i in sorted(issues.items()):
            st = by_issue.get(n, {}).get(S)
            if st is None:
                continue  # absence on the board is C7's finding
            open_blockers = [b for b in blocked_by.get(n, ()) if b in issues and issues[b]["state"] == "open"]
            bad = []
            if "done" in have and i["state"] == "closed" and st != smap["done"]:
                bad.append("closed but Status=%s" % st)
            if "done" in have and i["state"] == "open" and st == smap["done"]:
                bad.append("open but Status=Done")
            if "blocked" in have and st == smap["blocked"] and not open_blockers and blabel not in lab(i):
                bad.append("Status=blocked with no open blocker and no blocked label")
            if i["state"] == "open" and open_blockers and st in (smap.get("ready"), smap.get("in_progress")):
                bad.append("Status=%s with open blockers %s" % (st, [name(b) for b in open_blockers]))
            if "blocked" in have and (blabel in lab(i)) != (st == smap["blocked"]):
                bad.append("blocked label and Status disagree")
            if "in_review" in have and n in open_pr_for and st != smap["in_review"]:
                bad.append("open PR %s but Status=%s" % (open_pr_for[n], st))
            if bad:
                R.add("C4-status", "FAIL", name(n), "; ".join(bad), "issues/pulls/blocked_by/project exports",
                      "set the Status the state implies, or record why not")
            elif len(have) == 5:  # with a meaning missing the check ran only in part: FAIL rows stand, but no PASS is claimed
                R.ok("C4-status", name(n))

    # C5 closure criteria (object-local). A waived criterion stays UNTICKED with its text and an exception tag
    # naming a decision; the decision's scope names the PRs/issues AND (`waives`) what it waives.
    # An owner-pending criterion (policy.owner_pending, with the stated open decision) is OWNER, otherwise FAIL.
    proof = re.compile(pol.get("proof_regex", r"proof:"), re.I)
    tag = re.compile(pol.get("exception_regex", r"accepted exception:.*?\b(D-\d+)\b"), re.I)
    scopes = pol.get("exception_scopes", {})
    pend = []
    for k, e in enumerate(pol.get("owner_pending", [])):
        if all(isinstance(e.get(x), str) and e[x].strip() for x in ("object", "match", "decision")):
            pend.append(e)
        else:
            R.add("POLICY", "FAIL", "owner_pending[%d]" % k, "entry needs object, match and the stated open decision", "policy.owner_pending", "complete or remove it")
    closing_prs = {}
    for pn, cs in closes.items():
        for c in cs:
            closing_prs.setdefault(c, set()).add(pn)
    for n, i in sorted(issues.items()):
        fp, bad, waived = issue_fp(i), [], []  # `bad`: one entry = one finding (one criterion or one issue-level defect)
        boxes = [BOX.match(l) for l in (i.get("body") or "").splitlines()]
        boxes = [(m.group(1) != " ", m.group(2)) for m in boxes if m]
        pending = 0
        for t, txt in boxes:
            tg = tag.search(txt)
            if tg and t:
                bad.append("waived criterion is ticked (it must stay unticked): %s" % txt[:50])
            elif tg:
                waived.append((tg.group(1), txt))
            elif not t:
                e = next((e for e in pend if e["object"] == name(n) and e["match"].lower() in txt.lower()), None)
                if e and i["state"] == "closed":
                    pending += 1
                    R.add("C5-closure", "OWNER", name(n), "criterion unticked: %s; open decision: %s" % (txt[:60], e["decision"]),
                          "policy.owner_pending", "the owner decides; do not tick or reclassify without that decision")
                elif i["state"] == "closed":
                    bad.append("closed with an unticked criterion and no exception tag: %s" % txt[:60])
            elif not proof.search(txt):
                bad.append("ticked without proof: %s" % txt[:60])
        if i["state"] == "closed":
            if i.get("state_reason") == "not_planned":
                R.add("C5-closure", "OWNER", name(n), "closed as not planned", "state_reason", "confirm the owner meant to drop it")
                pending += 1  # an OWNER row: this object is not a PASS for this check
            kids = [c for c in children.get(n, ()) if c in issues and issues[c]["state"] == "open"]
            if kids:
                bad.append("closed parent with open children %s" % [name(c) for c in kids])
            for dec, txt in waived:  # each tagged criterion is validated on its own and yields its own row
                low, sc, prs_ = txt.lower(), scopes.get(dec) or {}, closing_prs.get(n, set())
                crit = re.split(r"\(accepted exception", txt, flags=re.I)[0].strip()
                what = crit.lower()
                lists_ok = all(isinstance(sc.get(k, []), list) and all(isinstance(x, int) for x in sc.get(k, [])) for k in ("prs", "issues"))
                if "not run" not in low or "not a pass" not in low:
                    bad.append("waiver tag for %s must say NOT RUN and not a pass: %s" % (dec, crit[:50]))
                elif not sc:
                    R.add("C5-closure", "MISSING", name(n), "scope of %s not given; waiver not evaluated: %s" % (dec, crit[:50]), "policy.exception_scopes",
                          "state which PRs/issues the decision row names and what it waives")
                elif not lists_ok or not (sc.get("prs") or sc.get("issues")) or not (isinstance(sc.get("waives"), str) and sc["waives"].strip()):
                    R.add("C5-closure", "MISSING", name(n), "scope of %s is malformed (needs integer lists in prs/issues, non-empty, and a `waives` text): %s" % (dec, crit[:50]),
                          "policy.exception_scopes", "fix the scope")
                elif sc["waives"].lower() not in what:
                    bad.append("%s waives %r, which this criterion is not about: %s" % (dec, sc["waives"], crit[:50]))
                elif not (prs_ <= set(sc.get("prs", [])) if prs_ else n in sc.get("issues", [])):
                    out = sorted(prs_ - set(sc.get("prs", [])))
                    bad.append("%s does not cover %s: a waiver never transfers to another PR: %s" % (dec, ("PR " + ", ".join(map(name, out))) if out else name(n), crit[:50]))
                else:
                    R.rows.append(dict(check="C5-closure", cls="WAIVER", object=name(n), fp=fp, evidence="decision %s" % dec,
                                       observed="criterion waived by the owner (%s): %s \u2014 NOT RUN, not a pass" % (dec, crit[:60])))
        for x in bad:
            R.add("C5-closure", "FAIL", name(n), x, "body / sub_issues export",
                  "reopen, tick with proof, or tag the exception per the repository's close rule", fp=fp)
        if not bad and not waived and not pending:
            R.ok("C5-closure", name(n), fp, local=True)

    # C6 milestone exit conditions. A milestone is proposed for closing only if every member is closed AND a
    # non-empty exit that names known issues/labels is met; an absent or empty exit is MISSING.
    exits = pol.get("milestone_exits", {})
    known_labels = {x["name"] for x in labels}
    for m in milestones:
        t = m["title"]
        mine = [i for i in issues.values() if (i.get("milestone") or {}).get("title") == t]
        open_n = [i["number"] for i in mine if i["state"] == "open"]
        failed = m["state"] == "closed" and bool(open_n)
        if failed:
            R.add("C6-milestone", "FAIL", "milestone:" + t, "closed with open issues %s" % [name(x) for x in open_n], "milestones/issues", "reopen or move")
        ex = exits.get(t) or {}
        reqc, reql = ex.get("require_closed", []), ex.get("require_labels_closed", [])
        if not (reqc or reql):
            R.add("C6-milestone", "MISSING", "milestone:" + t,
                  "no machine-checkable exit given (closed=%d, open=%d)" % (len(mine) - len(open_n), len(open_n)),
                  "policy.milestone_exits", "state the exit as issue numbers or labels; the description is: %r" % (m.get("description") or "")[:80])
            continue
        unknown = [name(n) for n in reqc if n not in issues] + [l for l in reql if l not in known_labels]
        if unknown:
            R.add("C6-milestone", "MISSING", "milestone:" + t, "exit names unknown objects %s" % unknown, "policy.milestone_exits", "fix the exit")
            continue
        need = [n for n in reqc if issues[n]["state"] != "closed"]
        need += [i["number"] for i in mine if set(reql) & set(lab(i)) and i["state"] != "closed"]
        if need and m["state"] == "closed":
            R.add("C6-milestone", "FAIL", "milestone:" + t, "closed but exit not met: %s" % [name(x) for x in sorted(set(need))], "policy.milestone_exits", "reopen the milestone")
        elif need or open_n or not mine:
            if not failed:
                R.ok("C6-milestone", "milestone:" + t)  # not yet met / members still open / no members: nothing to propose
        elif m["state"] == "open":
            R.add("C6-milestone", "FAIL", "milestone:" + t, "every member closed and exit met, but milestone open", "milestones", "close the milestone",
                  change=dict(op="close_milestone", number=m["number"]))
        else:
            R.ok("C6-milestone", "milestone:" + t)

    # C7 board
    flds = {f["name"] for f in P["fields"]["nodes"]}
    readme = P.get("readme") or ""
    R.ok("C7-board", "readme") if readme.strip() else R.add("C7-board", "FAIL", "readme", "empty", "project.readme", "write it")
    for f in sorted(flds):
        if f not in readme and f not in pol.get("builtin_fields", []):
            R.add("C7-board", "FAIL", "readme", "field %r is not mentioned in the README" % f, "project.readme vs fields", "update the README text")
    for role, spec in roles.items():
        if not resolve_role(P["fields"]["nodes"], spec):
            R.add("C7-board", "FAIL", "role:" + role, "no single-select field has exactly options %s" % spec["options"], "project.fields", "fix field or policy")
    for r in pol.get("required_roles", []):
        if r not in roles:
            R.add("C7-board", "MISSING", "role:" + r, "required role has no board_roles definition", "policy.required_roles/board_roles",
                  "define the role's options or remove it; the required-field check did not cover it")
    req = [resolve_role(P["fields"]["nodes"], roles[r]) for r in pol.get("required_roles", []) if r in roles]
    for n in sorted(issues):
        if n not in by_issue:
            R.add("C7-board", "FAIL", name(n), "no project item", "project.items", "add it to the board", change=dict(op="add_to_project", issue=n))
            continue
        miss = [f["name"] for f in req if f and not by_issue[n].get(f["name"])]
        if miss:
            R.add("C7-board", "FAIL", name(n), "empty fields %s" % miss, "project.items", "set from labels/title per the plan")
    for cls, obj, obs, prop in board_rows:
        R.add("C7-board", cls, obj, obs, "project.items", prop)
    for v in P["views"]["nodes"]:
        R.ok("C7-board", "view:" + v["name"]) if v.get("fields", {}).get("nodes") else R.add("C7-board", "FAIL", "view:" + v["name"], "no visible fields", "project.views", "fix view")
    R.notes.append("not exposed by the API, so not checked: built-in project workflows, charts, view sort direction, column order or widths; "
                   "grouping is only partly readable. Check these in the browser.")

    # C8 text and metadata hygiene
    if pol.get("milestones_on_issues_only"):
        for i in sorted((x for x in issues_all if "pull_request" in x), key=lambda x: x["number"]):
            if i.get("milestone"):
                R.add("C8-hygiene", "FAIL", "PR" + name(i["number"]), "pull request carries milestone %r; this distorts the milestone's closed count" % i["milestone"]["title"],
                      "issues.json", "clear the milestone on the pull request", change=dict(op="clear_milestone", number=i["number"]))
    for al in pol.get("field_aliases", []):  # names the plan once used for a board field -> the live name, by role
        f = resolve_role(P["fields"]["nodes"], roles[al["role"]]) if al["role"] in roles else None
        if not f:
            R.add("C8-hygiene", "MISSING", "alias:" + al["old"], "role %s not resolvable; field-name drift not checked" % al["role"], "policy.field_aliases", "fix policy or board")
            continue
        live, rx = f["name"], re.compile(r"\b%s\b" % re.escape(al["old"]))
        for n, i in sorted(issues.items()):
            for line in (i.get("body") or "").splitlines():
                segs = line.split(live) if live != al["old"] else [line]  # the live name is protected: the fix is idempotent
                outside = "".join(segs)
                if live != al["old"] and (("`%s`" % al["old"]) in outside or (rx.search(outside) and "board" in line.lower())):
                    new = live.join(rx.sub(live, x) for x in segs)
                    if new != line:
                        R.add("C8-hygiene", "FAIL", name(n), "uses the old field name %r; the live name is %r" % (al["old"], live), "issue body",
                              "replace it in this line", change=dict(op="edit_body_line", issue=n, old=line, new=new))
    for st in pol.get("stale_text", []):  # exact old->new lines for text that is wrong now (not history written before a merge)
        rx = re.compile(st["regex"])
        for n, i in sorted(issues.items()):
            for line in (i.get("body") or "").splitlines():
                if rx.search(line) and rx.sub(st["new"], line) != line:
                    R.add("C8-hygiene", "FAIL", name(n), "stale text: %s" % st.get("why", ""), "issue body",
                          "old -> new line", change=dict(op="edit_body_line", issue=n, old=line, new=rx.sub(st["new"], line)))
    return R, []


def main(argv):
    def read(path, what):  # an unreadable input file is a usage error (exit 2), never "findings"
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f), None
        except (OSError, ValueError) as e:
            return None, "cannot read %s %s (%s)" % (what, path, e.__class__.__name__)

    if len(argv) >= 2 and argv[1] == "fingerprint":
        if len(argv) != 3:
            print(__doc__)
            return 2
        obj, err = read(argv[2], "file")
        if err:
            print("usage:", err)
            return 2
        print(fingerprint(obj))
        return 0
    if len(argv) < 2 or argv[1].startswith("--"):
        print(__doc__)
        return 2
    d, rest, opts = argv[1], argv[2:], {}
    while rest:  # only the documented flags, each with a value; nothing is silently ignored
        flag = rest.pop(0)
        if flag not in ("--policy", "--previous", "--out") or not rest or flag in opts:
            print("usage: unknown, repeated or valueless option %r" % flag)
            return 2
        opts[flag] = rest.pop(0)
    pol, prev = {}, None
    if "--policy" in opts:
        pol, err = read(opts["--policy"], "policy")
        if err:
            print("invalid policy:", err)
            return 2
    if "--previous" in opts:
        prev, err = read(opts["--previous"], "previous report")
        ps = prev.get("passes", {}) if isinstance(prev, dict) else None
        if err or not (isinstance(ps, dict) and all(isinstance(v, dict) for v in ps.values())):
            print("usage:", err or "the previous report must be a JSON object whose `passes` maps check -> {object: fingerprint}")
            return 2
    probs = policy_problems(pol)
    if probs:
        print("invalid policy:", *probs, sep="\n  - ")
        return 2
    try:
        R, why = run(d, pol, prev)
    except Unreadable as e:
        R, why = None, ["unreadable export file %s" % e]
    except Exception as e:  # noqa: BLE001 - backstop: a crash must never exit 1 ("findings") or draw a conclusion
        print("no conclusion drawn: the checks stopped on an input shape they do not support (%s: %s)" % (e.__class__.__name__, str(e)[:120]))
        return 2
    if why:
        print("INCOMPLETE export: no conclusion drawn (nothing is reported as absent or passing):")
        for w in why:
            print("  -", w)
        return 3
    if "--out" in opts:
        with open(opts["--out"], "w", encoding="utf-8") as f:
            json.dump(dict(rows=R.rows, passes=R.passes, notes=R.notes), f, indent=1)
    tally = {c: sum(1 for r in R.rows if r["cls"] == c) for c in CLASSES}
    for r in R.rows:
        if r["cls"] not in ("PASS", "RETAINED"):
            print("%s | %s | %s | %s | %s | %s" % (r["check"], r["object"], r["cls"], r["observed"], r.get("evidence", ""), r.get("proposal", "")))
    for n in R.notes:
        print("note:", n)
    print("tally:", tally, "(WAIVER and RETAINED are not PASS)")
    waived = [r for r in R.rows if r["cls"] == "WAIVER"]
    print("accepted exceptions (not passes): %d" % len(waived))
    for r in waived:
        print("  -", r["object"], r["observed"])
    act = any(tally[c] for c in ("FAIL", "MISSING", "OWNER"))
    print("summary:", "findings to act on" if act else "nothing to act on; %d accepted exception(s), not passes" % len(waived))
    return 1 if act else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
