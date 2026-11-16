"""Review corrections L1-CORE-2: (A) internally inconsistent inventories, (B) inventory shape,
(C) the exclusive token write without hard links, (D) the wording of manifest check."""

import contextlib
import copy
import io
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from lab_agent import cli, hostrun, inventory, manifest
from tests import fixtures
from tests.test_closeout_apply import SENTINEL_ITEM, ApplyHarness
from tests.test_inventory_manifest import EVIDENCE, classes, load_inventory

SENTINEL_VOLUME = "local-lvm:vm-9050-disk-0"


def with_sentinel_volume(inv):
    """The fixture inventory plus the sentinel's disk, honestly owned by VMID 9050."""
    inv = copy.deepcopy(inv)
    inv["volumes"].append({"id": f"volume/{SENTINEL_VOLUME}", "volid": SENTINEL_VOLUME, "storage": "local-lvm",
                           "content": "images", "size": 1073741824, "vmid": fixtures.SENTINEL})
    inv["volumes"].sort(key=lambda v: v["volid"])
    return inv


VOLUME_ITEM = {"id": f"volume/{SENTINEL_VOLUME}", "type": "volume",
               "current_state": {"node": fixtures.NODE, "storage": "local-lvm", "size": 1073741824},
               "operation": "free", "reason": "synthetic test item", "dependencies": [], "backup": "none",
               "reversible": "no", "expected_result": "absent", "verify": "absent"}


class InconsistentInventoryTests(ApplyHarness, unittest.TestCase):
    """(A) The reviewer's two cases: refused before rendering, nothing executed."""

    def forged(self, edit, item, override_id):
        inv = edit(copy.deepcopy(self.inv))
        overrides = dict(EVIDENCE, **{override_id: {"class": "REMOVE_CANDIDATE",
                                                    "evidence": "forged evidence, long enough"}})
        m = copy.deepcopy(self.m)
        m["items"].append(copy.deepcopy(item))
        m["inventory_digest"] = inventory.digest(inv)  # the digest is recomputable, so bind it
        return inv, overrides, m

    def test_a_sentinel_guest_with_changed_vmid_refused(self):
        def edit(inv):
            next(g for g in inv["guests"] if g["id"] == "vm/9050")["vmid"] = 9051
            return inv
        inv, overrides, m = self.forged(edit, SENTINEL_ITEM, "vm/9050")
        self.assert_refused(m, r"inventory inconsistent: vm/9050: id does not match vmid 9051",
                            inv=inv, overrides=overrides)
        with self.assertRaisesRegex(inventory.IncompleteInventoryError, "inconsistent"):
            hostrun.render("apply-manifest", self.cfg, m, inventory=inv, overrides=overrides)
        with self.assertRaisesRegex(inventory.IncompleteInventoryError, "inconsistent"):
            manifest.build(inv, classes(self.inv, EVIDENCE))

    def test_b_sentinel_volume_with_null_owner_refused(self):
        self.inv = with_sentinel_volume(self.inv)
        self.assertEqual(classes(self.inv)[f"volume/{SENTINEL_VOLUME}"]["class"], "PRESERVE")

        def edit(inv):
            next(v for v in inv["volumes"] if v["volid"] == SENTINEL_VOLUME)["vmid"] = None
            return inv
        inv, overrides, m = self.forged(edit, VOLUME_ITEM, f"volume/{SENTINEL_VOLUME}")
        self.assert_refused(m, rf"inventory inconsistent: volume/{SENTINEL_VOLUME}: vmid None, but the volid "
                               r"names VMID 9050", inv=inv, overrides=overrides)
        with self.assertRaisesRegex(inventory.IncompleteInventoryError, "inconsistent"):
            hostrun.render("apply-manifest", self.cfg, m, inventory=inv, overrides=overrides)


