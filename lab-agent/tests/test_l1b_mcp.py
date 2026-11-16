"""Offline tests for the MCP launcher, install path and pin-review fixtures (mission L1B, task LA-MCP).

Nothing here starts a process, clones, installs or touches a network: ``subprocess.run``,
``os.execve`` and ``os.fchdir`` are replaced in every test, and the settings are synthetic.
A passing mock proves the launcher's own logic only. It proves nothing about the live server,
Proxmox permissions or the harness (offline only).
"""

import contextlib
import io
import json
import logging
import os
import re
import runpy
import shutil
import stat
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from lab_agent import cli, config, mcp
from tests import fixtures

REPO = Path(__file__).resolve().parents[2]
CANARY = "CANARY-7f3c9a1e-0b52-4d1b-9e6a-5c2d8f40aa17"
PIN = mcp.PIN["commit"]
OTHER = "0" * 40
REAL_FIND = mcp.find_executable  # the real lookup, kept before any test replaces it
FAKE_BIN = "/opt/fake"  # where the replaced lookup claims git and uv are

# The commit whose upstream source the two snapshots below were read from. It is written out here
# on purpose and is compared with the pin: moving the pin fails the tests that use the snapshots
# until someone re-reads the source at the new commit and updates the snapshots and this value.
# That is the whole guarantee; the snapshots' content is provenance recorded in the review document.
REVIEWED_COMMIT = "69686b06347c89d85c3725cf4a730c979b0148b7"

# Snapshot of the tool names the pinned server defines in the toolsets nodes, qemu, storage,
# pools, cluster and the always-loaded tasks (read from its source at the pinned commit with
# read-only requests on 2026-11-16; 141 names, as the review counted when it ran the server).
UPSTREAM_TOOLS = (
    "list_nodes", "get_node_status", "get_node_config", "get_node_version", "get_node_time", "set_node_time",
    "get_node_dns", "set_node_dns", "get_node_hosts", "set_node_hosts", "get_node_network",
    "get_node_network_interface", "apply_node_network", "revert_node_network", "get_node_netstat",
    "list_node_services", "get_node_service_state", "start_node_service", "stop_node_service",
    "restart_node_service", "reload_node_service", "get_node_syslog", "get_node_journal", "get_node_report",
    "get_node_subscription", "get_node_apt_update", "get_node_apt_changelog", "get_node_hardware",
    "get_node_rrd", "get_node_rrddata", "node_shutdown", "node_startall", "node_stopall", "node_migrateall",
    "get_node_aplinfo", "get_node_capabilities_qemu", "get_node_scan", "wakeonlan", "list_vms",
    "get_vm_status", "get_vm_config", "set_vm_config", "get_vm_pending", "start_vm", "stop_vm", "shutdown_vm",
    "reboot_vm", "reset_vm", "suspend_vm", "resume_vm", "create_vm", "clone_vm", "delete_vm",
    "convert_vm_to_template", "list_vm_snapshots", "create_vm_snapshot", "get_vm_snapshot_config",
    "rollback_vm_snapshot", "delete_vm_snapshot", "migrate_vm", "get_vm_migrate_preconditions",
    "resize_vm_disk", "move_vm_disk", "unlink_vm_disk", "import_vm_disk", "get_vm_firewall_rules",
    "add_vm_firewall_rule", "delete_vm_firewall_rule", "get_vm_firewall_options", "set_vm_firewall_options",
    "get_vm_firewall_log", "get_vm_rrddata", "vm_agent_exec", "vm_agent_exec_status", "vm_agent_get_fsinfo",
    "vm_agent_get_network_interfaces", "vm_agent_get_osinfo", "vm_agent_ping", "vm_agent_set_user_password",
    "get_vm_feature", "get_vm_vnc_proxy", "get_vm_spice_proxy", "get_vm_cloudinit", "regenerate_vm_cloudinit",
    "list_storage", "get_storage_config", "create_storage", "update_storage", "delete_storage",
    "get_node_storage_status", "list_storage_content", "get_storage_volume_info", "delete_storage_volume",
    "copy_storage_volume", "download_url_to_storage", "backup_vm", "restore_vm_backup",
    "restore_container_backup", "list_pools", "get_pool", "create_pool", "update_pool", "delete_pool",
    "get_cluster_status", "get_cluster_resources", "get_cluster_version", "get_cluster_nextid",
    "get_cluster_options", "set_cluster_options", "get_cluster_log", "list_cluster_tasks", "list_node_tasks",
    "get_task_status", "get_task_log", "stop_task", "list_ha_resources", "get_ha_resource", "add_ha_resource",
    "update_ha_resource", "delete_ha_resource", "list_ha_groups", "get_ha_status", "list_replication_jobs",
    "get_replication_job", "create_replication_job", "update_replication_job", "delete_replication_job",
    "list_backup_jobs", "get_backup_job", "create_backup_job", "update_backup_job", "delete_backup_job",
    "bulk_start_guests", "bulk_shutdown_guests", "bulk_migrate_guests", "list_metrics_servers",
    "create_metrics_server", "delete_metrics_server", "list_realm_sync_jobs", "analyze_schedule",
    "wait_for_task",
)
# The deny list reviewed for the project settings, by tool name (without the mcp__pve__ prefix).
DENIED = (
    "set_node_time",
    "set_node_dns",
    "set_node_hosts",
    "apply_node_network",
    "revert_node_network",
    "start_node_service",
    "stop_node_service",
    "restart_node_service",
    "reload_node_service",
    "node_shutdown",
    "node_startall",
    "node_stopall",
    "node_migrateall",
    "wakeonlan",
    "create_storage",
    "update_storage",
    "delete_storage",
    "download_url_to_storage",
    "create_pool",
    "update_pool",
    "delete_pool",
    "set_cluster_options",
    "add_ha_resource",
    "update_ha_resource",
    "delete_ha_resource",
    "create_replication_job",
    "update_replication_job",
    "delete_replication_job",
    "create_backup_job",
    "update_backup_job",
    "delete_backup_job",
    "bulk_start_guests",
    "bulk_shutdown_guests",
    "bulk_migrate_guests",
    "create_metrics_server",
    "delete_metrics_server",
    "migrate_vm",
    "import_vm_disk",
    "vm_agent_set_user_password",
)


def make_git_dir(install: Path) -> None:
    """Create ``<install>/.git`` the way a clone would leave it, with the parent ``mcp`` directory
    private (the launcher refuses a parent that is not exactly mode 700)."""
    install.parent.mkdir(exist_ok=True)
    os.chmod(install.parent, 0o700)
    (install / ".git").mkdir(parents=True, exist_ok=True)


def covered(spec: str) -> set[int]:
    """The IDs a PROXMOX_PROTECTED_VMIDS value protects, parsed as the server parses it
    (``guards.parse_protected``: IDs or ranges, ``hi - lo > 100000`` is invalid)."""
    ids: set[int] = set()
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        assert m, f"server would reject {part!r}"
        lo, hi = int(m[1]), int(m[2] or m[1])
        assert lo <= hi and hi - lo <= 100_000, f"server would reject {part!r}"
        ids.update(range(lo, hi + 1))
    return ids


