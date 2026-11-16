"""Synthetic-fixture tests for scripts/check.py. No network, no real repository data.
Run:  python3 -I -W error -m unittest discover -s <skill>/tests   (from outside the skill directory)
"""
import copy, json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import check  # noqa: E402

REPO = "o/r"


def issue(n, state="open", labels=(), ms="M1", body="", reason=None):
    return dict(number=n, state=state, state_reason=reason, title="t%d" % n, body=body, updated_at="2026-01-01T00:00:00Z",
                labels=[dict(name=x) for x in labels], milestone=dict(title=ms) if ms else None)


def item(n, ty="ISSUE", repo=REPO, archived=False, **vals):
    fv = [dict(field=dict(name=k), name=v) for k, v in vals.items()]
    return dict(type=ty, isArchived=archived, content=dict(number=n, repository=dict(nameWithOwner=repo)), fieldValues=dict(nodes=fv))


def links(sub=None, blk=None, nums=(1, 2, 3)):
    """Per-issue entries for every issue, as inventory.sh writes them."""
    sub, blk = sub or {1: [2], 2: [3]}, blk or {}
    return ([dict(parent=n, children=sub.get(n, [])) for n in nums], [dict(issue=n, blocked_by=blk.get(n, [])) for n in nums])


def base():
    issues = [issue(1, labels=["type:umbrella"], ms=None, body="- [ ] #2 child"),
              issue(2, labels=["type:epic"], body="- [ ] #3 child"),
              issue(3, labels=["type:sub-issue"], body="- [ ] do it")]
    P = dict(readme="Fields: Status, Kind", fields=dict(nodes=[
        dict(name="Status", options=[dict(name="Todo"), dict(name="Doing"), dict(name="Done"), dict(name="Stuck")]),
        dict(name="Kind", options=[dict(name="Umbrella"), dict(name="Epic"), dict(name="Sub-issue")])]),
        views=dict(nodes=[dict(name="V", fields=dict(nodes=[dict(name="Title")]))]),
        items=dict(pageInfo=dict(hasNextPage=False), nodes=[
            item(1, Status="Doing", Kind="Umbrella"), item(2, Status="Doing", Kind="Epic"), item(3, Status="Todo", Kind="Sub-issue")]))
    sub, blk = links()
    return dict(
        meta=dict(repo=REPO, complete=True, errors=[], expected=dict(issues=3, pulls=0, labels=2, milestones=1, project_items=3)),
        issues=issues, pulls=[], labels=[dict(name="type:epic"), dict(name="gate:x")],
        milestones=[dict(title="M1", number=1, state="open", description="exit text")],
        sub_issues=sub, blocked_by=blk, closing=[], project=dict(data=dict(user=dict(p=P))))


def board(fx):
    return next(iter(fx["project"]["data"]["user"].values()))


POLICY = dict(hierarchy=["umbrella", "epic", "sub-issue"], no_milestone_types=["umbrella"],
              board_roles=dict(status=dict(options=["Todo", "Doing", "Done", "Stuck"]),
                               kind=dict(options=["Umbrella", "Epic", "Sub-issue"])),
              required_roles=["kind"], status_map=dict(done="Done", blocked="Stuck", ready="Todo", in_progress="Doing", in_review="Doing"),
              milestone_exits={"M1": dict(require_closed=[3])})


def write(d, fx, skip=()):
    for k, v in fx.items():
        if k not in skip:
            with open(os.path.join(d, k + ".json"), "w") as f:
                json.dump(v, f)


def run(fx, pol=POLICY, prev=None, skip=()):
    with tempfile.TemporaryDirectory() as d:
        write(d, fx, skip)
        R, why = check.run(d, pol, prev)
    return R, why


def classes(R, check_id):
    return sorted((r["object"], r["cls"]) for r in R.rows if r["check"] == check_id and r["cls"] != "PASS")


def changes(R):
    return [r["change"] for r in R.rows if r.get("change")]


def apply_edits(fx, chs):
    """Apply edit_body_line changes to a fixture, as apply mode would."""
    for c in chs:
        if c["op"] == "edit_body_line":
            for i in fx["issues"]:
                if i["number"] == c["issue"]:
                    i["body"] = i["body"].replace(c["old"], c["new"])
    return fx


