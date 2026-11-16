"""Finding 3: apply-manifest renders and executes only after the full, inventory-bound check.

Every refusal must happen before a script is rendered and before any runner or ssh call;
the recorders below prove nothing was executed.
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

from lab_agent import classify, hostrun, inventory, manifest
from tests import fixtures
from tests.test_hostrun import NO_AGENT_ENV, Recorder
from tests.test_inventory_manifest import EVIDENCE, classes, load_inventory


class RunnerRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, 1)  # ssh-keygen probe: key is encrypted


def guest_item(rid, gtype, name, status, digest, template=False):
    return {"id": rid, "type": gtype,
            "current_state": {"node": fixtures.NODE, "name": name, "status": status, "digest": digest,
                              "template": template},
            "operation": "delete-purge" if status == "stopped" else "stop-and-delete-purge",
            "reason": "synthetic test item", "dependencies": [], "backup": "config-only", "reversible": "no",
            "expected_result": f"{rid} absent", "verify": f"{rid} not in /cluster/resources"}


SENTINEL_ITEM = guest_item("vm/9050", "qemu", "corelab-sentinel", "stopped", "c" * 40)       # PRESERVE
POOL_ITEM = guest_item("vm/9101", "qemu", "demo-1", "running", "e" * 40)                     # REUSE
CT_ITEM = guest_item("ct/120", "lxc", "old-ct", "stopped", "f" * 40)                         # UNKNOWN
ABSENT_ITEM = guest_item("vm/777", "qemu", "ghost", "stopped", "7" * 40)                     # not inventoried


class ApplyHarness:
    """setUp and the refusal assertion, shared with test_closeout_review."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.cfg = fixtures.make_lab(self.dir)
        (self.dir / "root_key").write_text("placeholder")
        os.chmod(self.dir / "root_key", 0o600)
        self.inv, _ = load_inventory()
        self.m = manifest.build(self.inv, classes(self.inv, EVIDENCE))

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, obj):
        path = self.dir / name
        path.write_text(json.dumps(obj))
        return str(path)

    def attempt(self, m, *, inv=None, overrides=None, answer="x\n"):
        """Run apply-manifest with a correct hash for ``m``; return (outcome, popen, runner, out)."""
        popen, runner, out = Recorder(), RunnerRecorder(), io.StringIO()
        paths = {"manifest_path": self.write("m.json", m),
                 "inventory_path": self.write("inv.json", self.inv if inv is None else inv),
                 "overrides_path": self.write("ov.json", EVIDENCE if overrides is None else overrides)}
        with mock.patch.object(manifest, "render_host_script", wraps=manifest.render_host_script) as rendered:
            try:
                code = hostrun.run("apply-manifest", self.cfg, expected_sha=manifest.manifest_hash(m),
                                   stdin=io.StringIO(answer), stdout=out, env=NO_AGENT_ENV, ancestors=(),
                                   is_tty=lambda: True, runner=runner, popen=popen,
                                   addr_check=lambda _addr: None, **paths)
                outcome = code
            except (manifest.ManifestError, classify.ClassificationError, inventory.IncompleteInventoryError,
                    hostrun.HostRunError) as exc:
                outcome = exc
        self.rendered_calls = rendered.call_count
        return outcome, popen, runner, out.getvalue()

    def assert_refused(self, m, pattern, **kw):
        outcome, popen, runner, out = self.attempt(m, **kw)
        self.assertIsInstance(outcome, Exception, f"expected a refusal, got exit {outcome}")
        self.assertRegex(str(outcome), pattern)
        self.assertEqual(popen.calls, [], "ssh must not be started")
        self.assertEqual(runner.calls, [], "no runner call (root-key probe) may happen")
        self.assertEqual(self.rendered_calls, 0, "no script may be rendered")
        self.assertNotIn("----- script -----", out)
        self.assertFalse((self.dir / "state" / "approvals.jsonl").exists())
        return outcome

    def with_items(self, *extra):
        m = copy.deepcopy(self.m)
        m["items"].extend(copy.deepcopy(list(extra)))
        return m


