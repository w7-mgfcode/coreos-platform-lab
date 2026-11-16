"""Mission L1B, task LA-DESTRUCT, round 2 (after the X1 and X2 reviews).

X1-a   a classification file and its binding entry are editable: build and check recompute.
X1-b   malformed API records end as a refusal, found through discovery with the fake transport.
X2-1   the sentinel's references are scanned whatever pool it is in.
X2-2   destroying a guest is guarded volume by volume.
X2-3/4 the approved state is re-checked right before each destructive command; locks and active
       tasks refuse. What remains is an OPEN RISK, and one test below says so by showing it.
X2-5   endpoint-specific shapes and independent completeness controls.
X2-6   active, pending and current views are all scanned.
X2-7   node, VMID and snapshot names are validated before use.
Also: verify_against_raw compares in JSON form (a real round trip through a file).

Offline only: the stub tools model what pvestub.py's docstring lists and nothing else.
"""

import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from lab_agent import classify, hostrun, inventory, manifest, pveapi
from tests import fixtures
from tests.test_closeout_round3 import override, stub_state
from tests.test_inventory_manifest import EVIDENCE, classes, load_inventory
from tests.test_l1b_destruct import HostBase, collected, make_lab_with, run_guard

ONLY_105 = {"vm/105": EVIDENCE["vm/105"]}
DISK_105 = "local-lvm:vm-105-disk-0"


