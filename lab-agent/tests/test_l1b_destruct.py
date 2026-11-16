"""Mission L1B, task LA-DESTRUCT: destructive-operation protection and fail-closed classification.

Closes R3-1 (sentinel VMID required and valid on both sides), R3-2 (positive controls and the
missing reference kinds in the host volume check), R3-3 (malformed input is a refusal), R3-4
(volume-name VMIDs: level 1 as strict as the host), F-E (two narrowed refusals), F-F (a local
binding of the inventory to its raw data) and OVR (the overrides digest bound into the manifest).

Offline only: synthetic RFC 5737 data, a fake API transport and stub Proxmox tools. Nothing here
shows how a real host behaves; every host-side result is the stub tools' answer.
"""

import contextlib
import copy
import io
import json
import os
import re
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from lab_agent import baseline, classify, cli, hostrun, inventory, manifest, pveapi
from lab_agent.config import load
from tests import fixtures
from tests.test_closeout_apply import SENTINEL_ITEM, ApplyHarness
from tests.test_closeout_round3 import LIB, MUTATING, STUBS, override, stub_state
from tests.test_inventory_manifest import EVIDENCE, classes, load_inventory


def collected():
    """What discover would write to raw.json, from the same fake transport."""
    transport = pveapi.FakeTransport(fixtures.api_routes())
    client = pveapi.Client("192.0.2.10", 8006, fixtures.TOKEN_ID, "x", transport)
    return inventory.collect(client, fixtures.NODE)


def make_lab_with(dir_, sentinel):
    """A lab whose settings carry ``sentinel`` verbatim (None = the line is absent)."""
    fixtures.make_lab(dir_)
    env = dir_ / "env"
    text = fixtures.env_text(dir_).replace(f"PVE_SENTINEL_VMID={fixtures.SENTINEL}\n",
                                           "" if sentinel is None else f"PVE_SENTINEL_VMID={sentinel}\n")
    env.write_text(text)
    os.chmod(env, 0o600)
    return load(env)


def add_volume(inv, volid, vmid, content="images"):
    inv = copy.deepcopy(inv)
    inv["volumes"].append({"id": f"volume/{volid}", "volid": volid, "storage": volid.split(":", 1)[0],
                           "content": content, "size": 1, "vmid": vmid})
    return inv


