"""Privilege matrix generator (acceptance check O-7): lab_agent.privmatrix.

Offline. The apidoc fixtures under tests/fixtures-privmatrix/ are SYNTHETIC: written for these
tests to the shape of the Proxmox API viewer file, not Proxmox data. The shape was compared
with one real apidoc.js on 2026-11-16 (that file's provenance is unverified), so a match here
shows the generator follows the documented shape, not that it is right for any other version.
Role contents in the tests are invented. Nothing here proves live permissions.
"""

import ast
import copy
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from lab_agent import privmatrix as pm
from tests import fixtures

FIX = Path(__file__).resolve().parent / "fixtures-privmatrix"
APIDOC = FIX / "apidoc-synthetic.js"
PLAN = FIX / "plan-synthetic.json"
LAB_AGENT = Path(__file__).resolve().parent.parent


def plan_copy():
    return pm.validate_plan(json.loads(PLAN.read_text()))


def synthetic_index():
    tree, _, _ = pm.load_apidoc(APIDOC)
    index, warnings = pm.index_schema(tree)
    assert warnings == [], warnings
    return index


def rows_by_id(rows, profile):
    return {r["id"]: r for r in rows if r["profile"] == profile}


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = pm.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class LoadingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text):
        p = self.dir / "apidoc.js"
        p.write_text(text)
        return p

    def test_synthetic_file_parses_without_executing_the_trailing_script(self):
        # The fixture ends with `throw new Error(...)`: the loader reads data, never runs it.
        tree, sha, size = pm.load_apidoc(APIDOC)
        self.assertEqual(len(sha), 64)
        self.assertEqual(size, APIDOC.stat().st_size)
        self.assertIn("throw new Error", APIDOC.read_text())
        self.assertEqual(tree[0]["path"], "/synthetic")

    def test_index_maps_path_and_method(self):
        index = synthetic_index()
        self.assertIn(("/synthetic/open", "GET"), index)
        self.assertNotIn(("/synthetic/open", "DELETE"), index)
        self.assertEqual(len(index), 23)

    def test_no_assignment_is_an_input_error(self):
        with self.assertRaises(pm.InputError):
            pm.load_apidoc(self.write("var other = [];\n"))

    def test_javascript_literal_is_refused_not_evaluated(self):
        marker = self.dir / "executed"
        p = self.write("const apiSchema = [ { path: '/x', info: {} } ];\n"
                       f"require('fs').writeFileSync('{marker}', '1');\n")
        with self.assertRaises(pm.InputError) as cm:
            pm.load_apidoc(p)
        self.assertIn("never executed", str(cm.exception))
        self.assertFalse(marker.exists())

    def test_non_array_and_non_utf8_are_input_errors(self):
        with self.assertRaises(pm.InputError):
            pm.load_apidoc(self.write("const apiSchema = {\"a\": 1};\n"))
        p = self.dir / "bin.js"
        p.write_bytes(b"const apiSchema = [];\xff\n")
        with self.assertRaises(pm.InputError):
            pm.load_apidoc(p)

    def test_duplicate_entry_is_a_warning_that_makes_the_result_incomplete(self):
        node = {"path": "/a", "info": {"GET": {"permissions": {"user": "all"}}}}
        index, warnings = pm.index_schema([node, dict(node)])
        self.assertEqual(len(index), 1)
        self.assertEqual(len(warnings), 1)
        status, code = pm.overall([], warnings, None)
        self.assertEqual((status, code), ("INCOMPLETE", 2))

    def test_malformed_nodes_are_skipped_with_a_warning(self):
        index, warnings = pm.index_schema(["not an object", {"path": 7, "info": {}}])
        self.assertEqual(index, {})
        self.assertEqual(len(warnings), 2)