class Base(unittest.TestCase):
    """Every test runs with the process-level side effects replaced."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.patchers = {}
        self.patch("lab_agent.mcp.os.environ", new=dict(os.environ, PATH="/usr/bin:/bin"))
        self.run_mock = self.patch("lab_agent.mcp.subprocess.run",
                                   side_effect=AssertionError("unexpected real subprocess"))
        self.exec_mock = self.patch("lab_agent.mcp.os.execve")
        self.chdir_mock = self.patch("lab_agent.mcp.os.fchdir")
        self.find_mock = self.patch("lab_agent.mcp.find_executable",
                                    side_effect=lambda name, path_value, roots: f"{FAKE_BIN}/{name}")

    def patch(self, target, **kw):
        p = mock.patch(target, **kw)
        m = p.start()
        self.patchers[target] = p
        self.addCleanup(p.stop)
        return m

    def lab(self, **overrides):
        cfg = fixtures.make_lab(self.dir, **overrides)
        (self.dir / "token").write_text(CANARY + "\n")
        os.chmod(self.dir / "token", 0o600)
        return cfg

    def fake_git(self, head):
        """Make ``git rev-parse HEAD`` report ``head``; any other process is a failure."""
        def run(cmd, **kw):
            if os.path.basename(cmd[0]) == "git" and cmd[-2:] == ["rev-parse", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, stdout=head + "\n", stderr="")
            raise AssertionError(f"unexpected process: {cmd[0]}")
        self.run_mock.side_effect = run

    def mark_installed(self, cfg):
        make_git_dir(mcp.install_dir(cfg))


class LaunchRefusalTests(Base):
    def test_refuses_when_not_installed(self):
        cfg = self.lab()
        with self.assertRaisesRegex(config.ConfigError, "not installed"):
            mcp.launch(cfg)
        self.exec_mock.assert_not_called()
        self.chdir_mock.assert_not_called()

    def test_refuses_when_head_is_not_the_pin(self):
        cfg = self.lab()
        self.mark_installed(cfg)
        self.fake_git(OTHER)
        with self.assertRaisesRegex(config.ConfigError, "not installed"):
            mcp.launch(cfg)
        self.exec_mock.assert_not_called()
        self.chdir_mock.assert_not_called()

    def test_refuses_when_git_fails_or_is_missing(self):
        cfg = self.lab()
        self.mark_installed(cfg)
        self.run_mock.side_effect = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 128, stdout="", stderr="x")
        with self.assertRaisesRegex(config.ConfigError, "not installed"):
            mcp.launch(cfg)
        self.run_mock.side_effect = FileNotFoundError("git")
        with self.assertRaisesRegex(config.ConfigError, "not installed"):
            mcp.launch(cfg)
        self.exec_mock.assert_not_called()

    def test_an_untrusted_or_missing_git_stops_the_launch_with_its_own_message(self):
        cfg = self.lab()
        self.mark_installed(cfg)
        self.find_mock.side_effect = config.ConfigError("git not found on PATH")
        with self.assertRaisesRegex(config.ConfigError, "git not found"):
            mcp.launch(cfg)
        self.exec_mock.assert_not_called()
        self.chdir_mock.assert_not_called()

    def test_a_gitfile_or_symlinked_dot_git_is_not_a_checkout(self):
        cfg = self.lab()
        path = mcp.install_dir(cfg)
        path.parent.mkdir()
        os.chmod(path.parent, 0o700)
        path.mkdir()
        elsewhere = self.dir / "elsewhere.git"
        elsewhere.mkdir()
        self.fake_git(PIN)
        (path / ".git").write_text(f"gitdir: {elsewhere}\n")
        self.assertIsNone(mcp.installed_commit(path))
        (path / ".git").unlink()
        (path / ".git").symlink_to(elsewhere)
        self.assertIsNone(mcp.installed_commit(path))
        with self.assertRaisesRegex(config.ConfigError, "not installed"):
            mcp.launch(cfg)
        self.assertFalse([c for c in self.run_mock.mock_calls])  # git was never asked
        (path / ".git").unlink()
        (path / ".git").mkdir()  # positive control: a real directory is asked
        self.assertEqual(mcp.installed_commit(path), PIN)

    def test_refuses_a_head_that_only_starts_like_the_pin(self):
        cfg = self.lab()
        self.mark_installed(cfg)
        self.fake_git(PIN[:12])
        with self.assertRaisesRegex(config.ConfigError, "not installed"):
            mcp.launch(cfg)
        self.exec_mock.assert_not_called()

    def test_positive_control_pinned_head_launches(self):
        cfg = self.lab()
        self.mark_installed(cfg)
        self.fake_git(PIN)
        mcp.launch(cfg)
        self.exec_mock.assert_called_once()
        file, argv, env = self.exec_mock.call_args.args
        self.assertEqual(file, f"{FAKE_BIN}/uv")
        self.assertEqual(argv, ["uv", "run", "--frozen", "--no-sync", "--project", str(mcp.install_dir(cfg)),
                                "proxmox-mcp-server"])
        self.assertEqual(env["PROXMOX_TOKEN_VALUE"], CANARY)

    def test_the_install_parent_is_validated_on_launch_before_git_or_the_project(self):
        cfg = self.lab()
        self.mark_installed(cfg)
        self.fake_git(PIN)
        parent = mcp.install_dir(cfg).parent
        mcp.launch(cfg)  # positive control: a private parent and a pinned checkout launch
        self.exec_mock.assert_called_once()
        self.exec_mock.reset_mock()
        self.run_mock.reset_mock()
        self.chdir_mock.reset_mock()
        for mode in (0o755, 0o770, 0o750):
            with self.subTest(parent_mode=oct(mode)):
                os.chmod(parent, mode)
                with self.assertRaisesRegex(config.ConfigError, "expected 700"):
                    mcp.launch(cfg)
        os.chmod(parent, 0o700)
        moved = self.dir / "moved-mcp"
        parent.rename(moved)
        parent.symlink_to(moved)
        with self.assertRaisesRegex(config.ConfigError, "symlink"):
            mcp.launch(cfg)
        self.exec_mock.assert_not_called()
        self.chdir_mock.assert_not_called()
        self.run_mock.assert_not_called()  # git was never asked in any refused case

    def test_a_missing_install_parent_is_not_installed_and_is_not_created_by_launch(self):
        cfg = self.lab()
        self.fake_git(PIN)
        with self.assertRaisesRegex(config.ConfigError, "not installed"):
            mcp.launch(cfg)
        self.assertFalse((cfg.state_dir() / "mcp").exists())

    def test_missing_ca_stops_before_chdir_and_exec(self):
        cfg = self.lab()
        self.mark_installed(cfg)
        self.fake_git(PIN)
        (self.dir / "ca.pem").unlink()
        with self.assertRaisesRegex(config.ConfigError, "PVE_CA_FILE"):
            mcp.launch(cfg)
        self.exec_mock.assert_not_called()
        self.chdir_mock.assert_not_called()


class TlsAndToolsetTests(Base):
    def test_ca_bundle_is_always_set_and_verification_never_off(self):
        cfg = self.lab()
        # Positive control: a hostile base environment changes nothing.
        base = {"PATH": "/usr/bin", "PROXMOX_VERIFY_SSL": "false", "PROXMOX_CA_BUNDLE": "/elsewhere/ca.pem",
                "PROXMOX_PASSWORD": "pw"}
        env = mcp.server_env(cfg, base)
        self.assertEqual(env["PROXMOX_CA_BUNDLE"], str(self.dir / "ca.pem"))
        self.assertNotIn("PROXMOX_VERIFY_SSL", env)
        self.assertEqual(env["PROXMOX_PASSWORD"], "")  # a stray .env cannot supply one

    def test_every_launch_carries_the_ca_bundle(self):
        cfg = self.lab()
        self.mark_installed(cfg)
        self.fake_git(PIN)
        mcp.launch(cfg)
        env = self.exec_mock.call_args.args[2]
        self.assertEqual(env["PROXMOX_CA_BUNDLE"], str(cfg.path("PVE_CA_FILE")))
        self.assertNotIn("PROXMOX_VERIFY_SSL", env)

    def test_source_never_switches_verification_off(self):
        text = (REPO / "lab-agent" / "lab_agent" / "mcp.py").read_text()
        self.assertNotIn("VERIFY_SSL", text)
        self.assertNotRegex(text, r"(?i)insecure|verify\s*=\s*false|--no-verify|-k\b")

    def test_toolsets_are_exactly_the_reviewed_list(self):
        self.assertEqual(mcp.TOOLSETS, "nodes,qemu,storage,pools,cluster")
        env = mcp.server_env(self.lab(), {})
        self.assertEqual(env["PROXMOX_TOOLSETS"].split(","), ["nodes", "qemu", "storage", "pools", "cluster"])
        for left_out in ("access", "firewall", "disks", "ceph", "acme", "sdn", "notifications", "appliances",
                         "lxc", "pdm", "all"):
            self.assertNotIn(left_out, env["PROXMOX_TOOLSETS"].split(","))

    def test_environment_is_an_allow_list(self):
        base = {"PATH": "/usr/bin", "HOME": "/h", "LANG": "C", "TMPDIR": "/t", "SSH_AUTH_SOCK": "/s",
                "HTTPS_PROXY": "http://198.51.100.1:3128", "PROXMOX_READ_ONLY": "true", "PDM_HOST": "x",
                "ANTHROPIC_API_KEY": "k"}
        env = mcp.server_env(self.lab(), base)
        for key in ("SSH_AUTH_SOCK", "HTTPS_PROXY", "PROXMOX_READ_ONLY", "PDM_HOST", "ANTHROPIC_API_KEY"):
            self.assertNotIn(key, env)
        self.assertEqual({k: env[k] for k in ("PATH", "HOME", "LANG", "TMPDIR")},
                         {k: base[k] for k in ("PATH", "HOME", "LANG", "TMPDIR")})


class ProtectedVmidTests(Base):
    CASES = {
        (9100, 9199): "100-9099,9200-109199",
        (100, 199): "200-100199",  # bottom of the ID space: nothing below
        (101, 101): "100-100,102-100101",
        (100, 100): "101-100100",
        (100100, 100199): "100-100099,100200-200199",  # exactly 100,000 below
        (100101, 100101): "101-100100,100102-200101",  # the lower side is cut at the cap
        (500000, 500010): "400000-499999,500011-600010",
        (999_999_900, 999_999_999): "999899900-999999899",  # top of the ID space: nothing above
        (999_999_000, 999_999_998): "999899000-999998999,999999999-999999999",
        (100, 999_999_999): "",  # the project range fills the space: nothing outside it
    }

    def test_edges(self):
        for (lo, hi), want in self.CASES.items():
            with self.subTest(lo=lo, hi=hi):
                self.assertEqual(mcp.protected_vmids(lo, hi), want)

    def test_output_is_valid_for_the_server_and_stays_in_the_id_space(self):
        for lo, hi in self.CASES:
            with self.subTest(lo=lo, hi=hi):
                ids = covered(mcp.protected_vmids(lo, hi))  # asserts the server's own limits
                self.assertTrue(all(100 <= i <= 999_999_999 for i in ids))
                self.assertFalse(ids & set(range(lo, min(hi, lo + 5000) + 1)))  # never the project range
                self.assertFalse(ids & {hi, lo})
                if lo > 100:
                    self.assertIn(lo - 1, ids)
                if hi < 999_999_999:
                    self.assertIn(hi + 1, ids)

    def test_the_documented_cap_is_100000_ids_each_side(self):
        ids = covered(mcp.protected_vmids(500000, 500010))
        self.assertIn(400000, ids)
        self.assertNotIn(399999, ids)
        self.assertIn(600010, ids)
        self.assertNotIn(600011, ids)

    def test_sentinel_and_neighbours_are_protected_but_the_project_range_is_not(self):
        cfg = self.lab()
        ids = covered(mcp.server_env(cfg, {})["PROXMOX_PROTECTED_VMIDS"])
        self.assertIn(int(cfg.get("PVE_SENTINEL_VMID")), ids)
        self.assertEqual({9099, 9200} - ids, set())
        self.assertEqual({9100, 9150, 9199} & ids, set())

    def test_invalid_range_is_refused_before_any_launch_step(self):
        for bad in ("9199-9100", "abc", "99-120", "9100", "9100-", "100-1000000000", "9100-9199,9300", "-5-9"):
            with self.subTest(value=bad):
                cfg = self.lab(PVE_VMID_RANGE=bad)
                make_git_dir(mcp.install_dir(cfg))
                self.fake_git(PIN)
                with self.assertRaisesRegex(config.ConfigError, "PVE_VMID_RANGE"):
                    mcp.launch(cfg)
                self.exec_mock.assert_not_called()
                self.chdir_mock.assert_not_called()

    def test_range_accepted_at_the_limits(self):
        for good in ("100-100", "100-999999999", "999999999-999999999"):
            with self.subTest(value=good):
                env = mcp.server_env(self.lab(PVE_VMID_RANGE=good), {})
                covered(env["PROXMOX_PROTECTED_VMIDS"])


class RunDirTests(Base):
    def prepared(self):
        cfg = self.lab()
        self.mark_installed(cfg)
        self.fake_git(PIN)
        return cfg

    def test_working_directory_is_a_fresh_private_directory_under_the_state_dir(self):
        cfg = self.prepared()
        seen = {}

        def record(fd):
            st = os.fstat(fd)
            seen.update(fd=fd, ident=(st.st_dev, st.st_ino), listing=sorted(os.listdir(fd)), mode=st.st_mode & 0o7777)
        self.chdir_mock.side_effect = record
        mcp.launch(cfg)
        expected = os.stat(cfg.state_dir() / "mcp-run")
        self.assertEqual(seen["ident"], (expected.st_dev, expected.st_ino))  # the descriptor is that directory
        self.assertEqual(seen["listing"], [])  # empty at the moment of the change: no stray .env
        self.assertEqual(seen["mode"], 0o700)
        self.chdir_mock.assert_called_once()
        with self.assertRaises(OSError):  # the descriptor was closed again
            os.fstat(seen["fd"])

    def test_chdir_happens_before_exec(self):
        cfg = self.prepared()
        order = []
        self.chdir_mock.side_effect = lambda p: order.append("chdir")
        self.exec_mock.side_effect = lambda *a: order.append("exec")
        mcp.launch(cfg)
        self.assertEqual(order, ["chdir", "exec"])

    def test_a_stray_env_file_is_refused(self):
        cfg = self.prepared()
        (cfg.state_dir() / "mcp-run").mkdir(mode=0o700)
        for name in (".env", ".env.local"):
            with self.subTest(name=name):
                f = cfg.state_dir() / "mcp-run" / name
                f.write_text("PROXMOX_READ_ONLY=true\n")
                with self.assertRaisesRegex(config.ConfigError, ".env"):
                    mcp.launch(cfg)
                self.exec_mock.assert_not_called()
                self.chdir_mock.assert_not_called()
                f.unlink()
        mcp.launch(cfg)  # positive control: the same directory without the file is accepted
        self.exec_mock.assert_called_once()

    def test_other_files_do_not_block(self):
        cfg = self.prepared()
        d = cfg.state_dir() / "mcp-run"
        d.mkdir(mode=0o700)
        (d / "notes.txt").write_text("x")
        mcp.launch(cfg)
        self.exec_mock.assert_called_once()

    def test_symlinked_or_not_exactly_private_directory_is_refused(self):
        cfg = self.prepared()
        target = self.dir / "elsewhere"
        target.mkdir(mode=0o700)
        link = cfg.state_dir() / "mcp-run"
        link.symlink_to(target)
        with self.assertRaisesRegex(config.ConfigError, "symlink"):
            mcp.launch(cfg)
        link.unlink()
        link.mkdir(mode=0o700)
        for mode in (0o770, 0o750, 0o755, 0o707):
            with self.subTest(mode=oct(mode)):
                os.chmod(link, mode)
                with self.assertRaisesRegex(config.ConfigError, "expected 700"):
                    mcp.launch(cfg)
        self.exec_mock.assert_not_called()
        os.chmod(link, 0o700)
        mcp.launch(cfg)  # positive control
        self.exec_mock.assert_called_once()

    def test_the_directory_is_created_as_700_whatever_the_umask(self):
        for umask in (0o000, 0o022, 0o077, 0o277):
            with self.subTest(umask=oct(umask)):
                cfg = self.lab(PVE_LAB_STATE=str(self.dir / f"state-{umask:o}"))
                old = os.umask(umask)
                try:
                    mcp.run_dir(cfg)
                finally:
                    os.umask(old)
                st = os.stat(self.dir / f"state-{umask:o}" / "mcp-run")
                self.assertEqual(st.st_mode & 0o7777, 0o700)
                self.assertEqual(os.stat(self.dir / f"state-{umask:o}").st_mode & 0o7777, 0o700)

    def test_a_refusal_does_not_leak_the_descriptor(self):
        cfg = self.prepared()
        d = cfg.state_dir() / "mcp-run"
        d.mkdir(mode=0o700)
        (d / ".env").write_text("x\n")
        fds = "/proc/self/fd"

        def count():
            return len(os.listdir(fds)) if os.path.isdir(fds) else 0
        before = count()
        for _ in range(20):
            with self.assertRaisesRegex(config.ConfigError, ".env"):
                mcp.launch(cfg)
        self.assertEqual(count(), before)


class SecretHandlingTests(Base):
    def run_and_collect(self, fn):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), self.assertNoLogs(level=logging.DEBUG):
            try:
                fn()
            except Exception as exc:  # noqa: BLE001 - the message is what is under test
                return out.getvalue() + err.getvalue(), exc
        return out.getvalue() + err.getvalue(), None

    def test_secret_is_only_in_the_server_environment(self):
        cfg = self.lab()
        self.mark_installed(cfg)
        self.fake_git(PIN)
        text, exc = self.run_and_collect(lambda: mcp.launch(cfg))
        self.assertIsNone(exc)
        file, argv, env = self.exec_mock.call_args.args
        self.assertEqual([k for k, v in env.items() if CANARY in v], ["PROXMOX_TOKEN_VALUE"])
        self.assertFalse([a for a in argv if CANARY in a])
        self.assertNotIn(CANARY, file + text + repr(cfg) + repr(self.chdir_mock.call_args))
        # The audit log and the working directory are paths, not values.
        self.assertFalse([v for k, v in env.items() if k != "PROXMOX_TOKEN_VALUE" and CANARY in v])

    def test_secret_and_hostile_variables_are_not_in_the_environment_of_git_or_uv(self):
        cfg = self.lab()
        calls = []
        self.run_mock.side_effect = lambda cmd, **kw: calls.append((cmd, kw)) or subprocess.CompletedProcess(
            cmd, 0, stdout=PIN + "\n", stderr="")
        self.mark_installed(cfg)
        parent = {"PROXMOX_TOKEN_VALUE": CANARY, "GIT_DIR": "/elsewhere", "UV_PROJECT_ENVIRONMENT": "/elsewhere",
                  "PYTHONPATH": "/elsewhere", "LD_PRELOAD": "/elsewhere/x.so"}
        with mock.patch.dict(os.environ, parent):
            mcp.install(cfg)
            mcp.installed_commit(mcp.install_dir(cfg))
        self.assertTrue(calls)
        for cmd, kw in calls:
            self.assertNotIn(CANARY, " ".join(cmd))
            # The child gets an explicit allow-listed environment, not the parent's.
            self.assertIn("env", kw)
            self.assertEqual(set(kw["env"]) - {"PATH", "HOME", "LANG", "TMPDIR", "GIT_CONFIG_NOSYSTEM",
                                               "GIT_CONFIG_GLOBAL", "GIT_TERMINAL_PROMPT"}, set())
            self.assertNotIn(CANARY, json.dumps(kw["env"]))

    def test_install_does_not_read_the_token_at_all(self):
        cfg = self.lab()
        (self.dir / "token").unlink()
        self.mark_installed(cfg)
        self.fake_git(PIN)
        self.run_mock.side_effect = lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, stdout=PIN + "\n", stderr="")
        self.assertEqual(mcp.install(cfg), mcp.install_dir(cfg))

    def test_errors_never_carry_the_secret(self):
        cases = {
            "world-readable token file": lambda cfg: os.chmod(self.dir / "token", 0o644),
            "two-line token file": lambda cfg: (self.dir / "token").write_text(CANARY + "\n" + CANARY + "\n"),
            "missing CA": lambda cfg: (self.dir / "ca.pem").unlink(),
            "bad token id": lambda cfg: None,
        }
        for label, break_it in cases.items():
            with self.subTest(case=label):
                cfg = self.lab(PVE_TOKEN_ID="not a token id" if label == "bad token id" else fixtures.TOKEN_ID)
                break_it(cfg)
                text, exc = self.run_and_collect(lambda: mcp.server_env(cfg, {}))
                self.assertIsInstance(exc, config.ConfigError)
                self.assertNotIn(CANARY, str(exc) + repr(exc) + text + repr(cfg))
                self.assertNotIn(CANARY, "".join(str(a) for a in exc.args))

    def test_cli_error_path_is_quiet_on_stdout_and_free_of_the_secret(self):
        cfg = self.lab()
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(cfg.source)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["mcp-launch"])
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), "")  # stdout belongs to the MCP protocol
        self.assertIn("not installed", err.getvalue())
        self.assertNotIn(CANARY, err.getvalue())

    def test_bin_script_reaches_the_same_refusal(self):
        cfg = self.lab()
        script = REPO / "lab-agent" / "bin" / "mcp-launch"
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"PVE_AGENT_ENV": str(cfg.source)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                self.assertRaises(SystemExit) as raised:
            runpy.run_path(str(script), run_name="__main__")
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("not installed", err.getvalue())
        self.exec_mock.assert_not_called()

    def test_mcp_json_carries_no_secret_or_setting(self):
        # The in-tree example is always checked; the local-only .mcp.json too, when this checkout has it.
        paths = [REPO / "lab-agent" / "mcp.example.json"]
        if (REPO / ".mcp.json").is_file():
            paths.append(REPO / ".mcp.json")
        for path in paths:
            data = json.loads(path.read_text())
            server = data["mcpServers"]["pve"]
            self.assertEqual(set(server), {"command", "args"}, path.name)  # no "env" block
            self.assertEqual(server["args"][-1], 'exec "$CLAUDE_PROJECT_DIR/lab-agent/bin/mcp-launch"', path.name)
            self.assertNotRegex(json.dumps(server), r"(?i)token|secret|password|PROXMOX_", path.name)


class InstallTests(Base):
    """``install`` against a recording fake of git and uv. Nothing is cloned or synced."""

    GIT, UV = f"{FAKE_BIN}/git", f"{FAKE_BIN}/uv"

    def setUp(self):
        super().setUp()
        self.cfg = self.lab()
        self.calls = []
        self.head = None
        self.checkout_lands_on = PIN
        self.fail = {}

    def start(self):
        path = mcp.install_dir(self.cfg)

        def run(cmd, **kw):
            self.calls.append(list(cmd))
            tool = os.path.basename(cmd[0])
            if tool == "uv" and "uv" in self.fail:
                raise self.fail["uv"]
            if tool == "git" and cmd[-2:] == ["rev-parse", "HEAD"]:
                if self.head is None:
                    return subprocess.CompletedProcess(cmd, 128, stdout="", stderr="no repo")
                return subprocess.CompletedProcess(cmd, 0, stdout=self.head + "\n", stderr="")
            if tool == "git" and "clone" in cmd:
                if "clone" in self.fail:
                    raise subprocess.CalledProcessError(128, cmd)
                make_git_dir(path)
                self.head = OTHER
            elif tool == "git" and "checkout" in cmd:
                if "checkout" in self.fail:
                    raise subprocess.CalledProcessError(1, cmd)
                self.head = self.checkout_lands_on
            return subprocess.CompletedProcess(cmd, 0)
        self.run_mock.side_effect = run
        return path

    def steps(self):
        return [c for c in self.calls if c[-2:] != ["rev-parse", "HEAD"]]

    def test_fresh_install_pins_the_commit_and_syncs_the_frozen_lockfile(self):
        path = self.start()
        self.assertEqual(mcp.install(self.cfg), path)
        clone, checkout, sync = self.steps()
        self.assertEqual(clone, [self.GIT, "clone", "--quiet", "--no-checkout", mcp.PIN["repo"], str(path)])
        self.assertTrue(mcp.PIN["repo"].startswith("https://github.com/ry-ops/"))
        self.assertEqual(checkout[-3:], ["--quiet", "--detach", PIN])
        self.assertEqual(sync, [self.UV, "sync", "--frozen", "--no-dev", "--project", str(path)])
        self.assertRegex(PIN, r"^[0-9a-f]{40}$")
        self.assertEqual(path.name, f"proxmox-mcp-server-{PIN[:12]}")
        self.assertEqual(path.parent.parent, self.cfg.state_dir())
        self.assertTrue(all(os.path.isabs(c[0]) for c in self.calls))

    def test_every_install_step_runs_in_a_sanitized_environment(self):
        self.start()
        parent = {"GIT_DIR": "/elsewhere", "GIT_WORK_TREE": "/elsewhere", "UV_INDEX_URL": "http://198.51.100.9/",
                  "HTTPS_PROXY": "http://198.51.100.1:3128", "PROXMOX_TOKEN_VALUE": CANARY}
        with mock.patch.dict(os.environ, parent):
            mcp.install(self.cfg)
        seen = [call.kwargs["env"] for call in self.run_mock.mock_calls if call.kwargs.get("env") is not None]
        self.assertEqual(len(seen), len(self.calls))
        for env in seen:
            self.assertNotIn("GIT_DIR", env)
            self.assertNotIn("GIT_WORK_TREE", env)
            self.assertNotIn("UV_INDEX_URL", env)
            self.assertNotIn("PROXMOX_TOKEN_VALUE", env)
            self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
            self.assertEqual(env["GIT_CONFIG_GLOBAL"], os.devnull)
        # Install steps (network) keep the proxy setting; the pin check (no network) does not.
        checks = [call.kwargs["env"] for call in self.run_mock.mock_calls if call.args[0][-2:] == ["rev-parse", "HEAD"]]
        steps = [call.kwargs["env"] for call in self.run_mock.mock_calls if call.args[0][-2:] != ["rev-parse", "HEAD"]]
        self.assertTrue(checks and steps)
        self.assertTrue(all("HTTPS_PROXY" in e for e in steps))
        self.assertTrue(all("HTTPS_PROXY" not in e for e in checks))

    def test_the_install_parent_is_created_private_whatever_the_umask_and_refused_otherwise(self):
        self.start()
        old = os.umask(0o000)
        try:
            mcp.install(self.cfg)
        finally:
            os.umask(old)
        mcp_dir = self.cfg.state_dir() / "mcp"
        self.assertEqual(os.stat(mcp_dir).st_mode & 0o7777, 0o700)
        # An existing parent that is not exactly private, or is a symlink, stops install before a process.
        shutil.rmtree(mcp_dir)
        self.calls.clear()
        mcp_dir.mkdir(mode=0o755)
        os.chmod(mcp_dir, 0o755)
        with self.assertRaisesRegex(config.ConfigError, "expected 700"):
            mcp.install(self.cfg)
        mcp_dir.rmdir()
        elsewhere = self.dir / "elsewhere"
        elsewhere.mkdir(mode=0o700)
        mcp_dir.symlink_to(elsewhere)
        with self.assertRaisesRegex(config.ConfigError, "symlink"):
            mcp.install(self.cfg)
        self.assertEqual([c for c in self.calls if c[-2:] != ["rev-parse", "HEAD"]], [])
        self.assertEqual(list(elsewhere.iterdir()), [])  # nothing was written through the link

    def test_the_install_parent_is_validated_even_when_the_checkout_is_already_at_the_pin(self):
        path = self.start()
        make_git_dir(path)
        self.head = PIN
        parent = path.parent
        mcp.install(self.cfg)  # positive control: private parent, pinned checkout, only uv runs
        self.assertEqual([os.path.basename(c[0]) for c in self.steps()], ["uv"])
        for label, mutate in (("mode 755", lambda: os.chmod(parent, 0o755)),
                              ("mode 770", lambda: os.chmod(parent, 0o770))):
            with self.subTest(parent=label):
                self.calls.clear()
                mutate()
                with self.assertRaisesRegex(config.ConfigError, "expected 700"):
                    mcp.install(self.cfg)
                self.assertEqual(self.calls, [])  # not even the pin check ran
                os.chmod(parent, 0o700)
        moved = self.dir / "moved-mcp"
        parent.rename(moved)
        parent.symlink_to(moved)
        self.calls.clear()
        with self.assertRaisesRegex(config.ConfigError, "symlink"):
            mcp.install(self.cfg)
        self.assertEqual(self.calls, [])

    def test_no_step_floats_to_a_branch_or_newer_dependency(self):
        self.start()
        mcp.install(self.cfg)
        flat = " ".join(" ".join(c) for c in self.calls)
        for floating in ("--upgrade", "--no-frozen", "--refresh", "origin/", "main", "master", "latest", "HEAD~"):
            self.assertNotIn(floating, flat.replace("rev-parse HEAD", ""))
        self.assertNotIn("pip", flat)

    def test_checkout_that_lands_elsewhere_stops_before_uv(self):
        self.start()
        self.checkout_lands_on = OTHER
        with self.assertRaisesRegex(config.ConfigError, "does not match the pin"):
            mcp.install(self.cfg)
        self.assertFalse([c for c in self.calls if os.path.basename(c[0]) == "uv"])

    def test_an_existing_checkout_at_the_pin_is_not_cloned_again(self):
        path = self.start()
        make_git_dir(path)
        self.head = PIN
        mcp.install(self.cfg)
        self.assertEqual([os.path.basename(c[0]) + " " + c[1] for c in self.steps()], ["uv sync"])

    def test_an_existing_checkout_at_another_commit_is_moved_to_the_pin(self):
        path = self.start()
        make_git_dir(path)
        self.head = OTHER
        mcp.install(self.cfg)
        kinds = [c[c.index("checkout")] if "checkout" in c else os.path.basename(c[0]) for c in self.steps()]
        self.assertEqual(kinds, ["checkout", "uv"])

    def test_failures_of_a_step_become_config_errors_without_a_command_line(self):
        for step, label in (("clone", "git clone"), ("checkout", "git checkout")):
            with self.subTest(step=step):
                self.calls.clear()
                self.head = None
                self.fail = {step: True}
                path = self.start()
                if path.exists():
                    shutil.rmtree(path)
                with self.assertRaisesRegex(config.ConfigError, f"{label} failed") as raised:
                    mcp.install(self.cfg)
                self.assertNotIn(str(self.dir), str(raised.exception))
                self.assertFalse([c for c in self.calls if os.path.basename(c[0]) == "uv"])
        self.head = PIN
        self.fail = {"uv": subprocess.CalledProcessError(2, ["uv", "sync"])}
        self.start()
        make_git_dir(mcp.install_dir(self.cfg))
        with self.assertRaisesRegex(config.ConfigError, r"uv sync failed \(exit 2\)") as raised:
            mcp.install(self.cfg)
        self.assertNotIn(str(self.dir), str(raised.exception))
        # Any other OSError raised while starting a step is also a ConfigError (not a traceback).
        self.fail = {"uv": PermissionError(13, "Permission denied")}
        with self.assertRaisesRegex(config.ConfigError, r"uv sync: could not run \(Permission denied\)"):
            mcp.install(self.cfg)

    def test_an_untrusted_git_or_uv_stops_install_before_any_process(self):
        for missing in ("git", "uv"):
            with self.subTest(missing=missing):
                self.start()
                self.calls.clear()
                self.find_mock.side_effect = lambda name, pv, roots, m=missing: (
                    (_ for _ in ()).throw(config.ConfigError(f"{m} not found on PATH")) if name == m
                    else f"{FAKE_BIN}/{name}")
                with self.assertRaisesRegex(config.ConfigError, f"{missing} not found"):
                    mcp.install(self.cfg)
                self.assertEqual(self.calls, [])


class RelativePathTests(Base):
    """Settings may name relative paths. They are resolved against the caller's directory
    before the working directory changes; the test uses the real ``chdir`` and competing files."""

    def setUp(self):
        super().setUp()
        self.patchers["lab_agent.mcp.os.fchdir"].stop()  # the real fchdir, restored at cleanup
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.dir)
        self.run_path = self.dir / "state" / "mcp-run"

    def test_ca_state_audit_and_project_paths_survive_the_chdir(self):
        cfg = self.lab(PVE_CA_FILE="ca.pem", PVE_LAB_STATE="state", PVE_TOKEN_FILE="token")
        self.mark_installed(cfg)
        self.fake_git(PIN)
        self.run_path.mkdir(mode=0o700, parents=True)
        (self.run_path / "ca.pem").write_text("COMPETING\n")  # what the relative name means after the chdir
        competing = self.run_path / "state" / "mcp" / f"proxmox-mcp-server-{PIN[:12]}"
        competing.mkdir(parents=True)
        mcp.launch(cfg)
        self.assertEqual(os.path.realpath(os.getcwd()), os.path.realpath(self.run_path))  # it did change
        self.assertEqual(Path("ca.pem").read_text(), "COMPETING\n")  # control: the trap is in place
        file, argv, env = self.exec_mock.call_args.args
        ca = env["PROXMOX_CA_BUNDLE"]
        self.assertTrue(os.path.isabs(ca))
        self.assertEqual(Path(ca).read_text(), "placeholder\n")  # the intended file, read from the new cwd
        project = argv[argv.index("--project") + 1]
        self.assertEqual(project, str(self.dir / "state" / "mcp" / f"proxmox-mcp-server-{PIN[:12]}"))
        self.assertTrue(os.path.isdir(project) and os.path.isdir(os.path.join(project, ".git")))
        self.assertNotEqual(os.path.realpath(project), os.path.realpath(competing))
        self.assertEqual(env["PROXMOX_AUDIT_LOG"], str(self.dir / "state" / "mcp-audit.jsonl"))
        self.assertTrue(os.path.isabs(file))

    def test_a_relative_ca_that_exists_only_after_the_chdir_is_refused_before_it(self):
        cfg = self.lab(PVE_CA_FILE="ca.pem", PVE_LAB_STATE="state")
        (self.dir / "ca.pem").unlink()
        self.mark_installed(cfg)
        self.fake_git(PIN)
        self.run_path.mkdir(mode=0o700, parents=True)
        (self.run_path / "ca.pem").write_text("COMPETING\n")
        before = os.getcwd()
        with self.assertRaisesRegex(config.ConfigError, "PVE_CA_FILE"):
            mcp.launch(cfg)
        self.assertEqual(os.getcwd(), before)
        self.exec_mock.assert_not_called()

    def test_install_and_run_directories_are_absolute_whatever_the_setting(self):
        cfg = self.lab(PVE_LAB_STATE="state")
        self.assertTrue(mcp.install_dir(cfg).is_absolute())
        self.assertTrue(mcp.run_dir(cfg).is_absolute())
        self.assertEqual(mcp.run_dir(cfg), self.dir / "state" / "mcp-run")


class ServerEnvPathTests(Base):
    def test_relative_empty_or_forbidden_entries_are_refused(self):
        cfg = self.lab()
        state = self.dir / "state"
        for label, value in (("relative", ".:/usr/bin"), ("empty entry", "/usr/bin::/bin"), ("trailing colon", "/usr/bin:"),
                             ("bare name", "bin"), ("run dir", f"{state}/mcp-run:/usr/bin"),
                             ("install tree", f"/usr/bin:{state}/mcp/x")):
            with self.subTest(case=label):
                with self.assertRaisesRegex(config.ConfigError, "PATH"):
                    mcp.server_env(cfg, {"PATH": value})
        env = mcp.server_env(cfg, {"PATH": "/usr/bin:/bin"})  # positive control
        self.assertEqual(env["PATH"], "/usr/bin:/bin")
        self.assertNotIn("PATH", mcp.server_env(cfg, {}))

    def test_home_and_tmpdir_must_be_absolute(self):
        env = mcp.server_env(self.lab(), {"HOME": ".", "TMPDIR": "tmp", "LANG": "C"})
        self.assertEqual(sorted(k for k in env if k in ("HOME", "TMPDIR", "LANG")), ["LANG"])


class HostAndPortTests(Base):
    """The server environment carries the validated host and port, never the raw settings."""

    def test_malformed_host_is_refused_before_any_launch_step(self):
        for bad in ("192.0.2.10;id", "evil host", "192.0.2.10:8006", "-oProxyCommand=x", "http://192.0.2.10",
                    "user@192.0.2.10", "0.0.0.0", "[2001:db8::1]", "192.0.2.10/24", "a..b", "$(id)"):
            with self.subTest(host=bad):
                cfg = self.lab(PVE_HOST=bad)
                with self.assertRaisesRegex(config.ConfigError, "PVE_HOST"):
                    mcp.server_env(cfg, {})
                self.mark_installed(cfg)
                self.fake_git(PIN)
                with self.assertRaisesRegex(config.ConfigError, "PVE_HOST"):
                    mcp.launch(cfg)
                self.exec_mock.assert_not_called()
                self.chdir_mock.assert_not_called()

    def test_malformed_port_is_refused(self):
        for bad in ("8006x", "0", "65536", "-1", "8 006", "8006.0", "\uff18\uff10\uff10\uff16", "0x1f46", "+8006"):
            with self.subTest(port=bad):
                with self.assertRaisesRegex(config.ConfigError, "PVE_PORT"):
                    mcp.server_env(self.lab(PVE_PORT=bad), {})

    def test_valid_values_reach_the_server_in_canonical_form(self):
        env = mcp.server_env(self.lab(PVE_HOST="2001:db8:0:0:0:0:0:1", PVE_PORT="08006"), {})
        self.assertEqual((env["PROXMOX_HOST"], env["PROXMOX_PORT"]), ("2001:db8::1", "8006"))
        env = mcp.server_env(self.lab(PVE_HOST="pve-test.example.invalid", PVE_PORT="443"), {})
        self.assertEqual((env["PROXMOX_HOST"], env["PROXMOX_PORT"]), ("pve-test.example.invalid", "443"))
        env = mcp.server_env(self.lab(), {})  # the default port when none is set
        self.assertEqual((env["PROXMOX_HOST"], env["PROXMOX_PORT"]), ("192.0.2.10", "8006"))

    def test_source_does_not_read_the_raw_settings(self):
        text = (REPO / "lab-agent" / "lab_agent" / "mcp.py").read_text()
        self.assertNotRegex(text, r'get\("PVE_(HOST|PORT)"\)')


class ToolEnvTests(unittest.TestCase):
    PARENT = {"PATH": "/usr/bin", "HOME": "/h", "LANG": "C", "TMPDIR": "/t", "GIT_DIR": "/x", "GIT_WORK_TREE": "/x",
              "GIT_EXEC_PATH": "/x", "GIT_CONFIG_COUNT": "1", "GIT_SSH_COMMAND": "evil", "UV_PROJECT_ENVIRONMENT": "/x",
              "UV_INDEX_URL": "http://198.51.100.9/", "PYTHONPATH": "/x", "LD_PRELOAD": "/x.so",
              "PROXMOX_TOKEN_VALUE": CANARY, "HTTPS_PROXY": "http://198.51.100.1:3128", "NO_PROXY": "x",
              "SSL_CERT_FILE": "/c.pem"}

    def test_only_listed_variables_reach_git_and_uv(self):
        env = mcp.tool_env(self.PARENT, ["/usr/bin", "/bin"])
        self.assertEqual(set(env), {"PATH", "HOME", "LANG", "TMPDIR", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL",
                                    "GIT_TERMINAL_PROMPT", "HTTPS_PROXY", "NO_PROXY", "SSL_CERT_FILE"})
        self.assertEqual(env["PATH"], "/usr/bin:/bin")
        self.assertNotIn(CANARY, json.dumps(env))

    def test_the_pin_check_gets_no_network_settings(self):
        env = mcp.tool_env(self.PARENT, ["/usr/bin"], network=False)
        self.assertEqual(set(env), {"PATH", "HOME", "LANG", "TMPDIR", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL",
                                    "GIT_TERMINAL_PROMPT"})

    def test_relative_home_and_tmpdir_are_dropped(self):
        env = mcp.tool_env({"HOME": "rel", "TMPDIR": ".", "LANG": "C"}, ["/usr/bin"])
        self.assertEqual({k for k in env if k in ("HOME", "TMPDIR")}, set())


class ExecutableResolutionTests(unittest.TestCase):
    """``find_executable`` on real files and directories (nothing is run)."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.bin = self.make_bin("bin")
        self.run_dir = self.d / "state" / "mcp-run"
        self.mcp_dir = self.d / "state" / "mcp"
        for p in (self.run_dir, self.mcp_dir):
            p.mkdir(parents=True)
        self.roots = [self.mcp_dir, self.run_dir]
        self.addCleanup(os.chdir, os.getcwd())

    def make_bin(self, name):
        d = self.d / name
        d.mkdir()
        os.chmod(d, 0o755)
        for tool in ("git", "uv"):
            f = d / tool
            f.write_text("#!/bin/sh\nexit 0\n")
            os.chmod(f, 0o755)
        return d

    def find(self, name, value):
        return REAL_FIND(name, value, self.roots)

    def test_positive_control_a_private_executable_on_an_absolute_path(self):
        self.assertEqual(self.find("uv", str(self.bin)), str(self.bin / "uv"))
        self.assertEqual(self.find("git", f"/nonexistent-dir:{self.bin}"), str(self.bin / "git"))

    def test_relative_and_empty_entries_never_select_an_executable(self):
        planted = self.run_dir / "uv"
        planted.write_text("#!/bin/sh\n")
        os.chmod(planted, 0o755)
        os.chdir(self.run_dir)
        self.assertEqual(self.find("uv", str(self.bin)), str(self.bin / "uv"))  # control: the same call, safe PATH
        for value in (f".:{self.bin}", f":{self.bin}", f"{self.bin}:", f"{self.bin}::/usr/bin", ".", "", None,
                      f"{os.path.relpath(self.bin, self.run_dir)}:{self.bin}"):
            with self.subTest(path=value):
                with self.assertRaises(config.ConfigError) as raised:
                    self.find("uv", value)
                self.assertNotIn(str(self.d), str(raised.exception))

    def test_entries_inside_the_run_or_install_directory_are_refused(self):
        planted = self.run_dir / "uv"
        planted.write_text("#!/bin/sh\n")
        os.chmod(planted, 0o755)
        (self.mcp_dir / "sub").mkdir()
        link = self.d / "linkdir"
        link.symlink_to(self.run_dir)
        for entry in (self.run_dir, self.mcp_dir, self.mcp_dir / "sub", link):
            with self.subTest(entry=entry.name):
                with self.assertRaisesRegex(config.ConfigError, "inside the lab-agent"):
                    self.find("uv", f"{entry}:{self.bin}")

    def test_a_trusted_looking_name_that_resolves_inside_is_refused(self):
        planted = self.run_dir / "uv"
        planted.write_text("#!/bin/sh\n")
        os.chmod(planted, 0o755)
        other = self.make_bin("bin2")
        (other / "uv").unlink()
        (other / "uv").symlink_to(planted)
        self.assertEqual(self.find("git", str(other)), str(other / "git"))  # control: the directory itself is fine
        with self.assertRaisesRegex(config.ConfigError, "resolves inside"):
            self.find("uv", str(other))

    def test_untrusted_ownership_or_permissions_are_refused(self):
        uv = self.bin / "uv"
        self.assertEqual(self.find("uv", str(self.bin)), str(uv))
        for mode in (0o775, 0o757, 0o777):
            with self.subTest(file_mode=oct(mode)):
                os.chmod(uv, mode)
                with self.assertRaisesRegex(config.ConfigError, "writable by group or others"):
                    self.find("uv", str(self.bin))
        os.chmod(uv, 0o755)
        os.chmod(self.bin, 0o775)
        with self.assertRaisesRegex(config.ConfigError, "directory .* is owned by another user or writable"):
            self.find("uv", str(self.bin))
        os.chmod(self.bin, 0o755)
        self.assertEqual(self.find("uv", str(self.bin)), str(uv))
        with mock.patch("lab_agent.mcp.os.getuid", return_value=os.getuid() + 1):  # a file of another user
            with self.assertRaisesRegex(config.ConfigError, "another user"):
                self.find("uv", str(self.bin))

    def test_a_symlink_in_a_writable_directory_is_resolved_so_a_swap_changes_nothing(self):
        trusted = str(self.bin / "uv")
        loose = self.d / "loose"
        loose.mkdir()
        os.chmod(loose, 0o777)  # a directory anybody could write into
        link = loose / "uv"
        link.symlink_to(trusted)
        self.assertEqual(self.find("git", str(self.bin)), str(self.bin / "git"))  # control: a plain private bin works
        got = self.find("uv", str(loose))
        self.assertEqual(got, os.path.realpath(trusted))  # the target, not the link that could be swapped
        self.assertNotEqual(got, str(link))
        self.assertFalse(os.path.islink(got))
        # The swap: the link is repointed at another program. What was returned still names the checked file.
        evil = self.make_bin("evil")
        link.unlink()
        link.symlink_to(evil / "uv")
        self.assertEqual(got, os.path.realpath(trusted))
        self.assertEqual(os.path.realpath(got), os.path.realpath(self.bin / "uv"))
        self.assertNotEqual(os.path.realpath(got), os.path.realpath(evil / "uv"))

    def test_every_directory_above_the_resolved_target_must_be_private(self):
        outer = self.d / "outer"
        inner = outer / "inner"
        inner.mkdir(parents=True)
        for directory in (outer, inner):
            os.chmod(directory, 0o755)
        (inner / "uv").write_text("#!/bin/sh\n")
        os.chmod(inner / "uv", 0o755)
        self.assertEqual(self.find("uv", str(inner)), str(inner / "uv"))  # positive control
        for mode in (0o775, 0o757, 0o777, 0o1777):  # a sticky bit does not excuse a directory of ours
            with self.subTest(outer_mode=oct(mode)):
                os.chmod(outer, mode)
                with self.assertRaisesRegex(config.ConfigError, "directory .* is owned by another user or writable"):
                    self.find("uv", str(inner))
        os.chmod(outer, 0o755)
        self.assertEqual(self.find("uv", str(inner)), str(inner / "uv"))

    def test_ancestors_of_a_symlink_target_are_checked_not_those_of_the_link(self):
        outer = self.d / "outer2"
        target_dir = outer / "t"
        target_dir.mkdir(parents=True)
        os.chmod(outer, 0o755)
        os.chmod(target_dir, 0o755)
        (target_dir / "uv").write_text("#!/bin/sh\n")
        os.chmod(target_dir / "uv", 0o755)
        private_link_dir = self.d / "linkbin"
        private_link_dir.mkdir()
        os.chmod(private_link_dir, 0o755)
        (private_link_dir / "uv").symlink_to(target_dir / "uv")
        self.assertEqual(self.find("uv", str(private_link_dir)), str(target_dir / "uv"))  # control
        os.chmod(outer, 0o775)  # the link's own directory is private, the target's ancestry is not
        with self.assertRaisesRegex(config.ConfigError, "directory .* is owned by another user or writable"):
            self.find("uv", str(private_link_dir))

    def test_the_root_sticky_exception_exists_for_tmp_style_directories(self):
        # This test module runs under a temporary directory below /tmp (root, sticky): every positive
        # control above passes through it. Here the same ancestry is read directly.
        probe = Path(self.tmp.name)
        chain = [probe, *probe.parents]
        world_writable = [c for c in chain if os.stat(c).st_mode & 0o002]
        for directory in world_writable:
            st = os.stat(directory)
            self.assertTrue(st.st_uid == 0 and st.st_mode & 0o1000, f"{directory} is world-writable and not root-sticky")

    def test_missing_or_non_executable_is_not_found(self):
        os.chmod(self.bin / "uv", 0o644)
        with self.assertRaisesRegex(config.ConfigError, "uv not found"):
            self.find("uv", str(self.bin))
        with self.assertRaisesRegex(config.ConfigError, "nosuchtool not found"):
            self.find("nosuchtool", str(self.bin))

    def test_the_first_match_wins_and_later_entries_are_not_consulted(self):
        second = self.make_bin("bin3")
        self.assertEqual(self.find("uv", f"{self.bin}:{second}"), str(self.bin / "uv"))
        os.chmod(self.bin / "uv", 0o775)  # untrusted first match is an error, not a silent fall-through
        with self.assertRaises(config.ConfigError):
            self.find("uv", f"{self.bin}:{second}")