class Completeness(unittest.TestCase):
    def test_clean_state_has_no_fail(self):
        R, why = run(base())
        self.assertEqual(why, [])
        self.assertEqual([(r["check"], r["object"], r["cls"]) for r in R.rows if r["cls"] in ("FAIL", "OWNER", "MISSING")], [])

    def test_truncated_export_draws_no_conclusion(self):
        fx = base()
        fx["issues"] = fx["issues"][:2]
        R, why = run(fx)
        self.assertIsNone(R)
        self.assertTrue(any("issues: expected 3, exported 2" in w for w in why))

    def test_failed_fetch_and_next_page_refuse(self):
        fx = base()
        fx["meta"]["errors"] = ["sub_issues for #2: HTTP 502"]
        self.assertTrue(run(fx)[1])
        fx = base()
        board(fx)["items"]["pageInfo"]["hasNextPage"] = True
        self.assertTrue(any("hasNextPage" in w for w in run(fx)[1]))

    def test_every_export_file_is_required(self):  # B2
        for f in check.FILES:
            R, why = run(base(), skip=(f,))
            self.assertIsNone(R, f)
            self.assertIn("missing export file %s.json" % f, why)

    def test_per_issue_coverage_of_links_and_closing(self):  # B2
        fx = base()
        fx["blocked_by"] = fx["blocked_by"][:2]
        self.assertTrue(any("blocked_by.json has no entry for ['#3']" in w for w in run(fx)[1]))
        fx = base()
        fx["sub_issues"] = fx["sub_issues"][1:]
        self.assertTrue(any("sub_issues.json has no entry" in w for w in run(fx)[1]))
        fx = base()
        fx["pulls"] = [dict(number=9, state="open")]
        fx["meta"]["expected"]["pulls"] = 1
        self.assertTrue(any("closing.json has no entry for PR ['#9']" in w for w in run(fx)[1]))

    def test_board_item_without_repository_identity_is_incomplete(self):  # B8
        fx = base()
        del board(fx)["items"]["nodes"][0]["content"]["repository"]
        self.assertTrue(any("without repository identity" in w for w in run(fx)[1]))


class Relationships(unittest.TestCase):
    def test_checklist_vs_native(self):
        fx = base()
        fx["sub_issues"], _ = links(sub={1: [2]})  # native link 2->3 missing
        R, _ = run(fx)
        self.assertIn(("#2", "FAIL"), classes(R, "C2-checklist"))
        self.assertIn(("#3", "FAIL"), classes(R, "C1-coverage"))

    def test_dependency_self_cycle_and_plan_edge(self):
        fx = base()
        _, fx["blocked_by"] = links(blk={2: [2], 3: [1], 1: [3]})
        R, _ = run(fx, dict(POLICY, plan_edges=[[3, 2]]))
        msgs = [r["observed"] for r in R.rows if r["check"] == "C3-dependencies"]
        self.assertTrue(any("self-link" in m for m in msgs))
        self.assertTrue(any(m.startswith("cycle") for m in msgs))
        self.assertTrue(any("plan edge on #2 missing" in m for m in msgs))

    def test_status_vs_state_vs_blockers(self):
        fx = base()
        fx["issues"][2]["state"] = "closed"
        _, fx["blocked_by"] = links(blk={2: [3]})
        R, _ = run(fx)
        self.assertIn(("#3", "FAIL"), classes(R, "C4-status"))
        self.assertIn(("#3", "FAIL"), classes(R, "C5-closure"))

    def test_status_role_unresolved_is_missing_not_pass(self):
        R, _ = run(base(), dict(POLICY, status_map={}))
        self.assertIn(("board", "MISSING"), classes(R, "C4-status"))

    def test_absent_status_meaning_is_missing_and_raises_no_false_fail(self):
        fx = base()
        fx["issues"][2]["state"] = "closed"  # closed, board says Todo: a FAIL only if `done` is defined
        smap = {k: v for k, v in POLICY["status_map"].items() if k != "done"}
        R, _ = run(fx, dict(POLICY, status_map=smap))
        got = classes(R, "C4-status")
        self.assertIn(("status_map:done", "MISSING"), got)
        self.assertNotIn(("#3", "FAIL"), got)
        self.assertFalse([c for c in got if c[1] == "PASS"])  # a partly run check claims no PASS
        self.assertNotIn("#3", R.passes.get("C4-status", {}))
        R2, _ = run(fx)  # control: with `done` defined the same state is a FAIL
        self.assertIn(("#3", "FAIL"), classes(R2, "C4-status"))