class FormTests(unittest.TestCase):
    """One synthetic operation per permission form, evaluated for the 'token' profile."""

    @classmethod
    def setUpClass(cls):
        cls.index = synthetic_index()
        cls.plan = plan_copy()
        cls.rows = rows_by_id(pm.build_matrix(cls.index, cls.plan), "token")
        cls.weak = rows_by_id(pm.build_matrix(cls.index, cls.plan), "weak")

    def test_no_privilege_and_world_are_allowed(self):
        self.assertEqual(self.rows["S-OPEN"]["state"], pm.ALLOW)
        self.assertEqual(self.rows["S-WORLD"]["state"], pm.ALLOW)

    def test_perm_all_privileges_with_role_and_path_of_the_grant(self):
        r = self.rows["S-ALL"]
        self.assertEqual((r["state"], r["verdict"]), (pm.ALLOW, "OK"))
        self.assertEqual(r["granted_by"], "ADM @ /pool/lab")  # inherited through pool membership
        self.assertIn("VM.PowerMgmt+VM.Config.Memory @ /vms/VM1", r["required"])

    def test_perm_all_is_denied_on_a_foreign_guest_with_the_same_token(self):
        # positive control above (S-ALL) shows the privilege exists for the pool guest
        r = self.rows["S-ALL-FOREIGN"]
        self.assertEqual((r["state"], r["verdict"]), (pm.DENY, "OK"))
        self.assertEqual(r["granted_by"], "-")

    def test_perm_all_needs_every_privilege_any_needs_one(self):
        idx, plan = self.index, plan_copy()
        plan["roles"]["ADM"].remove("VM.Config.Memory")
        plan = pm.validate_plan(plan)
        rows = rows_by_id(pm.build_matrix(idx, plan), "token")
        self.assertEqual(rows["S-ALL"]["state"], pm.DENY)   # one of two privileges is missing
        self.assertEqual(rows["S-ANY"]["state"], pm.ALLOW)  # `any`: one of two is enough
        self.assertEqual(rows["S-ALL"]["verdict"], "NARROWER")

    def test_and_requires_both_branches(self):
        self.assertEqual(self.rows["S-AND"]["state"], pm.ALLOW)
        self.assertIn("ADM @ /pool/lab", self.rows["S-AND"]["granted_by"])
        self.assertIn("STO @ /storage/S1", self.rows["S-AND"]["granted_by"])
        plan = plan_copy()
        plan["profiles"]["token"] = [e for e in plan["profiles"]["token"] if e["path"] != "/storage/S1"]
        plan["profiles"]["token"].append({"path": "/storage/S1", "role": "ADM"})  # no Datastore.Audit
        rows = rows_by_id(pm.build_matrix(self.index, plan), "token")
        self.assertEqual(rows["S-AND"]["state"], pm.DENY)

    def test_or_with_require_param_needs_the_parameter(self):
        self.assertEqual(self.rows["S-OR-POOL"]["state"], pm.ALLOW)    # `pool` supplied
        self.assertEqual(self.rows["S-OR-NOPOOL"]["state"], pm.DENY)   # same operation, no `pool`
        self.assertEqual(self.rows["S-OR-NOPOOL"]["verdict"], "OK")

    def test_perm_modify_allows_the_substitute_privilege_only_on_its_own_object(self):
        self.assertEqual(self.rows["S-PM-IN"]["state"], pm.ALLOW)   # VM.Allocate on a pool guest (R-15)
        self.assertEqual(self.rows["S-PM-OUT"]["state"], pm.DENY)   # a foreign guest

    def test_userid_param_self_is_conditional_never_allowed(self):
        r = self.rows["S-SELF"]
        self.assertEqual((r["state"], r["verdict"]), (pm.COND, "OK"))

    def test_userid_param_privilege_and_userid_group_are_unknown_never_allowed_or_denied(self):
        # Round 2: their semantics are not in the schema, so neither a grant nor its absence
        # may turn into a definite answer.
        for op_id in ("S-UPRIV", "S-UGROUP"):
            self.assertEqual(self.rows[op_id]["state"], pm.UNKNOWN, op_id)
            self.assertEqual(self.rows[op_id]["verdict"], "INCOMPLETE", op_id)
        plan = plan_copy()  # grants present: still UNKNOWN
        plan["roles"]["ADM"] += ["User.Modify", "Realm.AllocateUser"]
        plan["profiles"]["token"].append({"path": "/access", "role": "ADM"})
        rows = rows_by_id(pm.build_matrix(self.index, pm.validate_plan(plan)), "token")
        for op_id in ("S-UPRIV", "S-UGROUP"):
            self.assertEqual(rows[op_id]["state"], pm.UNKNOWN, op_id)
            self.assertEqual(rows[op_id]["verdict"], "INCOMPLETE")

    def test_doubtful_input_is_unknown_and_incomplete_never_allowed(self):
        for op_id in ("S-NOPERM", "S-EMPTYRULE", "S-WEIRDUSER", "S-UNKNOWNFORM", "S-BADPERM", "S-EMPTYAND",
                      "S-BADOPTION", "S-UNBOUND"):
            r = self.rows[op_id]
            self.assertEqual(r["state"], pm.UNKNOWN, op_id)
            self.assertEqual(r["verdict"], "INCOMPLETE", op_id)
        self.assertTrue(any("unknown permission form" in n for n in self.rows["S-UNKNOWNFORM"]["notes"]))
        self.assertTrue(any("no 'permissions' key" in n for n in self.rows["S-NOPERM"]["notes"]))
        self.assertTrue(any("unbound parameter 'mystery'" in n for n in self.rows["S-UNBOUND"]["notes"]))

    def test_doubtful_input_stays_unknown_even_when_every_role_is_granted_everywhere(self):
        plan = plan_copy()
        plan["roles"]["ADM"] += list(plan["roles"]["AUD"]) + ["Sys.Modify"]
        plan["profiles"]["token"] = [{"path": "/", "role": "ADM"}]
        rows = rows_by_id(pm.build_matrix(self.index, pm.validate_plan(plan)), "token")
        for op_id in ("S-NOPERM", "S-UNKNOWNFORM", "S-BADPERM", "S-EMPTYAND", "S-BADOPTION", "S-UNBOUND"):
            self.assertEqual(rows[op_id]["state"], pm.UNKNOWN, op_id)

    def test_text_only_rule_extracts_privileges_and_is_not_allowed(self):
        r = self.rows["S-TEXT"]
        self.assertEqual(r["state"], pm.TEXT)
        self.assertEqual(r["text_privs"], ["VM.Backup"])
        self.assertEqual(r["verdict"], "INCOMPLETE")
        self.assertTrue(any("root@pam" in n for n in r["notes"]))
        self.assertTrue(r["plan_only"]["satisfied"])  # the plan's own requirement is granted

    def test_description_naming_more_than_the_check_downgrades_allow_to_text_only(self):
        r = self.rows["S-TEXTEXTRA"]
        self.assertEqual(r["state"], pm.TEXT)
        self.assertTrue(any("Datastore.AllocateSpace" in n for n in r["notes"]))
        # Round 4: even a description that only restates the check makes the row TEXT-ONLY ...
        self.assertEqual(self.rows["S-DESCSAME"]["state"], pm.TEXT)
        # ... and the same kind of rule without any description text is decided by the check alone
        self.assertEqual((self.rows["S-ALL"]["state"], self.rows["S-ALL"]["verdict"]), (pm.ALLOW, "OK"))

    def test_root_only_and_allowtoken_zero_are_denied_for_a_token(self):
        self.assertEqual(self.rows["S-ROOT"]["state"], pm.DENY)
        self.assertEqual(self.rows["S-NOTOKEN"]["state"], pm.DENY)
        self.assertTrue(any("allowtoken 0" in n for n in self.rows["S-NOTOKEN"]["notes"]))

    def test_a_method_the_schema_does_not_have_is_a_mismatch(self):
        r = self.rows["S-NOMETHOD"]
        self.assertEqual((r["state"], r["verdict"]), (pm.MISSING, "MISSING-OP"))
        # control: the path exists with another method and is fine
        self.assertEqual(self.rows["S-OPEN"]["verdict"], "OK")

    def test_deeper_acl_replaces_the_inherited_one(self):
        # R-19: an entry on a deeper path replaces what is inherited. The pool role here has
        # no VM.Audit, so the pool guest loses the Auditor read that '/' alone would give.
        plan = plan_copy()
        plan["roles"]["POOLONLY"] = ["VM.PowerMgmt"]
        plan["profiles"]["token"] = [{"path": "/", "role": "AUD"}, {"path": "/pool/lab", "role": "POOLONLY"}]
        idx = {("/r", "GET"): {"permissions": {"check": ["perm", "/vms/{vmid}", ["VM.Audit"]]}}}
        plan["operations"] = [{"id": "R", "method": "GET", "path": "/r", "expect": {"token": "allow"},
                               "bind": {"vmid": "VM1"}},
                              {"id": "R2", "method": "GET", "path": "/r", "expect": {"token": "allow"},
                               "bind": {"vmid": "FOREIGN"}}]
        rows = rows_by_id(pm.build_matrix(idx, pm.validate_plan(plan), ["token"]), "token")
        self.assertEqual(rows["R"]["state"], pm.DENY)    # pool guest: pool entry replaces '/'
        self.assertEqual(rows["R2"]["state"], pm.ALLOW)  # control: a foreign guest keeps the inherited read

    def test_non_propagating_entry_applies_only_on_its_exact_path(self):
        idx = {("/r", "GET"): {"permissions": {"check": ["perm", "/vms/{vmid}", ["VM.Audit"]]}}}
        plan = plan_copy()
        plan["profiles"]["token"] = [{"path": "/vms", "role": "AUD", "propagate": False}]
        plan["operations"] = [{"id": "R", "method": "GET", "path": "/r", "expect": {"token": "allow"},
                               "bind": {"vmid": "X"}}]
        rows = rows_by_id(pm.build_matrix(idx, pm.validate_plan(plan), ["token"]), "token")
        self.assertEqual(rows["R"]["state"], pm.DENY)
        plan["profiles"]["token"][0]["propagate"] = True  # control
        rows = rows_by_id(pm.build_matrix(idx, pm.validate_plan(plan), ["token"]), "token")
        self.assertEqual(rows["R"]["state"], pm.ALLOW)


