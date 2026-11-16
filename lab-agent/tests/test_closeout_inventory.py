"""Finding 4: a conclusion refuses an inventory that lacks the data it rests on.

Synthetic inventories: the fixture inventory with entries added to ``errors``.
"""

import contextlib
import copy
import io
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from lab_agent import baseline, classify, cli, inventory, manifest, pveapi
from tests import fixtures
from tests.test_inventory_manifest import EVIDENCE, classes, load_inventory

N = fixtures.NODE
FIREWALL = "/cluster/firewall/options"  # refused in the fixture; no conclusion depends on it

# endpoint -> the purposes that must refuse when it was not read
DEPENDS = {
    "/cluster/resources": {"vmid-range", "classify", "manifest", "baseline"},
    f"/nodes/{N}/storage": {"vmid-range", "classify", "manifest"},
    f"/nodes/{N}/storage/local/content": {"vmid-range", "classify", "manifest"},
    "/storage": {"classify", "manifest", "baseline"},
    "/pools": {"classify", "manifest", "baseline"},
    "/access/users": {"classify", "manifest", "baseline"},
    "/access/users/olduser@pve/token": {"classify", "manifest", "baseline"},
    f"/nodes/{N}/network": {"classify", "manifest", "baseline"},
    f"/nodes/{N}/disks/list": {"classify", "manifest"},
    f"/nodes/{N}/qemu/105/config": {"manifest"},
    f"/nodes/{N}/lxc/120/config": {"manifest"},
    "/version": {"baseline"},
    "/access/acl": {"baseline"},
    f"/nodes/{N}/certificates/info": {"baseline"},
    FIREWALL: set(),
    "/cluster/status": set(),
    "/access/roles": set(),
    "/cluster/backup": set(),
    "/nodes/other-node/network": set(),  # another node's path is not this inventory's dependency
}


class RequireCompleteTests(unittest.TestCase):
    def setUp(self):
        self.inv, _ = load_inventory()
        self.cls = classes(self.inv, EVIDENCE)
        self.m = manifest.build(self.inv, self.cls)
        self.consumers = {
            "vmid-range": lambda i: classify.vmid_range_conflicts(i, 9100, 9199, fixtures.POOL),
            "classify": lambda i: classes(i, EVIDENCE),
            "manifest": lambda i: manifest.build(i, self.cls),
            "manifest-check": lambda i: manifest.validate(self.m, i, self.cls),
            "baseline": lambda i: baseline.snapshot(i, fixtures.POOL),
        }

    def partial(self, path):
        inv = copy.deepcopy(self.inv)
        inv["errors"][path] = "403 Permission check failed"
        return inv

    def test_fixture_inventory_is_complete_for_every_purpose(self):
        self.assertIn(FIREWALL, self.inv["errors"])
        for purpose in inventory.REQUIREMENTS:
            inventory.require_complete(self.inv, purpose)

    def test_each_conclusion_refuses_what_it_depends_on(self):
        for path, refusing in DEPENDS.items():
            inv = self.partial(path)
            for name, consume in self.consumers.items():
                purpose = "manifest" if name == "manifest-check" else name
                with self.subTest(path=path, consumer=name):
                    if purpose in refusing:
                        with self.assertRaises(inventory.IncompleteInventoryError) as ctx:
                            consume(inv)
                        self.assertIn(f"inventory incomplete for {purpose}", str(ctx.exception))
                        self.assertIn(path, str(ctx.exception))
                    else:
                        consume(inv)  # no exception

    def test_message_names_every_unread_endpoint(self):
        inv = self.partial("/pools")
        inv["errors"]["/access/acl"] = "403 Permission check failed"
        with self.assertRaises(inventory.IncompleteInventoryError) as ctx:
            baseline.snapshot(inv, fixtures.POOL)
        self.assertIn("/access/acl: 403", str(ctx.exception))
        self.assertIn("/pools: 403", str(ctx.exception))
        self.assertNotIn(FIREWALL, str(ctx.exception))

    def test_inventory_without_errors_record_refused(self):
        inv = copy.deepcopy(self.inv)
        del inv["errors"]
        for name, consume in self.consumers.items():
            with self.subTest(consumer=name), self.assertRaisesRegex(inventory.IncompleteInventoryError,
                                                                     "no errors record"):
                consume(inv)

    def test_inactive_storage_is_recorded_as_not_read(self):
        routes = fixtures.api_routes()
        node_storages = [dict(s, active=0 if s["storage"] == "local" else 1) for s in fixtures.NODE_STORAGES]
        routes[("GET", f"/nodes/{N}/storage")] = (200, node_storages)
        transport = pveapi.FakeTransport(routes)
        client = pveapi.Client("192.0.2.10", 8006, fixtures.TOKEN_ID, "x", transport)
        inv = inventory.normalize(inventory.collect(client, N))
        path = f"/nodes/{N}/storage/local/content"
        self.assertEqual(inv["errors"][path], inventory.INACTIVE)
        self.assertFalse([c for c in transport.calls if c[1].endswith("/storage/local/content")])
        for purpose in ("vmid-range", "classify", "manifest"):
            with self.assertRaisesRegex(inventory.IncompleteInventoryError,
                                        f"{purpose}: not read: {path}: storage inactive, content not read"):
                inventory.require_complete(inv, purpose)
        inventory.require_complete(inv, "baseline")


class CliCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)
        self.env = mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)})
        self.env.start()
        self.inv, _ = load_inventory()
        self.full = self.write("inv.json", self.inv)
        partial = copy.deepcopy(self.inv)
        partial["errors"]["/cluster/resources"] = "403 Permission check failed"
        self.partial = self.write("partial.json", partial)
        self.overrides = self.write("ov.json", EVIDENCE)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def write(self, name, obj):
        path = self.dir / name
        path.write_text(json.dumps(obj))
        return str(path)

    def run_cli(self, *argv, routes=None):
        transport = pveapi.FakeTransport(routes or fixtures.api_routes())
        fake = lambda cfg: pveapi.Client("192.0.2.10", 8006, fixtures.TOKEN_ID, "x", transport)  # noqa: E731
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(cli.Client, "from_config", side_effect=fake), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def assert_refused(self, *argv, **kw):
        code, out, err = self.run_cli(*argv, **kw)
        self.assertEqual(code, 2, out + err)
        self.assertIn("inventory incomplete", err)
        self.assertIn("/cluster/resources", err)
        return out

    def test_discover_exit_status_shows_incompleteness(self):
        code, out, _ = self.run_cli("discover", "--out-dir", str(self.dir / "d1"))
        self.assertEqual(code, 1)
        self.assertIn("INCOMPLETE: 1 endpoint(s) not read", out)
        written = json.loads((self.dir / "d1" / "inventory.json").read_text())
        self.assertIn(FIREWALL, written["errors"])  # the partial inventory is written, and marked
        routes = fixtures.api_routes()
        routes[("GET", FIREWALL)] = (200, {"enable": 0})
        code, out, _ = self.run_cli("discover", "--out-dir", str(self.dir / "d2"), routes=routes)
        self.assertEqual(code, 0)
        self.assertNotIn("INCOMPLETE", out)

    def test_classify_refuses(self):
        out = self.assert_refused("classify", "--inventory", self.partial, "--overrides", self.overrides,
                                  "--out", str(self.dir / "cls.json"))
        self.assertNotIn("VMID range conflict", out)
        self.assertFalse((self.dir / "cls.json").exists())

    def test_manifest_build_and_check_refuse(self):
        # build and check recompute the classification from the settings, the inventory and the
        # overrides, so they get the overrides this classification was made with. The refusals are
        # then for the incomplete inventory (assert_refused checks that wording), not for a
        # classification that does not match.
        cls = self.write("cls.json", classes(self.inv, EVIDENCE))
        self.assert_refused("manifest", "build", "--inventory", self.partial, "--classification", cls,
                            "--overrides", self.overrides, "--out", str(self.dir / "m.json"))
        self.assertFalse((self.dir / "m.json").exists())
        # A classification that is not what the given inputs produce is refused, with the complete
        # inventory too: here the overrides it was made with are left out. Nothing is written.
        code, _, err = self.run_cli("manifest", "build", "--inventory", self.full, "--classification", cls,
                                    "--out", str(self.dir / "m.json"))
        self.assertEqual(code, 2)
        self.assertIn("the classification file is not what the settings, the inventory and the overrides give", err)
        self.assertFalse((self.dir / "m.json").exists())
        self.assertEqual(self.run_cli("manifest", "build", "--inventory", self.full, "--classification", cls,
                                      "--overrides", self.overrides, "--out", str(self.dir / "m.json"))[0], 0)
        built = json.loads((self.dir / "m.json").read_text())
        self.assertEqual(built["inventory_digest"], inventory.digest(self.inv))
        self.assert_refused("manifest", "check", str(self.dir / "m.json"), "--inventory", self.partial,
                            "--classification", cls, "--overrides", self.overrides)
        # The same mismatch is refused by check against the complete inventory.
        code, _, err = self.run_cli("manifest", "check", str(self.dir / "m.json"), "--inventory", self.full,
                                    "--classification", cls)
        self.assertEqual(code, 2)
        self.assertIn("the classification file is not what the settings, the inventory and the overrides give", err)

    def test_baseline_save_and_verify_refuse(self):
        b = str(self.dir / "baseline.json")
        self.assert_refused("baseline", "save", "--inventory", self.partial, "--out", b)
        self.assertFalse(Path(b).exists())
        self.assertEqual(self.run_cli("baseline", "save", "--inventory", self.full, "--out", b)[0], 0)
        self.assert_refused("baseline", "verify", "--baseline", b, "--inventory", self.partial)
        routes = fixtures.api_routes()
        routes[("GET", "/cluster/resources")] = (403, "Permission check failed")
        self.assert_refused("baseline", "verify", "--baseline", b, routes=routes)  # live read


if __name__ == "__main__":
    unittest.main()
