import copy
import json
import os
import subprocess
import unittest
from pathlib import Path

from lab_agent import baseline, classify, hostrun, inventory, manifest, pveapi
from tests import fixtures

STUBS = Path(__file__).resolve().parent / "stubs"
LIB = Path(__file__).resolve().parent.parent / "host" / "lib.sh"


def load_inventory():
    transport = pveapi.FakeTransport(fixtures.api_routes())
    client = pveapi.Client("192.0.2.10", 8006, fixtures.TOKEN_ID, "x", transport)
    return inventory.normalize(inventory.collect(client, fixtures.NODE)), transport


def classes(inv, overrides=None):
    return classify.classify(inv, pool=fixtures.POOL, agent_user=fixtures.AGENT_USER, lab_storage="corelab",
                             sentinel=fixtures.SENTINEL, overrides=overrides)


EVIDENCE = {"vm/105": {"class": "REMOVE_CANDIDATE", "evidence": "old k8s lab node, stopped since 2025, owner confirmed"},
            "vm/106": {"class": "REMOVE_CANDIDATE", "evidence": "old web lab guest, owner confirmed obsolete"}}


class InventoryTests(unittest.TestCase):
    def test_collect_is_get_only_and_records_errors(self):
        inv, transport = load_inventory()
        self.assertEqual({c[0] for c in transport.calls}, {"GET"})
        self.assertIn("/cluster/firewall/options", inv["errors"])
        self.assertTrue(inv["errors"]["/cluster/firewall/options"].startswith("403"))

    def test_normalize(self):
        inv, _ = load_inventory()
        ids = {g["id"] for g in inv["guests"]}
        self.assertEqual(ids, {"vm/105", "vm/106", "vm/9050", "vm/9100", "vm/9101", "ct/120"})
        g105 = next(g for g in inv["guests"] if g["id"] == "vm/105")
        self.assertEqual(g105["digest"], "a" * 40)
        self.assertEqual(g105["disks"], ["local-lvm:vm-105-disk-0"])
        g106 = next(g for g in inv["guests"] if g["id"] == "vm/106")
        self.assertNotIn("local:iso/old.iso", g106["disks"])  # CD-ROM is not a disk
        backup = next(v for v in inv["volumes"] if "9150" in v["volid"])
        self.assertEqual(backup["vmid"], 9150)
        self.assertEqual(inv["pve_version"], "9.1.1")

    def test_digest_ignores_collection_time(self):
        inv, _ = load_inventory()
        other = dict(inv, collected_at="1999-01-01T00:00:00+00:00")
        self.assertEqual(inventory.digest(inv), inventory.digest(other))