class ComparisonTests(unittest.TestCase):
    """The plan comparison: broader, narrower, plan drift, live-only, incomplete."""

    @classmethod
    def setUpClass(cls):
        cls.index = synthetic_index()

    def matrix(self, plan, profile="token"):
        return rows_by_id(pm.build_matrix(self.index, plan), profile)

    def test_the_synthetic_plan_matches_where_the_schema_is_decidable(self):
        rows = self.matrix(plan_copy())
        self.assertEqual(rows["S-ALL"]["verdict"], "OK")
        self.assertEqual(rows["S-ALL-FOREIGN"]["verdict"], "OK")
        self.assertEqual(rows["S-LIVE"]["verdict"], "LIVE-ONLY")
        self.assertEqual(rows["S-LIVE"]["state"], pm.ALLOW)  # allowed at schema level: refusal is not in the schema

    def test_broader_than_planned_is_detected_with_its_positive_control(self):
        plan = plan_copy()
        rows = self.matrix(plan)
        self.assertEqual(rows["S-ALL-FOREIGN"]["verdict"], "OK")        # control: foreign guest refused
        plan["profiles"]["token"].append({"path": "/vms", "role": "ADM"})  # grant ADM on every guest
        rows = self.matrix(pm.validate_plan(plan))
        self.assertEqual(rows["S-ALL-FOREIGN"]["state"], pm.ALLOW)
        self.assertEqual(rows["S-ALL-FOREIGN"]["verdict"], "BROADER")
        self.assertEqual(rows["S-ALL-FOREIGN"]["granted_by"], "ADM @ /vms")

    def test_read_only_profile_that_can_write_is_broader(self):
        plan = plan_copy()
        self.assertEqual(self.matrix(plan, "weak")["S-ALL"]["verdict"], "OK")  # control
        plan["profiles"]["weak"] = [{"path": "/", "role": "ADM"}]
        self.assertEqual(self.matrix(pm.validate_plan(plan), "weak")["S-ALL"]["verdict"], "BROADER")

    def test_narrower_than_planned_is_detected(self):
        plan = plan_copy()
        plan["profiles"]["token"] = [e for e in plan["profiles"]["token"] if e["path"] != "/pool/lab"]
        rows = self.matrix(pm.validate_plan(plan))
        self.assertEqual(rows["S-ALL"]["verdict"], "NARROWER")

    def test_text_only_with_plan_requirement_not_granted_is_narrower(self):
        plan = plan_copy()
        plan["roles"]["ADM"].remove("VM.Backup")
        rows = self.matrix(pm.validate_plan(plan))
        self.assertEqual(rows["S-TEXT"]["state"], pm.TEXT)
        self.assertEqual(rows["S-TEXT"]["verdict"], "NARROWER")

    def test_text_only_with_plan_requirement_granted_where_denial_is_expected_is_broader(self):
        plan = plan_copy()
        for op in plan["operations"]:
            if op["id"] == "S-TEXT":
                op["expect"]["token"] = "deny"
        rows = self.matrix(plan)
        self.assertEqual(rows["S-TEXT"]["verdict"], "BROADER")
        # control: with the privilege removed the same text-only operation is merely incomplete
        plan["roles"]["ADM"].remove("VM.Backup")
        self.assertEqual(self.matrix(pm.validate_plan(plan))["S-TEXT"]["verdict"], "INCOMPLETE")

    def test_plan_privilege_the_schema_never_mentions_is_plan_drift(self):
        plan = plan_copy()
        for op in plan["operations"]:
            if op["id"] == "S-ALL":
                op["any_of"][0].append({"priv": "Sys.Console", "path": "/vms/VM1"})
        rows = self.matrix(plan)
        self.assertEqual(rows["S-ALL"]["verdict"], "PLAN-DRIFT")
        self.assertIn("Sys.Console", rows["S-ALL"]["why"])
        self.assertEqual(self.matrix(plan_copy())["S-ALL"]["verdict"], "OK")  # control

    def test_unknown_never_counts_as_a_match(self):
        rows = self.matrix(plan_copy())
        for op_id in ("S-UNKNOWNFORM", "S-NOPERM"):
            self.assertNotEqual(rows[op_id]["verdict"], "OK")
        # an unknown rule where the plan expects denial is also not a match
        plan = plan_copy()
        for op in plan["operations"]:
            if op["id"] == "S-UNKNOWNFORM":
                op["expect"]["token"] = "deny"
        self.assertEqual(self.matrix(plan)["S-UNKNOWNFORM"]["verdict"], "INCOMPLETE")

    def test_overall_status_ranks_mismatch_over_incomplete_over_match(self):
        full = pm.build_matrix(self.index, plan_copy())
        self.assertEqual(pm.overall(full, [], None), ("MISMATCH", 1))      # S-NOMETHOD
        without_missing = [r for r in full if r["verdict"] != "MISSING-OP"]
        self.assertEqual(pm.overall(without_missing, [], None), ("INCOMPLETE", 2))
        only_ok = [r for r in without_missing if r["verdict"] == "OK"]
        self.assertEqual(pm.overall(only_ok, [], None), ("MATCH", 0))

    def test_plan_validation_rejects_unusable_plans(self):
        bad = plan_copy()
        bad["profiles"]["token"].append({"path": "/x", "role": "NOROLE"})
        with self.assertRaises(pm.InputError):
            pm.validate_plan(bad)
        dup = plan_copy()
        dup["operations"].append(dict(dup["operations"][0]))
        with self.assertRaises(pm.InputError):
            pm.validate_plan(dup)
        worse = plan_copy()
        worse["operations"][0]["expect"] = {"token": "maybe"}
        with self.assertRaises(pm.InputError):
            pm.validate_plan(worse)
        with self.assertRaises(pm.InputError):
            pm.validate_plan({"roles": {}})


