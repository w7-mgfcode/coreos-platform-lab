"""Host action scripts against stub tools (offline only).

Each action is rendered exactly as the owner-only runner would send it (header, helpers,
action text) and run with ``bash -s`` in a temporary directory whose PATH starts with the
stand-ins of ``tests/stubs/l1b_tools.py``. Nothing here contacts a host. A pass shows what
the script does with the answers the stub gives; it does not show how real ``pvesh``,
``pveum``, ``pvesm`` or ``qm`` answer, nor real permissions, routing or recovery.

Differences between the rendered script and the one under test, all in the harness:
  * ``prepare`` and ``sentinel``: the fixed host locations (the lines ``la_sbin=``,
    ``la_cfgdir=``, ``la_home=``, and for prepare ``la_mountinfo=`` when a test crafts a
    mount table) point into the temporary directory, and for prepare ``/tmp``, ``/var/tmp``,
    ``/home`` and ``/run`` are taken out of the system-path list, because the temporary
    directory lives under one of them. Tests of the system-path refusal run the script
    unmodified.
  * the stub ``stat`` reports owner root and no group/other write bit, because the test user
    is not root; the tests that need a foreign owner or a writable directory say so in state.
  * the stub ``install`` drops ``-o``/``-g``; the stub ``chown`` only logs.

Set L1B_ACTION_DIR to run the same tests against another copy of the action files.
"""

import hashlib
import json
import lzma
import os
import re
import shlex
import subprocess
import unittest
from pathlib import Path

from lab_agent import hostrun
from tests import fixtures

STUB = Path(__file__).resolve().parent / "stubs" / "l1b_tools.py"
ACTIONS_DIR = hostrun.HOST_DIR / "actions"
TOOLS = ("pvesh", "qm", "pveum", "pvesm", "vzdump", "curl", "useradd", "passwd", "getent", "id",
         "hostname", "chown", "install", "stat")
NODE = "pve1"
PUBKEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBTESTKEYONLYxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FIXTURE_DESC = "Negative RBAC test fixture. Worthless by design. [corelab-fixture sentinel-v1 vmid=9050]"
PAYLOAD = b"fake-qcow2-image-" * 64


class LabCase(unittest.TestCase):
    def setUp(self):
        self.tmpd = fixtures.private_tmpdir()
        self.T = Path(os.path.realpath(self.tmpd.name))
        self.bin = self.T / "bin"
        self.bin.mkdir()
        for tool in TOOLS:
            (self.bin / tool).symlink_to(STUB)
        self.cfgdir = self.T / "cfg"
        self.cfgdir.mkdir()
        (self.cfgdir / "snip_key.pub").write_text(PUBKEY + " test\n")
        (self.T / "srv").mkdir()
        self.store = self.T / "srv" / "corelab"
        self.log = self.T / "calls.log"
        self.state_file = self.T / "state.json"
        self.state: dict = {}
        self.after: dict = {}
        self.mountinfo = None  # prepare reads the real mount table unless a test crafts one
        self.host_id = "0123456789abcdef" * 2
        (self.T / "machine-id").write_text(self.host_id + "\n")

    def tearDown(self):
        self.tmpd.cleanup()

    # -- harness ---------------------------------------------------------------------------
    def render(self, action, env):
        cfg = fixtures.make_lab(self.cfgdir, PVE_LAB_STORAGE_PATH=str(self.store), PVE_TEMPLATE_VMID="9100")
        script = hostrun.render(action, cfg)
        override = os.environ.get("L1B_ACTION_DIR")
        if override:
            script = script.replace((ACTIONS_DIR / f"{action}.sh").read_text(), (Path(override) / f"{action}.sh").read_text())
        unmodified = env.pop("_UNMODIFIED", False)
        if action in ("prepare", "sentinel") and not unmodified:
            script = self.rewrite_fixed(script, action)
        if action == "prepare" and "CL_SNIP_PUBKEY" in env:  # the renderer appends its own export later
            script = re.sub(r"^export CL_SNIP_PUBKEY=.*$", lambda _m: f"export CL_SNIP_PUBKEY={shlex.quote(env.pop('CL_SNIP_PUBKEY'))}",
                            script, flags=re.M)
        extras = {}  # fcos-template receives CL_VMID_RANGE and CL_SENTINEL_VMID from the renderer
        extras.update(env)
        head, rest = script.split("\n\n", 1)
        exports = "".join(f"export {k}={shlex.quote(v)}\n" for k, v in extras.items())
        return head + "\n" + exports + "\n" + rest

    def rewrite_fixed(self, script, action):
        """Point the fixed host locations at the temporary directory (see the module text)."""
        wanted = {"prepare": ("la_sbin", "la_cfgdir", "la_home"), "sentinel": ("la_cfgdir",)}[action]
        lines = re.findall(r"^la_machine_id=\S+$", script, re.M)
        self.assertEqual(len(lines), 1)
        script = script.replace(lines[0], f"la_machine_id={self.T / 'machine-id'}")
        places = {"la_sbin": self.T / "sbin", "la_cfgdir": self.T / "etc-corelab", "la_home": self.T / "home-snip"}
        for name in ("la_sbin", "la_cfgdir", "la_home"):
            lines = re.findall(rf"^{name}=\S+$", script, re.M)
            self.assertEqual(len(lines), 1 if name in wanted else 0, name)
            if lines:
                script = script.replace(lines[0], f"{name}={places[name]}")
        if action == "prepare":
            if self.mountinfo:
                line = re.findall(r"^la_mountinfo=\S+$", script, re.M)
                self.assertEqual(len(line), 1)
                script = script.replace(line[0], f"la_mountinfo={self.mountinfo}")
            denied = re.search(r'local denied="([^"]*)"', script)
            self.assertIsNotNone(denied)
            kept = " ".join(p for p in denied.group(1).split() if p not in ("/tmp", "/var/tmp", "/home", "/run"))
            script = script.replace(denied.group(0), f'local denied="{kept}"')
        return script

    def run_action(self, action, env=None, state=None):
        self.state = state if state is not None else self.state
        self.state_file.write_text(json.dumps(self.state))
        self.log.write_text("")
        (self.T / "sbin").mkdir(exist_ok=True)
        run_env = {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.T), "STUB_STATE": str(self.state_file),
                   "STUB_LOG": str(self.log), "TMPDIR": str(self.T)}
        proc = subprocess.run(["bash", "-s"], input=self.render(action, dict(env or {})), text=True,
                              capture_output=True, env=run_env, timeout=120)
        self.after = json.loads(self.state_file.read_text())
        return proc

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines() if line]

    def called(self, *prefix):
        return any(c[:len(prefix)] == list(prefix) for c in self.calls())

    def assertNotCalled(self, *prefix):
        self.assertFalse(self.called(*prefix), f"unexpected call {prefix}")

    def assertRefused(self, proc, code=3, text=None):
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        if text:
            self.assertIn(text, proc.stderr)