class ConsistencyRulesTests(unittest.TestCase):
    def setUp(self):
        self.inv, _ = load_inventory()

    def assert_inconsistent(self, inv, pattern):
        for purpose in inventory.REQUIREMENTS:
            with self.subTest(purpose=purpose), \
                    self.assertRaisesRegex(inventory.IncompleteInventoryError, pattern):
                inventory.require_complete(inv, purpose)

    def edited(self, section, rid, **changes):
        inv = copy.deepcopy(self.inv)
        next(r for r in inv[section] if r["id"] == rid).update(changes)
        return inv

    def test_fixture_is_consistent(self):
        self.assertEqual(inventory.inconsistencies(self.inv), [])

    def test_guest_identity(self):
        self.assert_inconsistent(self.edited("guests", "vm/105", type="lxc"), "vm/105: type lxc does not match")
        self.assert_inconsistent(self.edited("guests", "vm/105", vmid="105"), "vm/105: vmid is missing or not int")
        self.assert_inconsistent(self.edited("guests", "vm/105", id="vm/0105"), "vm/0105: id does not match")
        self.assert_inconsistent(self.edited("guests", "vm/9101", pool="other"), "vm/9101: pool 'other' is not")

    def test_volume_identity_and_ownership(self):
        self.assert_inconsistent(self.edited("volumes", "volume/local-lvm:vm-105-disk-0", vmid=9101),
                                 "vmid 9101, but the volid names VMID 105")
        self.assert_inconsistent(self.edited("volumes", "volume/local-lvm:vm-105-disk-0", storage="local"),
                                 "storage local does not match")
        self.assert_inconsistent(self.edited("volumes", "volume/local-lvm:vm-105-disk-0",
                                             id="volume/local-lvm:vm-106-disk-0"), "id does not match volid")
        backup = "volume/local:backup/vzdump-qemu-9150-2025_02_01-00_00_00.vma.zst"
        self.assert_inconsistent(self.edited("volumes", backup, vmid=None), "the volid names VMID 9150")

    def test_owner_is_the_last_vmid_in_the_volid(self):
        inv = copy.deepcopy(self.inv)  # linked clone on a directory storage: base of 9100, disk of 9101
        volid = "local:9100/base-9100-disk-0.qcow2/9101/vm-9101-disk-0.qcow2"
        inv["volumes"].append({"id": f"volume/{volid}", "volid": volid, "storage": "local", "content": "images",
                               "size": 1, "vmid": 9101})
        self.assertEqual(inventory.inconsistencies(inv), [])

    def test_other_identities_and_duplicates(self):
        self.assert_inconsistent(self.edited("storages", "storage/local", storage="local-lvm"),
                                 "storage/local: id does not match")
        self.assert_inconsistent(self.edited("network", "iface/vmbr0", iface="vmbr1"), "iface/vmbr0: id")
        self.assert_inconsistent(self.edited("disks", "disk//dev/sda", devpath="/dev/sdb"), "disk//dev/sda: id")
        inv = copy.deepcopy(self.inv)
        inv["tokens"].append({"id": "token/ghost@pve!x", "privsep": True, "expire": 0})
        self.assert_inconsistent(inv, "token/ghost@pve!x: user ghost@pve is not in users")
        inv = copy.deepcopy(self.inv)
        inv["guests"].append(copy.deepcopy(inv["guests"][0]))
        self.assert_inconsistent(inv, f"{inv['guests'][0]['id']}: listed twice")
        inv = copy.deepcopy(self.inv)
        inv["users"].append("root@pam")
        self.assert_inconsistent(inv, "user/root@pam: listed twice")