class SweepTests(unittest.TestCase):
    def setUp(self):
        self.index = synthetic_index()

    def test_pool_scoped_grant_allows_nothing_on_a_foreign_object(self):
        sw = pm.sweep(self.index, plan_copy())
        self.assertEqual(sw["foreign_write_allowed"], [])
        self.assertEqual(sw["total"], 23)

    def test_broad_grant_is_reported_as_a_foreign_write(self):
        plan = plan_copy()
        plan["profiles"]["token"].append({"path": "/vms", "role": "ADM"})
        sw = pm.sweep(self.index, pm.validate_plan(plan))
        self.assertIn("POST /synthetic/{vmid}/perm", sw["foreign_write_allowed"])
        status, code = pm.overall([], [], sw)
        self.assertEqual((status, code), ("MISMATCH", 1))

    def test_audit_only_and_no_privilege_writes_are_listed_apart(self):
        idx = {("/p", "POST"): {"permissions": {"check": ["perm", "/vms/{vmid}", ["VM.Audit"]]}},
               ("/q", "POST"): {"permissions": {"user": "world"}},
               ("/w", "POST"): {"permissions": {"check": ["perm", "/vms/{vmid}", ["VM.PowerMgmt"]]}}}
        plan = plan_copy()
        plan["profiles"]["token"] = [{"path": "/", "role": "AUD"}, {"path": "/vms", "role": "AUD"},
                                     {"path": "/vms", "role": "ADM"}]
        sw = pm.sweep(idx, pm.validate_plan(plan))
        self.assertEqual(sw["foreign_audit_only_write"], ["POST /p"])
        self.assertEqual(sw["foreign_no_privilege_write"], ["POST /q"])
        self.assertEqual(sw["foreign_write_allowed"], ["POST /w"])

    def test_undecided_operations_are_counted_never_allowed(self):
        sw = pm.sweep(self.index, plan_copy())
        self.assertGreaterEqual(sw["undecided"][pm.TEXT], 2)
        self.assertGreaterEqual(sw["undecided"][pm.UNKNOWN], 5)
        self.assertIn("GET /synthetic/nopermkey", sw["undecided_ops"])

    def test_unplanned_write_operations_in_scope_are_listed(self):
        plan = plan_copy()
        plan["operations"] = [o for o in plan["operations"] if o["path"] != "/synthetic/{vmid}/perm"]
        sw = pm.sweep(self.index, pm.validate_plan(plan))
        self.assertIn("POST /synthetic/{vmid}/perm", sw["in_scope_allowed_unplanned"])