class Milestones(unittest.TestCase):
    def test_closed_while_exit_unmet_fails(self):
        fx = base()
        fx["milestones"][0]["state"] = "closed"
        R, _ = run(fx)
        self.assertIn(("milestone:M1", "FAIL"), classes(R, "C6-milestone"))

    def test_closed_with_open_member_but_exit_list_met_is_fail_and_never_also_pass(self):
        fx = base()
        fx["milestones"][0]["state"] = "closed"
        fx["issues"][2]["state"] = "closed"  # the exit's issue (#3) is closed; member #2 is still open
        fx["issues"][2]["body"] = "- [x] do it *(proof: PR #9)*"
        board(fx)["items"]["nodes"][2] = item(3, Status="Done", Kind="Sub-issue")
        R, _ = run(fx)
        got = classes(R, "C6-milestone")
        self.assertIn(("milestone:M1", "FAIL"), got)
        self.assertNotIn(("milestone:M1", "PASS"), got)
        self.assertNotIn("milestone:M1", R.passes.get("C6-milestone", {}))

    def test_absent_or_empty_exit_is_missing_and_never_closes(self):  # B5
        for pol in (dict(POLICY, milestone_exits={}), dict(POLICY, milestone_exits={"M1": {}}),
                    dict(POLICY, milestone_exits={"M1": dict(require_closed=[], require_labels_closed=[])})):
            fx = base()
            for i in fx["issues"]:
                i["state"] = "closed"
            R, _ = run(fx, pol)
            self.assertIn(("milestone:M1", "MISSING"), classes(R, "C6-milestone"))
            self.assertEqual([c for c in changes(R) if c["op"] == "close_milestone"], [])

    def test_exit_naming_unknown_objects_is_missing(self):
        R, _ = run(base(), dict(POLICY, milestone_exits={"M1": dict(require_closed=[99])}))
        self.assertIn(("milestone:M1", "MISSING"), classes(R, "C6-milestone"))

    def test_member_still_open_blocks_the_close_proposal(self):
        fx = base()
        fx["issues"][2]["state"] = "closed"  # the exit (#3 closed) is met, but #2 is an open member
        R, _ = run(fx)
        self.assertEqual([c for c in changes(R) if c["op"] == "close_milestone"], [])

    def test_all_members_closed_and_valid_exit_proposes_close(self):
        fx = base()
        for i in fx["issues"]:
            i["state"] = "closed"
        R, _ = run(fx)
        self.assertEqual([c["op"] for c in changes(R) if c["op"] == "close_milestone"], ["close_milestone"])


class NotPlanned(unittest.TestCase):
    def test_closed_as_not_planned_is_owner_and_never_also_pass(self):
        fx = base()
        fx["issues"][2] = issue(3, state="closed", labels=["type:sub-issue"], body="- [x] do it *(proof: PR #9)*", reason="not_planned")
        board(fx)["items"]["nodes"][2] = item(3, Status="Done", Kind="Sub-issue")
        R, _ = run(fx)
        got = classes(R, "C5-closure")
        self.assertIn(("#3", "OWNER"), got)
        self.assertNotIn(("#3", "PASS"), got)
        self.assertNotIn("#3", R.passes.get("C5-closure", {}))  # so a later run cannot report it RETAINED