class CliHarness:
    def run_cli(self, main, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        self.assertNotIn("Traceback", err.getvalue())
        return code, out.getvalue(), err.getvalue()

    def write(self, name, obj):
        path = self.dir / name
        path.write_text(obj if isinstance(obj, str) else json.dumps(obj))
        return str(path)


class SentinelAgentSideTests(CliHarness, unittest.TestCase):
    """R3-1, agent side: no removal-capable path without a valid sentinel VMID (exit 2)."""

    BAD = ("0", "-1", "-9050", "abc", "09050", "9050.0", "99", "1000000000", "9050 x", "0x2f")

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)
        self.inv, _ = load_inventory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_invalid_sentinel_values_are_refused_by_the_parser(self):
        for value in (None, 0, -1, True, False, 9050.0, "0", "09050", "", " 9050", [9050], 99, 1000000000):
            with self.subTest(value=value), self.assertRaises(classify.ClassificationError):
                classify.sentinel_vmid(value)
        self.assertEqual((classify.sentinel_vmid(9050), classify.sentinel_vmid("9050"),
                          classify.sentinel_vmid("100"), classify.sentinel_vmid(999999999)),
                         (9050, 9050, 100, 999999999))

    def test_config_context_refuses_missing_and_invalid_settings(self):
        for value in (None,) + self.BAD:
            with self.subTest(value=value):
                cfg = make_lab_with(self.dir, value)
                with self.assertRaisesRegex(classify.ClassificationError, "PVE_SENTINEL_VMID|sentinel VMID"):
                    classify.config_context(cfg)
        self.assertEqual(classify.config_context(make_lab_with(self.dir, "9050"))["sentinel"], 9050)  # control

    def test_classify_itself_needs_a_valid_sentinel(self):
        kw = dict(pool=fixtures.POOL, agent_user=fixtures.AGENT_USER, lab_storage="corelab")
        for bad in (None, 0, -5, "9050x", True):
            with self.subTest(sentinel=bad), self.assertRaises(classify.ClassificationError):
                classify.classify(self.inv, sentinel=bad, **kw)
        self.assertIn("vm/9050", classify.classify(self.inv, sentinel=9050, **kw))  # control

    def test_cli_classify_exit_2_and_nothing_written(self):
        inv = self.write("inv.json", self.inv)
        for value in (None,) + self.BAD:
            cfg = make_lab_with(self.dir, value)
            out = self.dir / "cls.json"
            with self.subTest(value=value):
                self.cfg = cfg
                code, _o, err = self.run_cli(cli.main, "classify", "--inventory", inv, "--out", str(out))
                self.assertEqual(code, 2, err)
                self.assertIn("sentinel", err)
                self.assertFalse(out.exists())
        self.cfg = make_lab_with(self.dir, "9050")  # control: the same call succeeds with a valid value
        code, _o, err = self.run_cli(cli.main, "classify", "--inventory", inv, "--out", str(self.dir / "cls.json"))
        self.assertEqual(code, 1, err)  # 1 = the fixture's known VMID-range conflict, not a refusal
        self.assertTrue((self.dir / "cls.json").exists())

    def test_no_sentinel_mode_is_explicit_and_cannot_feed_a_manifest(self):
        cfg = make_lab_with(self.dir, None)
        ctx = classify.config_context(cfg, no_sentinel=True)
        self.assertEqual((ctx["sentinel"], ctx["no_sentinel"]), (None, True))
        cls = classify.classify(self.inv, **ctx)
        self.assertEqual(cls[classify.BINDING_ID]["class"], "UNKNOWN")
        self.assertIn("no-sentinel", cls[classify.BINDING_ID]["reason"])
        with self.assertRaisesRegex(classify.ClassificationError, "no-sentinel mode cannot propose a removal"):
            classify.classify(self.inv, overrides=EVIDENCE, **ctx)
        with self.assertRaisesRegex(manifest.ManifestError, "no sentinel binding"):
            manifest.build(self.inv, cls)
        # a hand-edit of the classification does not turn it into a usable one
        forged = dict(cls, **{"vm/105": {"class": "REMOVE_CANDIDATE", "reason": "forged evidence text"}})
        with self.assertRaisesRegex(manifest.ManifestError, "no sentinel binding"):
            manifest.build(self.inv, forged)
        # a value that is set but invalid is still refused in the named mode
        with self.assertRaises(classify.ClassificationError):
            classify.config_context(make_lab_with(self.dir, "0"), no_sentinel=True)
        # control: the strict classification of the same inventory does build
        manifest.build(self.inv, classes(self.inv, EVIDENCE))

    def test_manifest_without_a_valid_sentinel_is_refused_by_every_agent_command(self):
        good = manifest.build(self.inv, classes(self.inv, EVIDENCE))
        self.assertIn("sentinel VMID 9050", manifest.dry_run(good))
        for value in (None, 0, -1, True, "9050", 9050.0, 99):
            bad = copy.deepcopy(good)
            if value is None:
                del bad["sentinel_vmid"]
            else:
                bad["sentinel_vmid"] = value
            with self.subTest(value=value):
                with self.assertRaisesRegex(manifest.ManifestError, "sentinel_vmid"):
                    manifest.validate_structure(bad)
                code, out, err = self.run_cli(cli.main, "manifest", "dry-run", self.write("m.json", bad))
                self.assertEqual((code, out), (2, ""), err)
        code, out, _e = self.run_cli(cli.main, "manifest", "dry-run", self.write("ok.json", good))  # control
        self.assertEqual(code, 0)
        self.assertIn("vm/105", out)

    def test_manifest_cannot_name_the_sentinel_or_a_volume_that_carries_its_vmid(self):
        good = manifest.build(self.inv, classes(self.inv, EVIDENCE))
        bad = copy.deepcopy(good)
        bad["items"][0].update(SENTINEL_ITEM)
        with self.assertRaisesRegex(manifest.ManifestError, "vm/9050: classified PRESERVE .*sentinel guest 9050"):
            manifest.validate_structure(bad)
        # a classification forged by hand cannot get the sentinel into a draft either
        forged = classes(self.inv, EVIDENCE)
        forged["vm/9050"] = {"class": "REMOVE_CANDIDATE", "reason": "forged by hand, long enough"}
        with self.assertRaisesRegex(manifest.ManifestError, "vm/9050: classified PRESERVE"):
            manifest.build(self.inv, forged)

    def test_validate_refuses_a_classification_made_for_another_sentinel_or_none(self):
        m = manifest.build(self.inv, classes(self.inv, EVIDENCE))
        other = classify.classify(self.inv, pool=fixtures.POOL, agent_user=fixtures.AGENT_USER,
                                  lab_storage="corelab", sentinel=9051, overrides=EVIDENCE)
        with self.assertRaisesRegex(manifest.ManifestError, "built for sentinel VMID 9050, but .* has 9051"):
            manifest.validate(m, self.inv, other)
        stripped = {k: v for k, v in classes(self.inv, EVIDENCE).items() if k != classify.BINDING_ID}
        with self.assertRaisesRegex(manifest.ManifestError, "no sentinel binding"):
            manifest.validate(m, self.inv, stripped)
        with self.assertRaisesRegex(manifest.ManifestError, "no sentinel binding"):
            manifest.build(self.inv, stripped)
        manifest.validate(m, self.inv, classes(self.inv, EVIDENCE))  # control

    def test_the_binding_entry_is_not_an_overridable_resource(self):
        with self.assertRaisesRegex(classify.ClassificationError, "unknown resource"):
            classes(self.inv, {classify.BINDING_ID: {"class": "UNKNOWN"}})


class SentinelApplyPathTests(ApplyHarness, unittest.TestCase):
    """R3-1 on the owner path: refused before the dry-run lists anything, before render, before ssh."""

    def test_apply_refuses_an_invalid_sentinel_setting_before_the_dry_run(self):
        for value in (None, "0", "-3", "abc", "09050"):
            self.cfg = make_lab_with(self.dir, value)
            with self.subTest(value=value):
                self.assert_refused(self.m, "sentinel")  # also: no "Manifest for node" listing in the output

    def test_apply_dry_run_listing_needs_the_valid_setting(self):
        outcome, popen, _runner, out = self.attempt(self.m, answer="x\n")
        # control: a valid setting reaches the listing. Nothing follows it: execution is disabled.
        self.assertIsInstance(outcome, hostrun.HostRunError)
        self.assertIn("disabled in this version", str(outcome))
        self.assertIn("Manifest for node", out)
        self.cfg = make_lab_with(self.dir, "0")
        outcome, _popen, _runner, out = self.attempt(self.m)
        self.assertIsInstance(outcome, classify.ClassificationError)
        self.assertNotIn("Manifest for node", out)

    def test_apply_refuses_a_setting_that_differs_from_the_manifests_sentinel(self):
        self.cfg = make_lab_with(self.dir, "9051")
        self.assert_refused(self.m, "built for sentinel VMID 9050, but .* has 9051")

    def test_show_and_run_exit_2_with_nothing_on_stdout(self):
        self.cfg = make_lab_with(self.dir, "0")
        argv = ["show", "apply-manifest", "--manifest", self.write("m.json", self.m),
                "--inventory", self.write("i.json", self.inv), "--overrides", self.write("o.json", EVIDENCE)]
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = hostrun.main(argv)
        self.assertEqual((code, out.getvalue()), (2, ""))
        self.assertIn("sentinel", err.getvalue())