class DefaultPlanTests(unittest.TestCase):
    """The embedded RBAC design (plan s6.1) against a schema derived from the plan itself.

    The derived schema only proves the embedded role table and ACLs are consistent with the
    embedded expectations; it says nothing about Proxmox.
    """

    def setUp(self):
        self.plan = pm.load_plan(None)

    def ideal_schema(self):
        index = {}
        for op in self.plan["operations"]:
            if op["id"] == "N10":
                continue
            alts = op.get("any_of") or []
            if alts:
                branches = [["and"] + [["perm", r["path"], [r["priv"]]] for r in alt] for alt in alts]
                check = branches[0] if len(branches) == 1 else ["or"] + branches
                entry = {"allowtoken": 1, "permissions": {"check": check}}
            elif op.get("category") == "self":
                entry = {"allowtoken": 1, "permissions": {"check": ["userid-param", "self"]}}
            else:
                entry = {"allowtoken": 1, "permissions": {"user": "all"}}
            index[(op["path"], op["method"])] = entry
        return index

    def test_embedded_plan_is_valid_and_uses_logical_names_only(self):
        text = json.dumps(pm.DEFAULT_PLAN)
        self.assertNotIn("@pve", text)
        self.assertNotIn("192.", text)
        self.assertEqual(set(self.plan["profiles"]), {"routine", "read-only"})
        ids = [o["id"] for o in self.plan["operations"]]
        self.assertEqual(len(ids), len(set(ids)))
        for needed in ("P1", "P8", "N7", "N8", "N9", "N13", "X2"):
            self.assertIn(needed, ids)

    def test_plan_acls_follow_section_6_1(self):
        acls = {(e["path"], e["role"]) for e in self.plan["profiles"]["routine"]}
        self.assertEqual(acls, {("/", "PVEAuditor"), ("/pool/corelab", "PVEVMAdmin"),
                                ("/storage/LAB_STORAGE", "PVEDatastoreUser"),
                                ("/storage/VM_STORAGE", "PVEDatastoreUser"),
                                ("/sdn/zones/localnetwork/BRIDGE", "PVESDNUser")})
        self.assertEqual(self.plan["profiles"]["read-only"], [{"path": "/", "role": "PVEAuditor"}])

    def test_not_granted_privileges_are_in_no_assumed_role(self):
        # Plan s6.1 "Not granted": none of these may appear in a role the plan assigns.
        used = {e["role"] for acls in self.plan["profiles"].values() for e in acls}
        granted = {p for r in used for p in self.plan["_roles"][r]}
        for priv in ("Datastore.Allocate", "Datastore.AllocateTemplate", "Pool.Allocate", "Permissions.Modify",
                     "Sys.Modify", "Sys.AccessNetwork"):
            self.assertNotIn(priv, granted, priv)

    def test_derived_schema_gives_no_mismatch_and_is_complete_where_checkable(self):
        schema = self.ideal_schema()
        # Rows that share an API path with a different expectation use distinct plan bindings;
        # the derived entry for a shared path is the union of requirements, so keep only paths
        # used once and check the rest separately below.
        paths = {}
        for op in self.plan["operations"]:
            paths.setdefault((op["path"], op["method"]), []).append(op["id"])
        single = {k: v for k, v in paths.items() if len(v) == 1}
        plan = copy.deepcopy(self.plan)
        plan["operations"] = [o for o in plan["operations"] if (o["path"], o["method"]) in single
                              and o["id"] != "N10"]
        rows = pm.build_matrix(schema, pm.validate_plan(plan))
        bad = [(r["id"], r["profile"], r["verdict"], r["why"]) for r in rows if r["verdict"] != "OK"]
        self.assertEqual(bad, [])
        self.assertGreater(len(rows), 20)

    def test_tampered_role_is_caught_with_its_positive_control(self):
        schema = {("/pools/{poolid}", "PUT"): {"permissions": {"check": ["perm", "/pool/{poolid}", ["Pool.Allocate"]]}}}
        plan = copy.deepcopy(self.plan)
        plan["operations"] = [o for o in plan["operations"] if o["id"] == "N7"]
        rows = pm.build_matrix(schema, pm.validate_plan(plan), ["routine"])
        self.assertEqual(rows[0]["verdict"], "OK")                       # control: Pool.Allocate not granted
        plan["roles"]["PVEVMAdmin"].append("Pool.Allocate")
        rows = pm.build_matrix(schema, pm.validate_plan(plan), ["routine"])
        self.assertEqual(rows[0]["verdict"], "BROADER")
        self.assertEqual(rows[0]["granted_by"], "PVEVMAdmin @ /pool/corelab")

    def test_clone_uses_the_pool_branch_only_when_pool_is_supplied(self):
        check = ["and", ["perm", "/vms/{vmid}", ["VM.Clone"]],
                 ["or", ["perm", "/vms/{newid}", ["VM.Allocate"]],
                  ["perm", "/pool/{pool}", ["VM.Allocate"], "require_param", "pool"]]]
        desc = ("You need 'VM.Clone' permissions on /vms/{vmid}, and 'VM.Allocate' permissions on /vms/{newid} "
                "(or on the VM pool /pool/{pool}). You also need 'Datastore.AllocateSpace' on any used storage "
                "and 'SDN.Use' on any used bridge/vnet")
        schema = {("/nodes/{node}/qemu/{vmid}/clone", "POST"): {"permissions": {"check": check, "description": desc}}}
        plan = copy.deepcopy(self.plan)
        plan["operations"] = [o for o in plan["operations"] if o["id"] == "P1"]
        rows = pm.build_matrix(schema, pm.validate_plan(plan), ["routine"])
        # the description names two requirements the check does not hold: TEXT-ONLY, not ALLOW
        self.assertEqual((rows[0]["state"], rows[0]["verdict"]), (pm.TEXT, "INCOMPLETE"))
        self.assertTrue(rows[0]["plan_only"]["satisfied"])
        self.assertIn("VM.Allocate @ /pool/corelab", rows[0]["required"])
        self.assertIn("PVEVMAdmin @ /pool/corelab", rows[0]["granted_by"])
        plan["operations"][0]["params"] = []  # clone without `pool`: needs VM.Allocate on the new VMID
        rows = pm.build_matrix(schema, pm.validate_plan(plan), ["routine"])
        self.assertEqual(rows[0]["state"], pm.TEXT)  # Round 4: text is present, so no definite answer
        del schema[("/nodes/{node}/qemu/{vmid}/clone", "POST")]["permissions"]["description"]
        plan["operations"][0]["any_of"] = [[{"priv": "VM.Clone", "path": "/vms/TEMPLATE"},
                                            {"priv": "VM.Allocate", "path": "/vms/NEWID"}]]  # only what the check holds
        rows = pm.build_matrix(schema, pm.validate_plan(plan), ["routine"])
        self.assertEqual(rows[0]["state"], pm.DENY)  # the check alone decides: no VM.Allocate on the new VMID
        self.assertEqual(rows[0]["verdict"], "NARROWER")

    def test_parameter_restrictions_are_live_only_not_a_pass(self):
        live = [o["id"] for o in self.plan["operations"] if (o.get("expect") or {}).get("routine") == "live-only"]
        self.assertEqual(live, ["N10", "N11", "N12"])


def mini(ops, **plan_edits):
    """Synthetic plan restricted to `ops`; each op is (id, method, path, bind, expect-dict)."""
    plan = plan_copy()
    plan["operations"] = [{"id": i, "method": m, "path": p, "bind": b, "expect": e} for i, m, p, b, e in ops]
    plan.update(plan_edits)
    return pm.validate_plan(plan)


GRANTED = ["perm", "/vms/{vmid}", ["VM.PowerMgmt"]]      # token: allowed on the pool guest VM1
DENIED = ["perm", "/vms/{vmid}", ["VM.Snapshot.Rollback"]]  # token: no role grants it
UNKNOWN_FORM = ["perm-future", "/", ["Sys.Audit"]]
BOTH = {"token": "allow", "weak": "allow"}


def one_row(check, expect, bind=None, desc=None, profile="token"):
    perms = {"check": check}
    if desc is not None:
        perms["description"] = desc
    idx = {("/x", "POST"): {"permissions": perms}}
    plan = mini([("X", "POST", "/x", bind or {"vmid": "VM1"}, {"token": expect, "weak": expect})])
    return rows_by_id(pm.build_matrix(idx, plan), profile)["X"]