class Waivers(unittest.TestCase):
    TAG = " *(accepted exception: scan waived by owner, D-12 — NOT RUN, not a pass)*"
    pol = dict(POLICY, exception_scopes={"D-12": dict(prs=[10], waives="scan")})

    def closed3(self, body, prs=(10,)):
        fx = base()
        fx["issues"][2].update(state="closed", body=body)
        fx["closing"] = [dict(pr=p, closes=[3]) for p in prs]
        fx["pulls"] = [dict(number=p, state="closed") for p in prs]
        fx["meta"]["expected"]["pulls"] = len(prs)
        return fx

    def c5(self, fx, pol=None):
        R, why = run(fx, pol or self.pol)
        self.assertEqual(why, [])
        return [(r["cls"], r["observed"]) for r in R.rows if r["check"] == "C5-closure" and r["object"] == "#3"]

    def test_tag_is_a_waiver_not_a_pass(self):
        self.assertEqual([c for c, _ in self.c5(self.closed3("- [ ] pre-push scan of the text" + self.TAG))], ["WAIVER"])

    def test_untagged_unticked_on_closed_issue_fails(self):
        self.assertEqual([c for c, _ in self.c5(self.closed3("- [ ] pre-push scan of the text"))], ["FAIL"])

    def test_waiver_does_not_transfer_to_another_pr(self):
        out = self.c5(self.closed3("- [ ] pre-push scan of the text" + self.TAG, prs=(10, 11)))
        self.assertEqual([c for c, _ in out], ["FAIL"])
        self.assertIn("never transfers", out[0][1])

    def test_scan_waiver_does_not_cover_an_unrelated_criterion_on_the_same_pr(self):  # B4
        out = self.c5(self.closed3("- [ ] firewall negative test passes" + self.TAG))
        self.assertEqual([c for c, _ in out], ["FAIL"])
        self.assertIn("not about", out[0][1])

    def test_scope_without_waives_is_missing(self):  # B4
        out = self.c5(self.closed3("- [ ] pre-push scan of the text" + self.TAG), dict(POLICY, exception_scopes={"D-12": dict(prs=[10])}))
        self.assertEqual([c for c, _ in out], ["MISSING"])

    def test_waived_criterion_must_stay_unticked(self):
        self.assertIn("must stay unticked", self.c5(self.closed3("- [x] pre-push scan of the text" + self.TAG))[0][1])

    def test_tag_without_not_run_is_rejected(self):
        self.assertIn("NOT RUN", self.c5(self.closed3("- [ ] pre-push scan *(accepted exception: waived by owner, D-12)*"))[0][1])

    def test_unknown_decision_scope_is_missing(self):
        self.assertEqual([c for c, _ in self.c5(self.closed3("- [ ] pre-push scan" + self.TAG), dict(POLICY))], ["MISSING"])

    def test_ticked_without_proof(self):
        self.assertIn("ticked without proof", self.c5(self.closed3("- [x] done"))[0][1])

    def test_tagged_criterion_beside_an_untagged_defect_gives_waiver_and_fail(self):  # B4: one criterion, one finding
        out = self.c5(self.closed3("- [ ] pre-push scan of the text" + self.TAG + "\n- [ ] firewall negative test passes\n- [x] done"))
        self.assertEqual(sorted(c for c, _ in out), ["FAIL", "FAIL", "WAIVER"])  # waived + unticked defect + ticked without proof

    def test_two_tagged_criteria_are_judged_separately(self):
        out = self.c5(self.closed3("- [ ] pre-push scan of the text" + self.TAG + "\n- [ ] unrelated check" + self.TAG))
        self.assertEqual(sorted(c for c, _ in out), ["FAIL", "WAIVER"])

    def test_scope_is_compared_structurally(self):
        for sc in (dict(prs=["10"], waives="scan"), dict(prs=[], waives="scan"), dict(prs=[10], waives=" ")):
            out = self.c5(self.closed3("- [ ] pre-push scan of the text" + self.TAG), dict(POLICY, exception_scopes={"D-12": sc}))
            self.assertEqual([c for c, _ in out], ["MISSING"], sc)
        out = self.c5(self.closed3("- [ ] pre-push scan" + self.TAG), dict(POLICY, exception_scopes={"D-12": dict(prs=[11], waives="scan")}))
        self.assertEqual([c for c, _ in out], ["FAIL"])  # scope names another PR
        out = self.c5(self.closed3("- [ ] pre-push scan" + self.TAG, prs=()), dict(POLICY, exception_scopes={"D-12": dict(issues=[3], waives="scan")}))
        self.assertEqual([c for c, _ in out], ["WAIVER"])  # no closing PR: the issue itself is named

    def test_waivers_key_in_policy_is_rejected_not_ignored(self):
        import io, contextlib
        self.assertTrue(check.policy_problems(dict(POLICY, waivers=[])))
        with tempfile.TemporaryDirectory() as d:
            write(d, base())
            pf = os.path.join(d, "pol.json")
            with open(pf, "w") as f:
                json.dump(dict(POLICY, waivers=[dict(check="C4-status", object="board", decision="D-12", scope="x", waives="status")]), f)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(check.main(["check.py", d, "--policy", pf]), 2)
            self.assertIn("invalid policy", out.getvalue())

    def test_unresolved_rows_cannot_be_reclassified_by_policy(self):
        R, _ = run(base(), dict(POLICY, status_map={}))
        self.assertIn(("board", "MISSING"), classes(R, "C4-status"))
        self.assertFalse(any(r["cls"] == "WAIVER" for r in R.rows))

    def test_exit_zero_with_waivers_lists_them_and_says_not_passes(self):
        import io, contextlib
        fx = base()
        for i in fx["issues"]:
            i["state"] = "closed"
            i["body"] = i["body"].replace("[ ]", "[x]") + " (proof: PR)"
        fx["issues"][2]["body"] = "- [ ] pre-push scan of the text" + self.TAG
        fx["milestones"][0]["state"] = "closed"
        fx["pulls"], fx["closing"] = [dict(number=10, state="closed")], [dict(pr=10, closes=[3])]
        fx["meta"]["expected"]["pulls"] = 1
        for it in board(fx)["items"]["nodes"]:
            for v in it["fieldValues"]["nodes"]:
                if v["field"]["name"] == "Status":
                    v["name"] = "Done"
        with tempfile.TemporaryDirectory() as d:
            write(d, fx)
            pf = os.path.join(d, "pol.json")
            with open(pf, "w") as f:
                json.dump(dict(self.pol), f)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = check.main(["check.py", d, "--policy", pf])
        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertIn("accepted exceptions (not passes): 1", text)
        self.assertIn("pre-push scan of the text", text)
        self.assertIn("nothing to act on; 1 accepted exception(s), not passes", text)

    def test_owner_pending_turns_fail_into_owner_only_with_a_stated_decision(self):  # SA-3
        fx = self.closed3("- [ ] relies on the outside prerequisite")
        pend = dict(object="#3", match="outside prerequisite", decision="D-13 is open")
        out = self.c5(fx, dict(POLICY, owner_pending=[pend]))
        self.assertEqual([c for c, _ in out], ["OWNER"])
        self.assertEqual([c for c, _ in self.c5(fx, dict(POLICY))], ["FAIL"])
        R, _ = run(fx, dict(POLICY, owner_pending=[dict(pend, decision="")]))
        self.assertIn(("owner_pending[0]", "FAIL"), classes(R, "POLICY"))


