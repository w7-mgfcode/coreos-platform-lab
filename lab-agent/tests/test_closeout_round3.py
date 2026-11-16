"""Correction round L1-CORE-3 for finding 3.

LEVEL 1 (agent side): an identity is bound to its section, classification dispatches on the
section, the sentinel test comes first, ids are matched in full, malformed input is refused
with exit 2. LEVEL 2 (host side): the rendered apply script checks live, against the owner's
settings, that it never touches the sentinel, that a guest's pool is the inventoried one, and
that a volume is not the sentinel's or used by a guest outside the pool.
"""

import contextlib
import copy
import io
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from lab_agent import classify, cli, hostrun, inventory, manifest
from tests import fixtures
from tests.test_closeout_apply import SENTINEL_ITEM, ApplyHarness, guest_item
from tests.test_closeout_review import SENTINEL_VOLUME, VOLUME_ITEM, with_sentinel_volume
from tests.test_inventory_manifest import EVIDENCE, classes, load_inventory

STUBS = Path(__file__).resolve().parent / "stubs"
LIB = Path(__file__).resolve().parent.parent / "host" / "lib.sh"
MUTATING = ("qm", "pct", "pvesm", "vzdump")
FORGED_EVIDENCE = "forged evidence, long enough"


def override(*ids):
    return {rid: {"class": "REMOVE_CANDIDATE", "evidence": FORGED_EVIDENCE} for rid in ids}


class SectionBindingTests(ApplyHarness, unittest.TestCase):
    """The reviewer's N1, N1b and N2: refused before rendering, nothing executed."""

    def bound(self, inv, *items):
        m = copy.deepcopy(self.m)
        m["items"].extend(copy.deepcopy(list(items)))
        m["inventory_digest"] = inventory.digest(inv)
        return m

    def test_n1_guest_entry_in_tokens_refused(self):
        inv = copy.deepcopy(self.inv)
        sentinel = next(g for g in inv["guests"] if g["id"] == "vm/9050")
        inv["guests"].remove(sentinel)
        inv["tokens"].append(dict(sentinel, vmid=9051))
        inv["users"].append("vm/9050")
        m = self.bound(inv, SENTINEL_ITEM)
        self.assert_refused(m, r"inventory inconsistent: .*'vm/9050' is not a valid user id",
                            inv=inv, overrides=dict(EVIDENCE, **override("vm/9050")))
        self.assertIn("vm/9050: not a token id", "; ".join(inventory.inconsistencies(
            dict(inv, users=[u for u in inv["users"] if u != "vm/9050"]))))

    def test_n1b_volume_entry_in_tokens_refused(self):
        inv = with_sentinel_volume(self.inv)
        rid = f"volume/{SENTINEL_VOLUME}"
        inv["tokens"].append({"id": rid, "vmid": None, "privsep": True, "expire": 0})
        inv["volumes"] = [v for v in inv["volumes"] if v["id"] != rid]
        inv["users"].append(rid)
        m = self.bound(inv, VOLUME_ITEM)
        self.assert_refused(m, r"inventory inconsistent: .*is not a valid user id",
                            inv=inv, overrides=dict(EVIDENCE, **override(rid)))

    def test_n2_sentinel_in_the_pool_keeps_its_volume_preserved(self):
        inv = with_sentinel_volume(self.inv)
        next(g for g in inv["guests"] if g["id"] == "vm/9050")["pool"] = fixtures.POOL
        self.assertEqual(inventory.inconsistencies(inv), [])  # consistent, yet must not open the sentinel
        self.assertEqual(classes(inv)[f"volume/{SENTINEL_VOLUME}"]["class"], "PRESERVE")
        m = self.bound(inv, VOLUME_ITEM)
        self.assert_refused(m, rf"volume/{SENTINEL_VOLUME}: PRESERVE cannot be overridden",
                            inv=inv, overrides=dict(EVIDENCE, **override(f"volume/{SENTINEL_VOLUME}")))

    def test_classification_uses_the_section_not_the_prefix(self):
        kinds = {rid: kind for rid, (kind, _item) in inventory.resources(self.inv).items()}
        self.assertEqual(kinds["vm/9050"], "guest")
        self.assertEqual(kinds["token/corelab-agent@pve!lab"], "token")
        self.assertEqual(kinds["volume/local-lvm:vm-105-disk-0"], "volume")
        self.assertEqual(kinds["user/root@pam"], "user")

    def test_every_section_accepts_only_its_own_id_form(self):
        cases = {"guests": "volume/local-lvm:vm-105-disk-0", "volumes": "vm/105", "storages": "vm/105",
                 "network": "storage/local", "disks": "iface/vmbr0", "tokens": "user/root@pam"}
        for section, wrong in cases.items():
            inv = copy.deepcopy(self.inv)
            inv[section][0]["id"] = wrong
            with self.subTest(section=section), \
                    self.assertRaisesRegex(inventory.IncompleteInventoryError, "inventory inconsistent"):
                inventory.require_complete(inv, "classify")

    def test_trailing_newline_in_an_id_refused(self):
        inv = copy.deepcopy(self.inv)
        inv["guests"][0]["id"] += "\n"
        with self.assertRaisesRegex(inventory.IncompleteInventoryError, r"'ct/120\\n': id does not match"):
            inventory.require_complete(inv, "classify")
        inv = copy.deepcopy(self.inv)
        inv["users"][0] += "\n"
        with self.assertRaisesRegex(inventory.IncompleteInventoryError, "not a valid user id"):
            inventory.require_complete(inv, "classify")
        for rid in ("vm/105\n", "vm/0105", "volume/local-lvm:vm-105-disk-0\n"):
            bad = copy.deepcopy(self.m)
            bad["items"][0]["id"] = rid
            with self.subTest(id=rid), self.assertRaisesRegex(manifest.ManifestError, "not a supported resource id"):
                manifest.validate_structure(bad)
        bad = copy.deepcopy(self.m)
        bad["items"][0]["current_state"]["name"] = "old-k8s-node\n"
        with self.assertRaisesRegex(manifest.ManifestError, "name is missing or malformed"):
            manifest.validate_structure(bad)