# ------------------------------------------------------------------------------ bootstrap
class BootstrapTests(LabCase):
    def setUp(self):
        super().setUp()
        self.state = {"users": [], "tokens": {}}

    def test_positive_control_valid_days_create_token_once(self):
        proc = self.run_action("bootstrap", {"CL_EXPIRE_DAYS": "90"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.count("CORELAB_TOKEN_SECRET="), 1)
        add = next(c for c in self.calls() if c[1:4] == ["user", "token", "add"])
        expire = int(add[add.index("--expire") + 1])
        self.assertGreater(expire, 1_700_000_000)

    def test_ha1_crafted_expire_days_never_reach_arithmetic(self):
        marker = self.T / "pwned"
        crafted = [f"a[$(touch {marker})]", f"x[`touch {marker}`]", "1+1", "0", "-5", "010", "1e3", "366",
                   "99999999999", " 5", "5 ", "5\nfoo", "0x10", ""]
        for value in crafted:
            with self.subTest(value=value):
                proc = self.run_action("bootstrap", {"CL_EXPIRE_DAYS": value}, state={"users": [], "tokens": {}})
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(marker.exists(), "a command ran as the script's user")
                self.assertNotIn("CORELAB_TOKEN_SECRET", proc.stdout)
                self.assertNotCalled("pveum", "user", "add")
                self.assertNotCalled("pveum", "user", "token", "add")

    def test_ha1_bounds_are_inclusive(self):
        for value, code in (("1", 0), ("365", 0)):
            with self.subTest(value=value):
                proc = self.run_action("bootstrap", {"CL_EXPIRE_DAYS": value}, state={"users": [], "tokens": {}})
                self.assertEqual(proc.returncode, code, proc.stderr)

    def test_user_and_token_names_are_validated(self):
        for key, value in (("CL_USER", "-x@pve"), ("CL_USER", "a@pam"), ("CL_USER", "a b@pve"),
                           ("CL_TOKEN", "-t"), ("CL_TOKEN", "t;x"), ("CL_TOKEN", "1abc")):
            with self.subTest(key=key, value=value):
                proc = self.run_action("bootstrap", {key: value, "CL_EXPIRE_DAYS": "90"},
                                       state={"users": [], "tokens": {}})
                self.assertRefused(proc)
                self.assertNotCalled("pveum", "user", "add")

    def test_ha10_failed_or_unusable_listing_is_not_absence(self):
        cases = {
            "user list fails": {"fail": ["pveum user list"]},
            "user list empty output": {"garbage": {"pveum user list": ""}},
            "user list not an array": {"garbage": {"pveum user list": '{"data": []}'}},
            "token list fails": {"users": [{"userid": "corelab-agent@pve"}], "fail": ["pveum user token list"]},
            "token list empty output": {"users": [{"userid": "corelab-agent@pve"}],
                                        "garbage": {"pveum user token list": ""}},
            "user list with an empty record": {"garbage": {"pveum user list": "[{}]"}},
            "user list with a duplicate": {"garbage": {"pveum user list": '[{"userid":"a@pve"},{"userid":"a@pve"}]'}},
            "user id is not a scalar": {"garbage": {"pveum user list": '[{"userid":["corelab-agent@pve"]}]'}},
            "token list with an empty record": {"users": [{"userid": "corelab-agent@pve"}],
                                                "garbage": {"pveum user token list": "[{}]"}},
        }
        for name, extra in cases.items():
            with self.subTest(name):
                state = {"users": [], "tokens": {}}
                state.update(extra)
                proc = self.run_action("bootstrap", {"CL_EXPIRE_DAYS": "90"}, state=state)
                self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
                self.assertNotCalled("pveum", "user", "add")
                self.assertNotCalled("pveum", "user", "token", "add")
                self.assertNotIn("CORELAB_TOKEN_SECRET", proc.stdout)

    def test_ha10_positive_control_existing_user_and_free_token(self):
        proc = self.run_action("bootstrap", {"CL_EXPIRE_DAYS": "90"},
                               state={"users": [{"userid": "corelab-agent@pve"}], "tokens": {"corelab-agent@pve": []}})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotCalled("pveum", "user", "add")

    def test_secret_is_not_in_argv_or_stderr(self):
        proc = self.run_action("bootstrap", {"CL_EXPIRE_DAYS": "90"})
        secret = "test-only-token-value-not-a-secret"
        self.assertNotIn(secret, proc.stderr)
        self.assertNotIn(secret, self.log.read_text())

    def test_8_unusable_token_responses_are_refused_without_echoing_them(self):
        good = "test-only-token-value-not-a-secret"
        bad = {"value with a newline": json.dumps({"value": good + "\nCORELAB_TOKEN_SECRET=injected"}),
               "value with a trailing newline": json.dumps({"value": good + "\n"}),
               "value is an object": json.dumps({"value": {"a": good}}),
               "value is a list": json.dumps({"value": [good]}),
               "value too short": json.dumps({"value": "abc"}),
               "value with other characters": json.dumps({"value": good + " ;rm"}),
               "no value": json.dumps({"full-tokenid": "x"}),
               "response is a list": json.dumps([{"value": good}]),
               "response is text": "not json at all " + good,
               "empty response": ""}
        for name, text in bad.items():
            with self.subTest(name):
                state = {"users": [], "tokens": {}, "garbage": {"pveum user token add": text}}
                proc = self.run_action("bootstrap", {"CL_EXPIRE_DAYS": "90"}, state=state)
                self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
                self.assertNotIn("CORELAB_TOKEN_SECRET", proc.stdout)
                self.assertNotIn(good, proc.stdout + proc.stderr)
                self.assertNotIn("injected", proc.stdout + proc.stderr)
                self.assertNotCalled("pveum", "acl")

    def test_acl_failure_names_the_token_and_prints_no_secret(self):
        proc = self.run_action("bootstrap", {"CL_EXPIRE_DAYS": "90"},
                               state={"users": [], "tokens": {}, "fail": ["pveum acl modify"]})
        self.assertEqual(proc.returncode, 4)
        self.assertNotIn("CORELAB_TOKEN_SECRET", proc.stdout)
        self.assertIn("remove the token by hand", proc.stderr)


# ------------------------------------------------------------------------------- prepare
class PrepareTests(LabCase):
    def setUp(self):
        super().setUp()
        (self.T / "vz").mkdir()
        self.state = {"pools": [], "acl_list": [],
                      "storages": [{"storage": "local", "type": "dir", "path": str(self.T / "vz"), "content": "iso,backup"},
                                   {"storage": "local-lvm", "type": "lvmthin", "content": "images,rootdir"}]}

    def other_storage(self, name, path):
        self.state["storages"].append({"storage": name, "type": "dir", "path": str(path), "content": "images"})

    def make_record(self, storage="corelab", path=None, host=None, state="complete", token="ab" * 16, raw=None, **over):
        """A storage record as an earlier run would have left it. If the storage directory exists it also
        gets the marker, and a complete record carries the directory's real device, inode and filesystem id."""
        d = self.T / "etc-corelab"
        d.mkdir(exist_ok=True)
        os.chmod(d, 0o755)
        rec = {"storage": storage, "path": str(path or self.store), "host": host or self.host_id,
               "state": state, "token": token}
        if self.store.exists():
            (self.store / ".corelab-project").write_text(f"storage=corelab\ntoken={token}\n")
            if state == "complete":
                fsid = subprocess.run(["stat", "-f", "-c", "%i", str(self.store)], capture_output=True, text=True,
                                      check=True).stdout.strip()
                rec.update(dev=str(os.stat(self.store).st_dev), ino=str(os.stat(self.store).st_ino), fsid=fsid)
        elif state == "complete":
            rec.update(dev="1", ino="2", fsid="3")
        rec.update(over)
        text = "".join(f"{k}={v}\n" for k, v in rec.items() if v is not None) if raw is None else raw
        self.record = d / "storage-corelab.record"
        self.record.write_text(text)

    def write_mountinfo(self, *lines):
        path = self.T / "mountinfo"
        path.write_text("\n".join(lines) + "\n")
        self.mountinfo = str(path)

    def assertNothingChanged(self):
        for call in (("pveum", "pool", "add"), ("pvesm", "add"), ("useradd",), ("chown",), ("pveum", "acl"), ("install",)):
            self.assertNotCalled(*call)

    def test_positive_control_full_run(self):
        proc = self.run_action("prepare")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.called("pveum", "pool", "add", "corelab"))
        self.assertTrue(self.called("pvesm", "add", "dir", "corelab"))
        writer = self.T / "sbin" / "corelab-snippet-put"
        self.assertEqual(writer.stat().st_mode & 0o777, 0o755)
        self.assertIn(f"dir = {self.store}/snippets", (self.T / "etc-corelab" / "snippet-writer.conf").read_text())
        keys = (self.T / "home-snip" / ".ssh" / "authorized_keys").read_text()
        self.assertEqual(keys, f'restrict,from="192.0.2.50",command="/usr/local/sbin/corelab-snippet-put" {PUBKEY}\n')
        self.assertEqual(list((self.T / "sbin").glob(".corelab-*")), [])  # temporary files are gone
        fields = dict(l.split("=", 1) for l in (self.T / "etc-corelab" / "storage-corelab.record").read_text().splitlines())
        self.assertEqual({k: fields[k] for k in ("storage", "path", "host", "state")},
                         {"storage": "corelab", "path": str(self.store), "host": self.host_id, "state": "complete"})
        self.assertEqual(fields["dev"], str(os.stat(self.store).st_dev))
        self.assertEqual(fields["ino"], str(os.stat(self.store).st_ino))
        self.assertRegex(fields["token"], r"^[0-9a-f]{32}$")
        self.assertEqual((self.store / ".corelab-project").read_text(), f"storage=corelab\ntoken={fields['token']}\n")
        self.assertEqual((self.T / "etc-corelab" / "storage-corelab.record").stat().st_mode & 0o777, 0o644)

    def test_positive_control_second_run_changes_nothing_more(self):
        self.assertEqual(self.run_action("prepare").returncode, 0)
        proc = self.run_action("prepare", state=self.after)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotCalled("pveum", "pool", "add")
        self.assertNotCalled("pvesm", "add")
        self.assertNotCalled("useradd")

    # -- storage path ----------------------------------------------------------------------
    def test_ha2_traversal_and_odd_paths_refused_before_any_change(self):
        for path in (f"{self.T}/srv/../srv/corelab", f"{self.T}/srv/./corelab", f"{self.T}/srv//corelab",
                     f"{self.store}/", "srv/corelab", f"{self.T}/srv/co relab", f"{self.T}/srv/co$(id)",
                     f"/{'a' * 201}", "/onlyone"):
            with self.subTest(path=path):
                proc = self.run_action("prepare", {"CL_LAB_STORAGE_PATH": path})
                self.assertRefused(proc)
                self.assertNothingChanged()

    def test_ha2_symlinked_component_refused(self):
        real = self.T / "srv" / "real"
        real.mkdir()
        (self.T / "srv" / "link").symlink_to(real)
        for path in (self.T / "srv" / "link" / "corelab", self.T / "srv" / "link"):
            with self.subTest(path=str(path)):
                proc = self.run_action("prepare", {"CL_LAB_STORAGE_PATH": str(path)})
                self.assertRefused(proc, text="symbolic link")
                self.assertNothingChanged()

    def test_ha2_system_paths_refused_with_the_unmodified_script(self):
        for path in ("/etc/corelab", "/etc", "/usr/local/corelab", "/var/lib/vz/corelab", "/var/lib/vz",
                     "/var/lib", "/var/lib/pve-cluster/x", "/boot/x", "/root/x", "/mnt/pve/nas", "/lib/x"):
            with self.subTest(path=path):
                proc = self.run_action("prepare", {"CL_LAB_STORAGE_PATH": path, "_UNMODIFIED": True})
                self.assertRefused(proc)
                self.assertNothingChanged()

    def test_ha2_overlap_with_existing_storage_refused(self):
        shared = self.T / "srv" / "shared"
        shared.mkdir()
        (shared / "sub").mkdir()
        self.other_storage("nas", shared)
        for path in (shared, shared / "sub", self.T / "srv" / "shared" / "new"):
            with self.subTest(path=str(path)):
                proc = self.run_action("prepare", {"CL_LAB_STORAGE_PATH": str(path)})
                self.assertRefused(proc)
                self.assertNothingChanged()
        inner = self.store / "other"  # the candidate contains an existing storage
        inner.mkdir(parents=True)
        self.state["storages"] = self.state["storages"][:2]
        self.other_storage("inner", inner)
        self.make_record()
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="overlaps")
        self.assertNothingChanged()

    def test_ha2_storage_path_that_is_a_storage_through_an_alias_link_is_refused(self):
        real = self.T / "srv" / "shared"
        real.mkdir()
        alias = self.T / "srv" / "alias"
        alias.symlink_to(real)
        self.other_storage("nas", alias)
        proc = self.run_action("prepare", {"CL_LAB_STORAGE_PATH": str(real)})
        self.assertRefused(proc, text="overlaps")
        self.assertNothingChanged()

    def test_ha2_owner_and_write_bits_of_existing_components(self):
        self.store.mkdir()
        base = json.loads(json.dumps(self.state))
        for key, text in (("foreign", "not owned by root"), ("writable", "writable by group or others")):
            for target in (self.store, self.T / "srv"):
                with self.subTest(kind=key, target=str(target)):
                    state = dict(base, **{key: [str(target)]})
                    proc = self.run_action("prepare", state=state)
                    self.assertRefused(proc, text=text)
                    self.assertNothingChanged()

    def test_ha2_missing_parent_refused(self):
        proc = self.run_action("prepare", {"CL_LAB_STORAGE_PATH": f"{self.T}/nowhere/corelab"})
        self.assertRefused(proc, text="does not exist")
        self.assertNothingChanged()

    # -- mount aliases (crafted mount tables: by construction, no real bind mount is made) --
    def alias_layout(self, *mount_lines):
        shared, alias = self.T / "srv" / "shared", self.T / "srv" / "alias"
        shared.mkdir()
        alias.mkdir()
        self.other_storage("nas", shared)
        self.write_mountinfo("1 0 8:1 / / rw - ext4 /dev/sda1 rw", *[l.format(alias=alias) for l in mount_lines])
        return alias / "project"

    def test_1_bind_mount_alias_of_another_storage_refused(self):
        path = self.alias_layout("2 1 8:1 /shared {alias} rw - ext4 /dev/sda1 rw")
        proc = self.run_action("prepare", {"CL_LAB_STORAGE_PATH": str(path)})
        self.assertRefused(proc, text="different mounts of the same device")
        self.assertNothingChanged()

    def test_1_same_source_through_another_mount_refused(self):
        path = self.alias_layout("2 1 0:45 /@alias {alias} rw - btrfs /dev/sda1 rw")
        proc = self.run_action("prepare", {"CL_LAB_STORAGE_PATH": str(path)})
        self.assertRefused(proc, text="same mount source")
        self.assertNothingChanged()

    def test_1_positive_control_a_separate_filesystem_is_accepted(self):
        path = self.alias_layout("2 1 8:2 / {alias} rw - ext4 /dev/sdb1 rw")
        proc = self.run_action("prepare", {"CL_LAB_STORAGE_PATH": str(path)})
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_1_positive_control_one_mount_is_accepted(self):
        self.write_mountinfo("1 0 8:1 / / rw - ext4 /dev/sda1 rw")
        self.assertEqual(self.run_action("prepare").returncode, 0)

    def test_1_unplaceable_layout_is_refused(self):
        self.write_mountinfo("1 0 8:1 / /somewhere/else rw - ext4 /dev/sda1 rw")
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="cannot place")
        self.assertNothingChanged()
        (self.T / "mountinfo").unlink()
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="cannot place")

    def test_1_storage_whose_path_cannot_be_checked_is_refused(self):
        self.other_storage("gone", self.T / "srv" / "not-there")
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="cannot verify")
        self.assertNothingChanged()

    # -- provenance ------------------------------------------------------------------------
    def test_2_existing_directory_without_a_record_is_refused_even_if_empty_or_familiar(self):
        for layout in ((), ("snippets", "import", "template"), ("dump", "images")):
            with self.subTest(layout=layout):
                if self.store.exists():
                    for child in self.store.iterdir():
                        child.rmdir()
                else:
                    self.store.mkdir()
                for name in layout:
                    (self.store / name).mkdir()
                proc = self.run_action("prepare")
                self.assertRefused(proc, text="no root-owned record")
                self.assertNothingChanged()

    def test_2_record_for_another_storage_or_path_refused(self):
        self.store.mkdir()
        self.make_record(storage="other")
        self.assertRefused(self.run_action("prepare"), text="names another storage or path")
        self.make_record(path=self.T / "srv" / "else")
        self.assertRefused(self.run_action("prepare"), text="names another storage or path")
        self.assertNothingChanged()

    def test_2_record_that_is_a_link_or_whose_directory_is_not_root_owned_is_refused(self):
        self.store.mkdir()
        self.make_record()
        rec = self.T / "etc-corelab" / "storage-corelab.record"
        base = json.loads(json.dumps(self.state))
        proc = self.run_action("prepare", state=dict(base, foreign=[str(self.T / "etc-corelab")]))
        self.assertRefused(proc, text="not owned by root")
        content = rec.read_text()
        rec.unlink()
        (self.T / "elsewhere.txt").write_text(content)
        rec.symlink_to(self.T / "elsewhere.txt")
        self.assertRefused(self.run_action("prepare", state=base), text="symbolic link")
        self.assertNothingChanged()

    def test_2_adopting_a_recorded_directory_inspects_children_first(self):
        self.store.mkdir()
        self.make_record()
        (self.store / "data.txt").write_text("someone's file")
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="data.txt")
        self.assertNothingChanged()
        (self.store / "data.txt").unlink()
        snippets = self.store / "snippets"
        snippets.mkdir()
        for name, text in (("notes.txt", "x"), ("corelab-ok.ign", "{}")):
            (snippets / name).write_text(text)
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="regular corelab-*.ign")
        self.assertNotCalled("chown")
        (snippets / "notes.txt").unlink()
        (snippets / "corelab-link.ign").symlink_to(self.T / "elsewhere.txt")
        self.assertRefused(self.run_action("prepare"), text="regular corelab-*.ign")
        self.assertNotCalled("chown")
        (snippets / "corelab-link.ign").unlink()
        proc = self.run_action("prepare")  # positive control: recorded, known layout, only a corelab-*.ign file
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_2_registered_storage_without_a_record_is_refused(self):
        self.store.mkdir()
        self.state["storages"].append({"storage": "corelab", "type": "dir", "path": str(self.store),
                                       "content": "snippets,import,iso,backup"})
        self.assertRefused(self.run_action("prepare"), text="no root-owned record")
        self.make_record()
        proc = self.run_action("prepare")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotCalled("pvesm", "add")

    def test_2_registered_storage_at_another_path_is_not_changed(self):
        self.state["storages"].append({"storage": "corelab", "type": "dir", "path": str(self.T / "srv" / "elsewhere"),
                                       "content": "snippets,import,iso,backup"})
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="not changing it")
        self.assertNotCalled("pvesm", "add")

    def test_2_record_without_a_directory_continues_an_interrupted_run(self):
        self.make_record(state="pending")  # the pending record is written first; the directory was never created
        proc = self.run_action("prepare")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.called("pvesm", "add", "dir", "corelab"))
        self.assertIn("state=complete", self.record.read_text())

    # -- round 3: record trust, directory instance, host, nested mounts ---------------------
    def adoptable_store(self):
        self.store.mkdir()
        (self.store / "snippets").mkdir()
        self.make_record()

    def test_r3_1_record_that_others_can_write_is_refused_before_parsing(self):
        self.adoptable_store()
        for mode in (0o664, 0o646, 0o666, 0o620):
            with self.subTest(mode=oct(mode)):
                os.chmod(self.record, mode)
                state = dict(self.state, real_modes=[str(self.record)])
                proc = self.run_action("prepare", state=state)
                self.assertRefused(proc, text="writable by group or others")
                self.assertNothingChanged()
        os.chmod(self.record, 0o644)  # positive control: same record, same state, mode 644
        proc = self.run_action("prepare", state=dict(self.state, real_modes=[str(self.record)]))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_r3_1_record_file_that_is_not_root_owned_is_refused(self):
        self.adoptable_store()
        proc = self.run_action("prepare", state=dict(self.state, foreign=[str(self.record)]))
        self.assertRefused(proc, text="is not owned by root")
        self.assertNothingChanged()

    def test_r3_1_record_directory_that_others_can_write_is_refused(self):
        self.adoptable_store()
        proc = self.run_action("prepare", state=dict(self.state, writable=[str(self.T / "etc-corelab")]))
        self.assertRefused(proc, text="writable by group or others")
        self.assertNothingChanged()

    def test_r3_1_marker_that_others_can_write_or_is_not_root_owned_is_refused(self):
        self.adoptable_store()
        marker = self.store / ".corelab-project"
        os.chmod(marker, 0o666)
        proc = self.run_action("prepare", state=dict(self.state, real_modes=[str(marker)]))
        self.assertRefused(proc, text="writable by group or others")
        os.chmod(marker, 0o644)
        proc = self.run_action("prepare", state=dict(self.state, foreign=[str(marker)]))
        self.assertRefused(proc, text="is not owned by root")
        self.assertNothingChanged()

    def test_r3_2_replaced_directory_is_not_adopted(self):
        self.adoptable_store()
        old = self.T / "srv" / "old-corelab"
        os.rename(self.store, old)          # keep the old one so the new directory gets a new inode
        self.store.mkdir()
        for name in ("snippets", "import"):
            (self.store / name).mkdir()
        proc = self.run_action("prepare")  # familiar children, no marker
        self.assertRefused(proc, text="no marker")
        (self.store / ".corelab-project").write_text(f"storage=corelab\ntoken={'ab' * 16}\n")  # marker copied over
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="not the directory instance recorded")
        (self.store / ".corelab-project").write_text(f"storage=corelab\ntoken={'cd' * 16}\n")  # other token
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="does not match the record")
        self.assertNothingChanged()

    def test_r3_2_edited_directory_identity_in_the_record_is_refused(self):
        for field, value in (("dev", "999999"), ("ino", "999999"), ("fsid", "ffff")):
            with self.subTest(field=field):
                if self.store.exists():
                    for child in self.store.iterdir():
                        child.unlink() if child.is_file() else child.rmdir()
                else:
                    self.store.mkdir()
                self.make_record(**{field: value})
                proc = self.run_action("prepare")
                self.assertRefused(proc, text="not the directory instance recorded")
                self.assertNothingChanged()

    def test_r3_2_complete_record_whose_directory_is_gone_is_not_recreated(self):
        self.make_record(state="complete")
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="is gone")
        self.assertNothingChanged()

    def test_r3_2_pending_record_with_a_directory(self):
        self.store.mkdir()
        self.make_record(state="pending")
        proc = self.run_action("prepare")  # pending, directory made by us (marker matches the token): completes
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("state=complete", self.record.read_text())
        self.assertIn("ino=", self.record.read_text())
        # pending, but the directory carries no marker (made by someone else): refused
        for child in self.store.iterdir():
            child.unlink() if child.is_file() else child.rmdir()
        self.make_record(state="pending")
        (self.store / ".corelab-project").unlink()
        proc = self.run_action("prepare", state=self.after)
        self.assertRefused(proc, text="no marker")
        (self.store / ".corelab-project").write_text(f"storage=corelab\ntoken={'00' * 16}\n")
        self.assertRefused(self.run_action("prepare", state=self.after), text="does not match the record")

    def test_r3_3_mounts_at_or_beneath_the_directory_are_refused(self):
        self.adoptable_store()
        for name, mount in (("snippets bind mount", f"{self.store}/snippets"), ("the directory itself", f"{self.store}"),
                            ("deeper mount", f"{self.store}/import/deeper")):
            with self.subTest(name):
                self.write_mountinfo("1 0 8:1 / / rw - ext4 /dev/sda1 rw",
                                     f"2 1 8:7 / {mount} rw - ext4 /dev/sdz9 rw")
                proc = self.run_action("prepare")
                self.assertRefused(proc, text="a mount lies at or beneath")
                self.assertNothingChanged()
        # positive controls: a mount elsewhere, and a mount whose name only starts like the path
        self.write_mountinfo("1 0 8:1 / / rw - ext4 /dev/sda1 rw", f"2 1 8:7 / {self.T}/srv/other rw - ext4 /dev/sdz9 rw",
                             f"3 1 8:8 / {self.store}x rw - ext4 /dev/sdz8 rw")
        proc = self.run_action("prepare")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_r3_3_an_unreadable_mount_table_refuses_adoption(self):
        self.adoptable_store()
        self.mountinfo = str(self.T / "no-such-mountinfo")
        self.assertRefused(self.run_action("prepare"), text="cannot place")
        self.assertNothingChanged()

    def test_r3_5_record_from_another_host_is_refused(self):
        self.adoptable_store()
        self.make_record(host="f" * 32)
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="another host")
        self.assertNothingChanged()
        self.make_record(host=None)  # positive control
        self.assertEqual(self.run_action("prepare").returncode, 0)

    def test_r3_5_unusable_machine_id_is_refused(self):
        self.adoptable_store()
        for text in ("", "short\n", "0123456789ABCDEF0123456789ABCDEF\n", self.host_id + "\n" + self.host_id + "\n"):
            with self.subTest(text=text[:12]):
                (self.T / "machine-id").write_text(text)
                self.assertRefused(self.run_action("prepare"), text="machine id")
        (self.T / "machine-id").unlink()
        self.assertNotEqual(self.run_action("prepare").returncode, 0)
        self.assertNothingChanged()

    def test_r3_7_record_that_is_cut_short_or_appended_to_is_refused(self):
        self.adoptable_store()
        good = self.record.read_text()
        cases = {"no final newline": good.rstrip("\n"), "junk appended without newline": good + "evil=1",
                 "empty": "", "blank line": good + "\n", "unknown key": good + "evil=1\n", "repeated key": good + "token=" + "ab" * 16 + "\n",
                 "not key=value": good + "hello\n", "shell text": good + "path=$(id)\n"}
        for name, text in cases.items():
            with self.subTest(name):
                self.make_record(raw=text)
                self.assertRefused(self.run_action("prepare"))
                self.assertNothingChanged()
        self.make_record(raw=good)
        self.assertEqual(self.run_action("prepare").returncode, 0)

    # -- snippet writer home ---------------------------------------------------------------
    def test_ha4_home_and_ssh_are_root_owned(self):
        proc = self.run_action("prepare")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        installs = [c for c in self.calls() if c[0] == "install"]
        for target in (self.T / "home-snip", self.T / "home-snip" / ".ssh"):
            line = next(c for c in installs if c[-1] == str(target))
            self.assertEqual(line[line.index("-o") + 1], "root")
        self.assertFalse(any("corelab-snip" in c for c in installs), "an install gave a directory to corelab-snip")
        self.assertTrue(self.called("chown", "-h", "root:corelab-snip", "--", f"{self.store}/snippets"))

    def test_3_old_layout_with_a_home_the_user_controls_is_refused_before_any_change(self):
        (self.T / "home-snip" / ".ssh").mkdir(parents=True)
        for owned, text in (([str(self.T / "home-snip")], "older layout"),
                            ([str(self.T / "home-snip" / ".ssh")], "older layout"),
                            ([], None)):
            with self.subTest(foreign=owned):
                proc = self.run_action("prepare", state=dict(self.state, foreign=owned))
                if text:
                    self.assertRefused(proc, text=text)
                    self.assertNothingChanged()
                else:  # positive control: the same tree, root-owned, is fine
                    self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_3_writable_home_is_refused(self):
        (self.T / "home-snip").mkdir()
        proc = self.run_action("prepare", state=dict(self.state, writable=[str(self.T / "home-snip")]))
        self.assertRefused(proc, text="writable by group or others")
        self.assertNothingChanged()

    def test_3_write_location_not_owned_by_root_is_refused(self):
        for target in (self.T / "sbin", ):
            with self.subTest(target=str(target)):
                (self.T / "sbin").mkdir(exist_ok=True)
                proc = self.run_action("prepare", state=dict(self.state, foreign=[str(target)]))
                self.assertRefused(proc, text="not owned by root")
                self.assertNothingChanged()

    def test_ha4_planted_links_do_not_redirect_a_root_write(self):
        victim = self.T / "victim"
        victim.write_text("original")
        victim2 = self.T / "victim2"
        victim2.write_text("original2")
        ssh = self.T / "home-snip" / ".ssh"
        ssh.mkdir(parents=True)
        (ssh / "authorized_keys.new").symlink_to(victim)
        (ssh / "authorized_keys").symlink_to(victim2)
        proc = self.run_action("prepare")
        self.assertEqual(victim.read_text(), "original")
        self.assertEqual(victim2.read_text(), "original2")
        self.assertRefused(proc, text="authorized_keys.new")
        (ssh / "authorized_keys.new").unlink()
        proc = self.run_action("prepare")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        dest = ssh / "authorized_keys"
        self.assertFalse(dest.is_symlink())
        self.assertEqual(victim2.read_text(), "original2")
        self.assertIn("restrict,from=", dest.read_text())

    def test_ha4_symlinked_home_or_ssh_refused(self):
        real = self.T / "real-home"
        real.mkdir()
        (self.T / "home-snip").symlink_to(real)
        self.assertRefused(self.run_action("prepare"), text="symbolic link")
        (self.T / "home-snip").unlink()
        (self.T / "home-snip").mkdir()
        (self.T / "home-snip" / ".ssh").symlink_to(real)
        self.assertRefused(self.run_action("prepare"), text="symbolic link")
        self.assertNothingChanged()

    def test_7_configuration_directory_that_is_a_link_is_refused_before_install(self):
        target = self.T / "elsewhere"
        target.mkdir()
        os.chmod(target, 0o700)
        (self.T / "etc-corelab").symlink_to(target)
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="symbolic link")
        self.assertNothingChanged()
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)
        self.assertEqual(list(target.iterdir()), [])

    def test_ha4_symlinked_snippets_directory_refused(self):
        self.store.mkdir()
        self.make_record()
        (self.T / "elsewhere").mkdir()
        (self.store / "snippets").symlink_to(self.T / "elsewhere")
        proc = self.run_action("prepare")
        self.assertRefused(proc, text="not a real directory")
        self.assertNotCalled("chown")

    def test_6_unreadable_directory_listing_is_an_error_not_an_empty_directory(self):
        self.store.mkdir()
        self.make_record()
        snippets = self.store / "snippets"
        snippets.mkdir()
        (snippets / "corelab-x.ign").write_text("{}")
        os.chmod(snippets, 0o000)
        try:
            proc = self.run_action("prepare")
        finally:
            os.chmod(snippets, 0o755)
        self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
        self.assertNotCalled("chown")
        self.assertNothingChanged()

    # -- parameters and listings -----------------------------------------------------------
    def test_injected_key_address_and_names_are_refused(self):
        cases = {"CL_SNIP_PUBKEY": [PUBKEY + "\nssh-rsa AAAA evil", PUBKEY + ' ",command="x', "ssh-rsa AAAA"],
                 "CL_WORKSTATION_ADDR": ['192.0.2.50",command="x', "192.0.2.0/24", "host.example", "192.0.2.1 "],
                 "CL_POOL": ["a b", "-x", "a;b"], "CL_BRIDGE": ["vmbr0'; reboot; '"],
                 "CL_USER": ["x y@pve", "-u@pve"], "CL_TOKEN": ["t;x"]}
        for key, values in cases.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    proc = self.run_action("prepare", {key: value})
                    self.assertRefused(proc)
                    self.assertNothingChanged()

    def test_ha10_and_5_failed_or_unusable_listing_is_not_absence(self):
        cases = {"pools fail": {"fail": ["pvesh get /pools"]},
                 "pools empty": {"garbage": {"pvesh get /pools": ""}},
                 "pools with an empty record": {"garbage": {"pvesh get /pools": "[{}]"}},
                 "pools with a duplicate": {"garbage": {"pvesh get /pools": '[{"poolid":"a"},{"poolid":"a"}]'}},
                 "pool id is not a scalar": {"garbage": {"pvesh get /pools": '[{"poolid":["corelab"]}]'}},
                 "storages fail": {"fail": ["pvesh get /storage"]},
                 "storages empty": {"garbage": {"pvesh get /storage": ""}},
                 "storage without id": {"garbage": {"pvesh get /storage": '[{"type": "dir"}]'}},
                 "storage without type": {"garbage": {"pvesh get /storage": '[{"storage": "x"}]'}},
                 "dir storage without a path": {"garbage": {"pvesh get /storage": '[{"storage": "x", "type": "dir"}]'}},
                 "nfs storage with a relative path": {"garbage": {"pvesh get /storage": '[{"storage": "x", "type": "nfs", "path": "rel"}]'}},
                 "unknown storage type": {"garbage": {"pvesh get /storage": '[{"storage": "x", "type": "mystery"}]'}},
                 "duplicate storage id": {"garbage": {"pvesh get /storage": '[{"storage":"x","type":"lvm"},{"storage":"x","type":"lvm"}]'}},
                 "storages not an array": {"garbage": {"pvesh get /storage": "{}"}}}
        for name, extra in cases.items():
            with self.subTest(name):
                state = json.loads(json.dumps(self.state))
                state.update(extra)
                proc = self.run_action("prepare", state=state)
                self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
                self.assertNothingChanged()

    def test_acl_listing_failure_is_reported(self):
        proc = self.run_action("prepare", state=dict(self.state, fail=["pveum acl list"]))
        self.assertEqual(proc.returncode, 4)