class InventoryShapeTests(unittest.TestCase):
    """(B) A missing or empty section, or a wrong version, does not pass as complete."""

    def setUp(self):
        self.inv, _ = load_inventory()

    def test_missing_section_refused(self):
        for section in inventory.SECTIONS:
            inv = copy.deepcopy(self.inv)
            del inv[section]
            for purpose in inventory.REQUIREMENTS:
                with self.subTest(section=section, purpose=purpose), \
                        self.assertRaisesRegex(inventory.IncompleteInventoryError, f"{section} is missing"):
                    inventory.require_complete(inv, purpose)

    def test_wrong_type_refused(self):
        inv = copy.deepcopy(self.inv)
        inv["guests"] = {}
        with self.assertRaisesRegex(inventory.IncompleteInventoryError, "guests is missing or not a list"):
            inventory.require_complete(inv, "vmid-range")

    def test_empty_section_refused_where_a_host_always_has_entries(self):
        # L1B (F-E): per purpose. acl and certificates feed only the baseline, so an unread
        # endpoint there no longer blocks classify, manifest or vmid-range (test_l1b_destruct.py).
        for purpose, sections in inventory.NON_EMPTY_BY_PURPOSE.items():
            for section in sections:
                inv = copy.deepcopy(self.inv)
                inv[section] = []
                with self.subTest(purpose=purpose, section=section), \
                        self.assertRaisesRegex(inventory.IncompleteInventoryError, f"{section} is empty"):
                    inventory.require_complete(inv, purpose)

    def test_empty_guests_and_errors_alone_cannot_hide_the_sentinel(self):
        # The reviewer's probe: errors emptied and guests deleted made vmid-range report nothing.
        inv = copy.deepcopy(self.inv)
        inv["errors"] = {}
        del inv["guests"]
        with self.assertRaisesRegex(inventory.IncompleteInventoryError, "guests is missing"):
            inventory.require_complete(inv, "vmid-range")

    def test_empty_optional_sections_allowed(self):
        inv = copy.deepcopy(self.inv)
        for section in set(inventory.SECTIONS) - set(inventory.NON_EMPTY):
            inv[section] = []
        inventory.require_complete(inv, "baseline")

    def test_inventory_version_checked(self):
        for value in (None, 0, 2, "1"):
            inv = copy.deepcopy(self.inv)
            if value is None:
                del inv["inventory_version"]
            else:
                inv["inventory_version"] = value
            with self.subTest(version=value), \
                    self.assertRaisesRegex(inventory.IncompleteInventoryError, "inventory_version"):
                inventory.require_complete(inv, "classify")