class ApplyManifestGateTests(ApplyHarness, unittest.TestCase):

    # -- refusals ------------------------------------------------------------------------
    def test_preserve_item_refused(self):
        self.assert_refused(self.with_items(SENTINEL_ITEM), "vm/9050: classified PRESERVE")

    def test_reuse_item_refused(self):
        self.assert_refused(self.with_items(POOL_ITEM), "vm/9101: classified REUSE")

    def test_modify_item_refused(self):
        overrides = dict(EVIDENCE, **{"ct/120": {"class": "MODIFY", "reason": "additive change only"}})
        self.assert_refused(self.with_items(CT_ITEM), "ct/120: classified MODIFY", overrides=overrides)

    def test_unknown_item_refused(self):
        self.assert_refused(self.with_items(CT_ITEM), "ct/120: classified UNKNOWN")

    def test_item_absent_from_classification_refused(self):
        self.assertNotIn("vm/777", classes(self.inv, EVIDENCE))
        self.assert_refused(self.with_items(ABSENT_ITEM), "vm/777: classified UNKNOWN")

    def test_state_mismatch_refused(self):
        m = copy.deepcopy(self.m)
        m["items"][0]["current_state"]["digest"] = "9" * 40
        self.assert_refused(m, "state differs from the inventory: vm/105: digest")

    def test_classification_file_is_not_trusted(self):
        # An override cannot turn a PRESERVE resource into a removal: the rules are re-applied.
        overrides = dict(EVIDENCE, **{"vm/9050": {"class": "REMOVE_CANDIDATE", "evidence": "x" * 20}})
        self.assert_refused(self.with_items(SENTINEL_ITEM), "PRESERVE cannot be overridden", overrides=overrides)

    def test_without_overrides_nothing_is_removable(self):
        self.assert_refused(self.m, "vm/105: classified UNKNOWN", overrides={})

    def test_missing_inventory_digest_refused(self):
        m = copy.deepcopy(self.m)
        m["inventory_digest"] = None
        self.assert_refused(m, "no inventory_digest")

    def test_other_inventory_refused(self):
        other = copy.deepcopy(self.inv)
        other["users"].append("someone@pve")
        self.assert_refused(self.m, "manifest was built from", inv=other)

    def test_incomplete_inventory_refused(self):
        partial = copy.deepcopy(self.inv)
        partial["errors"][f"/nodes/{fixtures.NODE}/qemu/105/config"] = "403 Permission check failed"
        m = copy.deepcopy(self.m)
        m["inventory_digest"] = inventory.digest(partial)  # bound to it, so only completeness can refuse
        self.assert_refused(m, rf"inventory incomplete for manifest: not read: /nodes/{fixtures.NODE}/qemu/105/config",
                            inv=partial)

    def test_missing_inventory_argument_refused(self):
        popen, runner = Recorder(), RunnerRecorder()
        with self.assertRaisesRegex(hostrun.HostRunError, "--inventory"):
            hostrun.run("apply-manifest", self.cfg, manifest_path=self.write("m.json", self.m),
                        expected_sha=manifest.manifest_hash(self.m), stdin=io.StringIO("x\n"), stdout=io.StringIO(),
                        env=NO_AGENT_ENV, ancestors=(), is_tty=lambda: True, runner=runner, popen=popen)
        self.assertEqual((popen.calls, runner.calls), ([], []))

    def test_render_itself_refuses(self):
        bad = self.with_items(SENTINEL_ITEM)
        with self.assertRaisesRegex(manifest.ManifestError, "classified PRESERVE"):
            hostrun.render("apply-manifest", self.cfg, bad, inventory=self.inv, overrides=EVIDENCE)
        with self.assertRaisesRegex(hostrun.HostRunError, "--inventory"):
            hostrun.render("apply-manifest", self.cfg, self.m)
        with self.assertRaisesRegex(manifest.ManifestError, "classified PRESERVE"):
            manifest.render_host_script(bad, self.inv, classes(self.inv, EVIDENCE))

    def test_show_refuses_unvalidated_manifest(self):
        env = mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)})
        with env:
            for argv, pattern in (
                    (["show", "apply-manifest", "--manifest", self.write("m.json", self.m)], "--inventory"),
                    (["show", "apply-manifest", "--manifest", self.write("bad.json", self.with_items(SENTINEL_ITEM)),
                      "--inventory", self.write("inv.json", self.inv), "--overrides", self.write("ov.json", EVIDENCE)],
                     "classified PRESERVE")):
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = hostrun.main(argv)
                self.assertEqual(code, 2)
                self.assertRegex(err.getvalue(), pattern)
                self.assertEqual(out.getvalue(), "")

    # -- the accepted case: validated and listed, then refused, because execution is disabled -------
    def test_valid_manifest_is_validated_and_listed_but_never_rendered_or_sent(self):
        script = hostrun.render("apply-manifest", self.cfg, self.m, inventory=self.inv, overrides=EVIDENCE)
        sha = hostrun.script_hash(script)
        for answer in (sha[:8] + "\n", "x\n", ""):  # the right hash prefix changes nothing: no prompt exists
            with self.subTest(answer=answer):
                outcome, popen, runner, out = self.attempt(self.m, answer=answer)
                self.assertIsInstance(outcome, hostrun.HostRunError)
                self.assertIn("apply-manifest is disabled in this version of the tooling", str(outcome))
                self.assertIn("Manifest for node", out)  # the request passed validation; the plan was listed
                self.assertEqual(self.rendered_calls, 0, "no script may be rendered for a run")
                self.assertEqual(popen.calls, [], "ssh must not be started")
                self.assertEqual(runner.calls, [], "no root-key probe may happen")
                self.assertNotIn("----- script -----", out)
                self.assertNotIn("Type the first 8 characters", out)
                self.assertFalse((self.dir / "state" / "approvals.jsonl").exists())
                self.assertFalse((self.dir / "state" / "runs").exists())
        # The spy is live on the preview path, so "nothing rendered" above and in every refusal check
        # of this class is an observation and not an artefact of the spy.
        with mock.patch.object(manifest, "render_host_script", wraps=manifest.render_host_script) as rendered:
            hostrun.render("apply-manifest", self.cfg, self.m, inventory=self.inv, overrides=EVIDENCE)
        self.assertEqual(rendered.call_count, 1)
        self.assertIn(f"CL_MANIFEST_SHA256={manifest.manifest_hash(self.m)}", script)

    def test_show_renders_valid_manifest(self):
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(self.cfg.source)}):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = hostrun.main(["show", "apply-manifest", "--manifest", self.write("m.json", self.m),
                                     "--inventory", self.write("inv.json", self.inv),
                                     "--overrides", self.write("ov.json", EVIDENCE)])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(),
                         hostrun.render("apply-manifest", self.cfg, self.m, inventory=self.inv, overrides=EVIDENCE))

    def test_other_actions_take_no_manifest_inputs(self):
        with self.assertRaisesRegex(hostrun.HostRunError, "does not take"):
            hostrun.render("preflight", self.cfg, inventory=self.inv)


if __name__ == "__main__":
    unittest.main()