class TrustedBuildTests(unittest.TestCase):
    """X1-a: the binding is metadata; the command line's calls recompute and compare."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.inv, _ = load_inventory()
        self.cfg = fixtures.make_lab(self.dir)
        self.ctx = classify.config_context(self.cfg)
        self.good = json.loads(json.dumps(classes(self.inv, EVIDENCE)))  # as read back from a file

    def tearDown(self):
        self.tmp.cleanup()

    def forged_from_no_sentinel(self):
        """A no-sentinel classification, hand-edited into something the primitives accept."""
        cfg = make_lab_with(self.dir, None)
        cls = classify.classify(self.inv, **classify.config_context(cfg, no_sentinel=True))
        cls = json.loads(json.dumps(cls))
        cls[classify.BINDING_ID].update({"class": "PRESERVE", "sentinel_vmid": fixtures.SENTINEL})
        cls["vm/105"] = {"class": "REMOVE_CANDIDATE", "reason": "forged by hand, long enough"}
        return cls

    def test_the_primitive_accepts_a_forged_binding_which_is_why_it_is_not_the_command_line_path(self):
        forged = self.forged_from_no_sentinel()
        m = manifest.build(self.inv, forged)  # builds: the binding is only metadata
        self.assertEqual(m["sentinel_vmid"], fixtures.SENTINEL)
        manifest.validate(m, self.inv, forged)  # and checks

    def test_build_trusted_refuses_the_forged_no_sentinel_classification(self):
        forged = self.forged_from_no_sentinel()
        with self.assertRaisesRegex(manifest.ManifestError, "not what the settings, the inventory and the overrides give"):
            manifest.build_trusted(self.inv, forged, None, self.ctx)
        # the forger's other way: settings without a sentinel can not even produce a context
        with self.assertRaises(classify.ClassificationError):
            classify.config_context(make_lab_with(self.dir, None))
        # and the explicit no-sentinel context is refused by the recompute itself
        with self.assertRaisesRegex(manifest.ManifestError, "no-sentinel mode"):
            manifest.build_trusted(self.inv, forged, None,
                                   classify.config_context(make_lab_with(self.dir, None), no_sentinel=True))

    def test_an_edited_overrides_digest_is_refused(self):
        edited = copy.deepcopy(self.good)
        edited[classify.BINDING_ID]["overrides_digest"] = classify.overrides_digest({"x": {"class": "UNKNOWN"}})
        manifest.build(self.inv, edited)  # the primitive still takes it
        with self.assertRaisesRegex(manifest.ManifestError, "differs at: binding/classification"):
            manifest.build_trusted(self.inv, edited, EVIDENCE, self.ctx)

    def test_overrides_that_do_not_match_the_classification_are_refused(self):
        with self.assertRaisesRegex(manifest.ManifestError, "differs at"):
            manifest.build_trusted(self.inv, self.good, {}, self.ctx)  # classification made with EVIDENCE
        with self.assertRaisesRegex(manifest.ManifestError, "differs at"):
            manifest.build_trusted(self.inv, self.good, None, self.ctx)

    def test_an_edited_entry_or_a_different_sentinel_is_refused(self):
        edited = copy.deepcopy(self.good)
        edited["vm/9101"]["class"] = "REMOVE_CANDIDATE"
        with self.assertRaisesRegex(manifest.ManifestError, "differs at: vm/9101"):
            manifest.build_trusted(self.inv, edited, EVIDENCE, self.ctx)
        other = classify.config_context(make_lab_with(self.dir, "9051"))
        with self.assertRaisesRegex(manifest.ManifestError, "differs at"):
            manifest.build_trusted(self.inv, self.good, EVIDENCE, other)

    def test_check_trusted_recomputes_too(self):
        m = manifest.build_trusted(self.inv, self.good, EVIDENCE, self.ctx)  # control: genuine inputs build
        manifest.check_trusted(m, self.inv, self.good, EVIDENCE, self.ctx)
        forged = self.forged_from_no_sentinel()
        manifest.validate(manifest.build(self.inv, forged), self.inv, forged)  # primitive: accepted
        with self.assertRaisesRegex(manifest.ManifestError, "not what the settings"):
            manifest.check_trusted(manifest.build(self.inv, forged), self.inv, forged, None, self.ctx)
        with self.assertRaisesRegex(manifest.ManifestError, "not what the settings"):
            manifest.check_trusted(m, self.inv, self.good, {}, self.ctx)

    def test_trusted_calls_refuse_a_classification_that_is_not_one(self):
        for bad in ([], None, {"vm/105": {"class": "REMOVE-CANDIDATE", "reason": "x"}}):
            with self.subTest(bad=str(bad)[:30]), self.assertRaises(manifest.ManifestError):
                manifest.build_trusted(self.inv, bad, EVIDENCE, self.ctx)


class MalformedRecordsTests(unittest.TestCase):
    """X1-b: through discovery with the fake transport, malformed records are refusals."""

    def discover(self, **changes):
        routes = fixtures.api_routes()
        for path, data in changes.items():
            routes[("GET", path.replace("NODE", fixtures.NODE))] = (200, data)
        client = pveapi.Client("192.0.2.10", 8006, fixtures.TOKEN_ID, "x", pveapi.FakeTransport(routes))
        col = inventory.collect(client, fixtures.NODE)  # must not raise
        return col, inventory.normalize(col)  # must not raise

    def test_control_the_unmodified_fixture(self):
        col, inv = self.discover()
        self.assertNotIn("/cluster/resources", inv["errors"])
        inventory.require_complete(inv, "classify")

    def test_each_malformed_record_ends_as_a_refusal(self):
        cases = {
            "/cluster/resources": (["bad"], "item 0 is not an object"),
            "/storage": ([{"type": "dir"}], "item 0 has no storage"),
            "/nodes/NODE/storage": ([{"active": 1}], "item 0 has no storage"),
            "/nodes/NODE/storage/local/content": ([{"size": 1}], "item 0 has no volid"),
            "/access/users": ([{"enable": 1}], "item 0 has no userid"),
            "/pools": ([5], "item 0 is not an object"),
            "/nodes/NODE/network": ([{"type": "eth"}], "item 0 has no iface"),
            "/nodes/NODE/disks/list": ([{"used": ""}], "item 0 has no devpath"),
            "/access/acl": ([{"path": "/", "ugid": "x"}], "item 0 has no type"),
            "/cluster/backup": ([{"enabled": 1}], "item 0 has no id"),
            "/nodes/NODE/certificates/info": ([{"san": "not-a-list"}], "san that is not a list"),
            "/nodes/NODE/qemu/105/config": (["x"], "not an object"),
            "/version": (["x"], "not an object"),
        }
        for path, (data, why) in cases.items():
            with self.subTest(path=path):
                col, inv = self.discover(**{path: data})
                real = path.replace("NODE", fixtures.NODE)
                self.assertRegex(inv["errors"][real], "malformed response: .*" + why)
                self.assertNotIn(real, col["raw"])
                purpose = "baseline" if path in ("/access/acl", "/nodes/NODE/certificates/info", "/version") else (
                    "manifest" if "/config" in path else "classify")
                if path == "/cluster/backup":
                    continue  # recorded, but no conclusion depends on it
                with self.assertRaises(inventory.IncompleteInventoryError):
                    inventory.require_complete(inv, purpose)

    def test_a_guest_without_an_integer_vmid_is_refused(self):
        bad = [dict(r) for r in fixtures.RESOURCES]
        bad[0]["vmid"] = "105"
        col, inv = self.discover(**{"/cluster/resources": bad})
        self.assertRegex(inv["errors"]["/cluster/resources"], "no integer vmid")
        with self.assertRaises(inventory.IncompleteInventoryError):
            inventory.require_complete(inv, "classify")

    def test_hand_built_raw_data_is_refused_not_a_traceback(self):
        col = collected()
        col["raw"]["/cluster/resources"] = ["bad"]
        col["raw"][f"/nodes/{fixtures.NODE}/storage"] = [{"active": 1}]
        with self.assertRaisesRegex(inventory.IncompleteInventoryError, "raw data malformed"):
            inventory.normalize(col)
        self.assertTrue(any("raw data malformed" in p for p in inventory.verify_against_raw({}, col)))


class RawRoundTripTests(unittest.TestCase):
    """verify_against_raw compares in JSON form: a genuine discover result verifies after a file round trip."""

    def test_round_trip_through_files(self):
        with tempfile.TemporaryDirectory() as d:
            raw, inv_file = Path(d) / "raw.json", Path(d) / "inventory.json"
            col = collected()
            inv = inventory.normalize(col)
            self.assertTrue(isinstance(inv["acl"][0], tuple))  # why the old comparison failed
            raw.write_text(json.dumps(col, indent=2, sort_keys=True))
            inv_file.write_text(json.dumps(inv, indent=2, sort_keys=True))
            loaded_inv, loaded_raw = json.loads(inv_file.read_text()), json.loads(raw.read_text())
            self.assertTrue(isinstance(loaded_inv["acl"][0], list))
            self.assertEqual(inventory.verify_against_raw(loaded_inv, loaded_raw), [])
            tampered = copy.deepcopy(loaded_inv)
            tampered["acl"].append(["/", "user", "x@pve", "Administrator"])
            self.assertEqual(inventory.verify_against_raw(tampered, loaded_raw), ["acl differs from what the raw data gives"])
            tampered = copy.deepcopy(loaded_inv)
            tampered["errors"] = {}
            self.assertTrue(any("errors differs" in p for p in inventory.verify_against_raw(tampered, loaded_raw)))


class SentinelScanTests(HostBase):
    """X2-1: the sentinel's references count whatever pool it is in."""

    def sentinel_in_pool(self, **config):
        state = stub_state()
        next(r for r in state["resources"] if r.get("vmid") == fixtures.SENTINEL)["pool"] = fixtures.POOL
        state["configs"][str(fixtures.SENTINEL)].update(config)
        return state

    def test_in_pool_sentinel_referencing_a_clean_iso_blocks_its_free(self):
        state = self.sentinel_in_pool(ide2="corelab:iso/corelab-dummy.iso,media=cdrom")
        proc = self.guard("cl_guard_volume corelab corelab:iso/corelab-dummy.iso", state)
        self.refused(proc, "used by the sentinel guest pve-test/qemu/9050")

    def test_controls(self):
        state = self.sentinel_in_pool()
        self.assertEqual(self.guard("cl_guard_volume corelab corelab:iso/corelab-dummy.iso", state).returncode, 0)
        state = stub_state()  # sentinel outside the pool, referencing: refused as before
        state["configs"][str(fixtures.SENTINEL)]["ide2"] = "corelab:iso/corelab-dummy.iso,media=cdrom"
        self.refused(self.guard("cl_guard_volume corelab corelab:iso/corelab-dummy.iso", state), "used by the sentinel")

    def test_other_in_pool_guests_are_still_not_scanned(self):
        state = stub_state()
        state["configs"]["9101"]["ide2"] = "corelab:iso/corelab-dummy.iso,media=cdrom"
        self.assertEqual(self.guard("cl_guard_volume corelab corelab:iso/corelab-dummy.iso", state).returncode, 0)