class LaunchResolutionTests(Base):
    """``launch`` with the real executable lookup (the replaced one is switched off)."""

    def setUp(self):
        super().setUp()
        self.patchers["lab_agent.mcp.find_executable"].stop()
        self.bin = self.dir / "bin"
        self.bin.mkdir(mode=0o755)
        os.chmod(self.bin, 0o755)
        for tool in ("git", "uv"):
            (self.bin / tool).write_text("#!/bin/sh\nexit 0\n")
            os.chmod(self.bin / tool, 0o755)
        self.cfg = self.lab()
        self.mark_installed(self.cfg)
        self.fake_git(PIN)

    def test_positive_control_trusted_uv_is_executed_with_a_validated_path(self):
        mcp.os.environ["PATH"] = str(self.bin)
        mcp.launch(self.cfg)
        file, argv, env = self.exec_mock.call_args.args
        self.assertEqual(file, str(self.bin / "uv"))
        self.assertEqual(env["PATH"], str(self.bin))
        self.assertEqual(env["PROXMOX_TOKEN_VALUE"], CANARY)

    def test_the_executed_file_is_the_resolved_target_not_the_symlink(self):
        link_dir = self.dir / "links"
        link_dir.mkdir(mode=0o755)
        os.chmod(link_dir, 0o777)  # writable by others: the link inside could be swapped
        (link_dir / "uv").symlink_to(self.bin / "uv")
        mcp.os.environ["PATH"] = f"{link_dir}:{self.bin}"  # git comes from the private bin, uv from the link
        mcp.launch(self.cfg)
        file = self.exec_mock.call_args.args[0]
        self.assertEqual(file, os.path.realpath(self.bin / "uv"))
        self.assertFalse(os.path.islink(file))

    def test_a_relative_path_entry_never_gets_the_token(self):
        (self.dir / "uv").write_text("#!/bin/sh\n")  # a uv in the caller's directory
        os.chmod(self.dir / "uv", 0o755)
        for value in (f".:{self.bin}", f"{self.bin}:", f"::{self.bin}"):
            with self.subTest(path=value):
                mcp.os.environ["PATH"] = value
                with self.assertRaisesRegex(config.ConfigError, "PATH holds an empty or relative entry"):
                    mcp.launch(self.cfg)
        self.exec_mock.assert_not_called()
        self.chdir_mock.assert_not_called()

    def test_an_executable_in_the_run_directory_never_gets_the_token(self):
        run = self.dir / "state" / "mcp-run"
        run.mkdir(mode=0o700, parents=True)
        (run / "uv").write_text("#!/bin/sh\n")
        os.chmod(run / "uv", 0o755)
        mcp.os.environ["PATH"] = f"{run}:{self.bin}"
        with self.assertRaisesRegex(config.ConfigError, "inside the lab-agent"):
            mcp.launch(self.cfg)
        self.exec_mock.assert_not_called()
        self.chdir_mock.assert_not_called()