class Round2Tests(unittest.TestCase):
    """Regression tests for the findings of the independent review (round 2)."""

    # (1) uncovered operation/profile pairs and zero comparisons
    def test_custom_profile_without_expectations_is_an_error_not_a_match(self):
        plan = plan_copy()
        plan["profiles"] = {"custom": [{"path": "/", "role": "AUD"}]}
        plan["sweep_profile"] = "custom"
        plan["operations"] = [{"id": "A", "method": "GET", "path": "/synthetic/open", "category": "read",
                               "bind": {}}]
        plan = pm.validate_plan(plan)
        with self.assertRaises(pm.InputError) as cm:
            pm.build_matrix(synthetic_index(), plan)
        self.assertIn("no expectation for profile(s): custom", str(cm.exception))
        plan["operations"][0]["expect"] = {"custom": "allow"}   # positive control: covered, so it runs
        rows = pm.build_matrix(synthetic_index(), pm.validate_plan(plan))
        self.assertEqual([(r["id"], r["profile"], r["verdict"]) for r in rows], [("A", "custom", "OK")])

    def test_cli_refuses_a_plan_with_uncovered_pairs_and_an_empty_schema(self):
        tmp = fixtures.private_tmpdir()
        self.addCleanup(tmp.cleanup)
        plan = plan_copy()
        plan["profiles"] = {"custom": [{"path": "/", "role": "AUD"}]}
        plan["sweep_profile"] = "custom"
        plan["operations"] = [{"id": "A", "method": "GET", "path": "/nothing", "category": "read", "bind": {}}]
        pf, af = Path(tmp.name) / "plan.json", Path(tmp.name) / "apidoc.js"
        pf.write_text(json.dumps(plan))
        af.write_text("const apiSchema = [];\n")
        code, out, err = run_main(["--apidoc", str(af), "--plan", str(pf)])
        self.assertEqual(code, 3)
        self.assertNotIn("MATCH", out)
        self.assertIn("no expectation", err)

    def test_zero_rows_never_match(self):
        self.assertEqual(pm.overall([], [], None), ("INCOMPLETE", 2))
        ok_row = [{"verdict": "OK"}]
        self.assertEqual(pm.overall(ok_row, [], None), ("MATCH", 0))  # control

    def test_expectation_for_an_unknown_profile_is_rejected(self):
        plan = plan_copy()
        plan["operations"][0]["expect"]["typo"] = "allow"
        with self.assertRaises(pm.InputError):
            pm.validate_plan(plan)
        with self.assertRaises(pm.InputError):
            pm.build_matrix(synthetic_index(), plan_copy(), ["nope"])

    # (2) incompleteness is carried apart from the Boolean outcome
    def test_or_with_an_unknown_branch_and_a_granted_branch_is_not_a_complete_match(self):
        r = one_row(["or", UNKNOWN_FORM, GRANTED], "allow")
        self.assertEqual(r["state"], pm.ALLOW)
        self.assertTrue(r["incomplete"])
        self.assertEqual(r["verdict"], "INCOMPLETE")
        control = one_row(["or", GRANTED, GRANTED], "allow")
        self.assertEqual((control["verdict"], control["incomplete"]), ("OK", False))

    def test_and_with_an_unknown_branch_and_a_denied_branch_is_not_a_complete_match(self):
        r = one_row(["and", UNKNOWN_FORM, DENIED], "deny")
        self.assertEqual(r["state"], pm.DENY)
        self.assertTrue(r["incomplete"])
        self.assertEqual(r["verdict"], "INCOMPLETE")
        control = one_row(["and", DENIED, DENIED], "deny")
        self.assertEqual((control["verdict"], control["incomplete"]), ("OK", False))

    def test_a_decisive_outcome_still_reports_a_mismatch_despite_an_unknown_branch(self):
        self.assertEqual(one_row(["or", UNKNOWN_FORM, GRANTED], "deny")["verdict"], "BROADER")
        self.assertEqual(one_row(["and", UNKNOWN_FORM, DENIED], "allow")["verdict"], "NARROWER")

    def test_nested_unknown_reaches_the_top(self):
        r = one_row(["and", GRANTED, ["or", GRANTED, ["and", UNKNOWN_FORM, DENIED]]], "allow")
        self.assertEqual((r["state"], r["incomplete"], r["verdict"]), (pm.ALLOW, True, "INCOMPLETE"))

    # (3) userid-group grammar
    def test_userid_group_with_an_unsupported_option_is_unknown(self):
        for node in (["userid-group", ["User.Modify"], "unrecognized-option"],
                     ["userid-group", ["User.Modify"], "groups_param", "frobnicate"],
                     ["userid-group", ["User.Modify"], "groups_param"],
                     ["userid-group", "User.Modify"], ["userid-group", []], ["userid-group"]):
            with self.subTest(node=node):
                r = one_row(node, "deny", bind={})
                self.assertEqual(r["state"], pm.UNKNOWN)
                self.assertEqual(r["verdict"], "INCOMPLETE")
                self.assertTrue(any("unsupported 'userid-group' grammar" in n for n in r["notes"]))

    def test_valid_userid_group_grammar_is_unknown_with_or_without_grants(self):
        for node in (["userid-group", ["User.Modify"]], ["userid-group", ["User.Modify"], "groups_param", "create"],
                     ["userid-group", ["User.Modify"], "groups_param", "update"]):
            r = one_row(node, "deny", bind={})
            self.assertEqual((r["state"], r["verdict"]), (pm.UNKNOWN, "INCOMPLETE"), node)
            self.assertTrue(any("semantics not established" in n for n in r["notes"]))

    # (4) descriptions that add a path or a condition
    def test_description_adding_a_path_keeps_the_operation_text_only(self):
        r = one_row(GRANTED, "allow", desc="Also requires 'VM.PowerMgmt' on /vms/SENTINEL.")
        self.assertEqual((r["state"], r["verdict"]), (pm.TEXT, "INCOMPLETE"))
        self.assertTrue(any("paths not in the check: /vms/SENTINEL" in n for n in r["notes"]))
        control = one_row(GRANTED, "allow")  # the same rule with no description text
        self.assertEqual((control["state"], control["verdict"]), (pm.ALLOW, "OK"))

    def test_description_adding_a_condition_keeps_the_operation_text_only(self):
        for text in ("Only allowed when the guest is stopped.", "Unless the guest is a template.",
                     "This is required for linked clones.",
                     # round 3: wording no keyword list would catch
                     "Access is limited to root@pam.", "Access is contingent upon group membership.",
                     "For stopped guests.", "Power management for the guest."):
            with self.subTest(text=text):
                r = one_row(GRANTED, "allow", desc=text)
                self.assertEqual((r["state"], r["verdict"], r["incomplete"]), (pm.TEXT, "INCOMPLETE", True))
                self.assertTrue(any("only the structured check alone can decide" in n for n in r["notes"]), r["notes"])

    def test_any_description_text_makes_the_row_text_only_even_a_restatement(self):
        # Round 4: there is no list of wordings known to add nothing.
        for text in ("Needs 'VM.PowerMgmt' on /vms/{vmid}.", "You need 'VM.PowerMgmt' permissions on /vms/{vmid}",
                     "x"):
            with self.subTest(text=text):
                r = one_row(GRANTED, "allow", desc=text)
                self.assertEqual((r["state"], r["verdict"], r["incomplete"]), (pm.TEXT, "INCOMPLETE", True))
        for text in ("", "   ", "\n"):  # control: no text at all, so the structured check decides alone
            with self.subTest(empty=text):
                r = one_row(GRANTED, "allow", desc=text)
                self.assertEqual((r["state"], r["verdict"], r["incomplete"]), (pm.ALLOW, "OK", False))

    def test_or_rule_with_a_denied_branch_named_by_the_description_is_text_only(self):
        # The reviewer's example: the rule is satisfied by one branch, the text names the denied one.
        rule = ["or", ["perm", "/vms/{vmid}", ["VM.PowerMgmt"]], ["perm", "/vms/{other}", ["VM.PowerMgmt"]]]
        bind = {"vmid": "SENTINEL", "other": "VM1"}   # SENTINEL: no grant; VM1 (pool guest): granted
        with_text = one_row(rule, "allow", bind=bind, desc="Needs 'VM.PowerMgmt' on /vms/{vmid}.")
        self.assertEqual((with_text["state"], with_text["verdict"], with_text["incomplete"]),
                         (pm.TEXT, "INCOMPLETE", True))
        control = one_row(rule, "allow", bind=bind)  # same rule, no description: decided by the check alone
        self.assertEqual((control["state"], control["verdict"], control["incomplete"]), (pm.ALLOW, "OK", False))
        denied_branch_only = ["perm", "/vms/{vmid}", ["VM.PowerMgmt"]]
        self.assertEqual(one_row(denied_branch_only, "deny", bind=bind)["verdict"], "OK")  # control

    def test_root_restriction_in_a_description_downgrades_the_verdict(self):
        r = one_row(GRANTED, "allow", desc="Access is limited to root@pam.")
        self.assertEqual(r["verdict"], "INCOMPLETE")
        self.assertTrue(any("root@pam" in n for n in r["notes"]))

    def test_a_denial_with_description_text_is_text_only_because_text_can_add_an_alternative(self):
        r = one_row(DENIED, "deny", desc="Also requires 'VM.PowerMgmt' on /vms/SENTINEL.")
        self.assertEqual((r["state"], r["verdict"]), (pm.TEXT, "INCOMPLETE"))
        self.assertEqual(one_row(DENIED, "deny", desc="")["verdict"], "OK")  # control: no text, decided alone

    # round 5: early denials follow the same policy
    def early(self, entry, expect="deny"):
        idx = {("/x", "POST"): entry}
        plan = mini([("X", "POST", "/x", {"vmid": "VM1"}, {"token": expect, "weak": expect})])
        return rows_by_id(pm.build_matrix(idx, plan), "token")["X"]

    def test_allowtoken_zero_with_description_text_or_an_unknown_form_is_not_complete(self):
        known = {"check": GRANTED}
        control = self.early({"allowtoken": 0, "permissions": known})
        self.assertEqual((control["state"], control["verdict"], control["incomplete"]), (pm.DENY, "OK", False))
        for label, perms in (("description", {**known, "description": "Alternatively available to pool members."}),
                             ("unknown form", {"check": UNKNOWN_FORM}),
                             ("unknown branch", {"check": ["or", UNKNOWN_FORM, GRANTED]})):
            with self.subTest(label):
                r = self.early({"allowtoken": 0, "permissions": perms})
                self.assertEqual((r["verdict"], r["incomplete"]), ("INCOMPLETE", True))
        r = self.early({"allowtoken": 0, "permissions": {**known, "description": "Alternatively available to pool members."}})
        self.assertEqual(r["state"], pm.TEXT)

    def test_root_only_with_description_text_or_an_unknown_form_is_not_complete(self):
        control = self.early({"permissions": {"user": "root@pam"}})
        self.assertEqual((control["state"], control["verdict"], control["incomplete"]), (pm.DENY, "OK", False))
        control = self.early({"permissions": {"user": "root@pam", "check": GRANTED}})
        self.assertEqual((control["state"], control["verdict"]), (pm.DENY, "OK"))
        for label, perms in (("description", {"user": "root@pam", "description": "Alternatively available to pool members."}),
                             ("unknown form", {"user": "root@pam", "check": UNKNOWN_FORM})):
            with self.subTest(label):
                r = self.early({"permissions": perms})
                self.assertEqual((r["verdict"], r["incomplete"]), ("INCOMPLETE", True))
        # a whitespace-only description is no text
        self.assertEqual(self.early({"permissions": {"user": "root@pam", "description": "  "}})["verdict"], "OK")

    def test_a_plan_expecting_allow_against_an_early_denial_is_still_a_definite_mismatch(self):
        r = self.early({"allowtoken": 0, "permissions": {"check": GRANTED}}, expect="allow")
        self.assertEqual(r["verdict"], "NARROWER")   # control: decisive when nothing is in doubt

    # (5) sweep uncertainty reaches the overall result
    def test_sweep_uncertainty_makes_the_overall_result_incomplete(self):
        rows = [{"verdict": "OK"}]
        decidable = {("/a", "GET"): {"permissions": {"user": "all"}}}
        sw = pm.sweep(decidable, plan_copy())
        self.assertTrue(sw["complete"])
        self.assertEqual(pm.overall(rows, [], sw), ("MATCH", 0))            # positive control
        doubtful = {**decidable, ("/b", "GET"): {"allowtoken": 1}}   # no 'permissions' key
        sw = pm.sweep(doubtful, plan_copy())
        self.assertFalse(sw["complete"])
        self.assertEqual(pm.overall(rows, [], sw), ("INCOMPLETE", 2))

    def test_sweep_counts_a_definite_outcome_that_rests_on_an_incomplete_rule(self):
        idx = {("/c", "POST"): {"permissions": {"check": ["or", UNKNOWN_FORM, GRANTED]}}}
        sw = pm.sweep(idx, plan_copy())
        self.assertEqual(sw["undecided"]["INCOMPLETE-RULE"], 1)
        self.assertFalse(sw["complete"])

    def test_cli_sweep_with_an_undecided_operation_is_not_a_match(self):
        tmp = fixtures.private_tmpdir()
        self.addCleanup(tmp.cleanup)
        plan = plan_copy()
        plan["operations"] = [o for o in plan["operations"] if o["id"] in ("S-OPEN", "S-ALL", "S-ALL-FOREIGN")]
        pf = Path(tmp.name) / "plan.json"
        pf.write_text(json.dumps(plan))
        code, out, _ = run_main(["--apidoc", str(APIDOC), "--plan", str(pf)])
        self.assertEqual(code, 0, out)                               # control without the sweep
        code, out, _ = run_main(["--apidoc", str(APIDOC), "--plan", str(pf), "--sweep"])
        self.assertEqual(code, 2, out)
        self.assertIn("sweep INCOMPLETE", out)

    # (8) both plan alternatives are encoded
    def test_rollback_plan_accepts_either_privilege(self):
        plan = pm.load_plan(None)
        plan["operations"] = [o for o in plan["operations"] if o["id"] == "P4b"]
        text = "You need 'VM.Snapshot' or 'VM.Snapshot.Rollback' on the guest."
        idx = {(plan["operations"][0]["path"], "POST"): {"permissions": {"user": "all", "description": text}}}
        for removed, expected in (("VM.Snapshot.Rollback", True), ("VM.Snapshot", True)):
            with self.subTest(removed=removed):
                p = copy.deepcopy(plan)
                p["roles"]["PVEVMAdmin"].remove(removed)
                row = pm.build_matrix(idx, pm.validate_plan(p), ["routine"])[0]
                self.assertIs(row["plan_only"]["satisfied"], expected)
                self.assertEqual(row["verdict"], "INCOMPLETE")        # text-only, never a pass
        p = copy.deepcopy(plan)  # control: neither privilege granted -> the plan itself is not satisfied
        p["roles"]["PVEVMAdmin"] = [x for x in p["roles"]["PVEVMAdmin"] if not x.startswith("VM.Snapshot")]
        row = pm.build_matrix(idx, pm.validate_plan(p), ["routine"])[0]
        self.assertEqual(row["verdict"], "NARROWER")
        self.assertEqual(len(pm.DEFAULT_PLAN["operations"][[o["id"] for o in pm.DEFAULT_PLAN["operations"]]
                                                       .index("P4b")]["any_of"]), 2)

    def test_download_url_plan_has_the_audit_plus_modify_alternative(self):
        plan = pm.load_plan(None)
        plan["operations"] = [o for o in plan["operations"] if o["id"] == "X2"]
        idx = {(plan["operations"][0]["path"], "POST"):
               {"permissions": {"user": "all", "description": "Needs Datastore.AllocateTemplate, Sys.Modify and "
                                                              "Sys.Audit on /, or Sys.AccessNetwork on the node."}}}
        row = pm.build_matrix(idx, pm.validate_plan(plan), ["routine"])[0]
        self.assertEqual(row["verdict"], "INCOMPLETE")               # control: plan denies it, text-only
        self.assertFalse(row["plan_only"]["satisfied"])
        p = copy.deepcopy(plan)  # grant only the SECOND alternative: Sys.Audit + Sys.Modify on /
        p["roles"]["PVEAuditor"].append("Sys.Modify")
        p["roles"]["PVEDatastoreUser"].append("Datastore.AllocateTemplate")
        row = pm.build_matrix(idx, pm.validate_plan(p), ["routine"])[0]
        self.assertTrue(row["plan_only"]["satisfied"])
        self.assertEqual(row["verdict"], "BROADER")
        self.assertNotIn("Sys.AccessNetwork", {r["priv"] for r in row["plan_only"]["detail"][1]
                                               if r["held"]})