# ------------------------------------------------------------------------------- sentinel
class SentinelTests(LabCase):
    VOLID = "local:backup/vzdump-qemu-9050.vma.zst"
    ISO_SHA = hashlib.sha256(b"\0" * 1048576).hexdigest()

    def setUp(self):
        super().setUp()
        self.store.mkdir()
        self.state = {"resources": [], "configs": {}, "content": {"local": [], "local-lvm": []},
                      "storages": [{"storage": "corelab", "type": "dir", "path": str(self.store),
                                    "content": "snippets,import,iso,backup"}]}
        self.record_file = self.T / "etc-corelab" / "sentinel-9050.record"

    def fixture(self, **changes):
        cfg = {"digest": "a" * 40, "name": "corelab-sentinel", "memory": "64", "cores": "1",
               "scsi0": "local-lvm:vm-9050-disk-0,size=1G", "description": FIXTURE_DESC + "\n"}
        res = {"id": "qemu/9050", "type": "qemu", "vmid": 9050, "node": NODE, "name": "corelab-sentinel",
               "status": "stopped", "template": 0}
        for key, value in changes.items():
            target = res if key in res else cfg
            if value is None:
                target.pop(key, None)
            else:
                target[key] = value
        if "name" in changes:  # the name is in the list entry and in the config
            cfg["name"] = changes["name"]
        self.state["resources"] = [res]
        self.state["configs"] = {"9050": cfg}
        self.state["content"]["local-lvm"] = [{"volid": "local-lvm:vm-9050-disk-0", "vmid": 9050}]

    def write_record(self, lines=None, **over):
        iso = self.store / "template" / "iso" / "corelab-dummy.iso"
        rec = {"vmid": "9050", "node": NODE, "host": self.host_id, "lab_storage": "corelab", "lab_path": str(self.store),
               "vm_storage": "local-lvm", "backup_storage": "local", "iso_path": str(iso),
               "digest": "a" * 40, "disk": "local-lvm:vm-9050-disk-0,size=1G",
               "backup_volid": self.VOLID, "iso_sha256": self.ISO_SHA,
               "iso_id": f"{os.stat(iso).st_dev}:{os.stat(iso).st_ino}" if iso.exists() else None}
        rec.update(over)
        if rec["iso_sha256"] is None:
            rec["iso_id"] = None
        d = self.record_file.parent
        d.mkdir(exist_ok=True)
        os.chmod(d, 0o755)
        self.record_file.write_text("".join(f"{k}={v}\n" for k, v in rec.items() if v is not None) if lines is None else lines)

    def backup_listed(self, *volids):
        self.state["content"]["local"] = [{"volid": v, "vmid": 9050, "content": "backup"} for v in volids]

    def iso(self, data=b"\0" * 1048576):
        path = self.store / "template" / "iso" / "corelab-dummy.iso"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def recorded_fixture(self, record=None, **changes):
        """A guest, a backup and an ISO as the script would have left them, with their record."""
        self.fixture(**changes)
        self.backup_listed(self.VOLID)
        self.iso()
        self.write_record(**(record or {}))

    def test_positive_control_creates_everything_once_records_it_and_accepts_it_again(self):
        proc = self.run_action("sentinel")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.called("qm", "create", "9050"))
        self.assertTrue(self.called("vzdump", "9050"))
        iso = self.store / "template" / "iso" / "corelab-dummy.iso"
        self.assertEqual(iso.stat().st_size, 1048576)
        text = self.record_file.read_text()
        for key in ("vmid=9050", f"node={NODE}", f"host={self.host_id}", "lab_storage=corelab", f"lab_path={self.store}",
                    "vm_storage=local-lvm", "backup_storage=local", f"iso_path={iso}", "digest=" + "f" * 40,
                    f"backup_volid={self.VOLID}", f"iso_sha256={self.ISO_SHA}",
                    f"iso_id={os.stat(iso).st_dev}:{os.stat(iso).st_ino}"):
            self.assertIn(key, text)
        self.assertEqual(self.record_file.stat().st_mode & 0o777, 0o644)
        self.assertEqual(list(self.record_file.parent.glob(".*")), [])
        again = self.run_action("sentinel", state=self.after)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertNotCalled("qm", "create")
        self.assertNotCalled("vzdump")
        self.assertIn("NOT PROVEN", again.stderr)

    def test_ha3_recorded_fixture_is_accepted_positive_control(self):
        self.recorded_fixture()
        proc = self.run_action("sentinel")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotCalled("qm")
        self.assertNotCalled("vzdump")
        self.assertIn("matches the record", proc.stderr)

    def test_4_an_exact_looking_guest_backup_and_iso_without_a_record_are_refused(self):
        self.fixture()
        self.backup_listed(self.VOLID)
        self.iso()
        proc = self.run_action("sentinel")
        self.assertRefused(proc, text="no record of creating")
        self.assertIn("Check by hand", proc.stderr)
        self.assertNotCalled("qm")
        self.assertNotCalled("vzdump")
        self.assertFalse(self.record_file.exists())

    def test_ha3_recorded_guest_that_does_not_have_the_fixture_shape_is_refused(self):
        cases = {
            "in a pool": {"pool": "corelab"}, "running": {"status": "running"}, "template": {"template": 1},
            "lxc": {"type": "lxc"}, "other node": {"node": "other"},
            "network device": {"net0": "virtio,bridge=vmbr0"},
            "second disk": {"scsi1": "local-lvm:vm-9050-disk-1,size=500G"},
            "bigger disk": {"scsi0": "local-lvm:vm-9050-disk-0,size=500G"},
            "foreign disk": {"scsi0": "tank:vm-9050-disk-0,size=1G"},
            "passthrough": {"hostpci0": "0000:01:00.0"}, "lock": {"lock": "backup"},
            "old description without marker": {"description": "Negative RBAC test fixture. Worthless by design."},
            "no description": {"description": None}, "other name": {"name": "web-prod"},
        }
        for name, change in cases.items():
            with self.subTest(name):
                self.state = {"resources": [], "configs": {}, "content": {"local": [], "local-lvm": []},
                              "storages": self.state["storages"]}
                self.recorded_fixture(**change)
                proc = self.run_action("sentinel")
                self.assertRefused(proc, text="fixture shape")
                self.assertNotCalled("vzdump")
                self.assertNotCalled("qm")

    def test_4_changed_digest_or_disk_since_the_record_is_refused(self):
        self.recorded_fixture(record={"digest": "b" * 40})
        self.assertRefused(self.run_action("sentinel"), text="changed since the record")
        self.recorded_fixture(record={"disk": "local-lvm:vm-9050-disk-7,size=1G"})
        self.assertRefused(self.run_action("sentinel"), text="differs from the record")

    def test_4_recorded_guest_that_is_gone_is_not_recreated(self):
        self.recorded_fixture()
        self.state["resources"] = []
        proc = self.run_action("sentinel")
        self.assertRefused(proc, text="is gone")
        self.assertNotCalled("qm")

    def test_4_a_bad_record_is_refused(self):
        cases = {"other vmid": {"vmid": "9051"}, "other node": {"node": "elsewhere"}, "bad digest": {"digest": "xyz"},
                 "bad disk": {"disk": "tank:vm-9050-disk-0,size=1G"}, "bad iso hash": {"iso_sha256": "12"}}
        for name, over in cases.items():
            with self.subTest(name):
                self.recorded_fixture(record=over)
                self.assertRefused(self.run_action("sentinel"))
                self.assertNotCalled("qm")
        for name, text in (("unknown key", "vmid=9050\nnode=pve1\nevil=1\n"), ("repeated key", "vmid=9050\nvmid=9050\n"),
                           ("not key=value", "hello\n"), ("shell text", "vmid=9050\nnode=$(id)\n")):
            with self.subTest(name):
                self.recorded_fixture()
                self.write_record(lines=text)
                self.assertRefused(self.run_action("sentinel"))
        self.recorded_fixture()
        self.assertRefused(self.run_action("sentinel", state=dict(self.state, foreign=[str(self.record_file)])),
                           text="is not owned by root")

    def test_4_unrecorded_backup_or_iso_without_a_guest_blocks_creation(self):
        self.backup_listed(self.VOLID)
        proc = self.run_action("sentinel")
        self.assertRefused(proc, text="nothing records them")
        self.assertNotCalled("qm", "create")
        self.state["content"]["local"] = []
        self.iso()
        proc = self.run_action("sentinel")
        self.assertRefused(proc, text="nothing records it")
        self.assertNotCalled("qm", "create")

    def test_4_backups_must_be_exactly_the_recorded_one(self):
        for name, volids in (("missing", ()), ("another", ("local:backup/vzdump-qemu-9050-other.vma.zst",)),
                             ("extra", (self.VOLID, "local:backup/vzdump-qemu-9050-extra.vma.zst"))):
            with self.subTest(name):
                self.recorded_fixture()
                self.backup_listed(*volids)
                proc = self.run_action("sentinel")
                self.assertRefused(proc, text="not exactly the recorded one")
                self.assertNotCalled("vzdump")

    def test_4_iso_must_be_the_recorded_one(self):
        for name, data in (("other content", b"\1" * 1048576), ("wrong size", b"small")):
            with self.subTest(name):
                self.recorded_fixture()
                self.iso(data)
                self.assertRefused(self.run_action("sentinel"), text="dummy ISO")
        self.recorded_fixture()
        victim = self.T / "victim"
        victim.write_bytes(b"\0" * 1048576)
        (self.store / "template" / "iso" / "corelab-dummy.iso").unlink()
        (self.store / "template" / "iso" / "corelab-dummy.iso").symlink_to(victim)
        self.assertRefused(self.run_action("sentinel"), text="dummy ISO")

    def test_4_a_run_interrupted_after_the_guest_continues_with_backup_and_iso(self):
        self.fixture()
        self.write_record(backup_volid=None, iso_sha256=None)
        proc = self.run_action("sentinel")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.called("vzdump", "9050"))
        self.assertNotCalled("qm", "create")
        self.assertIn(f"iso_sha256={self.ISO_SHA}", self.record_file.read_text())
        self.assertIn("backup_volid=", self.record_file.read_text())

    # -- round 3 ---------------------------------------------------------------------------
    def test_r3_1_record_that_others_can_write_is_refused_before_parsing(self):
        self.recorded_fixture()
        for mode in (0o664, 0o646, 0o666):
            with self.subTest(mode=oct(mode)):
                os.chmod(self.record_file, mode)
                proc = self.run_action("sentinel", state=dict(self.state, real_modes=[str(self.record_file)]))
                self.assertRefused(proc, text="writable by group or others")
                self.assertNotCalled("qm")
                self.assertNotCalled("vzdump")
        os.chmod(self.record_file, 0o644)
        proc = self.run_action("sentinel", state=dict(self.state, real_modes=[str(self.record_file)]))  # control
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc = self.run_action("sentinel", state=dict(self.state, writable=[str(self.record_file.parent)]))
        self.assertRefused(proc, text="writable by group or others")

    def test_r3_5_record_from_another_host_is_refused(self):
        self.recorded_fixture(record={"host": "f" * 32})
        proc = self.run_action("sentinel")
        self.assertRefused(proc, text="another host")
        self.assertNotCalled("qm")
        self.assertNotCalled("vzdump")
        self.recorded_fixture()  # control: same data, this host
        self.assertEqual(self.run_action("sentinel").returncode, 0)

    def test_r3_5_unusable_machine_id_is_refused(self):
        self.recorded_fixture()
        for text in ("", "short\n", "0123456789ABCDEF0123456789ABCDEF\n"):
            with self.subTest(text=text[:12]):
                (self.T / "machine-id").write_text(text)
                self.assertRefused(self.run_action("sentinel"), text="machine id")
                self.assertNotCalled("qm")

    def test_r3_4_record_made_for_other_storages_or_another_iso_location_is_refused(self):
        other = str(self.T / "srv" / "other")
        for name, over in (("other project storage id", {"lab_storage": "elsewhere"}), ("other project path", {"lab_path": other}),
                           ("other VM storage", {"vm_storage": "tank"}), ("other backup storage", {"backup_storage": "nas"}),
                           ("other ISO path", {"iso_path": other + "/template/iso/corelab-dummy.iso"})):
            with self.subTest(name):
                self.recorded_fixture(record=over)
                proc = self.run_action("sentinel")
                self.assertRefused(proc, text="other storages or another ISO location")
                self.assertNotCalled("qm")
                self.assertNotCalled("vzdump")

    def test_r3_4_same_content_iso_in_another_file_is_refused(self):
        self.recorded_fixture()
        iso = self.store / "template" / "iso" / "corelab-dummy.iso"
        copy = self.store / "template" / "iso" / "copy"
        copy.write_bytes(iso.read_bytes())   # same bytes, new file (new inode)
        iso.unlink()
        os.rename(copy, iso)
        proc = self.run_action("sentinel")
        self.assertRefused(proc, text="not the same file")

    def test_r3_7_record_that_is_cut_short_or_appended_to_is_refused(self):
        self.recorded_fixture()
        good = self.record_file.read_text()
        cases = {"no final newline": good.rstrip("\n"), "junk appended without newline": good + "evil=1",
                 "empty": "", "blank line": good + "\n", "unknown key": good + "evil=1\n"}
        for name, text in cases.items():
            with self.subTest(name):
                self.write_record(lines=text)
                self.assertRefused(self.run_action("sentinel"))
                self.assertNotCalled("qm")
        self.write_record(lines=good)
        self.assertEqual(self.run_action("sentinel").returncode, 0)

    def test_r3_volume_ids_with_underscores_are_accepted(self):
        volid = "local:backup/vzdump-qemu-9050-2026_11_16-12_00_00.vma.zst"
        self.recorded_fixture(record={"backup_volid": volid})
        self.backup_listed(volid)
        proc = self.run_action("sentinel")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_r3_6_numeric_aliases_of_a_vmid_are_not_two_identities(self):
        res = '[{{"vmid": {a}, "type": "qemu"}}, {{"vmid": {b}, "type": "qemu"}}]'
        back = f"pvesh get /nodes/{NODE}/storage/local/content --content"
        cases = {"09050 alone": ("pvesh get /cluster/resources", '[{"vmid": "09050", "type": "qemu"}]'),
                 "9050 and 09050": ("pvesh get /cluster/resources", res.format(a="9050", b='"09050"')),
                 "9050 and 9050.0": ("pvesh get /cluster/resources", res.format(a="9050", b="9050.0")),
                 "plus sign": ("pvesh get /cluster/resources", '[{"vmid": "+9050", "type": "qemu"}]'),
                 "below the VMID range": ("pvesh get /cluster/resources", '[{"vmid": "99", "type": "qemu"}]'),
                 "backup entry 09050": (back, '[{"volid": "local:backup/x", "vmid": "09050"}]')}
        for name, (prefix, text) in cases.items():
            with self.subTest(name):
                state = json.loads(json.dumps(self.state))
                state["garbage"] = {prefix: text}
                proc = self.run_action("sentinel", state=state)
                self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
                self.assertNotCalled("qm", "create")
                self.assertNotCalled("vzdump")

    def test_ha3_orphan_volumes_of_the_vmid_block_creation(self):
        self.state["content"]["local-lvm"] = [{"volid": "local-lvm:vm-9050-disk-0", "vmid": 9050}]
        proc = self.run_action("sentinel")
        self.assertRefused(proc, text="no guest uses them")
        self.assertNotCalled("qm", "create")

    def test_ha1_numeric_parameters_are_validated(self):
        marker = self.T / "pwned"
        for value in (f"9050[$(touch {marker})]", "0", "09050", "99", "-1", "9050 ", "abc", "1000000000", ""):
            with self.subTest(value=value):
                proc = self.run_action("sentinel", {"CL_SENTINEL_VMID": value})
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(marker.exists())
                self.assertNotCalled("qm")
                self.assertNotCalled("vzdump")

    def test_ha10_and_5_failed_or_unusable_listing_is_not_absence(self):
        back = f"pvesh get /nodes/{NODE}/storage/local/content --content"
        cases = {"resources fail": {"fail": ["pvesh get /cluster/resources"]},
                 "resources empty": {"garbage": {"pvesh get /cluster/resources": ""}},
                 "resources with an empty record": {"garbage": {"pvesh get /cluster/resources": "[{}]"}},
                 "resources with a non-numeric vmid": {"garbage": {"pvesh get /cluster/resources": '[{"vmid":"x","type":"qemu"}]'}},
                 "resources duplicate": {"garbage": {"pvesh get /cluster/resources": '[{"vmid":1,"type":"qemu"},{"vmid":1,"type":"lxc"}]'}},
                 "storages fail": {"fail": ["pvesh get /storage"]},
                 "storages with an empty record": {"garbage": {"pvesh get /storage": "[{}]"}},
                 "backup list fails": {"fail": [back]}, "backup list empty": {"garbage": {back: ""}},
                 "backup list not objects": {"garbage": {back: "[1]"}},
                 "backup list with an empty record": {"garbage": {back: "[{}]"}},
                 "backup list without a vmid": {"garbage": {back: '[{"volid":"local:backup/x"}]'}}}
        for name, extra in cases.items():
            with self.subTest(name):
                state = json.loads(json.dumps(self.state))
                state.update(extra)
                proc = self.run_action("sentinel", state=state)
                self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
                self.assertNotCalled("vzdump")
                self.assertNotCalled("qm", "create")

    def test_9_a_failed_or_unusable_digest_is_not_ready(self):
        self.recorded_fixture()
        config_call = f"pvesh get /nodes/{NODE}/qemu/9050/config"
        cfg = dict(self.state["configs"]["9050"])
        cfg.pop("digest")
        for name, extra in (("no digest field", {"garbage": {config_call: json.dumps(cfg)}}),
                            ("config unreadable", {"fail": [config_call]})):
            with self.subTest(name):
                state = json.loads(json.dumps(self.state))
                state.update(extra)
                proc = self.run_action("sentinel", state=state)
                self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
                self.assertNotIn("fixtures ready", proc.stderr)
                self.assertNotIn("sentinel config digest", proc.stdout)

    def test_storage_path_must_be_the_registered_project_storage(self):
        self.state["storages"][0]["path"] = str(self.T / "srv" / "other")
        proc = self.run_action("sentinel")
        self.assertRefused(proc, text="not a directory storage")
        self.assertNotCalled("qm", "create")
        self.state["storages"] = []
        self.assertRefused(self.run_action("sentinel"), text="run prepare first")

    def test_backup_storage_must_not_be_the_project_storage(self):
        proc = self.run_action("sentinel", {"CL_SENTINEL_BACKUP_STORAGE": "corelab"})
        self.assertRefused(proc, text="project storage")

    def test_planted_iso_link_is_not_written_through(self):
        victim = self.T / "victim"
        victim.write_text("original")
        iso_dir = self.store / "template" / "iso"
        iso_dir.mkdir(parents=True)
        (iso_dir / "corelab-dummy.iso").symlink_to(victim)
        proc = self.run_action("sentinel")
        self.assertRefused(proc, text="nothing records it")
        self.assertEqual(victim.read_text(), "original")
        self.assertNotCalled("qm", "create")

    def test_configuration_directory_that_is_a_link_is_refused(self):
        (self.T / "elsewhere").mkdir()
        (self.T / "etc-corelab").symlink_to(self.T / "elsewhere")
        proc = self.run_action("sentinel")
        self.assertRefused(proc, text="symbolic link")
        self.assertNotCalled("qm", "create")