class Hygiene(unittest.TestCase):
    def test_pr_with_milestone_when_plan_gives_milestones_to_issues_only(self):
        fx = base()
        fx["issues"].append(dict(issue(9, ms="M1"), pull_request={}))
        fx["pulls"] = [dict(number=9, state="open")]
        fx["closing"] = [dict(pr=9, closes=[])]
        fx["meta"]["expected"]["pulls"] = 1
        R, _ = run(fx, dict(POLICY, milestones_on_issues_only=True))
        self.assertIn(("PR#9", "FAIL"), classes(R, "C8-hygiene"))
        R, _ = run(fx, POLICY)
        self.assertEqual(classes(R, "C8-hygiene"), [])

    def test_old_field_name_gives_exact_line_change(self):
        fx = base()
        fx["issues"][2]["body"] = "- [ ] set the board field `Type` to Sub-issue"
        R, _ = run(fx, dict(POLICY, field_aliases=[dict(old="Type", role="kind")]))
        self.assertEqual(changes(R)[0]["new"], "- [ ] set the board field `Kind` to Sub-issue")

    def alias_fx(self, body):
        fx = base()
        board(fx)["fields"]["nodes"][1]["name"] = "Work Type"
        for it in board(fx)["items"]["nodes"]:
            for v in it["fieldValues"]["nodes"]:
                if v["field"]["name"] == "Kind":
                    v["field"]["name"] = "Work Type"
        fx["issues"][2]["body"] = body
        return fx, dict(POLICY, field_aliases=[dict(old="Type", role="kind")])

    def test_alias_fix_is_idempotent_type_to_work_type(self):  # B6
        fx, pol = self.alias_fx("- [ ] set the board field `Type`; the board field Work Type is live\n- [ ] board field `Work Type`")
        R, _ = run(fx, pol)
        ch = changes(R)
        self.assertEqual(len(ch), 1)
        self.assertEqual(ch[0]["new"], "- [ ] set the board field `Work Type`; the board field Work Type is live")
        self.assertNotIn("Work Work", ch[0]["new"])
        R, _ = run(apply_edits(fx, ch), pol)  # second run on the corrected text proposes nothing
        self.assertEqual(changes(R), [])
        R, _ = run(*self.alias_fx("- [ ] the board field Work Type"))
        self.assertEqual(changes(R), [])

    def test_stale_text_gives_old_new_line_and_history_is_not_matched(self):
        fx = base()
        fx["issues"][2]["body"] = "Decision: D-13 is proposed\nThe PR was opened and not merged"
        pol = dict(POLICY, stale_text=[dict(regex=r"D-13 is proposed", new="D-13 is decided", why="status copied from an older row")])
        R, _ = run(fx, pol)
        self.assertEqual([c["new"] for c in changes(R)], ["Decision: D-13 is decided"])

    def test_no_op_rerun_after_applying_the_corrections(self):  # B6 and no-op requirement
        fx = base()
        fx["issues"][2]["body"] = "Decision: D-13 is proposed\n- [ ] board field `Type`"
        pol = dict(POLICY, field_aliases=[dict(old="Type", role="kind")],
                   stale_text=[dict(regex=r"D-13 is proposed", new="D-13 is decided", why="x")])
        R, _ = run(fx, pol)
        self.assertEqual(len(changes(R)), 2)
        fx = apply_edits(fx, changes(R))
        R, _ = run(fx, pol)
        self.assertEqual(changes(R), [])