class ClassifyTests(unittest.TestCase):
    def setUp(self):
        self.inv, _ = load_inventory()

    def test_defaults_are_conservative(self):
        c = classes(self.inv)
        self.assertEqual(c["vm/105"]["class"], "UNKNOWN")  # outside the pool is not evidence
        self.assertEqual(c["vm/9101"]["class"], "REUSE")
        self.assertEqual(c["vm/9050"]["class"], "PRESERVE")
        self.assertEqual(c["iface/vmbr0"]["class"], "PRESERVE")
        self.assertEqual(c["disk//dev/sda"]["class"], "PRESERVE")
        self.assertEqual(c["disk//dev/sdb"]["class"], "UNKNOWN")
        self.assertEqual(c["user/root@pam"]["class"], "PRESERVE")
        self.assertEqual(c["storage/local"]["class"], "PRESERVE")
        self.assertNotIn("REMOVE_CANDIDATE", {v["class"] for v in c.values()})

    def test_remove_candidate_needs_evidence(self):
        with self.assertRaisesRegex(classify.ClassificationError, "evidence"):
            classes(self.inv, {"vm/105": {"class": "REMOVE_CANDIDATE", "evidence": "old"}})
        c = classes(self.inv, EVIDENCE)
        self.assertEqual(c["vm/105"]["class"], "REMOVE_CANDIDATE")

    def test_preserve_and_unknown_ids_cannot_be_overridden(self):
        with self.assertRaisesRegex(classify.ClassificationError, "PRESERVE"):
            classes(self.inv, {"vm/9050": {"class": "REMOVE_CANDIDATE", "evidence": "x" * 20}})
        with self.assertRaisesRegex(classify.ClassificationError, "unknown resource"):
            classes(self.inv, {"vm/777": {"class": "UNKNOWN"}})

    def test_vmid_range_conflicts(self):
        conflicts = classify.vmid_range_conflicts(self.inv, 9100, 9199, fixtures.POOL)
        self.assertEqual(len(conflicts), 1)
        self.assertIn("9150", conflicts[0])
        self.assertEqual(classify.vmid_range_conflicts(self.inv, 9200, 9299, fixtures.POOL), [])


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.inv, _ = load_inventory()
        self.cls = classes(self.inv, EVIDENCE)
        self.m = manifest.build(self.inv, self.cls)

    def test_build_and_validate(self):
        self.assertEqual([i["id"] for i in self.m["items"]], ["vm/105", "vm/106"])
        self.assertEqual(self.m["items"][1]["operation"], "stop-and-delete-purge")  # 106 is running
        manifest.validate(self.m, self.inv, self.cls)

    def test_hash_is_canonical(self):
        reordered = json.loads(json.dumps(self.m, sort_keys=False))
        reordered = {k: reordered[k] for k in reversed(list(reordered))}
        self.assertEqual(manifest.manifest_hash(self.m), manifest.manifest_hash(reordered))
        changed = copy.deepcopy(self.m)
        changed["items"][0]["reason"] += "!"
        self.assertNotEqual(manifest.manifest_hash(self.m), manifest.manifest_hash(changed))

    def test_unknown_resource_cannot_be_deleted(self):
        bad = copy.deepcopy(self.m)
        bad["items"].append(dict(copy.deepcopy(self.m["items"][0]), id="ct/120", type="lxc",
                                 current_state={"node": fixtures.NODE, "name": "old-ct", "status": "stopped",
                                                "digest": "f" * 40, "template": False}))
        with self.assertRaisesRegex(manifest.ManifestError, "classified UNKNOWN"):
            manifest.validate(bad, self.inv, self.cls)

    def test_preserve_resource_cannot_be_deleted(self):
        bad = copy.deepcopy(self.m)
        bad["items"][0].update(id="vm/9050", current_state={"node": fixtures.NODE, "name": "corelab-sentinel",
                                                           "status": "stopped", "digest": "c" * 40,
                                                           "template": False})
        with self.assertRaisesRegex(manifest.ManifestError, "classified PRESERVE"):
            manifest.validate(bad, self.inv, self.cls)

    def test_state_change_detected(self):
        fresh = copy.deepcopy(self.inv)
        next(g for g in fresh["guests"] if g["id"] == "vm/105")["digest"] = "9" * 40
        problems = manifest.revalidate(self.m, fresh)
        self.assertEqual(len(problems), 1)
        self.assertIn("digest", problems[0])
        with self.assertRaises(manifest.ManifestError):
            manifest.validate(self.m, fresh, self.cls)
        gone = copy.deepcopy(self.inv)
        gone["guests"] = [g for g in gone["guests"] if g["id"] != "vm/106"]
        self.assertIn("vm/106: no longer exists", manifest.revalidate(self.m, gone))

    def test_injection_attempts_rejected(self):
        for field, value in (("id", "vm/105; rm -rf /"), ("id", "vm/105\nreboot"), ("id", "../etc")):
            bad = copy.deepcopy(self.m)
            bad["items"][0][field] = value
            with self.assertRaises(manifest.ManifestError):
                manifest.validate_structure(bad)
        bad = copy.deepcopy(self.m)
        bad["items"][0]["current_state"]["name"] = "x$(reboot)"
        with self.assertRaises(manifest.ManifestError):
            manifest.validate_structure(bad)
        bad = copy.deepcopy(self.m)
        bad["items"][0]["operation"] = "wipe-disk"
        with self.assertRaises(manifest.ManifestError):
            manifest.validate_structure(bad)

    def test_dry_run_is_pure(self):
        before = copy.deepcopy(self.m)
        with fixtures.private_tmpdir() as d:
            cwd = os.getcwd()
            os.chdir(d)
            try:
                text = manifest.dry_run(self.m)
            finally:
                os.chdir(cwd)
            self.assertEqual(os.listdir(d), [])
        self.assertEqual(self.m, before)
        self.assertIn("vm/105", text)
        self.assertIn(manifest.manifest_hash(self.m), text)


