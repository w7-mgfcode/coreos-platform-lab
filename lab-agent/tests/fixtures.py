"""Synthetic Proxmox data for offline tests. Addresses come from documentation ranges
(192.0.2.0/24, RFC 5737) and names are invented; nothing here describes a real lab."""

from __future__ import annotations

import copy
import os
import stat
import tempfile
from pathlib import Path

NODE = "pve-test"
POOL = "corelab"
AGENT_USER = "corelab-agent@pve"
TOKEN_ID = "corelab-agent@pve!lab"
SENTINEL = 9050

RESOURCES = [
    {"id": "qemu/105", "type": "qemu", "vmid": 105, "node": NODE, "name": "old-k8s-node", "status": "stopped",
     "template": 0},
    {"id": "qemu/106", "type": "qemu", "vmid": 106, "node": NODE, "name": "old-web", "status": "running",
     "template": 0},
    {"id": "qemu/9050", "type": "qemu", "vmid": 9050, "node": NODE, "name": "corelab-sentinel",
     "status": "stopped", "template": 0},
    {"id": "qemu/9100", "type": "qemu", "vmid": 9100, "node": NODE, "name": "corelab-fcos-template",
     "status": "stopped", "template": 1, "pool": POOL},
    {"id": "qemu/9101", "type": "qemu", "vmid": 9101, "node": NODE, "name": "demo-1", "status": "running",
     "template": 0, "pool": POOL},
    {"id": "lxc/120", "type": "lxc", "vmid": 120, "node": NODE, "name": "old-ct", "status": "stopped", "template": 0},
    {"id": "storage/pve-test/local", "type": "storage", "storage": "local", "node": NODE},
]

CONFIGS = {
    105: {"name": "old-k8s-node", "digest": "a" * 40, "scsi0": "local-lvm:vm-105-disk-0,size=32G"},
    106: {"name": "old-web", "digest": "b" * 40, "scsi0": "local-lvm:vm-106-disk-0,size=16G",
          "ide2": "local:iso/old.iso,media=cdrom"},
    9050: {"name": "corelab-sentinel", "digest": "c" * 40, "scsi0": "local-lvm:vm-9050-disk-0,size=1G"},
    9100: {"name": "corelab-fcos-template", "digest": "d" * 40, "scsi0": "local-lvm:base-9100-disk-0,size=10G",
           "ide2": "local-lvm:vm-9100-cloudinit,media=cdrom"},
    9101: {"name": "demo-1", "digest": "e" * 40, "scsi0": "local-lvm:vm-9101-disk-0,size=10G"},
}
LXC_CONFIGS = {120: {"hostname": "old-ct", "digest": "f" * 40, "rootfs": "local-lvm:vm-120-disk-0,size=8G"}}

STORAGES = [
    {"storage": "local", "type": "dir", "content": "iso,vztmpl,backup", "path": "/var/lib/vz"},
    {"storage": "local-lvm", "type": "lvmthin", "content": "images,rootdir"},
    {"storage": "corelab", "type": "dir", "content": "snippets,import,iso,backup", "path": "/srv/corelab"},
]
NODE_STORAGES = [{"storage": s["storage"], "active": 1} for s in STORAGES]

CONTENT = {
    "local": [
        {"volid": "local:backup/vzdump-qemu-105-2025_01_01-00_00_00.vma.zst", "content": "backup", "size": 1000,
         "vmid": 105},
        {"volid": "local:backup/vzdump-qemu-9150-2025_02_01-00_00_00.vma.zst", "content": "backup", "size": 2000,
         "vmid": 9150},
        {"volid": "local:iso/old.iso", "content": "iso", "size": 4096},
    ],
    "local-lvm": [
        {"volid": "local-lvm:vm-105-disk-0", "content": "images", "size": 34359738368, "vmid": 105},
        {"volid": "local-lvm:vm-9101-disk-0", "content": "images", "size": 10737418240, "vmid": 9101},
    ],
    "corelab": [{"volid": "corelab:iso/corelab-dummy.iso", "content": "iso", "size": 1048576}],
}

NETWORK = [
    {"iface": "eno1", "type": "eth", "active": 1},
    {"iface": "vmbr0", "type": "bridge", "cidr": "192.0.2.10/24", "gateway": "192.0.2.1",
     "bridge_ports": "eno1", "active": 1},
    {"iface": "vmbr9", "type": "bridge", "active": 1},
]
DISKS = [{"devpath": "/dev/sda", "used": "LVM", "size": 500107862016, "serial": "TESTSERIAL1", "model": "TESTDISK"},
         {"devpath": "/dev/sdb", "used": "", "size": 1000204886016, "serial": "TESTSERIAL2", "model": "TESTDISK"}]