class ViewTests(HostBase):
    """X2-6: current, default (pending applied) and pending views are all scanned."""

    VOLUME = "corelab:snippets/user.yaml"

    def test_reference_only_in_the_pending_changes(self):
        state = stub_state()
        state["pending_changes"] = {"106": {"cicustom": f"user={self.VOLUME}"}}
        proc = self.guard(f"cl_guard_volume corelab {self.VOLUME}", state)
        self.refused(proc, r"used by guest pve-test/qemu/106 outside pool corelab \((default|pending) view")

    def test_reference_only_in_the_current_view(self):
        state = stub_state()  # active config uses it; a pending change has replaced it, so the default view does not
        state["configs"]["106"]["cicustom"] = f"user={self.VOLUME}"
        state["pending_changes"] = {"106": {"cicustom": "user=corelab:snippets/other.yaml"}}
        proc = self.guard(f"cl_guard_volume corelab {self.VOLUME}", state)
        self.refused(proc, r"\((current|pending) view")
        calls = [c for c in proc.calls if c[:2] == ["pvesh", "get"] and c[2].endswith("/106/config")]
        self.assertEqual(sorted("--current" in c for c in calls), [False, True])  # both views were read

    def test_pending_listing_that_is_malformed_is_refused(self):
        for text in ("null", "", "[]", "{}", "[{}]", '[{"value": "x"}]', '[{"key": "scsi0", "value": {"a": 1}}]'):
            state = stub_state()
            state["raw"] = {f"/nodes/{fixtures.NODE}/qemu/106/pending": text}
            with self.subTest(text=text):
                self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "pending config of")

    def test_the_stub_models_the_three_views(self):
        state = stub_state()
        state["pending_changes"] = {"106": {"memory": "2048"}}
        proc = self.guard("cl_views_of pve-test/qemu/106", state)
        rows = [r.split("\t") for r in proc.stdout.splitlines()]
        self.assertIn(["pve-test/qemu/106", "pending", "memory", "2048"], rows)
        self.assertIn(["pve-test/qemu/106", "default", "memory", "2048"], rows)
        self.assertNotIn(["pve-test/qemu/106", "current", "memory", "2048"], rows)