class RenderedScriptTests(unittest.TestCase):
    """Run the rendered cleanup script against stub Proxmox tools."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        inv, _ = load_inventory()
        self.inv = inv
        self.m = manifest.build(inv, classes(inv, EVIDENCE))
        self.state = {
            "resources": fixtures.RESOURCES,
            # every listed guest has a config (a listed guest without one is a malformed host)
            "configs": {**{str(k): v for k, v in fixtures.CONFIGS.items()},
                        **{str(k): v for k, v in fixtures.LXC_CONFIGS.items()}},
            "content": fixtures.content_listing_for(fixtures.CONTENT, list(fixtures.CONFIGS.values())
                                                    + list(fixtures.LXC_CONFIGS.values())),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, state):
        (self.dir / "state.json").write_text(json.dumps(state))
        (self.dir / "calls.log").write_text("")
        cfg = fixtures.make_lab(self.dir)
        script = hostrun.render("apply-manifest", cfg, self.m, inventory=self.inv, overrides=EVIDENCE)
        env = {"PATH": f"{STUBS}:/usr/bin:/bin", "STUB_STATE": str(self.dir / "state.json"),
               "STUB_LOG": str(self.dir / "calls.log")}
        # destructive execution is disabled in the shipped text: the guards run in a test-only copy
        proc = subprocess.run(["bash", "-s"], input=fixtures.for_stub_run(script), text=True, capture_output=True,
                              env=env)
        calls = [json.loads(l) for l in (self.dir / "calls.log").read_text().splitlines()]
        return proc, calls

    def test_matching_state_executes_in_order(self):
        proc, calls = self.run_script(self.state)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        mutating = [c for c in calls if c[0] in ("qm", "pct", "pvesm", "vzdump")]
        self.assertEqual(mutating, [["qm", "destroy", "105", "--purge", "1"],
                                    ["qm", "stop", "106"], ["qm", "destroy", "106", "--purge", "1"]])
        self.assertIn("manifest complete", proc.stderr)

    def test_changed_state_stops_before_any_change(self):
        state = copy.deepcopy(self.state)
        state["configs"]["105"]["digest"] = "9" * 40
        proc, calls = self.run_script(state)
        self.assertEqual(proc.returncode, 3)
        self.assertIn("digest changed", proc.stderr)
        self.assertFalse([c for c in calls if c[0] in ("qm", "pct", "pvesm", "vzdump")])

    def test_later_item_change_stops_the_batch_there(self):
        state = copy.deepcopy(self.state)
        for r in state["resources"]:
            if r.get("vmid") == 106:
                r["name"] = "renamed"
        proc, calls = self.run_script(state)
        self.assertEqual(proc.returncode, 3)
        mutating = [c for c in calls if c[0] in ("qm", "pct", "pvesm", "vzdump")]
        self.assertEqual(mutating, [["qm", "destroy", "105", "--purge", "1"]])


class BaselineTests(unittest.TestCase):
    def test_no_drift_and_drift(self):
        inv, _ = load_inventory()
        snap = baseline.snapshot(inv, fixtures.POOL)
        self.assertEqual(baseline.compare(snap, baseline.snapshot(inv, fixtures.POOL)), [])
        changed = copy.deepcopy(inv)
        changed["users"].append("intruder@pve")
        changed["guests"].append({"id": "vm/9199", "vmid": 9199, "type": "qemu", "node": fixtures.NODE,
                                  "status": "stopped", "digest": "", "name": "x", "pool": fixtures.POOL,
                                  "template": False})
        diffs = baseline.compare(snap, baseline.snapshot(changed, fixtures.POOL))
        self.assertEqual(diffs, ["users: added 'intruder@pve'"])  # project guests are not drift


if __name__ == "__main__":
    unittest.main()