class RealGitRegressionTests(unittest.TestCase):
    """Real, local git on throwaway repositories in a temporary directory. No network, no clone:
    the pin check must not be redirected by Git's own environment variables."""

    def setUp(self):
        self.tmp = fixtures.private_tmpdir()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.git = shutil.which("git")
        self.assertIsNotNone(self.git, "git is required for this regression test")
        self.env = {"PATH": os.environ["PATH"], "HOME": str(self.d), "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
        self.head_a = self.repo(self.d / "mcp" / "a", 1)
        self.head_b = self.repo(self.d / "other", 2)
        self.assertNotEqual(self.head_a, self.head_b)
        self.a, self.b = self.d / "mcp" / "a", self.d / "other"

    def sh(self, *args, cwd=None):
        out = subprocess.run([self.git, *args], cwd=cwd, env=self.env, check=True, capture_output=True, text=True)
        return out.stdout.strip()

    def repo(self, path, commits):
        path.mkdir(parents=True)
        self.sh("init", "-q", cwd=path)
        for i in range(commits):
            self.sh("commit", "--allow-empty", "-q", "-m", f"c{i}", cwd=path)
        return self.sh("rev-parse", "HEAD", cwd=path)

    def hostile(self, **extra):
        return {"PATH": os.environ["PATH"], **extra}

    def test_the_premise_git_environment_redirects_an_unsanitized_call(self):
        env = {**self.env, "GIT_DIR": str(self.b / ".git")}
        naive = subprocess.run([self.git, "-C", str(self.a), "rev-parse", "HEAD"], env=env, capture_output=True,
                               text=True).stdout.strip()
        self.assertEqual(naive, self.head_b)  # the control: the attack works against a plain call

    def test_installed_commit_reports_the_checkout_not_the_redirected_repository(self):
        self.assertEqual(mcp.installed_commit(self.a, self.hostile()), self.head_a)  # positive control
        for label, extra in (("GIT_DIR", {"GIT_DIR": str(self.b / ".git")}),
                             ("GIT_DIR+GIT_WORK_TREE", {"GIT_DIR": str(self.b / ".git"), "GIT_WORK_TREE": str(self.a)}),
                             ("GIT_COMMON_DIR", {"GIT_COMMON_DIR": str(self.b / ".git")}),
                             ("GIT_OBJECT_DIRECTORY", {"GIT_OBJECT_DIRECTORY": str(self.b / ".git" / "objects")})):
            with self.subTest(variable=label):
                got = mcp.installed_commit(self.a, self.hostile(**extra))
                self.assertEqual(got, self.head_a)
                self.assertNotEqual(got, self.head_b)

    def test_a_gitfile_pointing_at_another_repository_is_not_a_checkout(self):
        c = self.d / "mcp" / "c"
        c.mkdir()
        (c / ".git").write_text(f"gitdir: {self.b / '.git'}\n")
        naive = subprocess.run([self.git, "-C", str(c), "rev-parse", "HEAD"], env=self.env, capture_output=True,
                               text=True).stdout.strip()
        self.assertEqual(naive, self.head_b)  # control: plain git follows the redirect
        self.assertIsNone(mcp.installed_commit(c, self.hostile()))

    def test_a_relative_path_entry_is_refused_by_the_pin_check_itself(self):
        with self.assertRaisesRegex(config.ConfigError, "PATH holds an empty or relative entry"):
            mcp.installed_commit(self.a, {"PATH": f".:{os.environ['PATH']}"})

    def test_launch_refuses_when_git_variables_make_another_repository_look_like_the_pin(self):
        lab = self.d / "lab"
        lab.mkdir(mode=0o700)
        cfg = fixtures.make_lab(lab)
        bin_dir = self.d / "bin"
        bin_dir.mkdir(mode=0o755)
        os.chmod(bin_dir, 0o755)
        (bin_dir / "uv").write_text("#!/bin/sh\nexit 0\n")
        os.chmod(bin_dir / "uv", 0o755)
        path = f"{bin_dir}:{os.path.dirname(self.git)}"
        with mock.patch.dict(mcp.PIN, {"commit": self.head_b}):
            installed = mcp.install_dir(cfg)
            installed.parent.mkdir(parents=True)
            os.chmod(installed.parent, 0o700)
            shutil.copytree(self.a, installed)  # a different repository than the one named by the pin
            self.assertEqual(self.sh("rev-parse", "HEAD", cwd=installed), self.head_a)
            with mock.patch.dict(os.environ, {"PATH": path, "GIT_DIR": str(self.b / ".git")}), \
                    mock.patch("lab_agent.mcp.os.execve") as execve, mock.patch("lab_agent.mcp.os.fchdir"):
                with self.assertRaisesRegex(config.ConfigError, "not installed"):
                    mcp.launch(cfg)
                execve.assert_not_called()
        # Positive control: the same layout is accepted when the checkout really is at the pin.
        with mock.patch.dict(mcp.PIN, {"commit": self.head_a}):
            moved = mcp.install_dir(cfg)
            moved.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(moved.parent, 0o700)
            shutil.copytree(self.a, moved)
            with mock.patch.dict(os.environ, {"PATH": path}), \
                    mock.patch("lab_agent.mcp.os.execve") as execve, mock.patch("lab_agent.mcp.os.fchdir"):
                mcp.launch(cfg)
                self.assertEqual(execve.call_args.args[0], str(bin_dir / "uv"))


class ExampleEntryTests(unittest.TestCase):
    """``mcp.example.json``: the publication-safe example of the project MCP entry."""

    EXAMPLE = REPO / "lab-agent" / "mcp.example.json"

    def test_example_has_the_structure_of_the_project_entry_and_no_value(self):
        data = json.loads(self.EXAMPLE.read_text())
        self.assertEqual(list(data), ["mcpServers"])
        self.assertEqual(list(data["mcpServers"]), ["pve"])
        server = data["mcpServers"]["pve"]
        self.assertEqual(set(server), {"command", "args"})  # no env block
        self.assertEqual(server["command"], "sh")
        self.assertEqual(server["args"], ["-c", 'exec "$CLAUDE_PROJECT_DIR/lab-agent/bin/mcp-launch"'])
        self.assertTrue((REPO / "lab-agent" / "bin" / "mcp-launch").is_file())
        self.assertNotRegex(self.EXAMPLE.read_text(), r"(?i)token|secret|password|PROXMOX_|/home/|@")

    def test_the_example_equals_the_local_entry_when_there_is_one(self):
        local = REPO / ".mcp.json"
        expected = json.loads(local.read_text()) if local.is_file() else json.loads(self.EXAMPLE.read_text())
        self.assertEqual(json.loads(self.EXAMPLE.read_text()), expected)


class PinReviewFixtureTests(unittest.TestCase):
    """The pin review as a regression fixture. It does not replace re-reading the upstream
    source when the pin moves (docs/mcp-server-review.md)."""

    def test_snapshot_shape(self):
        self.assertEqual(len(UPSTREAM_TOOLS), 141)
        self.assertEqual(len(set(UPSTREAM_TOOLS)), 141)

    def test_deny_list_is_39_distinct_names_that_all_exist_upstream(self):
        self.assertEqual(len(DENIED), 39)
        self.assertEqual(len(set(DENIED)), 39)
        self.assertEqual(sorted(set(DENIED) - set(UPSTREAM_TOOLS)), [])  # a typo would make a rule a no-op

    def test_no_denied_name_is_a_prefix_trap(self):
        # The deny entries are exact names: none ends in a wildcard and none contains a dot or a slash.
        for name in DENIED:
            self.assertRegex(name, r"^[a-z][a-z0-9_]*$")

    def test_what_stays_allowed_is_what_the_review_says(self):
        allowed = [n for n in UPSTREAM_TOOLS if n not in DENIED]
        self.assertEqual(len(allowed), 102)
        self.assertEqual(sorted(n for n in allowed if n.startswith("vm_agent")),
                         ["vm_agent_exec", "vm_agent_exec_status", "vm_agent_get_fsinfo",
                          "vm_agent_get_network_interfaces", "vm_agent_get_osinfo", "vm_agent_ping"])
        for must_stay_allowed in ("clone_vm", "set_vm_config", "create_vm_snapshot", "backup_vm", "delete_vm"):
            self.assertIn(must_stay_allowed, allowed)
        # No generic escape hatch that takes a raw API path is advertised.
        self.assertFalse([n for n in allowed if re.search(r"(^|_)(raw|request|api_call|proxy_call)(_|$)", n)])

    def test_the_snapshots_belong_to_the_pinned_commit(self):
        # Fails when the pin moves until the snapshots are re-read at the new commit.
        self.assertEqual(REVIEWED_COMMIT, mcp.PIN["commit"],
                         "the pin moved: re-read the upstream tool names at the new commit, then update "
                         "UPSTREAM_TOOLS, DENIED, REVIEWED_COMMIT and the review document together")
        self.assertRegex(REVIEWED_COMMIT, r"^[0-9a-f]{40}$")

    def test_pin_metadata_is_consistent(self):
        self.assertEqual(mcp.PIN["license"], "MIT")
        self.assertEqual(mcp.PIN["version"], "2.14.0")
        text = (REPO / "lab-agent" / "docs" / "mcp-server-review.md").read_text()
        self.assertIn(REVIEWED_COMMIT, text)


class SetOneFragmentTests(unittest.TestCase):
    """The proposed SET-1 settings fragment (an isolated proposal, never installed)."""

    DIR = REPO / "lab-agent" / "proposed" / "settings"
    PREFIX = "mcp__pve__"
    # The upstream server's own read/write classification (registry.is_read_only at the pin).
    READS = {"vm_agent_exec_status", "wait_for_task"}
    WRITES = {"get_vm_vnc_proxy", "get_vm_spice_proxy"}

    @classmethod
    def read_only(cls, name):
        if name in cls.READS:
            return True
        if name in cls.WRITES:
            return False
        return name.startswith(("get_", "list_", "vm_agent_get_"))

    def fragment(self):
        return json.loads((self.DIR / "set1-option-c.fragment.json").read_text())

    def test_the_fragment_is_checked_against_the_snapshot_of_the_pinned_commit(self):
        self.assertEqual(REVIEWED_COMMIT, mcp.PIN["commit"])
        self.assertIn(REVIEWED_COMMIT, (self.DIR / "README.md").read_text())

    def test_shape_and_the_two_removed_keys(self):
        frag = self.fragment()
        self.assertEqual(set(frag), {"permissions", "enabledMcpjsonServers"})
        self.assertEqual(set(frag["permissions"]), {"allow"})
        self.assertEqual(frag["enabledMcpjsonServers"], ["pve"])
        text = json.dumps(frag)
        self.assertNotIn("mcp__pve__*", text)
        self.assertNotIn("enableAllProjectMcpServers", text)
        self.assertNotIn("hooks", text)
        self.assertNotIn("deny", text)

    def test_every_allowed_name_is_a_reviewed_read_only_tool_and_none_is_denied(self):
        allow = self.fragment()["permissions"]["allow"]
        self.assertEqual(len(allow), len(set(allow)))
        names = []
        for entry in allow:
            self.assertTrue(entry.startswith(self.PREFIX), entry)
            names.append(entry[len(self.PREFIX):])
        self.assertEqual(sorted(set(names) - set(UPSTREAM_TOOLS)), [])
        self.assertEqual(sorted(set(names) & set(DENIED)), [])
        self.assertEqual([n for n in names if not self.read_only(n)], [])

    def test_it_is_complete_the_other_non_denied_tools_keep_prompting(self):
        names = {e[len(self.PREFIX):] for e in self.fragment()["permissions"]["allow"]}
        readers = {n for n in UPSTREAM_TOOLS if n not in DENIED and self.read_only(n)}
        self.assertEqual(names, readers)
        self.assertEqual(len(names), 69)
        prompting = [n for n in UPSTREAM_TOOLS if n not in DENIED and n not in names]
        self.assertEqual(len(prompting), 33)
        for write in ("clone_vm", "set_vm_config", "delete_vm", "vm_agent_exec", "vm_agent_ping",
                      "get_vm_vnc_proxy", "get_vm_spice_proxy", "backup_vm", "restore_vm_backup"):
            self.assertIn(write, prompting)

    def test_the_proposal_directory_holds_only_proposal_files_and_says_so(self):
        self.assertEqual(sorted(p.name for p in self.DIR.iterdir()), ["README.md", "set1-option-c.fragment.json"])
        readme = (self.DIR / "README.md").read_text()
        self.assertIn("proposal", readme.lower())
        self.assertIn("not installed", readme.lower())

    def test_no_real_value_in_the_proposal_files(self):
        for p in self.DIR.iterdir():
            text = p.read_text()
            self.assertNotRegex(text, r"/home/|/Users/|@gmail")


if __name__ == "__main__":
    unittest.main()