USERS = [{"userid": "root@pam"}, {"userid": AGENT_USER}, {"userid": "olduser@pve"}]
TOKENS = {AGENT_USER: [{"tokenid": "lab", "privsep": 1, "expire": 1900000000}], "olduser@pve": [], "root@pam": []}
ACL = [{"path": "/", "type": "user", "ugid": AGENT_USER, "roleid": "PVEAuditor"},
       {"path": "/pool/corelab", "type": "token", "ugid": TOKEN_ID, "roleid": "PVEVMAdmin"}]
CERTS = [{"filename": "pve-ssl.pem", "subject": "/CN=pve-test.example.invalid",
          "san": ["pve-test", "192.0.2.10"], "notafter": 1900000000, "fingerprint": "AA:BB"}]


def api_routes() -> dict[tuple[str, str], tuple[int, object]]:
    routes: dict[tuple[str, str], tuple[int, object]] = {
        ("GET", "/version"): (200, {"version": "9.1.1", "release": "9.1"}),
        ("GET", "/cluster/status"): (200, [{"type": "node", "name": NODE}]),
        ("GET", "/cluster/resources"): (200, copy.deepcopy(RESOURCES)),
        ("GET", "/storage"): (200, copy.deepcopy(STORAGES)),
        ("GET", "/pools"): (200, [{"poolid": POOL}]),
        ("GET", "/access/users"): (200, copy.deepcopy(USERS)),
        ("GET", "/access/acl"): (200, copy.deepcopy(ACL)),
        ("GET", "/access/roles"): (200, [{"roleid": "PVEAuditor"}]),
        ("GET", "/cluster/backup"): (200, []),
        ("GET", f"/nodes/{NODE}/network"): (200, copy.deepcopy(NETWORK)),
        ("GET", f"/nodes/{NODE}/storage"): (200, copy.deepcopy(NODE_STORAGES)),
        ("GET", f"/nodes/{NODE}/disks/list"): (200, copy.deepcopy(DISKS)),
        ("GET", f"/nodes/{NODE}/certificates/info"): (200, copy.deepcopy(CERTS)),
        ("GET", "/cluster/firewall/options"): (403, "Permission check failed (/, Sys.Audit)"),
        ("GET", f"/nodes/{NODE}/firewall/options"): (200, {"enable": 1}),
    }
    for vmid, cfg in CONFIGS.items():
        routes[("GET", f"/nodes/{NODE}/qemu/{vmid}/config")] = (200, dict(cfg))
    for vmid, cfg in LXC_CONFIGS.items():
        routes[("GET", f"/nodes/{NODE}/lxc/{vmid}/config")] = (200, dict(cfg))
    for st, items in CONTENT.items():
        routes[("GET", f"/nodes/{NODE}/storage/{st}/content")] = (200, copy.deepcopy(items))
    for user, toks in TOKENS.items():
        routes[("GET", f"/access/users/{user}/token")] = (200, copy.deepcopy(toks))
    return routes


def env_text(tmp: Path, **overrides: str) -> str:
    values = {
        "PVE_HOST": "192.0.2.10", "PVE_NODE": NODE, "PVE_CA_FILE": str(tmp / "ca.pem"),
        "PVE_TOKEN_ID": TOKEN_ID, "PVE_TOKEN_FILE": str(tmp / "token"),
        "PVE_ROOT_KEY": str(tmp / "root_key"), "PVE_SNIP_KEY": str(tmp / "snip_key"),
        "PVE_KNOWN_HOSTS": str(tmp / "known_hosts"), "PVE_LAB_STATE": str(tmp / "state"),
        "PVE_VM_STORAGE": "local-lvm", "PVE_LAB_STORAGE_PATH": "/srv/corelab", "PVE_BRIDGE": "vmbr0",
        "PVE_VMID_RANGE": "9100-9199", "PVE_SENTINEL_VMID": str(SENTINEL),
        "PVE_SENTINEL_BACKUP_STORAGE": "local", "PVE_TEMPLATE_VMID": "9100",
        "PVE_WORKSTATION_ADDR": "192.0.2.50",
        "FCOS_IMAGE_URL": "https://builds.example.invalid/fcos.qcow2.xz", "FCOS_IMAGE_SHA256": "0" * 64,
    }
    values.update(overrides)
    return "".join(f"{k}={v}\n" for k, v in values.items())