class ShapeTests(HostBase):
    """X2-5 and X2-7: endpoint-specific shapes; an independent completeness control; checked names."""

    VOLUME = "corelab:iso/corelab-dummy.iso"

    def test_a_record_without_the_endpoints_fields_is_not_a_listing(self):
        for text in ('[{}]', '[{"type": "qemu"}]', '[{"type": "qemu", "vmid": 105}]',
                     '[{"type": "storage", "vmid": 105, "node": "pve-test"}]',
                     '[{"type": "qemu", "vmid": "x1", "node": "pve-test"}]',
                     '[{"type": "qemu", "vmid": 105, "node": "a b"}]'):
            state = stub_state()
            state["raw"] = {"/cluster/resources": text}
            with self.subTest(text=text):
                self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "guest listing")

    def test_content_records_need_a_volume_id(self):
        for text in ('[{}]', '[{"size": 1}]', '[{"volid": ""}]', '[{"volid": "nocolon"}]', '[{"volid": 5}]'):
            state = stub_state()
            state["raw"] = {f"/nodes/{fixtures.NODE}/storage/corelab/content": text}
            with self.subTest(text=text):
                self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "listing of corelab")

    def test_a_wrapped_or_nested_config_is_refused_not_skipped(self):
        wrapped = {"data": {"scsi0": "local-lvm:vm-106-disk-0,size=1G", "digest": "e" * 40}}
        for cfg in (wrapped, {"digest": "x", "scsi0": {"file": "local-lvm:vm-106-disk-0"}},
                    {"digest": "x", "scsi0": ["local-lvm:vm-106-disk-0"]}, {"digest": "x", "scsi0": None}):
            state = stub_state()
            state["raw"] = {f"/nodes/{fixtures.NODE}/qemu/106/config": json.dumps(cfg)}
            with self.subTest(cfg=str(cfg)[:40]):
                self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "config of pve-test/qemu/106")

    def test_a_guest_listing_without_the_sentinel_is_incomplete(self):
        state = stub_state()
        state["resources"] = [r for r in state["resources"] if r.get("vmid") != fixtures.SENTINEL]
        self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "does not contain the sentinel guest 9050")
        self.refused(self.guard("cl_guard_guest qemu 105 ''", state), "does not contain the sentinel guest 9050")
        self.refused(self.guard("cl_require_listed '' ''", state), "does not contain the sentinel guest 9050")
        # a container record is no stand-in for the sentinel qemu guest
        state["resources"].append({"id": "lxc/9050", "type": "lxc", "vmid": 9050, "node": fixtures.NODE,
                                   "name": "fake", "status": "stopped", "template": 0})
        self.refused(self.guard("cl_require_listed '' ''", state), "does not contain the sentinel guest")

    def test_every_guest_and_storage_the_manifest_names_must_be_listed(self):
        self.assertEqual(self.guard("cl_require_listed 'qemu/105 lxc/120' 'local corelab'").returncode, 0)  # control
        state = stub_state()
        state["resources"] = [r for r in state["resources"] if r.get("vmid") != 106]  # a shortened listing
        self.refused(self.guard("cl_require_listed 'qemu/105 qemu/106' 'local'", state), "guest qemu/106 is not in")
        state = stub_state()
        state["node_storages"] = [{"storage": "local", "active": 1}]
        self.refused(self.guard("cl_require_listed 'qemu/105' 'local corelab'", state), "storage corelab is not in")
        for bad in ("qemu/105;reboot", "qemu/0105", "tape/105", "$(x)"):
            with self.subTest(bad=bad):
                self.refused(self.guard(f"cl_require_listed '{bad}' 'local'"), "is not a guest reference")
        self.refused(self.guard("cl_require_listed 'qemu/105' 'lo;cal'"), "is not a storage name")

    def test_the_rendered_script_names_what_it_needs_before_anything(self):
        script = self.script({"vm/105": EVIDENCE["vm/105"], **override("volume/corelab:iso/corelab-dummy.iso")})
        self.assertIn("\ncl_require_listed qemu/105 corelab\n", script)
        self.assertLess(script.index("\ncl_require_listed "), script.index("\ncl_guard_guest "))
        self.assertLess(script.index("\nCL_NODE="), script.index("\ncl_require_listed "))

    def script(self, overrides, backup_storage=None):
        m = manifest.build(self.inv, classes(self.inv, overrides), backup_storage)
        return hostrun.render("apply-manifest", self.cfg, m, inventory=self.inv, overrides=overrides)

    def test_unsafe_names_in_listings_are_refused_before_any_use(self):
        for node in ("x*", "a b", "a;b", "-x", "$(id)", "a/b"):
            state = stub_state()
            state["resources"][0]["node"] = node
            with self.subTest(node=node):
                self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "guest listing")
        for name in ("*", "a b", "../x", "a;b"):
            state = stub_state()
            state["raw"] = {f"/nodes/{fixtures.NODE}/qemu/106/snapshot": json.dumps([{"name": "current"}, {"name": name}])}
            with self.subTest(snapshot=name):
                self.refused(self.guard(f"cl_guard_volume corelab {self.VOLUME}", state), "snapshot listing of")
        for bad in ("-x", "a b", "a;b", "$(id)", "nocolon"):
            self.refused(self.guard(f"cl_guard_volume corelab '{bad}'"), "is not a volume id")
        self.refused(self.guard("cl_guard_volume 'bad;storage' corelab:x"), "is not a storage name")