class CliTests(unittest.TestCase):
    def test_text_report_and_exit_code(self):
        code, out, err = run_main(["--apidoc", str(APIDOC), "--plan", str(PLAN)])
        self.assertEqual(code, 1, err)  # S-NOMETHOD is a mismatch
        self.assertIn("RESULT: MISMATCH", out)
        self.assertIn("S-ALL", out)
        self.assertIn("apidoc-synthetic.js", out)
        self.assertNotIn(str(FIX), out)  # file name only, no absolute path

    def test_json_output_is_complete_and_deterministic(self):
        a = run_main(["--apidoc", str(APIDOC), "--plan", str(PLAN), "--sweep", "--format", "json"])
        b = run_main(["--apidoc", str(APIDOC), "--plan", str(PLAN), "--sweep", "--format", "json"])
        self.assertEqual(a, b)
        doc = json.loads(a[1])
        self.assertEqual(doc["status"], "MISMATCH")
        self.assertEqual(doc["meta"]["file"], "apidoc-synthetic.js")
        self.assertEqual(len(doc["meta"]["sha256"]), 64)
        self.assertIn("sweep", doc)
        self.assertEqual(len(doc["rows"]), 2 * len(plan_copy()["operations"]))

    def test_input_errors_exit_3_and_usage_errors_exit_3(self):
        code, _, err = run_main(["--apidoc", str(FIX / "does-not-exist.js")])
        self.assertEqual(code, 3)
        code, _, err = run_main([])
        self.assertEqual(code, 3)  # argparse would exit 2, which here means INCOMPLETE
        self.assertIn("--apidoc", err)

    def test_incomplete_exit_code_is_2(self):
        tmp = fixtures.private_tmpdir()
        self.addCleanup(tmp.cleanup)
        plan = plan_copy()
        plan["operations"] = [o for o in plan["operations"] if o["id"] in ("S-OPEN", "S-NOPERM")]
        plan["operations"][0]["expect"]["token"] = "allow"
        p = Path(tmp.name) / "plan.json"
        p.write_text(json.dumps(plan))
        code, out, _ = run_main(["--apidoc", str(APIDOC), "--plan", str(p)])
        self.assertEqual(code, 2)
        self.assertIn("RESULT: INCOMPLETE", out)
        self.assertIn("not a pass", out)

    def test_clean_plan_exit_code_is_0(self):
        tmp = fixtures.private_tmpdir()
        self.addCleanup(tmp.cleanup)
        plan = plan_copy()
        plan["operations"] = [o for o in plan["operations"] if o["id"] in ("S-OPEN", "S-ALL", "S-ALL-FOREIGN")]
        p = Path(tmp.name) / "plan.json"
        p.write_text(json.dumps(plan))
        code, out, _ = run_main(["--apidoc", str(APIDOC), "--plan", str(p)])
        self.assertEqual(code, 0, out)
        self.assertIn("RESULT: MATCH", out)

    def test_runs_as_a_module_with_a_minimal_environment(self):
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/nonexistent"}
        proc = subprocess.run([sys.executable, "-m", "lab_agent.privmatrix", "--apidoc", str(APIDOC),
                               "--plan", str(PLAN)], cwd=LAB_AGENT, env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("RESULT: MISMATCH", proc.stdout)

    def test_module_uses_only_the_standard_library_and_no_network_or_process_api(self):
        tree = ast.parse((LAB_AGENT / "lab_agent" / "privmatrix.py").read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add(node.module.split(".")[0])
        self.assertLessEqual(imported, {"argparse", "copy", "hashlib", "json", "re", "sys", "pathlib", "__future__"})
        for banned in ("socket", "urllib", "http", "subprocess", "ssl", "os", "eval", "exec"):
            self.assertNotIn(banned, imported)
        calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertNotIn("eval", calls)
        self.assertNotIn("exec", calls)
        self.assertNotIn("compile", calls)


if __name__ == "__main__":
    unittest.main()