class Board(unittest.TestCase):
    def test_required_role_without_definition_is_missing_not_silently_dropped(self):
        R, _ = run(base(), dict(POLICY, required_roles=["kind", "knd"]))  # a misspelled role
        self.assertIn(("role:knd", "MISSING"), classes(R, "C7-board"))
        R2, _ = run(base())  # control: every required role defined, no such row
        self.assertFalse([c for c in classes(R2, "C7-board") if c[1] == "MISSING"])

    def test_items_keyed_by_repo_type_number(self):  # B8
        fx = base()
        nodes = board(fx)["items"]["nodes"]
        nodes.append(item(3, repo="other/repo", Status="Done", Kind="Sub-issue"))   # same number, other repository
        nodes.append(item(3, ty="PULL_REQUEST", Status="Done", Kind="Sub-issue"))    # same number, a pull request
        nodes.append(item(2, Status="Doing", Kind="Epic"))                           # duplicate
        nodes.append(item(1, archived=True, Status="Doing", Kind="Umbrella"))        # archived copy
        nodes.append(dict(type="DRAFT_ISSUE", isArchived=False, content={}, fieldValues=dict(nodes=[])))
        fx["meta"]["expected"]["project_items"] = len(nodes)
        R, why = run(fx)
        self.assertEqual(why, [])
        rows = classes(R, "C7-board")
        self.assertEqual(sorted(c for _, c in rows), ["FAIL", "OWNER", "OWNER"])  # duplicate; other-repo; archived
        self.assertEqual([r for r in classes(R, "C4-status")], [])                 # #3 status taken from the right item
        self.assertTrue(any("draft 1" in n and "pull request 1" in n for n in R.notes))

    def test_unexposed_api_facts_are_a_note_not_a_finding(self):  # SA-2
        R, _ = run(base(), dict(POLICY, milestone_exits={"M1": dict(require_closed=[])}))
        self.assertTrue(any("not exposed by the API" in n for n in R.notes))
        self.assertFalse(any(r["object"] == "board:unexposed" for r in R.rows))

    def test_clean_audit_exits_zero(self):  # SA-2
        fx = base()
        for i in fx["issues"]:
            i["state"] = "closed"
            i["body"] = i["body"].replace("[ ]", "[x]") + " (proof: PR)"
        fx["milestones"][0]["state"] = "closed"
        for it in board(fx)["items"]["nodes"]:
            for v in it["fieldValues"]["nodes"]:
                if v["field"]["name"] == "Status":
                    v["name"] = "Done"
        with tempfile.TemporaryDirectory() as d:
            write(d, fx)
            pf = os.path.join(d, "pol.json")
            with open(pf, "w") as f:
                json.dump(POLICY, f)
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(check.main(["check.py", d, "--policy", pf]), 0)
                os.remove(os.path.join(d, "labels.json"))
                self.assertEqual(check.main(["check.py", d, "--policy", pf]), 3)