# ------------------------------------------------------------------------- fcos-template
class FcosTemplateTests(LabCase):
    def setUp(self):
        super().setUp()
        self.store.mkdir()
        self.xz = lzma.compress(PAYLOAD)
        self.sha = hashlib.sha256(self.xz).hexdigest()
        (self.T / "image.xz").write_bytes(self.xz)
        self.state = {"resources": [], "configs": {}, "content": {"local-lvm": []}, "pools": [{"poolid": "corelab"}],
                      "storages": [{"storage": "corelab", "type": "dir", "path": str(self.store),
                                    "content": "snippets,import,iso,backup"}],
                      "curl_src": str(self.T / "image.xz")}
        self.env = {"CL_FCOS_IMAGE_SHA256": self.sha}

    def go(self, extra=None, **kw):
        env = dict(self.env)
        env.update(extra or {})
        return self.run_action("fcos-template", env, **kw)

    def good_template(self, **changes):
        cfg = {"digest": "d" * 40, "name": "corelab-fcos-template", "template": "1",
               "scsi0": "local-lvm:base-9100-disk-0,size=10G", "ide2": "local-lvm:vm-9100-cloudinit,media=cdrom",
               "serial0": "socket", "vga": "serial0", "net0": "virtio=BC:24:11:00:00:01,bridge=vmbr0",
               "boot": "order=scsi0"}
        res = {"id": "qemu/9100", "type": "qemu", "vmid": 9100, "node": NODE, "name": "corelab-fcos-template",
               "status": "stopped", "template": 1, "pool": "corelab"}
        for key, value in changes.items():
            target = res if key in res else cfg
            if value is None:
                target.pop(key, None)
            else:
                target[key] = value
        if "name" in changes:  # the name is in the list entry and in the config
            cfg["name"] = changes["name"]
        self.state["resources"] = [res]
        self.state["configs"] = {"9100": cfg}

    def test_positive_control_builds_the_template(self):
        proc = self.go()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.after["imported"], [{"vmid": 9100, "bytes": len(PAYLOAD), "src": self.after["imported"][0]["src"]}])
        self.assertTrue(self.called("curl"))
        self.assertTrue(self.called("qm", "template", "9100"))
        self.assertEqual(self.after["configs"]["9100"]["template"], "1")
        self.assertEqual(list((self.store / "import").glob(".*")), [], "temporary files are removed")
        self.assertTrue((self.store / "import" / f"corelab-fcos-{self.sha}.artifact").is_file())

    def test_ha5_failed_decompression_creates_no_guest(self):
        junk = b"this is not an xz stream" * 10
        (self.T / "image.xz").write_bytes(junk)
        proc = self.go({"CL_FCOS_IMAGE_SHA256": hashlib.sha256(junk).hexdigest()})
        self.assertEqual(proc.returncode, 4, proc.stderr)
        self.assertIn("decompression failed", proc.stderr)
        self.assertNotCalled("qm")

    def test_ha5_truncated_xz_creates_no_guest(self):
        truncated = self.xz[: len(self.xz) // 2]
        (self.T / "image.xz").write_bytes(truncated)
        proc = self.go({"CL_FCOS_IMAGE_SHA256": hashlib.sha256(truncated).hexdigest()})
        self.assertEqual(proc.returncode, 4, proc.stderr)
        self.assertNotCalled("qm")

    def test_ha7_download_with_wrong_checksum_is_discarded(self):
        proc = self.go({"CL_FCOS_IMAGE_SHA256": "0" * 64})
        self.assertRefused(proc, text="checksum mismatch")
        self.assertNotCalled("qm")
        self.assertEqual(list((self.store / "import").glob("*")), [])

    def test_ha7_tampered_cache_is_refused_on_every_use(self):
        imp = self.store / "import"
        imp.mkdir()
        for suffix in (".artifact", ".qcow2"):  # the current and the earlier cache name
            (imp / f"corelab-fcos-{self.sha}{suffix}").write_bytes(b"tampered")
        proc = self.go()
        self.assertRefused(proc, text="does not match the pinned sha256")
        self.assertNotCalled("qm")
        self.assertNotCalled("curl")

    def test_ha7_valid_cache_is_used_without_download_and_imported_after_fresh_decompression(self):
        imp = self.store / "import"
        imp.mkdir()
        (imp / f"corelab-fcos-{self.sha}.artifact").write_bytes(self.xz)
        (imp / f"corelab-fcos-{self.sha}.qcow2").write_bytes(b"stale decompressed copy that must be ignored")
        proc = self.go()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotCalled("curl")
        self.assertEqual(self.after["imported"][0]["bytes"], len(PAYLOAD))

    def test_ha7_cache_symlink_refused(self):
        imp = self.store / "import"
        imp.mkdir()
        (self.T / "elsewhere").write_bytes(self.xz)
        (imp / f"corelab-fcos-{self.sha}.artifact").symlink_to(self.T / "elsewhere")
        self.assertRefused(self.go(), text="symbolic link")
        self.assertNotCalled("qm")

    def test_ha6_existing_partial_guest_is_reported_and_left_alone(self):
        self.good_template(template=None, scsi0="local-lvm:vm-9100-disk-0,size=10G")
        self.state["resources"][0]["template"] = 0
        proc = self.go()
        self.assertRefused(proc, text="not resuming, not deleting")
        self.assertIn("config key: scsi0 = local-lvm:vm-9100-disk-0", proc.stderr)
        self.assertNotCalled("qm")
        self.assertNotCalled("curl")

    def test_ha6_failure_after_creation_reports_what_exists_and_deletes_nothing(self):
        for failing in ("qm disk import", "qm set", "qm template"):
            with self.subTest(failing):
                state = {"resources": [], "configs": {}, "content": {"local-lvm": []}, "pools": [{"poolid": "corelab"}],
                         "storages": self.state["storages"], "curl_src": self.state["curl_src"], "fail": [failing]}
                proc = self.go(state=state)
                self.assertEqual(proc.returncode, 4, proc.stderr)
                self.assertIn("PARTIAL", proc.stderr)
                self.assertIn("config key: name", proc.stderr)
                self.assertNotCalled("qm", "destroy")
                self.assertNotCalled("pvesm", "free")
                self.assertTrue(self.after["resources"], "the guest was left in place for the owner")
                # a second run does not resume it either
                again = self.go(state={k: v for k, v in self.after.items() if k != "fail"})
                self.assertRefused(again, text="not resuming, not deleting")
                self.assertNotCalled("qm", "create")

    def test_ha8_existing_template_must_match_pool_and_configuration(self):
        cases = {
            "no pool": {"pool": None},
            "other pool": {"pool": "other"},
            "other node": {"node": "elsewhere"},
            "running": {"status": "running"},
            "not a template": {"template": 0},
            "other name": {"name": "web"},
            "disk on another storage": {"scsi0": "tank:base-9100-disk-0,size=10G"},
            "no cloud-init drive": {"ide2": None},
            "no serial console": {"serial0": None},
            "other bridge": {"net0": "virtio,bridge=vmbr9"},
            "no boot order": {"boot": None},
        }
        for name, change in cases.items():
            with self.subTest(name):
                self.good_template(**change)
                proc = self.go()
                self.assertRefused(proc)
                self.assertNotCalled("qm")

    def test_ha8_matching_template_is_accepted_without_changes(self):
        self.good_template()
        proc = self.go()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("exists and matches", proc.stderr)
        self.assertNotCalled("qm")
        self.assertNotCalled("curl")

    def test_ha9_template_vmid_must_be_inside_range_and_not_the_sentinel(self):
        marker = self.T / "pwned"
        for value in ("9200", "9099", "99", "9050", f"9100[$(touch {marker})]", "09100", "-9100", "9100 ", "", "abc"):
            with self.subTest(value=value):
                proc = self.go({"CL_TEMPLATE_VMID": value})
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(marker.exists())
                self.assertNotCalled("qm")
                self.assertNotCalled("curl")
        proc = self.go({"CL_VMID_RANGE": "9000-9199", "CL_TEMPLATE_VMID": "9050"})
        self.assertRefused(proc, text="sentinel")
        proc = self.go({"CL_VMID_RANGE": "9200-9100"})
        self.assertRefused(proc, text="above")
        for bad in ("9100", "9100-", "-9199", "9100-9199-9200", "9100 - 9199", "09100-9199", "99-9199", "9100-9199\n", "a-b"):
            with self.subTest(range=bad):
                self.assertRefused(self.go({"CL_VMID_RANGE": bad}), text="CL_VMID_RANGE")
                self.assertNotCalled("qm")

    def test_ha9_range_and_sentinel_must_be_given(self):
        for name in ("CL_VMID_RANGE", "CL_SENTINEL_VMID"):
            with self.subTest(name):
                script = self.render("fcos-template", {"CL_FCOS_IMAGE_SHA256": self.sha})
                script = script.replace(f"export {name}=", f"unset {name}; : ")
                self.state_file.write_text(json.dumps(self.state))
                self.log.write_text("")
                proc = subprocess.run(["bash", "-s"], input=script, text=True, capture_output=True,
                                      env={"PATH": f"{self.bin}:/usr/bin:/bin", "STUB_STATE": str(self.state_file),
                                           "STUB_LOG": str(self.log)})
                self.assertNotEqual(proc.returncode, 0)
                self.assertNotCalled("qm")

    def test_ha10_failed_or_unusable_listing_is_not_absence(self):
        cases = {"resources fail": {"fail": ["pvesh get /cluster/resources"]},
                 "resources empty": {"garbage": {"pvesh get /cluster/resources": ""}},
                 "resources not objects": {"garbage": {"pvesh get /cluster/resources": "[1, 2]"}},
                 "resources with an empty record": {"garbage": {"pvesh get /cluster/resources": "[{}]"}},
                 "resources with 09100": {"garbage": {"pvesh get /cluster/resources": '[{"vmid": "09100", "type": "qemu"}]'}},
                 "resources 9100 and 09100": {"garbage": {"pvesh get /cluster/resources":
                                              '[{"vmid": 9100, "type": "qemu"}, {"vmid": "09100", "type": "qemu"}]'}},
                 "pools with an empty record": {"garbage": {"pvesh get /pools": "[{}]"}},
                 "storages with an empty record": {"garbage": {"pvesh get /storage": "[{}]"}},
                 "volumes with an empty record": {"garbage": {f"pvesh get /nodes/{NODE}/storage/local-lvm/content": "[{}]"}},
                 "pools fail": {"fail": ["pvesh get /pools"]},
                 "storages empty": {"garbage": {"pvesh get /storage": ""}},
                 "volume list fails": {"fail": [f"pvesh get /nodes/{NODE}/storage/local-lvm/content"]},
                 "volume list empty": {"garbage": {f"pvesh get /nodes/{NODE}/storage/local-lvm/content": ""}}}
        for name, extra in cases.items():
            with self.subTest(name):
                state = json.loads(json.dumps(self.state))
                state.update(extra)
                proc = self.go(state=state)
                self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
                self.assertNotCalled("qm")
                self.assertNotCalled("curl")

    def test_orphan_volumes_block_creation(self):
        self.state["content"]["local-lvm"] = [{"volid": "local-lvm:vm-9100-disk-0", "vmid": 9100}]
        proc = self.go()
        self.assertRefused(proc, text="no guest uses them")
        self.assertNotCalled("qm")

    def test_url_and_pool_validation(self):
        for key, value in (("CL_FCOS_IMAGE_URL", "http://builds.example.invalid/a.xz"),
                           ("CL_FCOS_IMAGE_URL", "https://builds.example.invalid/a b.xz"),
                           ("CL_FCOS_IMAGE_URL", "https://builds.example.invalid/$(id).xz"),
                           ("CL_FCOS_IMAGE_URL", "-o/etc/x"), ("CL_FCOS_IMAGE_SHA256", "G" * 64),
                           ("CL_POOL", "a b"), ("CL_BRIDGE", "x;y")):
            with self.subTest(key=key, value=value):
                proc = self.go({key: value})
                self.assertRefused(proc)
                self.assertNotCalled("curl")
                self.assertNotCalled("qm")

    def test_download_uses_https_only_and_pins_redirects(self):
        self.assertEqual(self.go().returncode, 0)
        curl = next(c for c in self.calls() if c[0] == "curl")
        for flag in ("--fail", "--proto", "--proto-redir", "--tlsv1.2"):
            self.assertIn(flag, curl)
        self.assertEqual(curl[curl.index("--proto-redir") + 1], "=https")
        self.assertEqual(curl[-2], "--")


# --------------------------------------------------------------------------------- static
class ScriptTextTests(unittest.TestCase):
    def test_every_action_is_valid_bash(self):
        # bash -n runs nothing, but the isolation guard checks which tools a script names, so the
        # stand-ins come first on PATH here too.
        with fixtures.private_tmpdir() as tmp:
            for tool in TOOLS:
                (Path(tmp) / tool).symlink_to(STUB)
            env = {"PATH": f"{tmp}:/usr/bin:/bin"}
            for path in sorted(ACTIONS_DIR.glob("*.sh")):
                with self.subTest(path.name):
                    proc = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True, env=env)
                    self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_headers_do_not_claim_more_than_the_code_checks(self):
        for name in ("prepare", "sentinel", "fcos-template", "bootstrap"):
            header = "\n".join(l for l in (ACTIONS_DIR / f"{name}.sh").read_text().splitlines()[:40] if l.startswith("#"))
            with self.subTest(name):
                self.assertNotRegex(header, r"(?i)\bidempotent\b")
                self.assertNotRegex(header, r"(?i)checksum-verified")

    def test_no_listing_is_read_through_a_grep_q_pipeline(self):
        for path in sorted(ACTIONS_DIR.glob("*.sh")):
            with self.subTest(path.name):
                self.assertNotRegex(path.read_text(), r"\bgrep -qx? 1\b")

    def test_no_script_names_internal_register_ids(self):
        for path in sorted(ACTIONS_DIR.glob("*.sh")):
            with self.subTest(path.name):
                self.assertNotRegex(path.read_text(), r"\bSR-\d+\b")


if __name__ == "__main__":
    unittest.main()