class TokenWithoutHardLinksTests(unittest.TestCase):
    """(C) Where os.link is not supported, the secret is still written, exclusively."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.out = Path(self.tmp.name) / "out"
        self.out.mkdir(mode=0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def no_links(self):
        return mock.patch.object(hostrun.os, "link", side_effect=PermissionError(1, "Operation not permitted"))

    def test_secret_is_written_without_hard_links(self):
        with self.no_links():
            hostrun.write_private(self.out / "token", b"secret\n", exclusive=True)
        self.assertEqual((self.out / "token").read_bytes(), b"secret\n")
        self.assertEqual((self.out / "token").stat().st_mode & 0o777, 0o600)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["token"])

    def test_fallback_never_overwrites_or_follows(self):
        victim = Path(self.tmp.name) / "victim"
        real_link = os.link

        # L1B: write_private links by directory descriptor, so the mock takes dst_dir_fd and the
        # dangling symlink appears inside that directory. What the test asserts is unchanged.
        def appears_then_fails(src, dst, *, dst_dir_fd=None, **kw):  # a dangling symlink appears, then link is unsupported
            os.symlink(victim, dst, dir_fd=dst_dir_fd)
            raise PermissionError(1, "Operation not permitted")

        with mock.patch.object(hostrun.os, "link", side_effect=appears_then_fails):
            with self.assertRaisesRegex(hostrun.HostRunError, "already exists"):
                hostrun.write_private(self.out / "token", b"secret\n", exclusive=True)
        self.assertFalse(victim.exists())
        self.assertTrue((self.out / "token").is_symlink())
        self.assertEqual([p.name for p in self.out.iterdir()], ["token"])
        self.assertIs(os.link, real_link)

    def test_fallback_failure_keeps_one_private_recovery_file_and_no_destination(self):
        # L1B: the opens are relative to a directory descriptor (the mock passes dir_fd on and
        # does not count the opens of the directory itself).
        real_open, calls = os.open, []

        def nth_open_fails(n):
            def failing(path, flags, mode=0o777, *a, dir_fd=None, **kw):
                if not flags & os.O_DIRECTORY:
                    calls.append(path)
                    if len(calls) == n:
                        raise OSError(28, "No space left on device")
                return real_open(path, flags, mode, *a, dir_fd=dir_fd, **kw)
            return failing

        # (a) The temporary file cannot be created: nothing is written, nothing is left.
        with self.no_links(), mock.patch.object(hostrun.os, "open", side_effect=nth_open_fails(1)):
            with self.assertRaisesRegex(OSError, "No space"):
                hostrun.write_private(self.out / "token", b"secret\n", exclusive=True)
        self.assertEqual(list(self.out.iterdir()), [])

        # (b) The temporary file is complete but the fallback create at the destination fails.
        # Deliberate L1B change (F-G): the one-time secret is not dropped. The destination does
        # not exist, and the only file left is the complete private temporary file, which the
        # error names.
        calls.clear()
        with self.no_links(), mock.patch.object(hostrun.os, "open", side_effect=nth_open_fails(2)):
            with self.assertRaisesRegex(hostrun.HostRunError, "is kept in"):
                hostrun.write_private(self.out / "token", b"secret\n", exclusive=True)
        self.assertEqual(calls[1], "token")  # the fallback targets the destination, by name in the directory
        self.assertFalse((self.out / "token").exists() or (self.out / "token").is_symlink())
        kept = list(self.out.iterdir())
        self.assertEqual(len(kept), 1)
        self.assertRegex(kept[0].name, r"^\.token\.[0-9a-f]{16}\.tmp$")
        self.assertEqual(kept[0].read_bytes(), b"secret\n")
        self.assertEqual(kept[0].stat().st_mode & 0o777, 0o600)

    def test_bootstrap_keeps_the_secret_without_hard_links(self):
        from tests.test_hostrun import NO_AGENT_ENV, Recorder, encrypted
        d = Path(self.tmp.name)
        cfg = fixtures.make_lab(d)
        (d / "root_key").write_text("placeholder")
        os.chmod(d / "root_key", 0o600)
        (d / "token").unlink()
        secret = "11111111-2222-3333-4444-555555555555"
        popen = Recorder(f"CORELAB_TOKEN_SECRET={secret}\n".encode())
        sha = hostrun.script_hash(hostrun.render("bootstrap", cfg))
        with self.no_links():
            code = hostrun.run("bootstrap", cfg, stdin=io.StringIO(sha[:8] + "\n"), stdout=io.StringIO(),
                               env=NO_AGENT_ENV, ancestors=(), is_tty=lambda: True, runner=encrypted, popen=popen,
                               addr_check=lambda _addr: None)
        self.assertEqual(code, 0)
        self.assertEqual((d / "token").read_text().strip(), secret)


class ManifestCheckWordingTests(unittest.TestCase):
    """(D) manifest check says what it validated against."""

    def test_check_names_its_inputs(self):
        with fixtures.private_tmpdir() as name:
            d = Path(name)
            cfg = fixtures.make_lab(d)
            inv, _ = load_inventory()
            (d / "inv.json").write_text(json.dumps(inv))
            (d / "cls.json").write_text(json.dumps(classes(inv, EVIDENCE)))
            # check recomputes the classification, so it gets the overrides the file was made with
            (d / "ov.json").write_text(json.dumps(EVIDENCE))
            (d / "m.json").write_text(json.dumps(manifest.build(inv, classes(inv, EVIDENCE))))
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(cfg.source)}), contextlib.redirect_stdout(out):
                code = cli.main(["manifest", "check", str(d / "m.json"), "--inventory", str(d / "inv.json"),
                                 "--classification", str(d / "cls.json"), "--overrides", str(d / "ov.json")])
                # Without those overrides the file is not what the inputs give: refused, and the
                # output does not claim a check.
                refused_out = io.StringIO()
                with contextlib.redirect_stdout(refused_out), contextlib.redirect_stderr(err):
                    refused = cli.main(["manifest", "check", str(d / "m.json"), "--inventory", str(d / "inv.json"),
                                        "--classification", str(d / "cls.json")])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertNotIn("manifest valid;", text)
        self.assertIn("the classification file", text)
        self.assertIn("matches the classification recomputed from the settings, the inventory and the overrides", text)
        self.assertNotIn("taken as given", text)
        self.assertEqual(refused, 2)
        self.assertIn("the classification file is not what the settings, the inventory and the overrides give",
                      err.getvalue())
        self.assertNotIn("manifest checked", refused_out.getvalue())


if __name__ == "__main__":
    unittest.main()