class MalformedInputTests(unittest.TestCase):
    """F-D: malformed input ends in the documented refusal, exit 2, no traceback."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)
        self.env = mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)})
        self.env.start()
        self.inv, _ = load_inventory()
        self.cls = classes(self.inv, EVIDENCE)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def write(self, name, obj):
        path = self.dir / name
        path.write_text(obj if isinstance(obj, str) else json.dumps(obj))
        return str(path)

    def refused(self, main, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        self.assertEqual(code, 2, err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        return err.getvalue()

    def test_cli_refusals(self):
        guest_not_object = copy.deepcopy(self.inv)
        guest_not_object["guests"][0] = "vm/105"
        user_is_list = copy.deepcopy(self.inv)
        user_is_list["users"][0] = ["root@pam"]
        out = str(self.dir / "o.json")
        inv = self.write("inv.json", self.inv)
        cases = [
            (("classify", "--inventory", self.write("a.json", guest_not_object), "--out", out), "not an object"),
            (("classify", "--inventory", self.write("b.json", user_is_list), "--out", out), "not a valid user id"),
            (("classify", "--inventory", inv, "--overrides", self.write("ov.json", ["x"]), "--out", out),
             "overrides must be"),
            (("classify", "--inventory", inv, "--overrides", self.write("ov2.json", {"vm/105": "x"}), "--out", out),
             "override must be an object"),
            # L1B round 2 (X1-a): the command line recomputes the classification, so a hand-added entry is
            # refused as "not what the settings give" (the primitive's own message is asserted below)
            (("manifest", "build", "--inventory", inv, "--classification",
              self.write("c.json", dict(self.cls, **{"vm/777": {"class": "REMOVE_CANDIDATE", "reason": "x"}})),
              "--out", out), "classification file is not what the settings"),
            (("manifest", "build", "--inventory", inv, "--classification", self.write("d.json", [1]), "--out", out),
             "classification must be"),
            (("manifest", "dry-run", self.write("e.json", [1, 2])), "a manifest must be a JSON object"),
            (("manifest", "hash", self.write("f.json", "{not json")), "Expecting property name"),
            (("classify", "--inventory", str(self.dir / "missing.json"), "--out", out), "No such file"),
            (("classify", "--inventory", self.write("g.json", [1]), "--out", out), "not a JSON object"),
        ]
        for argv, pattern in cases:
            with self.subTest(argv=argv[:2]):
                self.assertIn(pattern, self.refused(cli.main, *argv))
        self.assertFalse(Path(out).exists())
        with self.assertRaisesRegex(manifest.ManifestError, "vm/777: classified REMOVE_CANDIDATE but not in the inventory"):
            manifest.build(self.inv, dict(self.cls, **{"vm/777": {"class": "REMOVE_CANDIDATE", "reason": "x"}}))

    def test_host_run_refusals(self):
        m = self.write("m.json", manifest.build(self.inv, self.cls))
        for argv, pattern in (
                (("show", "apply-manifest", "--manifest", m, "--inventory", self.write("i.json", "[1"),
                  "--overrides", self.write("o.json", EVIDENCE)), "Expecting"),
                (("show", "apply-manifest", "--manifest", m, "--inventory", self.write("j.json", self.inv),
                  "--overrides", self.write("p.json", [1])), "overrides must be"),
                (("show", "apply-manifest", "--manifest", self.write("q.json", [1]),
                  "--inventory", self.write("k.json", self.inv), "--overrides", self.write("r.json", EVIDENCE)),
                 "a manifest must be a JSON object")):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, self.refused(hostrun.main, *argv))


def stub_state():
    configs = {str(k): v for k, v in fixtures.CONFIGS.items()}
    configs.update({str(k): v for k, v in fixtures.LXC_CONFIGS.items()})
    return {"resources": copy.deepcopy(fixtures.RESOURCES), "configs": copy.deepcopy(configs),
            "content": fixtures.content_listing_for(fixtures.CONTENT, configs.values())}


class LiveCheckTests(unittest.TestCase):
    """LEVEL 2: the rendered script run against the stub Proxmox tools."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)
        self.inv, _ = load_inventory()

    def tearDown(self):
        self.tmp.cleanup()

    def run_bash(self, script, state=None):
        (self.dir / "state.json").write_text(json.dumps(state or stub_state()))
        (self.dir / "calls.log").write_text("")
        env = {"PATH": f"{STUBS}:/usr/bin:/bin", "STUB_STATE": str(self.dir / "state.json"),
               "STUB_LOG": str(self.dir / "calls.log")}
        # destructive execution is disabled in the shipped text: the guards run in a test-only copy
        proc = subprocess.run(["bash", "-s"], input=fixtures.for_stub_run(script), text=True, capture_output=True,
                              env=env)
        calls = [json.loads(line) for line in (self.dir / "calls.log").read_text().splitlines()]
        return proc, [c for c in calls if c[0] in MUTATING]

    def render(self, inv, overrides):
        m = manifest.build(inv, classes(inv, overrides))
        return hostrun.render("apply-manifest", self.cfg, m, inventory=inv, overrides=overrides)

    def guard(self, command, **env):
        exports = {"CL_SENTINEL_VMID": str(fixtures.SENTINEL), "CL_POOL": fixtures.POOL, "CL_NODE": fixtures.NODE}
        exports.update(env)
        lines = ["set -euo pipefail"] + [f"export {k}={v}" for k, v in exports.items() if v is not None]
        return self.run_bash("\n".join(lines) + "\n" + LIB.read_text() + "\n" + command + "\n")

    def test_config_values_reach_the_script(self):
        script = self.render(self.inv, EVIDENCE)
        self.assertIn(f"export CL_POOL={fixtures.POOL}\n", script)
        self.assertIn(f"export CL_SENTINEL_VMID={fixtures.SENTINEL}", script)
        first_change = min(script.index(cmd) for cmd in ("\ncl_dump_config ", "\ncl_stop_guest ", "\ncl_destroy_guest "))
        preflight = script.index('cl_log "live safety checks passed"')
        self.assertLess(preflight, first_change)
        self.assertEqual(script.count("cl_guard_guest qemu 106 ''"), 3)  # preflight, before stop, before destroy

    def test_consistently_forged_pool_guest_aborts_before_anything_is_removed(self):
        inv = copy.deepcopy(self.inv)
        next(g for g in inv["guests"] if g["id"] == "vm/106")["pool"] = fixtures.POOL  # not so on the host
        self.assertEqual(inventory.inconsistencies(inv), [])
        script = self.render(inv, EVIDENCE)  # vm/105 honest, vm/106 forged
        proc, mutating = self.run_bash(script)
        self.assertEqual(proc.returncode, 6, proc.stderr)
        self.assertIn("qemu/106 is in pool '' on the host, but was inventoried in 'corelab'", proc.stderr)
        self.assertEqual(mutating, [])  # not even the honest vm/105
        self.assertNotIn("config of qemu/105 follows", proc.stdout)

    def test_legitimate_pool_guest_passes(self):
        overrides = override("vm/9101")
        script = self.render(self.inv, overrides)
        proc, mutating = self.run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("qemu/9101 is a live member of pool corelab", proc.stderr)
        self.assertEqual(mutating, [["qm", "stop", "9101"], ["qm", "destroy", "9101", "--purge", "1"]])

    def test_guest_moved_out_of_the_pool_after_inventory_aborts(self):
        script = self.render(self.inv, override("vm/9101"))
        state = stub_state()
        next(r for r in state["resources"] if r.get("vmid") == 9101).pop("pool")
        proc, mutating = self.run_bash(script, state)
        self.assertEqual(proc.returncode, 6)
        self.assertEqual(mutating, [])

    def test_orphan_volume_is_freed_and_used_volume_is_refused(self):
        script = self.render(self.inv, override("volume/corelab:iso/corelab-dummy.iso"))
        proc, mutating = self.run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(mutating, [["pvesm", "free", "corelab:iso/corelab-dummy.iso"]])
        # vm-105-disk-0 is classifiable (UNKNOWN, overridden) but still attached to vm/105,
        # which is outside the pool: the host refuses it.
        script = self.render(self.inv, override("volume/local-lvm:vm-105-disk-0"))
        proc, mutating = self.run_bash(script)
        self.assertEqual(proc.returncode, 6)
        self.assertIn("local-lvm:vm-105-disk-0 is used by guest pve-test/qemu/105 outside pool corelab", proc.stderr)
        self.assertEqual(mutating, [])

    # -- the host guards on their own, as if a forged manifest had reached the host --------
    def test_host_refuses_the_sentinel_guest(self):
        for vmid in ("9050", "09050"):
            with self.subTest(vmid=vmid):
                proc, mutating = self.guard(f"cl_guard_guest qemu {vmid} ''")
                self.assertEqual(proc.returncode, 6)
                self.assertIn("is the sentinel guest", proc.stderr)
                self.assertEqual(mutating, [])

    def test_host_refuses_sentinel_volumes(self):
        proc, _ = self.guard(f"cl_guard_volume local-lvm {SENTINEL_VOLUME}")  # by name
        self.assertEqual(proc.returncode, 6)
        self.assertIn("belongs to the sentinel guest 9050", proc.stderr)
        state = stub_state()  # by the host's listing, with a name that names no VMID
        state["content"]["local"].append({"volid": "local:images/disk.raw", "content": "images", "size": 1,
                                          "vmid": fixtures.SENTINEL})
        proc, _ = self.run_bash("set -euo pipefail\nexport CL_SENTINEL_VMID=9050 CL_POOL=corelab "
                                "CL_NODE=pve-test\n" + LIB.read_text() + "\ncl_guard_volume local local:images/disk.raw\n",
                                state)
        self.assertEqual(proc.returncode, 6)
        self.assertIn("belongs to the sentinel guest 9050", proc.stderr)

    def test_host_refuses_a_volume_used_outside_the_pool(self):
        proc, _ = self.guard("cl_guard_volume local local:iso/old.iso")  # vm/106 has it as its CD-ROM
        self.assertEqual(proc.returncode, 6)
        self.assertIn("used by guest pve-test/qemu/106", proc.stderr)

    def test_host_guard_needs_the_settings(self):
        proc, _ = self.guard("cl_guard_guest qemu 105 ''", CL_SENTINEL_VMID=None)
        self.assertEqual(proc.returncode, 6)
        self.assertIn("CL_SENTINEL_VMID is not set", proc.stderr)
        proc, _ = self.guard("cl_guard_guest qemu 105 ''", CL_POOL=None)
        self.assertEqual(proc.returncode, 6)

    def test_render_needs_the_sentinel_setting(self):
        d = self.dir / "nosentinel"
        d.mkdir(mode=0o700)
        text = fixtures.env_text(d).replace(f"PVE_SENTINEL_VMID={fixtures.SENTINEL}\n", "")
        (d / "env").write_text(text)
        os.chmod(d / "env", 0o600)
        from lab_agent.config import load
        cfg = load(d / "env")
        m = manifest.build(self.inv, classes(self.inv, EVIDENCE))
        # L1B (R3-1): refused by the classification step, before anything is checked or rendered,
        # instead of late at the parameter export. Same exit 2 for both callers.
        with self.assertRaisesRegex(classify.ClassificationError, "PVE_SENTINEL_VMID"):
            hostrun.render("apply-manifest", cfg, m, inventory=self.inv, overrides=EVIDENCE)


if __name__ == "__main__":
    unittest.main()