class ExitCodes(unittest.TestCase):
    """A crash must never look like "findings" (exit 1): bad input is 2, an unreadable export is 3."""

    def rc(self, argv_tail, pol=POLICY, pol_text=None, before=None):
        import io, contextlib
        with tempfile.TemporaryDirectory() as d:
            write(d, base())
            pf = os.path.join(d, "pol.json")
            with open(pf, "w") as f:
                f.write(pol_text if pol_text is not None else json.dumps(pol))
            if before:
                before(d)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return check.main(["check.py", d] + [pf if a == "POL" else a for a in argv_tail])

    def test_control_valid_run_reports_findings_as_before(self):
        self.assertIn(self.rc(["--policy", "POL"]), (0, 1))

    def test_missing_or_invalid_policy_file_is_2(self):
        self.assertEqual(self.rc(["--policy", "/nonexistent/policy.json"]), 2)
        self.assertEqual(self.rc(["--policy", "POL"], pol_text="{not json"), 2)
        self.assertEqual(self.rc(["--policy", "POL"], pol_text="[1, 2]"), 2)

    def test_wrong_policy_shapes_are_2_not_a_traceback(self):
        for bad in (dict(POLICY, board_roles=dict(status=["Todo", "Done"])),
                    dict(POLICY, exception_scopes={"D-12": "PR 5"}),
                    dict(POLICY, field_aliases={"Type": "kind"}),
                    dict(POLICY, stale_text=[dict(regex="(", new="x")]),
                    dict(POLICY, plan_edges=[[1, "2"]]),
                    dict(POLICY, required_roles="kind"),
                    dict(POLICY, milestone_exits={"M1": dict(require_closed=1)}),
                    dict(POLICY, owner_pending=[None]),
                    dict(POLICY, exception_regex="accepted exception"),
                    dict(POLICY, stale_text=[dict(regex="x", new=r"\g<missing>")])):
            self.assertEqual(self.rc(["--policy", "POL"], pol=bad), 2, bad)

    def test_malformed_previous_report_is_2(self):
        for text in ('{"passes": []}', '{"passes": {"C1-coverage": []}}', '[]'):
            def put(d, text=text):
                with open(os.path.join(d, "prev.json"), "w") as f:
                    f.write(text)
            import io, contextlib
            with tempfile.TemporaryDirectory() as d:
                write(d, base()); put(d)
                pf = os.path.join(d, "pol.json")
                with open(pf, "w") as f:
                    json.dump(POLICY, f)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(check.main(["check.py", d, "--policy", pf, "--previous", os.path.join(d, "prev.json")]), 2, text)

    def test_unforeseen_crash_is_2_never_findings(self):
        fx = base()
        fx["issues"][0]["labels"] = 7  # an export shape no validation foresees
        import io, contextlib
        with tempfile.TemporaryDirectory() as d:
            write(d, fx)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(check.main(["check.py", d]), 2)
            self.assertIn("no conclusion drawn", out.getvalue())

    def test_unknown_repeated_or_valueless_flag_is_2(self):
        self.assertEqual(self.rc(["--policy", "POL", "--prev", "x.json"]), 2)
        self.assertEqual(self.rc(["--policy"]), 2)
        self.assertEqual(self.rc(["--policy", "POL", "--policy", "POL"]), 2)
        self.assertEqual(self.rc(["--policy", "POL", "--previous", "/nonexistent/report.json"]), 2)

    def test_truncated_export_file_is_3(self):
        def cut(d):
            with open(os.path.join(d, "labels.json"), "w") as f:
                f.write('[{"name": "type:ep')
        self.assertEqual(self.rc(["--policy", "POL"], before=cut), 3)

    def test_fingerprint_of_unreadable_file_is_2(self):
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check.main(["check.py", "fingerprint", "/nonexistent/x.json"]), 2)
            self.assertEqual(check.main(["check.py", "fingerprint"]), 2)