def make_lab(tmp: Path, **overrides: str):
    """A temp directory with a private env file, token file and CA placeholder."""
    from lab_agent.config import load
    env = tmp / "env"
    env.write_text(env_text(tmp, **overrides))
    os.chmod(env, 0o600)
    token = tmp / "token"
    token.write_text("00000000-test-only-not-a-secret\n")
    os.chmod(token, 0o600)
    (tmp / "ca.pem").write_text("placeholder\n")
    (tmp / "known_hosts").write_text("placeholder\n")
    return load(env)


def private_tmpdir() -> tempfile.TemporaryDirectory:
    d = tempfile.TemporaryDirectory(prefix="corelab-test-")
    os.chmod(d.name, stat.S_IRWXU)
    return d


_DISK_KEY = __import__("re").compile(r"^(?:(?:scsi|virtio|ide|sata|efidisk|tpmstate|unused|mp)\d*|rootfs)$")


def content_listing_for(content, configs):
    """A copy of ``content`` in which every volume the guest configs name is listed, as a real host's
    storage listings show them (a config naming a volume the host does not list is a dangling entry).
    Files under iso/vztmpl/snippets/import/backup paths are left alone."""
    import copy
    import re
    out = copy.deepcopy(content)
    for cfg in configs:
        for key, value in cfg.items():
            if not _DISK_KEY.match(key) or not isinstance(value, str):
                continue
            item = re.sub(r"^file=", "", value.split(",", 1)[0])
            storage = item.split(":", 1)[0]
            if ":" not in item or re.match(r"^[^:]+:(?:iso|vztmpl|snippets|import|backup)/", item):
                continue
            if not any(v["volid"] == item for v in out.get(storage, [])):
                owner = re.search(r"-(\d+)-", item.split(":", 1)[1])
                out.setdefault(storage, []).append({"volid": item, "content": "images", "size": 1,
                                                    **({"vmid": int(owner.group(1))} if owner else {})})
    return out


# --------------------------------------------------------------------------- destructive execution is disabled
#
# The shipped ``host/lib.sh`` refuses every destructive command (``cl_destructive_gate``, exit 7), every
# rendered manifest script calls that gate as its first command, and the destructive commands themselves
# are not in the shipped text: each is a ``# DISABLED-COMMAND:`` comment. The guards around them are still
# exercised offline, against the stub tools only, through a TEST-ONLY copy of the script text in which
# the gate is a no-op and those comment lines are commands again, made immediately before the copy is
# handed to bash. Nothing outside ``tests/`` may use this helper, the shipped text is never modified,
# and a pass obtained through it says nothing about the safety of real execution.

GATE_NEUTRALIZED = "cl_destructive_gate() { :; }  # TEST-ONLY COPY: gate neutralized for stub-tool tests"
DISABLED_COMMAND = "# DISABLED-COMMAND: "
DISABLED_COMMANDS_PER_LIBRARY = 4  # stop-mode backup, stop, destroy, free


def for_stub_run(script: str) -> str:
    """TEST-ONLY: ``script`` (the host library plus a command, or a rendered script) with every
    refusing definition of the gate replaced by a no-op and every ``# DISABLED-COMMAND:`` line turned
    back into its command. Refuses a script without a definition, a definition that is neither the
    shipped refusing one nor this no-op, and a library copy that does not carry exactly the four
    disabled commands, so a change to the shipped text cannot go unnoticed here."""
    lines = script.split("\n")
    hits = [n for n, line in enumerate(lines) if line.startswith("cl_destructive_gate()")]
    if not hits:
        raise AssertionError("the script defines no cl_destructive_gate: it is not the host library")
    shipped = 0
    for n in hits:
        if lines[n] == GATE_NEUTRALIZED:
            continue
        if not lines[n].startswith('cl_destructive_gate() { cl_die 7 "destructive execution is disabled'):
            raise AssertionError(f"unexpected definition of cl_destructive_gate: {lines[n][:80]!r}")
        lines[n] = GATE_NEUTRALIZED
        shipped += 1
    disabled = [n for n, line in enumerate(lines) if line.lstrip().startswith(DISABLED_COMMAND)]
    if len(disabled) != DISABLED_COMMANDS_PER_LIBRARY * shipped:
        raise AssertionError(f"expected {DISABLED_COMMANDS_PER_LIBRARY} disabled commands per shipped library copy, "
                             f"found {len(disabled)} for {shipped}")
    for n in disabled:
        indent = lines[n][: len(lines[n]) - len(lines[n].lstrip())]
        lines[n] = indent + lines[n].lstrip()[len(DISABLED_COMMAND):]
    return "\n".join(lines)