class OverridesBindingTests(ApplyHarness, unittest.TestCase):
    """OVR: the overrides are bound to the manifest at build time and checked at apply time."""

    def test_digest_is_canonical_and_none_means_empty(self):
        self.assertEqual(classify.overrides_digest(None), classify.overrides_digest({}))
        a = classify.overrides_digest({"x": {"class": "UNKNOWN", "evidence": "e"}, "y": {"class": "MODIFY"}})
        b = classify.overrides_digest({"y": {"class": "MODIFY"}, "x": {"evidence": "e", "class": "UNKNOWN"}})
        self.assertEqual(a, b)
        self.assertNotEqual(a, classify.overrides_digest({}))

    def test_build_copies_the_digest_and_dry_run_shows_it(self):
        self.assertEqual(self.m["overrides_digest"], classify.overrides_digest(EVIDENCE))
        self.assertIn(self.m["overrides_digest"], manifest.dry_run(self.m))

    def test_other_overrides_file_is_refused_at_apply(self):
        extra = dict(EVIDENCE, **{"ct/120": {"class": "MODIFY", "reason": "an additive change"}})
        self.assert_refused(self.m, "overrides digest is .*the overrides file changed", overrides=extra)

    def test_edited_evidence_text_is_refused_at_apply(self):
        edited = copy.deepcopy(EVIDENCE)
        edited["vm/105"]["evidence"] += " and then some more words"
        self.assert_refused(self.m, "overrides digest is", overrides=edited)

    def test_same_overrides_in_another_key_order_pass(self):
        reordered = {k: EVIDENCE[k] for k in reversed(list(EVIDENCE))}
        hostrun.render("apply-manifest", self.cfg, self.m, inventory=self.inv, overrides=reordered)

    def test_check_against_a_classification_from_other_overrides_is_refused(self):
        other = classes(self.inv, dict(EVIDENCE, **{"ct/120": {"class": "MODIFY", "reason": "x"}}))
        with self.assertRaisesRegex(manifest.ManifestError, "overrides digest is"):
            manifest.validate(self.m, self.inv, other)

    def test_manifest_needs_a_valid_digest(self):
        for value in (None, "", "abc", "G" * 64, 5):
            bad = copy.deepcopy(self.m)
            bad["overrides_digest"] = value
            with self.subTest(value=value), self.assertRaisesRegex(manifest.ManifestError, "overrides_digest"):
                manifest.validate_structure(bad)