class DestroyGuardTests(HostBase):
    """X2-2: destroying a guest is guarded volume by volume, with the same reference checks."""

    def script(self, overrides, backup_storage=None):
        m = manifest.build(self.inv, classes(self.inv, overrides), backup_storage)
        return hostrun.render("apply-manifest", self.cfg, m, inventory=self.inv, overrides=overrides)

    def run_script(self, state, overrides=None, **kw):
        return self.guard(self.script(overrides or ONLY_105, **kw), state, autolist=False)

    @staticmethod
    def listed(state, *volids, vmid=None):
        """List volumes in the storage listings, as a host does for every volume it has."""
        for volid in volids:
            storage = volid.split(":")[0]
            if not any(v["volid"] == volid for v in state["content"].setdefault(storage, [])):
                state["content"][storage].append({"volid": volid, "content": "images", "size": 1,
                                                  **({"vmid": vmid} if vmid else {})})
        return state

    def test_control_unreferenced_disks_are_deleted_with_the_guest(self):
        proc = self.run_script(stub_state())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(["qm", "destroy", "105", "--purge", "1"], proc.mutating)
        state = json.loads((self.dir / "state.json").read_text())
        self.assertIn(DISK_105, state["deleted_volumes"])  # the stub models destroy deleting its volumes
        self.assertIn("the 1 volume(s) its destruction would delete passed", proc.stderr)

    def test_a_disk_the_sentinel_references_stops_the_destroy(self):
        for key, value in (("scsi1", f"{DISK_105},size=32G"), ("unused0", DISK_105), ("ide3", f"file={DISK_105}"),
                           ("scsi2", f"local-lvm:0,import-from={DISK_105}")):
            state = stub_state()
            state["configs"][str(fixtures.SENTINEL)][key] = value
            with self.subTest(key=key):
                proc = self.run_script(state)
                self.refused(proc, f"{DISK_105} is used by the sentinel guest pve-test/qemu/9050")
                self.assertEqual(proc.mutating, [])
                self.assertNotIn("deleted_volumes", json.loads((self.dir / "state.json").read_text()))

    def test_a_disk_an_outside_guest_references_stops_the_destroy(self):
        state = stub_state()
        state["configs"]["120"]["mp0"] = f"{DISK_105},mp=/data"  # the container outside the pool
        self.refused(self.run_script(state), r"is used by guest pve-test/lxc/120 outside pool corelab")

    def test_every_kind_in_the_destruction_set(self):
        sentinel = str(fixtures.SENTINEL)
        cases = {
            "unused disk": ({"unused0": "local-lvm:vm-105-disk-7"}, "local-lvm:vm-105-disk-7"),
            "cloud-init disk": ({"ide2": "local-lvm:vm-105-cloudinit,media=cdrom"}, "local-lvm:vm-105-cloudinit"),
            "efi disk": ({"efidisk0": "local-lvm:vm-105-disk-1,efitype=4m"}, "local-lvm:vm-105-disk-1"),
            "snapshot volume": (None, "local-lvm:vm-105-disk-9"),
            "vmstate": (None, "local-lvm:vm-105-state-snap1"),
            "owned, not in the config": (None, "local-lvm:vm-105-disk-3"),
        }
        for label, (cfg, volid) in cases.items():
            state = stub_state()
            if cfg:
                state["configs"]["105"].update(cfg)
            elif label == "snapshot volume":
                state["snapshots"] = {"105": {"s1": {"scsi0": f"{volid},size=1G"}}}
            elif label == "vmstate":
                state["snapshots"] = {"105": {"s1": {"vmstate": volid}}}
            else:
                state["content"]["local-lvm"].append({"volid": volid, "content": "images", "size": 1, "vmid": 105})
            state["configs"][sentinel]["scsi1"] = f"{volid},size=1G"
            self.listed(state, volid, vmid=105)
            with self.subTest(kind=label):
                proc = self.run_script(state)
                self.refused(proc, f"{re.escape(volid)} is used by the sentinel guest")
                self.assertEqual(proc.mutating, [])
        # control per kind: the same volumes without the sentinel's reference are deleted with the guest
        state = stub_state()
        state["configs"]["105"].update({"unused0": "local-lvm:vm-105-disk-7", "ide2": "local-lvm:vm-105-cloudinit,media=cdrom"})
        state["snapshots"] = {"105": {"s1": {"scsi0": "local-lvm:vm-105-disk-9,size=1G", "vmstate": "local-lvm:vm-105-state-snap1"}}}
        state["content"]["local-lvm"].append({"volid": "local-lvm:vm-105-disk-3", "content": "images", "size": 1, "vmid": 105})
        self.listed(state, "local-lvm:vm-105-disk-7", "local-lvm:vm-105-cloudinit", "local-lvm:vm-105-disk-9",
                    "local-lvm:vm-105-state-snap1", vmid=105)
        proc = self.run_script(state)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        deleted = json.loads((self.dir / "state.json").read_text())["deleted_volumes"]
        for volid in ("local-lvm:vm-105-disk-7", "local-lvm:vm-105-cloudinit", "local-lvm:vm-105-disk-9",
                      "local-lvm:vm-105-state-snap1", "local-lvm:vm-105-disk-3", DISK_105):
            self.assertIn(volid, deleted)

    def test_a_destruction_set_volume_that_names_the_sentinel_stops_the_destroy(self):
        state = stub_state()
        state["configs"]["105"]["scsi1"] = "local-lvm:vm-9050-disk-1,size=1G"
        proc = self.run_script(state)
        self.refused(proc, "belongs to the sentinel guest 9050")
        self.assertEqual(proc.mutating, [])

    def test_pending_only_reference_to_a_destruction_set_volume(self):
        state = stub_state()
        state["pending_changes"] = {str(fixtures.SENTINEL): {"scsi1": DISK_105}}
        self.refused(self.run_script(state), "is used by the sentinel guest")

    def test_shared_isos_are_not_in_the_destruction_set(self):
        state = stub_state()
        state["configs"]["105"]["ide2"] = "local:iso/old.iso,media=cdrom"  # also vm/106's CD-ROM
        proc = self.run_script(state)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("local:iso/old.iso", json.loads((self.dir / "state.json").read_text())["deleted_volumes"])

    def test_the_destroy_set_lists_both_kinds_of_source(self):
        state = stub_state()
        state["configs"]["105"]["ide2"] = "local-lvm:vm-105-cloudinit,media=cdrom"
        state["content"]["local-lvm"].append({"volid": "local-lvm:vm-105-disk-3", "content": "images", "size": 1})
        proc = self.guard("cl_fetch_guests\ncl_fetch_storages\ncl_destroy_set qemu 105", state)
        self.assertEqual(sorted(proc.stdout.split()), sorted([DISK_105, "local-lvm:vm-105-cloudinit",
                                                              "local-lvm:vm-105-disk-3"]))

    def test_unreadable_listings_stop_the_destroy_before_any_change(self):
        for path in (f"/nodes/{fixtures.NODE}/storage", f"/nodes/{fixtures.NODE}/storage/local-lvm/content",
                     f"/nodes/{fixtures.NODE}/qemu/9050/pending", f"/nodes/{fixtures.NODE}/qemu/105/pending"):
            for text in ("null", "{not json", "[{}]"):
                state = stub_state()
                state["raw"] = {path: text}
                with self.subTest(path=path, text=text):
                    proc = self.run_script(state)
                    self.assertEqual(proc.returncode, 6, proc.stderr)
                    self.assertEqual(proc.mutating, [])

    def test_the_sentinel_and_a_non_vmid_are_refused_directly(self):
        self.refused(self.guard("cl_guard_destroy_set qemu 9050"), "is the sentinel guest")
        self.refused(self.guard("cl_guard_destroy_set qemu 9x0"), "not a VMID")
        self.refused(self.guard("cl_guard_destroy_set qemu 777"), "is not in the live guest listing")