class Fingerprints(unittest.TestCase):
    """Stale-state: the hash covers the exact re-read JSON of each mutation target (SKILL.md lists the re-reads)."""

    def test_issue_body_label_milestone_state(self):
        a = issue(1, body="x")
        for b in (issue(1, body="y"), issue(1, body="x", labels=["l"]), issue(1, body="x", ms="M2"), issue(1, body="x", state="closed")):
            self.assertNotEqual(check.fingerprint(a), check.fingerprint(b))
        self.assertEqual(check.fingerprint(a), check.fingerprint(copy.deepcopy(a)))

    def test_board_item_field_value_change(self):  # B3
        a, b = item(3, Status="Todo", Kind="Sub-issue"), item(3, Status="Doing", Kind="Sub-issue")
        self.assertNotEqual(check.fingerprint(a), check.fingerprint(b))
        self.assertNotEqual(check.fingerprint(a), check.fingerprint(item(3, archived=True, Status="Todo", Kind="Sub-issue")))

    def test_project_readme_and_fields(self):  # B3
        a = board(base())
        b = copy.deepcopy(a)
        b["readme"] += " more"
        c = copy.deepcopy(a)
        c["fields"]["nodes"][0]["options"].append(dict(name="New"))
        self.assertEqual(len({check.fingerprint(x) for x in (a, b, c)}), 3)

    def test_dependency_change_and_order_independence(self):  # B3
        a = [dict(id=11, number=1), dict(id=12, number=2)]
        self.assertNotEqual(check.fingerprint(a), check.fingerprint(a[:1]))
        self.assertEqual(check.fingerprint(a), check.fingerprint(list(reversed(a))))  # a link set has no order
        self.assertNotEqual(check.fingerprint(a), check.fingerprint([dict(id=11, number=1), dict(id=13, number=3)]))

    def test_concurrent_change_is_detected_before_a_write(self):
        planned = check.fingerprint(issue(1, body="x"))
        reread = issue(1, body="x")
        reread["updated_at"] = "2026-01-02T00:00:00Z"  # someone edited it in between
        self.assertNotEqual(planned, check.fingerprint(reread))

    def test_retained_only_when_object_unchanged(self):
        R1, _ = run(base())
        prev = dict(passes=R1.passes)
        R2, _ = run(base(), prev=prev)
        self.assertTrue(any(r["cls"] == "RETAINED" for r in R2.rows))
        fx = base()
        fx["issues"][2]["body"] = "- [ ] changed"
        R3, _ = run(fx, prev=prev)
        self.assertEqual([r["cls"] for r in R3.rows if r["check"] == "C1-coverage" and r["object"] == "#3"], ["PASS"])
        fx = base()  # a parent change alone invalidates the C1 retention
        fx["sub_issues"], _ = links(sub={1: [3], 2: []})
        R4, _ = run(fx, prev=prev)
        self.assertEqual([r["cls"] for r in R4.rows if r["check"] == "C1-coverage" and r["object"] == "#3"], ["PASS"])


if __name__ == "__main__":
    unittest.main()