class MalformedInputTests(CliHarness, unittest.TestCase):
    """R3-3: refusals of the type the callers already catch, never a traceback."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)
        self.inv, _ = load_inventory()
        self.good = manifest.build(self.inv, classes(self.inv, EVIDENCE))

    def tearDown(self):
        self.tmp.cleanup()

    def mutated(self, **item_changes):
        m = copy.deepcopy(self.good)
        m["items"][0].update(item_changes)
        return m

    def test_unhashable_values_in_checked_fields_are_refusals(self):
        cases = {"operation": [1], "backup": {"a": 1}, "reversible": [], "dependencies": [[1]],
                 "current_state": None}
        for field, value in cases.items():
            with self.subTest(field=field), self.assertRaises(manifest.ManifestError):
                manifest.validate_structure(self.mutated(**{field: value}))
        m = copy.deepcopy(self.good)
        m["items"][0]["current_state"]["status"] = ["stopped"]
        with self.assertRaisesRegex(manifest.ManifestError, "status is not a known state"):
            manifest.validate_structure(m)

    def test_nulls_do_not_pass_as_the_text_none(self):
        m = copy.deepcopy(self.good)
        m["node"] = None
        with self.assertRaisesRegex(manifest.ManifestError, "node is missing"):
            manifest.validate_structure(m)
        vol = manifest.build(self.inv, classes(self.inv, dict(EVIDENCE, **override("volume/corelab:iso/corelab-dummy.iso"))))
        item = next(i for i in vol["items"] if i["type"] == "volume")
        for key in ("storage", "node"):
            bad = copy.deepcopy(vol)
            next(i for i in bad["items"] if i["type"] == "volume")["current_state"][key] = None
            with self.subTest(key=key), self.assertRaisesRegex(manifest.ManifestError, "needs node and storage"):
                manifest.validate_structure(bad)
        bad = copy.deepcopy(vol)
        next(i for i in bad["items"] if i["type"] == "volume")["current_state"]["size"] = True
        with self.assertRaisesRegex(manifest.ManifestError, "size must be an integer"):
            manifest.validate_structure(bad)
        self.assertEqual(item["current_state"]["size"], 1048576)  # control

    def test_empty_guest_digest_is_refused(self):
        m = copy.deepcopy(self.good)
        m["items"][0]["current_state"]["digest"] = ""
        with self.assertRaisesRegex(manifest.ManifestError, "digest is missing or malformed"):
            manifest.validate_structure(m)

    def test_cli_exit_2_for_malformed_manifests(self):
        for name, m in (("a", self.mutated(operation=[1])), ("b", self.mutated(dependencies=[{}])),
                        ("c", dict(self.good, node=["x"]))):
            with self.subTest(name=name):
                code, out, err = self.run_cli(cli.main, "manifest", "dry-run", self.write(f"{name}.json", m))
                self.assertEqual((code, out), (2, ""), err)

    def test_classification_without_a_reason_or_with_an_unknown_class(self):
        cls = classes(self.inv, EVIDENCE)
        no_reason = copy.deepcopy(cls)
        del no_reason["vm/105"]["reason"]
        with self.assertRaisesRegex(manifest.ManifestError, "reason is empty"):
            manifest.build(self.inv, no_reason)
        for bad in ({"class": "REMOVE-CANDIDATE", "reason": "x"}, {"class": None}, {"class": ["UNKNOWN"]}):
            with self.subTest(bad=bad), self.assertRaisesRegex(manifest.ManifestError, "classification must be"):
                manifest.build(self.inv, dict(cls, **{"vm/105": bad}))
        code, _o, err = self.run_cli(cli.main, "manifest", "build", "--inventory", self.write("i.json", self.inv),
                                     "--classification", self.write("c.json", no_reason),
                                     "--out", str(self.dir / "m.json"))
        self.assertEqual(code, 2, err)

    def test_override_evidence_and_reason_must_be_text(self):
        for field, value in (("evidence", 5), ("evidence", ["long enough evidence"]), ("reason", {"a": 1}),
                             ("evidence", {"x": 1})):
            ov = {"vm/105": {"class": "UNKNOWN", field: value}}
            with self.subTest(field=field, value=value), self.assertRaisesRegex(classify.ClassificationError,
                                                                               "must be text"):
                classes(self.inv, ov)
        self.assertEqual(classes(self.inv, {"vm/105": {"class": "UNKNOWN", "evidence": None}})["vm/105"]["class"],
                         "UNKNOWN")  # control: null is the same as absent

    def test_baseline_compare_refuses_what_is_not_a_baseline(self):
        snap = baseline.snapshot(self.inv, fixtures.POOL)
        for stored in ([], "x", None, 5, {}, dict(snap, baseline_version=2), dict(snap, baseline_version=True),
                       {k: v for k, v in snap.items() if k != "baseline_version"}):
            with self.subTest(stored=str(stored)[:30]), self.assertRaises(baseline.BaselineError):
                baseline.compare(stored, snap)
        self.assertEqual(baseline.compare(snap, snap), [])  # control

    def test_cli_baseline_verify_exit_2_on_a_malformed_stored_baseline(self):
        inv = self.write("inv.json", self.inv)
        for name, stored in (("list", ["x"]), ("empty", {}), ("text", "abc")):
            with self.subTest(name=name):
                code, _o, err = self.run_cli(cli.main, "baseline", "verify", "--baseline",
                                             self.write(f"{name}.json", stored), "--inventory", inv)
                self.assertEqual(code, 2, err)
        snap = self.write("snap.json", baseline.snapshot(self.inv, fixtures.POOL))
        self.assertEqual(self.run_cli(cli.main, "baseline", "verify", "--baseline", snap, "--inventory", inv)[0], 0)

    def test_snapshot_survives_a_fingerprint_that_is_not_text(self):
        inv = copy.deepcopy(self.inv)
        inv["certificates"].append({"filename": "x.pem", "fingerprint": 12345})
        self.assertIn("12345", baseline.snapshot(inv, fixtures.POOL)["certificate_fingerprints"])

    def test_a_requested_removal_is_never_dropped_silently(self):
        ov = dict(EVIDENCE, **{"user/olduser@pve": {"class": "REMOVE_CANDIDATE", "evidence": "owner confirmed gone"}})
        cls = classes(self.inv, ov)
        self.assertEqual(cls["user/olduser@pve"]["class"], "REMOVE_CANDIDATE")
        with self.assertRaisesRegex(manifest.ManifestError, "user/olduser@pve: .*only guests and volumes"):
            manifest.build(self.inv, cls)
        ok = manifest.build(self.inv, classes(self.inv, EVIDENCE))  # control
        self.assertEqual([i["id"] for i in ok["items"]], ["vm/105", "vm/106"])

    def test_apply_with_a_non_object_inventory_is_a_refusal(self):
        for bad in ([], "x", None):
            with self.subTest(bad=bad), self.assertRaises(inventory.IncompleteInventoryError):
                manifest.validate_for_apply(self.good, bad, classes(self.inv, EVIDENCE))


class VolumeNameVmidTests(unittest.TestCase):
    """R3-4: level 1 reads every VMID in a volume name, as the host guard does."""

    def setUp(self):
        self.inv, _ = load_inventory()

    def test_all_vmids_are_extracted_in_order(self):
        self.assertEqual(inventory.volid_vmids("local:9050/base-9050-disk-0.qcow2/9101/vm-9101-disk-0.qcow2"),
                         [9050, 9101])
        self.assertEqual(inventory.volid_vmids("local:backup/vzdump-lxc-120-2025.tar.zst"), [120])
        self.assertEqual(inventory.volid_vmids("local:iso/old.iso"), [])
        self.assertEqual(inventory.volid_owner("local:9050/base-9050-disk-0.qcow2/9101/vm-9101-disk-0.qcow2"), 9101)

    def test_a_volume_that_names_the_sentinel_anywhere_is_preserved(self):
        volid = "local:9050/base-9050-disk-0.qcow2/9101/vm-9101-disk-0.qcow2"  # owner 9101 is in the pool
        inv = add_volume(self.inv, volid, 9101)
        self.assertEqual(inventory.inconsistencies(inv), [])
        self.assertEqual(classes(inv)[f"volume/{volid}"]["class"], "PRESERVE")
        with self.assertRaisesRegex(classify.ClassificationError, "PRESERVE cannot be overridden"):
            classes(inv, override(f"volume/{volid}"))

    def test_a_pool_volume_that_also_names_a_foreign_guest_is_not_reuse(self):
        volid = "local:105/base-105-disk-0.qcow2/9101/vm-9101-disk-0.qcow2"
        inv = add_volume(self.inv, volid, 9101)
        self.assertEqual(classes(inv)[f"volume/{volid}"]["class"], "UNKNOWN")
        own = add_volume(self.inv, "local:9100/base-9100-disk-0.qcow2/9101/vm-9101-disk-0.qcow2", 9101)
        self.assertEqual(classes(own)["volume/local:9100/base-9100-disk-0.qcow2/9101/vm-9101-disk-0.qcow2"]["class"],
                         "REUSE")  # control: every VMID named belongs to the pool

    def test_a_manifest_cannot_carry_such_a_volume(self):
        volid = "corelab:9050/base-9050-disk-0.qcow2/9101/vm-9101-disk-0.qcow2"
        m = manifest.build(self.inv, classes(self.inv, dict(EVIDENCE, **override("volume/corelab:iso/corelab-dummy.iso"))))
        vol = next(i for i in m["items"] if i["type"] == "volume")
        bad = copy.deepcopy(m)
        next(i for i in bad["items"] if i["type"] == "volume")["id"] = f"volume/{volid}"
        with self.assertRaisesRegex(manifest.ManifestError, "name carries the sentinel VMID 9050"):
            manifest.validate_structure(bad)
        self.assertEqual(vol["id"], "volume/corelab:iso/corelab-dummy.iso")  # control

    def test_level_one_and_the_host_agree_on_every_name(self):
        """The same names through both levels: a sentinel verdict at one is a sentinel verdict at the other."""
        names = [("local-lvm:vm-9050-disk-0", 9050, "images"), ("local:backup/vzdump-qemu-9050-2025_01_01.vma.zst",
                                                                  9050, "backup"),
                 ("local:9050/base-9050-disk-0.qcow2/9101/vm-9101-disk-0.qcow2", 9101, "images"),
                 ("local:iso/vm-9050-notes.iso", None, "iso"), ("local-lvm:vm-777-disk-0", 777, "images"),
                 ("local:iso/plain.iso", None, "iso")]
        tmp = fixtures.private_tmpdir()
        self.addCleanup(tmp.cleanup)
        for volid, vmid, content in names:
            inv = add_volume(self.inv, volid, vmid, content)
            level1 = classes(inv)[f"volume/{volid}"]["class"] == "PRESERVE"
            state = stub_state()
            state["content"].setdefault(volid.split(":")[0], []).append(
                {"volid": volid, "content": content, "size": 1, **({"vmid": vmid} if vmid else {})})
            proc = run_guard(Path(tmp.name), f"cl_guard_volume {volid.split(':')[0]} {volid}", state)
            host = proc.returncode == 6 and "sentinel guest 9050" in proc.stderr
            with self.subTest(volid=volid):
                self.assertEqual(level1, host, proc.stderr)


class InventoryNarrowingTests(unittest.TestCase):
    """F-E: two refusals of legitimate inventories narrowed; each narrowed rule is still fail-closed."""

    def setUp(self):
        self.inv, _ = load_inventory()

    def test_iso_with_a_guest_like_name_and_no_owner_is_accepted(self):
        inv = add_volume(self.inv, "local:iso/vm-77-notes.iso", None, "iso")
        self.assertEqual(inventory.inconsistencies(inv), [])
        inventory.require_complete(inv, "classify")
        self.assertEqual(classes(inv)["volume/local:iso/vm-77-notes.iso"]["class"], "UNKNOWN")  # never REUSE

    def test_the_narrowing_is_only_for_free_form_content_with_no_owner(self):
        for volid, vmid, content in (("local-lvm:vm-77-disk-0", None, "images"),      # an image names its owner
                                     ("local:iso/vm-77-notes.iso", 9101, "iso"),       # an owner that disagrees
                                     ("local:iso/vm-77-notes.iso", None, None),        # content not stated
                                     ("local:backup/vzdump-qemu-77-x.vma.zst", None, "backup")):
            inv = add_volume(self.inv, volid, vmid, content)
            with self.subTest(volid=volid, vmid=vmid, content=content):
                self.assertTrue(any("but the volid names VMID 77" in p for p in inventory.inconsistencies(inv)))

    def test_unread_acl_or_certificates_no_longer_block_classify_manifest_or_vmid_range(self):
        for section in ("acl", "certificates"):
            inv = copy.deepcopy(self.inv)
            inv[section] = []
            inv["errors"]["/access/acl" if section == "acl" else f"/nodes/{fixtures.NODE}/certificates/info"] = "403"
            with self.subTest(section=section):
                for purpose in ("vmid-range", "classify", "manifest"):
                    inventory.require_complete(inv, purpose)
                self.assertIn("vm/105", classes(inv, EVIDENCE))
                manifest.build(inv, classes(inv, EVIDENCE))
                conflicts = classify.vmid_range_conflicts(inv, 9100, 9199, fixtures.POOL)
                self.assertTrue(len(conflicts) == 1 and "9150" in conflicts[0])
                with self.assertRaisesRegex(inventory.IncompleteInventoryError, f"{section} is empty"):
                    inventory.require_complete(inv, "baseline")  # the baseline still needs them

    def test_the_other_emptiness_checks_and_unread_endpoints_still_refuse(self):
        for section in ("users", "tokens", "storages", "network"):
            inv = copy.deepcopy(self.inv)
            inv[section] = []
            for purpose in ("vmid-range", "classify", "manifest"):
                with self.subTest(section=section, purpose=purpose), \
                        self.assertRaisesRegex(inventory.IncompleteInventoryError, f"{section} is empty"):
                    inventory.require_complete(inv, purpose)
        inv = copy.deepcopy(self.inv)  # an unread endpoint a purpose depends on is still named
        inv["errors"][f"/nodes/{fixtures.NODE}/qemu/105/config"] = "403 denied"
        with self.assertRaisesRegex(inventory.IncompleteInventoryError, "not read: .*qemu/105/config"):
            inventory.require_complete(inv, "manifest")

    def test_unread_pools_is_still_refused_but_now_says_which_endpoint(self):
        inv = copy.deepcopy(self.inv)
        inv["pools"] = []
        inv["errors"]["/pools"] = "403 denied"
        with self.assertRaisesRegex(inventory.IncompleteInventoryError,
                                    r"pool 'corelab' is not in pools.*endpoints recorded as not read: .*/pools"):
            inventory.require_complete(inv, "vmid-range")


class RawBindingTests(unittest.TestCase):
    """F-F: a digest and a re-derivation bind the inventory to the raw data recorded by discover.

    A same-user file can be rewritten together with its digest, so none of this is tamper
    resistance; it catches one-sided edits and mistakes."""

    def setUp(self):
        self.raw = collected()
        self.inv = inventory.normalize(self.raw)

    def test_genuine_pair_verifies_and_digest_is_recorded(self):
        self.assertRegex(self.inv["raw_digest"], r"^[0-9a-f]{64}$")
        self.assertEqual(inventory.verify_against_raw(self.inv, self.raw), [])
        self.assertEqual(inventory.verify_against_raw(self.inv, json.loads(json.dumps(self.raw))), [])  # via file

    def test_one_sided_edits_are_detected(self):
        emptied = dict(copy.deepcopy(self.inv), errors={})
        self.assertTrue(any("errors differs" in p for p in inventory.verify_against_raw(emptied, self.raw)))
        renamed = dict(copy.deepcopy(self.inv), node="other-node")
        self.assertTrue(inventory.verify_against_raw(renamed, self.raw))
        no_guests = dict(copy.deepcopy(self.inv), guests=[])
        self.assertTrue(any("guests differs" in p for p in inventory.verify_against_raw(no_guests, self.raw)))
        raw_edited = copy.deepcopy(self.raw)
        raw_edited["errors"] = {}
        self.assertTrue(any("raw_digest differs" in p for p in inventory.verify_against_raw(self.inv, raw_edited)))
        no_digest = {k: v for k, v in self.inv.items() if k != "raw_digest"}
        self.assertTrue(any("no raw_digest" in p for p in inventory.verify_against_raw(no_digest, self.raw)))
        self.assertTrue(inventory.verify_against_raw(self.inv, {"node": "x"}))  # raw that does not normalize

    def test_a_pair_edited_consistently_passes_which_is_the_stated_limit(self):
        raw = copy.deepcopy(self.raw)
        raw["errors"] = {}
        self.assertEqual(inventory.verify_against_raw(inventory.normalize(raw), raw), [])

    def test_the_digest_must_be_well_formed_when_present(self):
        for bad in (5, "abc", "G" * 64, None):
            inv = dict(copy.deepcopy(self.inv), raw_digest=bad)
            with self.subTest(bad=bad), self.assertRaisesRegex(inventory.IncompleteInventoryError, "raw_digest"):
                inventory.require_complete(inv, "classify")

    def test_the_inventory_digest_follows_the_raw_digest(self):
        other = copy.deepcopy(self.raw)
        other["raw"]["/version"] = {"version": "9.9.9"}
        self.assertNotEqual(inventory.digest(inventory.normalize(other)), inventory.digest(self.inv))


def run_guard(dir_, command, state, **env):
    """Run LIB plus ``command`` under the stub tools; return the CompletedProcess."""
    (dir_ / "state.json").write_text(json.dumps(state))
    (dir_ / "calls.log").write_text("")
    exports = {"CL_SENTINEL_VMID": str(fixtures.SENTINEL), "CL_POOL": fixtures.POOL, "CL_NODE": fixtures.NODE}
    exports.update(env)
    lines = ["set -euo pipefail"] + [f"export {k}={v}" for k, v in exports.items() if v is not None]
    script = "\n".join(lines) + "\n" + LIB.read_text() + "\n" + command + "\n"
    proc_env = {"PATH": f"{STUBS}:/usr/bin:/bin", "STUB_STATE": str(dir_ / "state.json"),
                "STUB_LOG": str(dir_ / "calls.log")}
    # destructive execution is disabled in the shipped text: the guards run in a test-only copy
    proc = subprocess.run(["bash", "-s"], input=fixtures.for_stub_run(script), text=True, capture_output=True,
                          env=proc_env)
    proc.calls = [json.loads(line) for line in (dir_ / "calls.log").read_text().splitlines()]
    proc.mutating = [c for c in proc.calls if c[0] in MUTATING]
    return proc


class HostBase(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)
        self.inv, _ = load_inventory()

    def tearDown(self):
        self.tmp.cleanup()

    def guard(self, command, state=None, autolist=True, **env):
        """Run ``command``; a ``cl_guard_volume STORAGE VOLID`` in it gets its volume into the storage
        listing first (the guard refuses a volume the host's listing does not show), unless ``autolist``
        is False."""
        state = state or stub_state()
        if autolist:
            for storage, volid in re.findall(r"^cl_guard_volume ([a-z][a-z0-9_.-]*) ([A-Za-z0-9][A-Za-z0-9_.-]*:\S+)$", command, re.M):
                if not any(v["volid"] == volid for v in state["content"].get(storage, [])):
                    state["content"].setdefault(storage, []).append({"volid": volid, "content": "images", "size": 1})
        return run_guard(self.dir, command, state, **env)

    def with_config(self, vmid, **fields):
        state = stub_state()
        state["configs"][str(vmid)].update(fields)
        return state

    def refused(self, proc, pattern, code=6):
        self.assertEqual(proc.returncode, code, proc.stderr)
        self.assertRegex(proc.stderr, pattern)
        self.assertEqual(proc.mutating, [])


class HostSentinelTests(HostBase):
    """R3-1, host side."""

    def test_invalid_sentinel_in_the_environment_is_refused_by_every_guard(self):
        for value in ("0", "00", "000", "-5", "abc", "09050", "9050 ", "12", "1000000000", ""):
            for cmd in ("cl_guard_guest qemu 105 ''", "cl_guard_volume corelab corelab:iso/corelab-dummy.iso",
                        "cl_expect_sentinel 9050"):
                with self.subTest(value=value, cmd=cmd[:18]):
                    self.refused(self.guard(cmd, CL_SENTINEL_VMID=f"'{value}'"), "CL_SENTINEL_VMID is not set to a valid")
        proc = self.guard("cl_guard_guest qemu 105 ''")  # control: the valid value passes the same call
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_expect_sentinel_compares_with_the_manifest(self):
        self.refused(self.guard("cl_expect_sentinel 9051"), "built for sentinel VMID 9051, but the settings say 9050")
        self.assertEqual(self.guard("cl_expect_sentinel 9050").returncode, 0)

    def test_the_rendered_script_stops_first_when_the_settings_changed(self):
        script = hostrun.render("apply-manifest", self.cfg, manifest.build(self.inv, classes(self.inv, EVIDENCE)),
                                inventory=self.inv, overrides=EVIDENCE)
        self.assertTrue(script.index("cl_expect_sentinel 9050") < script.index("cl_guard_guest qemu"))
        for value in ("0", "9051"):
            changed = script.replace(f"export CL_SENTINEL_VMID={fixtures.SENTINEL}", f"export CL_SENTINEL_VMID={value}")
            self.assertNotEqual(changed, script)
            (self.dir / "state.json").write_text(json.dumps(stub_state()))
            (self.dir / "calls.log").write_text("")
            env = {"PATH": f"{STUBS}:/usr/bin:/bin", "STUB_STATE": str(self.dir / "state.json"),
                   "STUB_LOG": str(self.dir / "calls.log")}
            proc = subprocess.run(["bash", "-s"], input=fixtures.for_stub_run(changed), text=True,
                                  capture_output=True, env=env)
            calls = [json.loads(line) for line in (self.dir / "calls.log").read_text().splitlines()]
            with self.subTest(value=value):
                self.assertEqual(proc.returncode, 6, proc.stderr)
                self.assertEqual([c for c in calls if c[0] in MUTATING], [])
        (self.dir / "calls.log").write_text("")  # control: the unchanged script runs to the end
        proc = subprocess.run(["bash", "-s"], input=fixtures.for_stub_run(script), text=True, capture_output=True,
                              env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)


class HostListingControlTests(HostBase):
    """R3-2: an empty, null or unparsable listing with exit status 0 stops the run with exit 6."""

    BAD = ("null", "", "[]", "{}", "{not json", "0")
    VOLUME = "corelab:iso/corelab-dummy.iso"

    def test_control_everything_readable_passes(self):
        proc = self.guard(f"cl_guard_volume corelab {self.VOLUME}")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("passed the live safety checks", proc.stderr)

    def test_bad_guest_listing_is_refused(self):
        for text in self.BAD:
            state = stub_state()
            state["raw"] = {"/cluster/resources": text}
            with self.subTest(text=text):
                self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "guest listing")
                self.refused(self.guard("cl_guard_guest qemu 105 ''", state), "guest listing")

    def test_bad_storage_listing_is_refused(self):
        for text in self.BAD:
            state = stub_state()
            state["raw"] = {f"/nodes/{fixtures.NODE}/storage/corelab/content": text}
            with self.subTest(text=text):
                self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "listing of corelab")

    def test_bad_guest_config_is_refused(self):
        for text in ("null", "", "[]", "{}", "{not json"):
            state = stub_state()
            state["raw"] = {f"/nodes/{fixtures.NODE}/qemu/105/config": text}
            with self.subTest(text=text):
                self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "config of pve-test/qemu/105")

    def test_bad_snapshot_listing_and_config_are_refused(self):
        for text in ("null", "", "[]", "{}", "{not json"):
            state = stub_state()
            state["raw"] = {f"/nodes/{fixtures.NODE}/qemu/106/snapshot": text}
            with self.subTest(text=text):
                self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "snapshot listing of")
        state = stub_state()
        state["snapshots"] = {"106": {"snap1": {"scsi0": "local-lvm:vm-106-disk-0,size=16G"}}}
        state["raw"] = {f"/nodes/{fixtures.NODE}/qemu/106/snapshot/snap1/config": "null"}
        self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "snapshot snap1 of")
        state["raw"] = {}  # control: the same snapshot, readable
        self.assertEqual(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state).returncode, 0)

    def test_unsafe_snapshot_name_is_refused(self):
        state = stub_state()
        state["raw"] = {f"/nodes/{fixtures.NODE}/qemu/106/snapshot": json.dumps([{"name": "current"}, {"name": "../x"}])}
        self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "not path-safe")

    def test_sentinel_name_wins_even_when_every_listing_is_bad(self):
        state = stub_state()
        state["raw"] = {"/cluster/resources": "null", f"/nodes/{fixtures.NODE}/storage/local-lvm/content": "null"}
        self.refused(self.guard("cl_guard_volume local-lvm local-lvm:vm-9050-disk-0", state), "sentinel guest 9050")

    def test_the_full_script_stops_before_any_change(self):
        script = hostrun.render("apply-manifest", self.cfg,
                                manifest.build(self.inv, classes(self.inv, dict(EVIDENCE, **override(
                                    "volume/corelab:iso/corelab-dummy.iso")))),
                                inventory=self.inv, overrides=dict(EVIDENCE, **override(
                                    "volume/corelab:iso/corelab-dummy.iso")))
        state = stub_state()
        state["raw"] = {"/cluster/resources": "null"}
        proc = self.guard(script, state)
        self.refused(proc, "guest listing")
        state["raw"] = {}
        proc = self.guard(script, state)  # control: the same script with readable listings
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(["pvesm", "free", "corelab:iso/corelab-dummy.iso"], proc.mutating)

    def test_verification_does_not_read_an_unreadable_listing_as_absent(self):
        for text in ("null", "", "{not json", "{}"):
            state = stub_state()
            state["raw"] = {"/cluster/resources": text}
            with self.subTest(text=text):
                proc = self.guard("cl_verify_guest_absent 105", state)
                self.assertEqual(proc.returncode, 5, proc.stderr)
        state = stub_state()
        state["raw"] = {f"/nodes/{fixtures.NODE}/storage/corelab/content": "null"}
        self.assertEqual(self.guard(f"cl_verify_volume_absent corelab {self.VOLUME}", state).returncode, 5)
        # controls: a readable listing says "still present" (5) or, once gone, passes (0)
        self.assertEqual(self.guard("cl_verify_guest_absent 105").returncode, 5)
        state = stub_state()
        state["resources"] = [r for r in state["resources"] if r.get("vmid") != 105]
        self.assertEqual(self.guard("cl_verify_guest_absent 105", state).returncode, 0)
        state = stub_state()
        state["content"]["corelab"] = []
        self.assertEqual(self.guard(f"cl_verify_volume_absent corelab {self.VOLUME}", state).returncode, 0)


class HostReferenceKindTests(HostBase):
    """R3-2: the three reference kinds the volume check missed, each with its positive control."""

    def test_cicustom_values_of_every_key(self):
        for key in ("user", "network", "meta", "vendor"):
            volid = f"corelab:snippets/{key}.yaml"
            state = self.with_config(106, cicustom=f"user=corelab:snippets/user.yaml,network=corelab:snippets/network.yaml,"
                                                   f"meta=corelab:snippets/meta.yaml,vendor=corelab:snippets/vendor.yaml")
            with self.subTest(key=key):
                self.refused(self.guard(f"cl_guard_volume corelab {volid}", state),
                             "used by guest pve-test/qemu/106")
                self.assertEqual(self.guard(f"cl_guard_volume corelab corelab:snippets/{key}-other.yaml",
                                            state).returncode, 0)  # control: another snippet is free

    def test_file_equals_reference(self):
        state = self.with_config(106, scsi1="file=local-lvm:vm-777-disk-0,size=1G",
                                 ide3="file=corelab:iso/extra.iso,media=cdrom", scsi2="local-lvm:vm-778-disk-0,size=1G")
        for volid, storage in (("local-lvm:vm-777-disk-0", "local-lvm"), ("corelab:iso/extra.iso", "corelab")):
            with self.subTest(volid=volid):
                self.refused(self.guard(f"cl_guard_volume {storage} {volid}", state), "used by guest pve-test/qemu/106")
        self.refused(self.guard("cl_guard_volume local-lvm local-lvm:vm-778-disk-0", state), "used by guest")  # old form
        self.assertEqual(self.guard("cl_guard_volume local-lvm local-lvm:vm-779-disk-0", state).returncode, 0)

    def test_import_from_reference(self):
        state = self.with_config(106, scsi1="local-lvm:0,import-from=corelab:import/disk.qcow2")
        self.refused(self.guard("cl_guard_volume corelab corelab:import/disk.qcow2", state), "used by guest")

    def test_snapshot_vmstate_volume(self):
        state = stub_state()
        state["snapshots"] = {"106": {"snap1": {"vmstate": "local-lvm:vm-106-state-snap1",
                                                "scsi0": "local-lvm:vm-106-disk-0,size=16G"}}}
        proc = self.guard("cl_guard_volume local-lvm local-lvm:vm-106-state-snap1", state)
        self.refused(proc, "used by snapshot snap1 of guest pve-test/qemu/106")
        # control 1: the same volume with no snapshot recorded is not found in use
        self.assertEqual(self.guard("cl_guard_volume local-lvm local-lvm:vm-106-state-snap1").returncode, 0)
        # control 2: a different volume with the snapshot present
        self.assertEqual(self.guard("cl_guard_volume local-lvm local-lvm:vm-106-state-snap2", state).returncode, 0)

    def test_snapshot_reference_in_a_container(self):
        state = stub_state()
        state["snapshots"] = {"120": {"pre": {"mp0": "local-lvm:vm-120-disk-1,mp=/data"}}}
        self.refused(self.guard("cl_guard_volume local-lvm local-lvm:vm-120-disk-1", state),
                     "used by snapshot pre of guest pve-test/lxc/120")

    def test_linked_clone_path_prefix_still_matches(self):
        state = self.with_config(106, scsi1="local:9100/base-9100-disk-0.qcow2/106/vm-106-disk-0.qcow2,size=1G")
        self.refused(self.guard("cl_guard_volume local local:9100/base-9100-disk-0.qcow2", state), "used by guest")

    def test_in_pool_guests_are_not_scanned(self):
        state = self.with_config(9101, cicustom="user=corelab:snippets/pool.yaml")
        self.assertEqual(self.guard("cl_guard_volume corelab corelab:snippets/pool.yaml", state).returncode, 0)


class StubSelfTests(HostBase):
    """The new stub features behave as documented, so the tests above mean what they say."""

    def test_stub_snapshot_listing_and_raw_override(self):
        state = stub_state()
        state["snapshots"] = {"106": {"a": {"x": "1"}}}
        state["raw"] = {"/cluster/resources": "null"}
        (self.dir / "state.json").write_text(json.dumps(state))
        (self.dir / "calls.log").write_text("")
        env = {"PATH": f"{STUBS}:/usr/bin:/bin", "STUB_STATE": str(self.dir / "state.json"),
               "STUB_LOG": str(self.dir / "calls.log")}
        run = lambda *a: subprocess.run(["pvesh", "get", *a], capture_output=True, text=True, env=env)  # noqa: E731
        self.assertEqual(json.loads(run(f"/nodes/{fixtures.NODE}/qemu/106/snapshot").stdout),
                         [{"name": "current"}, {"name": "a"}])
        self.assertEqual(json.loads(run(f"/nodes/{fixtures.NODE}/qemu/106/snapshot/a/config").stdout), {"x": "1"})
        self.assertEqual(json.loads(run(f"/nodes/{fixtures.NODE}/qemu/105/snapshot").stdout), [{"name": "current"}])
        self.assertEqual(run(f"/nodes/{fixtures.NODE}/qemu/106/snapshot/zz/config").returncode, 9)
        raw = run("/cluster/resources")
        self.assertEqual((raw.returncode, raw.stdout), (0, "null"))


if __name__ == "__main__":
    unittest.main()