class RevalidationTests(HostBase):
    """X2-3 and X2-4: the approved state is re-checked right before each destructive command.

    What this does NOT close is an OPEN RISK, shown by ``test_OPEN_RISK_...`` below."""

    def script(self, overrides, backup_storage=None):
        m = manifest.build(self.inv, classes(self.inv, overrides), backup_storage)
        return hostrun.render("apply-manifest", self.cfg, m, inventory=self.inv, overrides=overrides)

    def run_script(self, state, overrides=None, **kw):
        return self.guard(self.script(overrides or ONLY_105, **kw), state, autolist=False)

    def refused_not_destroyed(self, proc, pattern, code=6):
        """Refused with ``code`` after earlier steps (backup, stop) that were approved to happen;
        what must not happen is the destroy or the free."""
        self.assertEqual(proc.returncode, code, proc.stderr)
        self.assertRegex(proc.stderr, pattern)
        self.assertEqual([c for c in proc.mutating if c[1] in ("destroy", "free")], [])

    def with_trigger(self, **trigger):
        state = stub_state()
        state["triggers"] = [trigger]
        return state

    def test_a_config_change_during_the_backup_stops_the_destroy(self):
        state = self.with_trigger(on=["vzdump"], config={"105": {"digest": "9" * 40}})
        proc = self.run_script(state, backup_storage="local")
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertIn("config digest changed", proc.stderr)
        self.assertEqual([c for c in proc.mutating if c[0] != "vzdump"], [])
        control = self.run_script(stub_state(), backup_storage="local")  # control: no change, destroyed
        self.assertEqual(control.returncode, 0, control.stderr)
        self.assertIn(["qm", "destroy", "105", "--purge", "1"], control.mutating)

    def test_a_disk_added_during_the_backup_that_the_sentinel_uses_stops_the_destroy(self):
        state = self.with_trigger(on=["vzdump"], config={str(fixtures.SENTINEL): {"scsi1": f"{DISK_105},size=1G"}})
        proc = self.run_script(state, backup_storage="local")
        self.refused_not_destroyed(proc, "is used by the sentinel guest")
        self.assertEqual([c for c in proc.mutating if c[0] != "vzdump"], [])

    def test_a_reference_appearing_after_the_stop_stops_the_destroy(self):
        state = self.with_trigger(on=["qm", "stop", "106"], config={str(fixtures.SENTINEL): {"scsi1": "local-lvm:vm-106-disk-0"}})
        proc = self.run_script(state, overrides={"vm/106": EVIDENCE["vm/106"]})
        self.refused_not_destroyed(proc, "local-lvm:vm-106-disk-0 is used by the sentinel guest")
        self.assertEqual(proc.mutating, [["qm", "stop", "106"]])  # stopped, never destroyed

    def test_a_guest_that_is_running_again_is_not_destroyed(self):
        # the approved state before the destroy is "stopped"; vm/106 is running, as if started again
        proc = self.guard("cl_destroy_guest qemu 106 pve-test old-web stopped " + "b" * 40 + " 0")
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertIn("changed: expected", proc.stderr)
        self.assertEqual(proc.mutating, [])

    def test_a_lock_refuses_every_destructive_command(self):
        for lock in ("backup", "snapshot", "migrate"):
            state = stub_state()
            state["configs"]["105"]["lock"] = lock
            with self.subTest(lock=lock):
                for cmd in ("cl_destroy_guest qemu 105 pve-test old-k8s-node stopped " + "a" * 40 + " 0",
                            "cl_stop_guest qemu 105 pve-test old-k8s-node stopped " + "a" * 40 + " 0"):
                    # the digest in the config is the approved one: only the lock differs
                    proc = self.guard(cmd, state)
                    self.refused(proc, f"qemu/105 is locked \\('{lock}'\\)")

    def test_an_active_task_refuses_every_destructive_command(self):
        state = stub_state()
        state["tasks"] = [{"upid": "UPID:pve-test:0001:0002:00000003:vzdump:999:root@pam:"}]
        for cmd in ("cl_destroy_guest qemu 105 pve-test old-k8s-node stopped " + "a" * 40 + " 0",
                    "cl_stop_guest qemu 105 pve-test old-k8s-node stopped " + "a" * 40 + " 0",
                    "cl_free_volume corelab corelab:iso/corelab-dummy.iso 1048576"):
            with self.subTest(cmd=cmd.split()[0]):
                proc = self.guard(cmd, state)
                self.refused(proc, r"1 task\(s\) active on node pve-test")
        state["tasks"] = []  # control: no task, no lock, approved state: the command runs
        proc = self.guard("cl_destroy_guest qemu 105 pve-test old-k8s-node stopped " + "a" * 40 + " 0", state)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.mutating, [["qm", "destroy", "105", "--purge", "1"]])

    def test_a_task_starting_during_the_backup_stops_the_destroy(self):
        state = self.with_trigger(on=["vzdump"], tasks=[{"upid": "UPID:pve-test:1:2:3:qmstart:106:root@pam:"}])
        proc = self.run_script(state, backup_storage="local")
        self.refused_not_destroyed(proc, r"task\(s\) active")
        self.assertEqual([c for c in proc.mutating if c[0] != "vzdump"], [])

    def test_malformed_task_and_lock_data_is_refused(self):
        for text in ("null", "{}", "[{}]", "[1]", "{not json"):
            state = stub_state()
            state["raw"] = {f"/nodes/{fixtures.NODE}/tasks": text}
            with self.subTest(text=text):
                self.refused(self.guard("cl_no_active_tasks", state), "task listing")

    def test_a_volume_free_rechecks_references_and_size(self):
        state = stub_state()
        state["configs"][str(fixtures.SENTINEL)]["ide2"] = "corelab:iso/corelab-dummy.iso,media=cdrom"
        proc = self.guard("cl_free_volume corelab corelab:iso/corelab-dummy.iso 1048576", state, autolist=False)
        self.refused(proc, "used by the sentinel guest")
        proc = self.guard("cl_free_volume corelab corelab:iso/corelab-dummy.iso 5", stub_state(), autolist=False)
        self.assertEqual(proc.returncode, 3, proc.stderr)  # the size is not the approved one
        self.assertEqual(proc.mutating, [])
        proc = self.guard("cl_free_volume corelab corelab:iso/corelab-dummy.iso 1048576", stub_state(), autolist=False)
        self.assertEqual((proc.returncode, proc.mutating), (0, [["pvesm", "free", "corelab:iso/corelab-dummy.iso"]]))

    def test_OPEN_RISK_a_change_after_the_last_check_is_not_caught(self):
        """OPEN RISK, neither fixed nor accepted. The last check before `qm destroy` is the task
        listing. Another actor who attaches the guest's disk to the sentinel right after it is not
        seen: the destroy runs and deletes the disk. This test asserts the CURRENT, UNSAFE behaviour
        so that nobody reads the revalidation above as a closed race. If it starts to fail because
        the script got safer, delete it deliberately and say why in the report."""
        state = self.with_trigger(on=["pvesh", "get", f"/nodes/{fixtures.NODE}/tasks"],
                                  config={str(fixtures.SENTINEL): {"scsi1": f"{DISK_105},size=1G"}})
        proc = self.run_script(state)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(["qm", "destroy", "105", "--purge", "1"], proc.mutating)
        final = json.loads((self.dir / "state.json").read_text())
        self.assertIn(DISK_105, final["deleted_volumes"])  # the sentinel's disk was deleted


class StubModelTests(HostBase):
    """The stub's models do what pvestub.py says they do, so the tests above mean what they claim."""

    def test_destroy_deletes_volumes_and_a_lock_blocks_it(self):
        state = stub_state()
        state["configs"]["105"]["lock"] = "backup"
        proc = self.guard("qm destroy 105 --purge 1", state)
        self.assertEqual(proc.returncode, 9)
        self.assertNotIn("deleted_volumes", json.loads((self.dir / "state.json").read_text()))
        state = stub_state()
        proc = self.guard("qm destroy 105 --purge 1", state)
        self.assertEqual(proc.returncode, 0)
        final = json.loads((self.dir / "state.json").read_text())
        self.assertIn(DISK_105, final["deleted_volumes"])
        self.assertNotIn(DISK_105, [v["volid"] for v in final["content"]["local-lvm"]])

    def test_triggers_fire_once_after_the_matching_call(self):
        state = stub_state()
        state["triggers"] = [{"on": ["pvesh", "get", "/pools"], "config": {"105": {"memory": "1"}}}]
        proc = self.guard("pvesh get /pools >/dev/null; pvesh get /pools >/dev/null", state)
        final = json.loads((self.dir / "state.json").read_text())
        self.assertEqual(final["configs"]["105"]["memory"], "1")
        self.assertTrue(final["triggers"][0]["fired"])
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
