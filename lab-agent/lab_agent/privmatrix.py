"""Operation -> privilege matrix from the Proxmox API description (acceptance check O-7).

Reads an ``apidoc.js`` file (JavaScript that assigns a JSON tree to ``apiSchema``) WITHOUT
executing it: the JSON value after the assignment is decoded with the standard JSON decoder
and everything else in the file is ignored. For each planned operation it resolves the
permission check (``perm``, ``and``, ``or``, ``perm-modify``, ``userid-group``,
``userid-param``, plus the ``user``, ``description`` and ``allowtoken`` fields), evaluates it
against the ACL design of the plan (embedded below, replaceable with ``--plan FILE``) and
reports, per operation and profile, the privilege required, the role that grants it, the path
it is granted on and whether the result matches the plan. Offline only: it opens one local
file, makes no connection and touches no lab.

Rules the generator keeps:

* An unknown or unparsable permission form, a missing ``permissions`` key, an unbound path
  parameter, or a description-only (free text) rule is never treated as allowed. It is reported
  as UNKNOWN or TEXT-ONLY and makes the result INCOMPLETE.
* Role contents are NOT in the documentation text (plan R-20). The role table below is an
  ASSUMPTION of this tool; the matrix is only as good as it. ``pveum role list`` on the lab
  must confirm it (live check, not run).
* The ``description`` text can name requirements the machine check does not contain; those are
  extracted by pattern and reported, and the operation is then TEXT-ONLY, not ALLOW.

Run:  python3 -m lab_agent.privmatrix --apidoc FILE [--plan FILE] [--sweep] [--format json]
Exit: 0 every planned operation matches from structured schema data; 1 at least one
mismatch (narrower, broader, plan drift, missing operation); 2 no mismatch but incomplete;
3 input error.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

ALLOW, DENY, COND, UNKNOWN, TEXT, MISSING = "ALLOW", "DENY", "CONDITIONAL", "UNKNOWN", "TEXT-ONLY", "MISSING"
MISMATCH_VERDICTS = ("NARROWER", "BROADER", "PLAN-DRIFT", "MISSING-OP")
INCOMPLETE_VERDICTS = ("INCOMPLETE", "LIVE-ONLY")
PRIV_RE = re.compile(r"\b[A-Z][A-Za-z]+(?:\.[A-Z][A-Za-z]+)+\b")
PARAM_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_-]*)\}")
EXPECTATIONS = {  # category -> {profile: expectation}
    "read": {"routine": "allow", "read-only": "allow"},
    "routine": {"routine": "allow", "read-only": "deny"},
    "denied": {"routine": "deny", "read-only": "deny"},
    "self": {"routine": "conditional", "read-only": "conditional"},
}
EXPECT_VALUES = ("allow", "deny", "conditional", "live-only")


class InputError(Exception):
    """The apidoc file or the plan file cannot be used."""


# ---------------------------------------------------------------------------------------
# The plan's RBAC design (proxmox-admin-agent-plan.md r2: section 5 categories, 6.1 ACLs,
# 2.1 privilege rows R-nn, 9.3 and 9.4 test rows P/N). Logical names only, no lab values:
# NODE, LAB_STORAGE, VM_STORAGE, BRIDGE stand for the plan's variables.
# ---------------------------------------------------------------------------------------
def _req(priv: str, path: str) -> dict:
    return {"priv": priv, "path": path}


_V = "/vms/"
DEFAULT_PLAN: dict = {
    "plan_ref": "proxmox-admin-agent-plan r2: s5, s6.1, s2.1 (R-nn), s9.3 (P), s9.4 (N)",
    "roles": {
        "_source": "ASSUMED by this tool: role contents are not in the documentation text (plan R-20); "
                   "confirm with `pveum role list` on the lab (live check, not run)",
        "PVEAuditor": ["Datastore.Audit", "Mapping.Audit", "Pool.Audit", "SDN.Audit", "Sys.Audit",
                       "VM.Audit", "VM.GuestAgent.Audit"],
        "PVEVMAdmin": ["Datastore.AllocateSpace", "Datastore.Audit", "Pool.Audit", "SDN.Use",
                       "VM.Allocate", "VM.Audit", "VM.Backup", "VM.Clone", "VM.Config.CDROM",
                       "VM.Config.CPU", "VM.Config.Cloudinit", "VM.Config.Disk", "VM.Config.HWType",
                       "VM.Config.Memory", "VM.Config.Network", "VM.Config.Options", "VM.Console",
                       "VM.Migrate", "VM.PowerMgmt", "VM.Snapshot", "VM.Snapshot.Rollback",
                       "VM.GuestAgent.Audit", "VM.GuestAgent.FileSystemMgmt",
                       "VM.GuestAgent.Unrestricted"],
        "PVEDatastoreUser": ["Datastore.AllocateSpace", "Datastore.Audit"],
        "PVESDNUser": ["SDN.Audit", "SDN.Use"],
    },
    "profiles": {
        "routine": [
            {"path": "/", "role": "PVEAuditor"},
            {"path": "/pool/corelab", "role": "PVEVMAdmin"},
            {"path": "/storage/LAB_STORAGE", "role": "PVEDatastoreUser"},
            {"path": "/storage/VM_STORAGE", "role": "PVEDatastoreUser"},
            {"path": "/sdn/zones/localnetwork/BRIDGE", "role": "PVESDNUser"},
        ],
        "read-only": [{"path": "/", "role": "PVEAuditor"}],
    },
    "pools": {"corelab": ["TEMPLATE", "POOLVM"]},
    "contexts": {  # used by --sweep: one object of the lab scope, one foreign object
        "in-scope": {"bind": {"node": "NODE", "vmid": "POOLVM", "newid": "NEWID", "pool": "corelab",
                              "poolid": "corelab", "storage": "LAB_STORAGE"}},
        "foreign": {"bind": {"node": "NODE", "vmid": "SENTINEL", "newid": "FOREIGNNEW",
                             "pool": "otherpool", "poolid": "otherpool", "storage": "OTHER_STORAGE"}},
    },
    "operations": [
        {"id": "RD1", "name": "list all resources", "method": "GET", "path": "/cluster/resources",
         "category": "read", "bind": {}, "ref": "P9"},
        {"id": "RD2", "name": "read a foreign guest config", "method": "GET",
         "path": "/nodes/{node}/qemu/{vmid}/config", "category": "read",
         "bind": {"node": "NODE", "vmid": "SENTINEL"}, "any_of": [[_req("VM.Audit", _V + "SENTINEL")]],
         "ref": "s5 Read"},
        {"id": "RD3", "name": "guest status", "method": "GET", "path": "/nodes/{node}/qemu/{vmid}/status/current",
         "category": "read", "bind": {"node": "NODE", "vmid": "POOLVM"},
         "any_of": [[_req("VM.Audit", _V + "POOLVM")]], "ref": "s5 Read"},
        {"id": "RD4", "name": "storage content listing", "method": "GET",
         "path": "/nodes/{node}/storage/{storage}/content", "category": "read",
         "bind": {"node": "NODE", "storage": "LAB_STORAGE"},
         "any_of": [[_req("Datastore.Audit", "/storage/LAB_STORAGE")]], "ref": "R-12"},
        {"id": "P1", "name": "clone the pool template into the pool", "method": "POST",
         "path": "/nodes/{node}/qemu/{vmid}/clone", "category": "routine", "params": ["pool"],
         "bind": {"node": "NODE", "vmid": "TEMPLATE", "newid": "NEWID", "pool": "corelab"},
         "any_of": [[_req("VM.Clone", _V + "TEMPLATE"), _req("VM.Allocate", "/pool/corelab"),
                     _req("Datastore.AllocateSpace", "/storage/VM_STORAGE"),
                     _req("SDN.Use", "/sdn/zones/localnetwork/BRIDGE")],
                    [_req("VM.Clone", _V + "TEMPLATE"), _req("VM.Allocate", _V + "NEWID"),
                     _req("Datastore.AllocateSpace", "/storage/VM_STORAGE"),
                     _req("SDN.Use", "/sdn/zones/localnetwork/BRIDGE")]], "ref": "R-03"},
        {"id": "P2", "name": "change guest memory and CPU", "method": "PUT",
         "path": "/nodes/{node}/qemu/{vmid}/config", "category": "routine",
         "bind": {"node": "NODE", "vmid": "POOLVM"},
         "any_of": [[_req("VM.Config.Memory", _V + "POOLVM")]], "ref": "R-04"},
        {"id": "P3a", "name": "start a pool guest", "method": "POST",
         "path": "/nodes/{node}/qemu/{vmid}/status/start", "category": "routine",
         "bind": {"node": "NODE", "vmid": "POOLVM"}, "any_of": [[_req("VM.PowerMgmt", _V + "POOLVM")]],
         "ref": "R-06"},
        {"id": "P3b", "name": "shut down a pool guest", "method": "POST",
         "path": "/nodes/{node}/qemu/{vmid}/status/shutdown", "category": "routine",
         "bind": {"node": "NODE", "vmid": "POOLVM"}, "any_of": [[_req("VM.PowerMgmt", _V + "POOLVM")]],
         "ref": "R-06"},
        {"id": "P3c", "name": "stop a pool guest", "method": "POST",
         "path": "/nodes/{node}/qemu/{vmid}/status/stop", "category": "routine",
         "bind": {"node": "NODE", "vmid": "POOLVM"}, "any_of": [[_req("VM.PowerMgmt", _V + "POOLVM")]],
         "ref": "R-06"},
        {"id": "P4a", "name": "create a snapshot", "method": "POST",
         "path": "/nodes/{node}/qemu/{vmid}/snapshot", "category": "routine",
         "bind": {"node": "NODE", "vmid": "POOLVM"}, "any_of": [[_req("VM.Snapshot", _V + "POOLVM")]],
         "ref": "R-07"},
        {"id": "P4b", "name": "roll back a snapshot", "method": "POST",
         "path": "/nodes/{node}/qemu/{vmid}/snapshot/{snapname}/rollback", "category": "routine",
         "bind": {"node": "NODE", "vmid": "POOLVM", "snapname": "snap1"},
         "any_of": [[_req("VM.Snapshot.Rollback", _V + "POOLVM")], [_req("VM.Snapshot", _V + "POOLVM")]],
         "ref": "R-07: rollback needs VM.Snapshot or VM.Snapshot.Rollback"},
        {"id": "P4c", "name": "delete a snapshot", "method": "DELETE",
         "path": "/nodes/{node}/qemu/{vmid}/snapshot/{snapname}", "category": "routine",
         "bind": {"node": "NODE", "vmid": "POOLVM", "snapname": "snap1"},
         "any_of": [[_req("VM.Snapshot", _V + "POOLVM")]], "ref": "R-07"},
        {"id": "P5", "name": "vzdump a pool guest to the lab storage", "method": "POST",
         "path": "/nodes/{node}/vzdump", "category": "routine", "bind": {"node": "NODE"},
         "any_of": [[_req("VM.Backup", _V + "POOLVM"), _req("Datastore.AllocateSpace", "/storage/LAB_STORAGE")]],
         "ref": "R-08"},
        {"id": "P6", "name": "restore a backup to a new VMID in the pool", "method": "POST",
         "path": "/nodes/{node}/qemu", "category": "routine", "params": ["pool"],
         "bind": {"node": "NODE", "vmid": "NEWID", "pool": "corelab"},
         "any_of": [[_req("VM.Allocate", "/pool/corelab"), _req("Datastore.AllocateSpace", "/storage/VM_STORAGE"),
                     _req("SDN.Use", "/sdn/zones/localnetwork/BRIDGE")],
                    [_req("VM.Allocate", _V + "NEWID"), _req("Datastore.AllocateSpace", "/storage/VM_STORAGE"),
                     _req("SDN.Use", "/sdn/zones/localnetwork/BRIDGE")]], "ref": "R-09"},
        {"id": "P7", "name": "delete the pool guest's backup volume", "method": "DELETE",
         "path": "/nodes/{node}/storage/{storage}/content/{volume}", "category": "routine",
         "bind": {"node": "NODE", "storage": "LAB_STORAGE", "volume": "backup1"},
         "any_of": [[_req("Datastore.AllocateSpace", "/storage/LAB_STORAGE"), _req("VM.Backup", _V + "POOLVM")],
                    [_req("Datastore.Allocate", "/storage/LAB_STORAGE")]], "ref": "R-10"},
        {"id": "P8", "name": "delete a pool guest", "method": "DELETE", "path": "/nodes/{node}/qemu/{vmid}",
         "category": "routine", "bind": {"node": "NODE", "vmid": "POOLVM"},
         "any_of": [[_req("VM.Allocate", _V + "POOLVM")]], "ref": "R-13"},
        {"id": "T1", "name": "create a token for the own user", "method": "POST",
         "path": "/access/users/{userid}/token/{tokenid}", "category": "self",
         "bind": {"userid": "OWNUSER", "tokenid": "t1"}, "ref": "R-16"},
        {"id": "N1", "name": "set the sentinel's description", "method": "PUT",
         "path": "/nodes/{node}/qemu/{vmid}/config", "category": "denied",
         "bind": {"node": "NODE", "vmid": "SENTINEL"}, "any_of": [[_req("VM.Config.Options", _V + "SENTINEL")]],
         "ref": "N1"},
        {"id": "N2", "name": "start the sentinel", "method": "POST",
         "path": "/nodes/{node}/qemu/{vmid}/status/start", "category": "denied",
         "bind": {"node": "NODE", "vmid": "SENTINEL"}, "any_of": [[_req("VM.PowerMgmt", _V + "SENTINEL")]],
         "ref": "N2"},
        {"id": "N3", "name": "snapshot the sentinel", "method": "POST",
         "path": "/nodes/{node}/qemu/{vmid}/snapshot", "category": "denied",
         "bind": {"node": "NODE", "vmid": "SENTINEL"}, "any_of": [[_req("VM.Snapshot", _V + "SENTINEL")]],
         "ref": "N3"},
        {"id": "N4", "name": "create a guest without a pool", "method": "POST", "path": "/nodes/{node}/qemu",
         "category": "denied", "bind": {"node": "NODE", "vmid": "NEWID"},
         "any_of": [[_req("VM.Allocate", _V + "NEWID")]], "ref": "N4"},
        {"id": "N5", "name": "create in the pool with a disk on another storage", "method": "POST",
         "path": "/nodes/{node}/qemu", "category": "denied", "params": ["pool"],
         "bind": {"node": "NODE", "vmid": "NEWID", "pool": "corelab"},
         "any_of": [[_req("Datastore.AllocateSpace", "/storage/OTHER_STORAGE")]], "ref": "N5"},
        {"id": "N6", "name": "create in the pool with a NIC on another bridge", "method": "POST",
         "path": "/nodes/{node}/qemu", "category": "denied", "params": ["pool"],
         "bind": {"node": "NODE", "vmid": "NEWID", "pool": "corelab"},
         "any_of": [[_req("SDN.Use", "/sdn/zones/localnetwork/OTHER_BRIDGE")]], "ref": "N6"},
        {"id": "N7", "name": "add the sentinel to the pool", "method": "PUT", "path": "/pools/{poolid}",
         "category": "denied", "bind": {"poolid": "corelab"},
         "any_of": [[_req("Pool.Allocate", "/pool/corelab")]], "ref": "N7"},
        {"id": "N8", "name": "grant an ACL on the sentinel", "method": "PUT", "path": "/access/acl",
         "category": "denied", "bind": {"path": "/vms/SENTINEL"},
         "any_of": [[_req("Permissions.Modify", "/vms/SENTINEL")], [_req("VM.Allocate", "/vms/SENTINEL")]],
         "ref": "N8"},
        {"id": "N9", "name": "revert pending node network changes", "method": "DELETE",
         "path": "/nodes/{node}/network", "category": "denied", "bind": {"node": "NODE"},
         "any_of": [[_req("Sys.Modify", "/nodes/NODE")]], "ref": "N9"},
        {"id": "N10", "name": "set hookscript and args on a pool guest", "method": "PUT",
         "path": "/nodes/{node}/qemu/{vmid}/config", "category": "denied",
         "bind": {"node": "NODE", "vmid": "POOLVM"}, "expect": {"routine": "live-only", "read-only": "deny"},
         "ref": "N10, R-05: a parameter restriction, not in the schema text"},
        {"id": "N11", "name": "restore the sentinel's backup to a new VMID", "method": "POST",
         "path": "/nodes/{node}/qemu", "category": "denied", "params": ["pool"],
         "bind": {"node": "NODE", "vmid": "NEWID", "pool": "corelab"},
         "expect": {"routine": "live-only", "read-only": "deny"},
         "ref": "N11: the archive-owner check is not in the schema text"},
        {"id": "N12", "name": "attach the sentinel's disk to a pool guest", "method": "PUT",
         "path": "/nodes/{node}/qemu/{vmid}/config", "category": "denied",
         "bind": {"node": "NODE", "vmid": "POOLVM"}, "expect": {"routine": "live-only", "read-only": "deny"},
         "ref": "N12: the volume-ownership check is not in the schema text"},
        {"id": "N13", "name": "delete the sentinel's backup volume", "method": "DELETE",
         "path": "/nodes/{node}/storage/{storage}/content/{volume}", "category": "denied",
         "bind": {"node": "NODE", "storage": "LAB_STORAGE", "volume": "foreignbackup"},
         "any_of": [[_req("Datastore.Allocate", "/storage/LAB_STORAGE")],
                    [_req("Datastore.AllocateSpace", "/storage/LAB_STORAGE"), _req("VM.Backup", _V + "SENTINEL")]],
         "ref": "N13"},
        {"id": "N14", "name": "delete the dummy ISO", "method": "DELETE",
         "path": "/nodes/{node}/storage/{storage}/content/{volume}", "category": "denied",
         "bind": {"node": "NODE", "storage": "LAB_STORAGE", "volume": "dummyiso"},
         "any_of": [[_req("Datastore.Allocate", "/storage/LAB_STORAGE")]], "ref": "N14"},
        {"id": "N15", "name": "change the sentinel's memory", "method": "PUT",
         "path": "/nodes/{node}/qemu/{vmid}/config", "category": "denied",
         "bind": {"node": "NODE", "vmid": "SENTINEL"}, "any_of": [[_req("VM.Config.Memory", _V + "SENTINEL")]],
         "ref": "N15"},
        {"id": "X1", "name": "upload an image (Mode B)", "method": "POST",
         "path": "/nodes/{node}/storage/{storage}/upload", "category": "denied",
         "bind": {"node": "NODE", "storage": "LAB_STORAGE"},
         "any_of": [[_req("Datastore.AllocateTemplate", "/storage/LAB_STORAGE")]], "ref": "s6.1 not granted"},
        {"id": "X2", "name": "download an image by URL (Mode B)", "method": "POST",
         "path": "/nodes/{node}/storage/{storage}/download-url", "category": "denied",
         "bind": {"node": "NODE", "storage": "LAB_STORAGE"},
         "any_of": [[_req("Datastore.AllocateTemplate", "/storage/LAB_STORAGE"), _req("Sys.AccessNetwork", "/nodes/NODE")],
                    [_req("Datastore.AllocateTemplate", "/storage/LAB_STORAGE"), _req("Sys.Audit", "/"),
                     _req("Sys.Modify", "/")]],
         "ref": "R-11: Sys.AccessNetwork on the node, or Sys.Audit and Sys.Modify on /"},
        {"id": "X3", "name": "change the node network (Mode B)", "method": "PUT",
         "path": "/nodes/{node}/network", "category": "denied", "bind": {"node": "NODE"},
         "any_of": [[_req("Sys.Modify", "/nodes/NODE")]], "ref": "R-17"},
    ],
}


# ---------------------------------------------------------------------------------------
# apidoc.js loading (no execution)
# ---------------------------------------------------------------------------------------
def load_apidoc(path: str | Path) -> tuple[list, str, int]:
    """Return (tree, sha256 hex, size). The file is read as data and never executed."""
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"apidoc is not UTF-8: {exc.reason}") from exc
    m = re.search(r"(?:^|\n)[ \t]*(?:const|let|var)[ \t]+apiSchema[ \t]*=[ \t\r\n]*", text)
    if not m:
        raise InputError("no 'apiSchema =' assignment found")
    try:
        tree, _ = json.JSONDecoder().raw_decode(text, m.end())
    except json.JSONDecodeError as exc:
        raise InputError(f"apiSchema is not strict JSON ({exc.msg} at char {exc.pos}); "
                         "the file is never executed") from exc
    if not isinstance(tree, list):
        raise InputError("apiSchema is not a JSON array")
    return tree, hashlib.sha256(raw).hexdigest(), len(raw)


def index_schema(tree: list) -> tuple[dict, list[str]]:
    """Map (path, METHOD) -> info entry. Returns (index, warnings)."""
    ops: dict = {}
    warnings: list[str] = []

    def walk(node, depth: int) -> None:
        if depth > 64 or not isinstance(node, dict):
            warnings.append("schema node skipped: not an object or nested too deeply")
            return
        info = node.get("info")
        if info is not None:
            path = node.get("path")
            if not isinstance(path, str) or not isinstance(info, dict):
                warnings.append("schema node with a malformed 'path' or 'info' skipped")
            else:
                for method, entry in info.items():
                    key = (path, str(method).upper())
                    if key in ops:
                        warnings.append(f"duplicate schema entry {key[1]} {key[0]}: the later one is ignored")
                    else:
                        ops[key] = entry
        for child in node.get("children") or []:
            walk(child, depth + 1)

    for root in tree:
        walk(root, 0)
    return ops, warnings


# ---------------------------------------------------------------------------------------
# Evaluation model
# ---------------------------------------------------------------------------------------
class Unbound(Exception):
    pass


class Ctx:
    """Concrete objects an operation is evaluated against."""

    def __init__(self, bind: dict, params, pools: dict, default: str | None = None):
        self.bind = dict(bind)
        self.params = params          # set of supplied request parameters, or None = all supplied
        self.pools = {k: set(v) for k, v in pools.items()}
        self.default = default        # binding for names not in `bind` (sweep only); None = unbound

    def resolve(self, template: str) -> str:
        def sub(m):
            name = m.group(1)
            if name in self.bind:
                return str(self.bind[name])
            if self.default is None:
                raise Unbound(name)
            return "/" + self.default if name == "path" else self.default
        return PARAM_RE.sub(sub, template)

    def supplied(self, name: str) -> bool:
        return self.params is None or name in self.params


def chain_for(path: str, ctx: Ctx) -> list[str]:
    parts = [p for p in path.split("/") if p]
    chain, cur = ["/"], ""
    for p in parts:
        cur += "/" + p
        chain.append(cur)
    if len(parts) == 2 and parts[0] == "vms":
        for pool, members in ctx.pools.items():
            if parts[1] in members:  # a pool member inherits the pool's ACLs (plan R-19)
                chain.insert(len(chain) - 1, f"/pool/{pool}")
    return chain


def effective(profile: list, roles: dict, chain: list[str]) -> dict:
    """priv -> (role, acl path). Deeper entries replace inherited ones (plan R-19)."""
    current: list = []
    for i, p in enumerate(chain):
        last = i == len(chain) - 1
        hit = [e for e in profile if e["path"] == p and (e.get("propagate", True) or last)]
        if hit:
            current = hit
    grants: dict = {}
    for e in current:
        for priv in roles[e["role"]]:
            grants.setdefault(priv, (e["role"], e["path"]))
    return grants


def _leaf(form, path, privs, any_flag, state, **extra) -> dict:
    return {"form": form, "path": path, "privs": list(privs), "any": any_flag, "state": state, **extra}


def _held(privs, any_flag, grants):
    held = [p for p in dict.fromkeys(privs) if p in grants]
    ok = bool(held) if any_flag else len(held) == len(set(privs))
    return ok, held


def _combine(form: str, results: list) -> str:
    states = [r[0] for r in results]
    if form == "and":
        for s in (DENY, UNKNOWN, COND):
            if s in states:
                return s
        return ALLOW
    for s in (ALLOW, COND, UNKNOWN):
        if s in states:
            return s
    return DENY


def _unknown(form, tmpl, privs, any_flag, note):
    """An unevaluable node: UNKNOWN, with a leaf that records why. Always incomplete."""
    return UNKNOWN, [_leaf(form, tmpl, privs, any_flag, UNKNOWN, note=note)], [note], True


def eval_check(node, ctx: Ctx, prof: list, roles: dict, depth: int = 0) -> tuple[str, list, list, bool]:
    """Return (state, leaves, notes, incomplete) for one permission check node.

    `incomplete` is carried apart from the Boolean outcome: an `or` with a granted branch is
    ALLOW and an `and` with a denied branch is DENY whatever the other branches are, but if any
    branch inside the rule could not be evaluated the rule never counts as completely checked.
    """
    if depth > 32 or not isinstance(node, list) or not node or not isinstance(node[0], str):
        return _unknown("?", None, [], False, "malformed permission check node")
    form = node[0]
    if form in ("and", "or"):
        if len(node) < 2:
            return _unknown(form, None, [], False, f"'{form}' without operands")
        subs = [eval_check(n, ctx, prof, roles, depth + 1) for n in node[1:]]
        leaves = [leaf for sub in subs for leaf in sub[1]]
        notes = [n for sub in subs for n in sub[2]]
        state = _combine(form, subs)
        return state, leaves, notes, any(sub[3] for sub in subs) or state == UNKNOWN
    if form == "perm":
        return _eval_perm(node, ctx, prof, roles)
    if form == "perm-modify":
        return _eval_perm_modify(node, ctx, prof, roles)
    if form == "userid-param":
        return _eval_userid_param(node, ctx, prof, roles)
    if form == "userid-group":
        return _eval_userid_group(node, ctx, prof, roles)
    return _unknown(form, None, [], False, f"unknown permission form '{form}'")


def _eval_perm(node, ctx, prof, roles):
    if len(node) not in (3, 5) or not isinstance(node[1], str) or not isinstance(node[2], list) \
            or not node[2] or not all(isinstance(p, str) for p in node[2]):
        return _unknown("perm", None, [], False, "malformed 'perm' node")
    _, tmpl, privs = node[0], node[1], node[2]
    any_flag, require = False, None
    if len(node) == 5:
        key, val = node[3], node[4]
        if key == "any" and val in (0, 1) and not isinstance(val, bool):
            any_flag = bool(val)
        elif key == "require_param" and isinstance(val, str):
            require = val
        else:
            return _unknown("perm", tmpl, privs, False, f"unknown perm option '{key}'")
    if require is not None and not ctx.supplied(require):
        return DENY, [_leaf("perm", tmpl, privs, False, DENY, note=f"branch needs request parameter '{require}'")], \
            [], False
    try:
        concrete = ctx.resolve(tmpl)
    except Unbound as exc:
        return _unknown("perm", tmpl, privs, any_flag, f"unbound parameter '{exc}' in {tmpl}")
    grants = effective(prof, roles, chain_for(concrete, ctx))
    ok, held = _held(privs, any_flag, grants)
    leaf = _leaf("perm", tmpl, privs, any_flag, ALLOW if ok else DENY, resolved=concrete,
                 granted_by=[{"priv": p, "role": grants[p][0], "acl_path": grants[p][1]} for p in held],
                 missing=[p for p in dict.fromkeys(privs) if p not in grants])
    return leaf["state"], [leaf], [], False


def _eval_perm_modify(node, ctx, prof, roles):
    if len(node) != 2 or not isinstance(node[1], str):
        return _unknown("perm-modify", None, [], False, "malformed 'perm-modify' node")
    try:
        concrete = ctx.resolve(node[1])
    except Unbound as exc:
        return _unknown("perm-modify", node[1], [], True, f"unbound parameter '{exc}' in {node[1]}")
    # Plan R-15: Permissions.Modify, or a substitute right on the object's own kind of path.
    substitute = {"vms": "VM.Allocate", "storage": "Datastore.Allocate", "pool": "Pool.Allocate"}
    first = next((p for p in concrete.split("/") if p), "")
    privs = ["Permissions.Modify"] + ([substitute[first]] if first in substitute else [])
    grants = effective(prof, roles, chain_for(concrete, ctx))
    ok, held = _held(privs, True, grants)
    leaf = _leaf("perm-modify", node[1], privs, True, ALLOW if ok else DENY, resolved=concrete,
                 granted_by=[{"priv": p, "role": grants[p][0], "acl_path": grants[p][1]} for p in held],
                 missing=[p for p in privs if p not in grants])
    return leaf["state"], [leaf], [], False


def _assumed(form, privs, paths, note):
    """Forms whose semantics the schema does not state: always UNKNOWN and incomplete.

    The privileges are listed so a reader sees what the rule mentions, but the outcome is
    never ALLOW and never a definite DENY: neither would rest on evidence.
    """
    text = f"{form}: semantics not established ({note})"
    return UNKNOWN, [_leaf(form, "|".join(paths), privs, True, UNKNOWN, note=note)], [text], True


def _eval_userid_param(node, ctx, prof, roles):
    if len(node) != 2 or not isinstance(node[1], str):
        return _unknown("userid-param", None, [], False, "malformed 'userid-param' node")
    if node[1] == "self":
        return COND, [_leaf("userid-param", None, [], False, COND, note="allowed for the caller's own user id only")], \
            [], False
    if PRIV_RE.fullmatch(node[1]):
        return _assumed("userid-param", [node[1]], ["/access/realm/{realm}"],
                        "privilege on the realm of the user id")
    return _unknown("userid-param", None, [], False, f"unknown userid-param argument '{node[1]}'")


# Grammar seen in the schema: ["userid-group", [privileges]] optionally followed by
# "groups_param" and one of these actions. Anything else is not understood.
_USERID_GROUP_ACTIONS = ("create", "update")


def _eval_userid_group(node, ctx, prof, roles):
    ok = len(node) >= 2 and isinstance(node[1], list) and node[1] and all(isinstance(p, str) for p in node[1])
    if ok and len(node) == 4:
        ok = node[2] == "groups_param" and node[3] in _USERID_GROUP_ACTIONS
    elif ok:
        ok = len(node) == 2
    if not ok:
        return _unknown("userid-group", None, [], False, "unsupported 'userid-group' grammar")
    return _assumed("userid-group", node[1], ["/access", "/access/groups/{group}"],
                    "privilege on /access or on a group")


def schema_privs(leaves: list) -> set:
    return {p for leaf in leaves for p in leaf["privs"]}


PATH_RE = re.compile(r"(?<![\w/])/(?:[\w{}.-]+(?:/[\w{}.-]+)*)?")
CUE_RE = re.compile(r"\b(also|additionally|in addition|only|unless|except|if|when|requires?|required|must|restricted)\b",
                    re.IGNORECASE)


def description_extras(desc: str, leaves: list) -> list[str]:
    """Reasons why a description is NOT shown equivalent to the structured check ([] = no text).

    There is no list of wordings known to add nothing: text can add a requirement, but it can
    equally add an alternative, and a pattern cannot tell the two apart. A rule is decided by
    the structured check alone only when there is no description text at all. The first
    reasons below say what the text visibly adds, the last one always applies.
    """
    text = " ".join(desc.split())
    if not text:
        return []
    known = {leaf["path"] for leaf in leaves if leaf.get("path")}
    reasons = []
    extra = sorted(set(PRIV_RE.findall(text)) - schema_privs(leaves))
    if extra:
        reasons.append("privileges not in the check: " + ", ".join(extra))
    paths = {p.rstrip(".,;:") or "/" for p in PATH_RE.findall(text)}
    extra_paths = sorted(p for p in paths if p not in known)
    if extra_paths:
        reasons.append("paths not in the check: " + ", ".join(extra_paths))
    cues = sorted({c.group(1).lower() for c in CUE_RE.finditer(text)})
    if cues:
        reasons.append("wording that adds a condition: " + ", ".join(cues))
    reasons.append("description text is present; only the structured check alone can decide the rule")
    return reasons


def _res(state, leaves, notes, text_privs, incomplete=None) -> dict:
    return {"state": state, "leaves": leaves, "notes": notes, "text_privs": text_privs,
            "incomplete": state in (UNKNOWN, TEXT, MISSING) if incomplete is None else incomplete}


def _early_denial(why: str, perms, ctx: Ctx, prof: list, roles: dict) -> dict:
    """A denial that does not depend on the privilege check (root only, no API-token access).

    It follows the same policy as every other row: description text or an unknown or
    unevaluable form in the rule keeps the row from being complete, whatever the outcome.
    """
    notes = [why]
    leaves, incomplete, text_privs = [], False, []
    if isinstance(perms, dict):
        desc = perms.get("description")
        if isinstance(desc, str):
            text_privs = sorted(set(PRIV_RE.findall(desc)))
        if perms.get("check") is not None:
            _, leaves, more, incomplete = eval_check(perms["check"], ctx, prof, roles)
            notes += more
        if isinstance(desc, str) and desc.strip():
            notes.append("description text is present; only the structured check alone can decide the rule")
            return _res(TEXT, leaves, notes, text_privs, True)
    return _res(DENY, leaves, notes, text_privs, incomplete)


def evaluate_entry(entry, ctx: Ctx, prof: list, roles: dict) -> dict:
    """Evaluate one schema entry for one profile. Never returns ALLOW on doubtful input."""
    if entry is None:
        return _res(MISSING, [], ["operation not found in the schema"], [])
    if not isinstance(entry, dict):
        return _res(UNKNOWN, [], ["schema entry is not an object"], [])
    if entry.get("allowtoken") == 0:
        return _early_denial("not callable with an API token (allowtoken 0)", entry.get("permissions"),
                             ctx, prof, roles)
    if "permissions" not in entry:
        return _res(UNKNOWN, [], ["no 'permissions' key"], [])
    perms = entry["permissions"]
    if not isinstance(perms, dict):
        return _res(UNKNOWN, [], ["'permissions' is not an object"], [])
    user, check, desc = perms.get("user"), perms.get("check"), perms.get("description")
    desc = desc if isinstance(desc, str) else None
    text_privs = sorted(set(PRIV_RE.findall(desc))) if desc else []
    notes: list = []
    if desc and "root@pam" in desc:
        notes.append("description restricts some parameters to root@pam")
    if user not in (None, "all", "world", "root@pam"):
        return _res(UNKNOWN, [], [f"unknown 'user' value {user!r}"], text_privs)
    if user == "root@pam":
        return _early_denial("root@pam only", perms, ctx, prof, roles)
    if check is not None:
        state, leaves, more, incomplete = eval_check(check, ctx, prof, roles)
        notes += more
        reasons = description_extras(desc, leaves) if desc else []
        if state in (ALLOW, COND, DENY) and reasons:
            notes.append("description is not shown equivalent to the machine check: " + "; ".join(reasons))
            state, incomplete = TEXT, True
        return _res(state, leaves, notes, text_privs, incomplete)
    if desc is not None:
        notes.append("permission rule is free text only")
        return _res(TEXT, [], notes, text_privs)
    if user in ("all", "world"):
        return _res(ALLOW, [], ["no privilege required"], [])
    return _res(UNKNOWN, [], ["empty permission rule"], [])


# ---------------------------------------------------------------------------------------
# Plan loading and the comparison
# ---------------------------------------------------------------------------------------
def load_plan(path: str | Path | None) -> dict:
    if path is None:
        plan = copy.deepcopy(DEFAULT_PLAN)
    else:
        try:
            plan = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise InputError(f"cannot read the plan file: {exc}") from exc
    return validate_plan(plan)


def validate_plan(plan) -> dict:
    if not isinstance(plan, dict):
        raise InputError("plan is not an object")
    roles = plan.get("roles")
    profiles, ops = plan.get("profiles"), plan.get("operations")
    if not isinstance(roles, dict) or not isinstance(profiles, dict) or not profiles \
            or not isinstance(ops, list) or not ops:
        raise InputError("plan needs 'roles', non-empty 'profiles' and a non-empty 'operations' list")
    roles = {k: v for k, v in roles.items() if not k.startswith("_")}
    for name, privs in roles.items():
        if not isinstance(privs, list) or not all(isinstance(p, str) for p in privs):
            raise InputError(f"role {name!r} must be a list of privilege names")
    for pname, acls in profiles.items():
        for e in acls:
            if not isinstance(e, dict) or e.get("role") not in roles or not str(e.get("path", "")).startswith("/"):
                raise InputError(f"profile {pname!r} has an invalid ACL entry: {e!r}")
    if plan.get("sweep_profile", "routine") not in profiles:
        raise InputError("plan 'sweep_profile' is not one of the profiles")
    seen = set()
    for op in ops:
        if not isinstance(op, dict) or not all(isinstance(op.get(k), str) for k in ("id", "method", "path")):
            raise InputError(f"invalid operation entry: {op!r}")
        if op["id"] in seen:
            raise InputError(f"duplicate operation id {op['id']}")
        seen.add(op["id"])
        if op.get("category") not in EXPECTATIONS and "expect" not in op:
            raise InputError(f"operation {op['id']}: needs a known 'category' or an 'expect' map")
        for pname, exp in (op.get("expect") or {}).items():
            if exp not in EXPECT_VALUES:
                raise InputError(f"operation {op['id']}: bad expectation {exp!r}")
            if pname not in profiles:
                raise InputError(f"operation {op['id']}: expectation for unknown profile {pname!r}")
        for alt in op.get("any_of", []):
            if not isinstance(alt, list) or not all(isinstance(r, dict) and "priv" in r and "path" in r for r in alt):
                raise InputError(f"operation {op['id']}: 'any_of' must be a list of lists of {{priv, path}}")
    plan["_roles"] = roles
    return plan


def plan_only(op: dict, ctx: Ctx, prof: list, roles: dict):
    """Evaluate the plan's own requirement list. Returns (satisfied or None, detail)."""
    alts = op.get("any_of") or []
    if not alts:
        return None, []
    detail, satisfied = [], False
    for alt in alts:
        ok_all, parts = True, []
        for req in alt:
            grants = effective(prof, roles, chain_for(req["path"], ctx))
            held = req["priv"] in grants
            ok_all &= held
            parts.append({"priv": req["priv"], "path": req["path"], "held": held,
                          "by": f"{grants[req['priv']][0]}@{grants[req['priv']][1]}" if held else None})
        satisfied |= ok_all
        detail.append(parts)
    return satisfied, detail


def verdict_for(expect: str, res: dict, op: dict, po) -> tuple[str, str]:
    """Combine the schema result, the expectation and the plan-only evaluation."""
    state = res["state"]
    if state == MISSING:
        return "MISSING-OP", "the plan names an operation the schema does not contain"
    if expect == "live-only":
        return "LIVE-ONLY", f"the plan's refusal rests on a check the schema does not express (schema state {state})"
    plan_privs = {r["priv"] for alt in op.get("any_of", []) for r in alt}
    known = schema_privs(res["leaves"]) | set(res["text_privs"])
    if plan_privs and known and state in (ALLOW, COND, DENY, TEXT) and not plan_privs <= known:
        gone = ", ".join(sorted(plan_privs - known))
        return "PLAN-DRIFT", f"the plan names privilege(s) the schema does not mention: {gone}"
    want = {"allow": ALLOW, "deny": DENY, "conditional": COND}[expect]
    if state == want:
        if res.get("incomplete"):
            return "INCOMPLETE", f"{state} as planned, but a branch inside the rule could not be evaluated"
        return "OK", "schema result matches the plan"
    if state in (ALLOW, COND, DENY):
        order = {DENY: 0, COND: 1, ALLOW: 2}
        if order[state] > order[want]:
            return "BROADER", f"the schema grants {state} where the plan expects {want.upper()}"
        return "NARROWER", f"the schema gives {state} where the plan expects {want.upper()}"
    if po is not None:  # TEXT-ONLY / UNKNOWN: the plan's own requirements can still contradict the plan
        if want == ALLOW and po[0] is False:
            return "NARROWER", f"{state}; the plan's own requirements are not all granted (plan-only evaluation)"
        if want == DENY and po[0] is True:
            return "BROADER", f"{state}; the plan's own requirements are all granted (plan-only evaluation)"
    return "INCOMPLETE", f"{state}: not machine-checkable" + (
        f"; plan-only evaluation {'satisfied' if po[0] else 'not satisfied'}" if po and po[0] is not None else "")


def _fmt_required(res: dict) -> str:
    seen, out = set(), []
    for leaf in res["leaves"]:
        if leaf["privs"]:
            text = f"{'any of ' if leaf['any'] and len(leaf['privs']) > 1 else ''}" \
                   f"{'+'.join(leaf['privs'])} @ {leaf.get('resolved') or leaf['path']}"
            if text not in seen:
                seen.add(text)
                out.append(text)
    if not out and res["text_privs"]:
        out = ["text: " + ", ".join(res["text_privs"])]
    return "; ".join(out) or "-"


def _fmt_granted(res: dict) -> str:
    seen, out = set(), []
    for leaf in res["leaves"]:
        if leaf["state"] == ALLOW:
            for g in leaf.get("granted_by", []):
                t = f"{g['role']} @ {g['acl_path']}"
                if t not in seen:
                    seen.add(t)
                    out.append(t)
    return "; ".join(out) or "-"


def build_matrix(index: dict, plan: dict, profiles: list[str] | None = None) -> list[dict]:
    """One row per operation and selected profile. Every pair must have an expectation:
    a pair the plan does not cover is an error, never a silently omitted row."""
    selected = list(profiles or plan["profiles"])
    unknown = [p for p in selected if p not in plan["profiles"]]
    if unknown:
        raise InputError(f"unknown profile(s): {', '.join(unknown)}")
    if not selected:
        raise InputError("no profile selected")
    expectations = {}
    for op in plan["operations"]:
        expects = dict(EXPECTATIONS.get(op.get("category"), {}))
        expects.update(op.get("expect") or {})
        uncovered = [p for p in selected if p not in expects]
        if uncovered:
            raise InputError(f"operation {op['id']} has no expectation for profile(s): {', '.join(uncovered)}")
        expectations[op["id"]] = expects
    rows = []
    roles = plan["_roles"]
    for op in plan["operations"]:
        entry = index.get((op["path"], op["method"].upper()))
        for pname in selected:
            prof = plan["profiles"][pname]
            ctx = Ctx(op.get("bind", {}), set(op.get("params", [])), plan.get("pools", {}))
            res = evaluate_entry(entry, ctx, prof, roles)
            po = plan_only(op, ctx, prof, roles)
            expect = expectations[op["id"]][pname]
            verdict, why = verdict_for(expect, res, op, po)
            rows.append({"id": op["id"], "name": op.get("name", ""), "method": op["method"], "path": op["path"],
                         "profile": pname, "expect": expect, "state": res["state"], "verdict": verdict,
                         "why": why, "incomplete": res["incomplete"], "required": _fmt_required(res),
                         "granted_by": _fmt_granted(res), "notes": res["notes"], "text_privs": res["text_privs"],
                         "ref": op.get("ref", ""),
                         "plan_only": None if po[0] is None else {"satisfied": po[0], "detail": po[1]}})
    if not rows:
        raise InputError("no operation was compared")
    return rows


def sweep(index: dict, plan: dict) -> dict:
    """Evaluate every schema operation for the sweep profile (default routine) on a lab-scope and a foreign object.

    Unnamed path parameters bind to a generic 'other' object; `require_param` branches count
    as satisfiable. A write-method operation (POST/PUT/DELETE) that evaluates ALLOW on the
    foreign object through a privilege other than an ``*.Audit`` one is broader than the plan;
    one allowed through audit privileges only, or with no privilege at all, is listed apart.
    """
    roles, prof = plan["_roles"], plan["profiles"][plan.get("sweep_profile", "routine")]
    planned = {(o["path"], o["method"].upper()) for o in plan["operations"]}
    ctxs = {name: Ctx(c["bind"], None, plan.get("pools", {}), default="other")
            for name, c in plan["contexts"].items()}
    out = {"total": len(index), "profile": plan.get("sweep_profile", "routine"), "foreign_write_allowed": [], "foreign_audit_only_write": [],
           "foreign_no_privilege_write": [], "foreign_read_allowed": 0,
           "in_scope_allowed_unplanned": [], "undecided": {UNKNOWN: 0, TEXT: 0, COND: 0, "INCOMPLETE-RULE": 0},
           "undecided_ops": []}
    for (path, method), entry in sorted(index.items()):
        results = {n: evaluate_entry(entry, c, prof, roles) for n, c in ctxs.items()}
        states = {n: r["state"] for n, r in results.items()}
        key = f"{method} {path}"
        if states.get("foreign") == ALLOW:
            granted = {g["priv"] for leaf in results["foreign"]["leaves"] if leaf["state"] == ALLOW
                       for g in leaf.get("granted_by", [])}
            if method == "GET":
                out["foreign_read_allowed"] += 1
            elif not granted:  # allowed with no privilege at all (user 'all' or 'world')
                out["foreign_no_privilege_write"].append(key)
            elif all(p.endswith(".Audit") for p in granted):  # a POST that only needs an audit privilege
                out["foreign_audit_only_write"].append(key)
            else:
                out["foreign_write_allowed"].append(key)
        if states.get("in-scope") == ALLOW and (path, method) not in planned and method != "GET":
            out["in_scope_allowed_unplanned"].append(key)
        flagged = set(states.values()) & {UNKNOWN, TEXT, COND}
        # a definite outcome that rests on a rule with an unevaluable branch is also uncertain
        if any(r["incomplete"] and r["state"] in (ALLOW, DENY) for r in results.values()):
            flagged.add("INCOMPLETE-RULE")
        for s in flagged:
            out["undecided"][s] += 1
            if key not in out["undecided_ops"]:
                out["undecided_ops"].append(key)
    out["complete"] = not any(out["undecided"].values())
    return out


def overall(rows: list[dict], warnings: list[str], sweep_result: dict | None) -> tuple[str, int]:
    """MATCH only when something was compared, every row matched completely and the sweep
    (if run) left nothing undecided."""
    verdicts = [r["verdict"] for r in rows]
    mismatch = any(v in MISMATCH_VERDICTS for v in verdicts) or bool(sweep_result and sweep_result["foreign_write_allowed"])
    if mismatch:
        return "MISMATCH", 1
    incomplete = (not rows or any(v != "OK" for v in verdicts) or bool(warnings)
                  or bool(sweep_result and not sweep_result.get("complete", False)))
    return ("INCOMPLETE", 2) if incomplete else ("MATCH", 0)


# ---------------------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------------------
def render_text(meta: dict, rows: list[dict], sweep_result: dict | None, status: str) -> str:
    out = [f"privilege matrix (offline; schema {meta['file']}, sha256 {meta['sha256'][:16]}, {meta['size']} bytes)",
           f"plan: {meta['plan_ref']}",
           f"role contents: {meta['roles_source']}",
           "this is a document-level check: it proves nothing about live permissions, routing or recovery", ""]
    for pname in dict.fromkeys(r["profile"] for r in rows):
        out.append(f"profile: {pname}")
        w = max(len(r["id"]) for r in rows)
        out.append(f"{'ID':<{w}} {'OP':<44} {'EXPECT':<11} {'SCHEMA':<11} {'VERDICT':<10} REQUIRED / GRANTED BY")
        for r in (x for x in rows if x["profile"] == pname):
            op = f"{r['method']} {r['path']}"
            out.append(f"{r['id']:<{w}} {op[:44]:<44} {r['expect']:<11} {r['state']:<11} {r['verdict']:<10} "
                       f"{r['required']} | {r['granted_by']}")
            if r["verdict"] != "OK":
                out.append(f"      -> {r['why']}")
        out.append("")
    if sweep_result:
        out.append(f"sweep over {sweep_result['total']} schema operations ({sweep_result['profile']} profile)")
        out.append(f"  write operations allowed on a FOREIGN object: {len(sweep_result['foreign_write_allowed'])}")
        for k in sweep_result["foreign_write_allowed"]:
            out.append(f"    BROADER: {k}")
        out.append(f"  POST/PUT/DELETE allowed on a foreign object through audit privileges only: "
                   f"{len(sweep_result['foreign_audit_only_write'])} (read-class by privilege, informational)")
        out.append(f"  POST/PUT/DELETE allowed with no privilege required: "
                   f"{len(sweep_result['foreign_no_privilege_write'])} (informational)")
        out.append(f"  GET operations allowed on a foreign object: {sweep_result['foreign_read_allowed']} (plan: Auditor on /)")
        unplanned = sweep_result["in_scope_allowed_unplanned"]
        out.append(f"  unplanned write-method operations allowed on the lab scope: {len(unplanned)}")
        for k in unplanned[:40]:
            out.append(f"    {k}")
        if len(unplanned) > 40:
            out.append(f"    ... {len(unplanned) - 40} more (use --format json)")
        u = sweep_result["undecided"]
        out.append(f"  undecided (never counted as allowed): UNKNOWN {u[UNKNOWN]}, TEXT-ONLY {u[TEXT]}, "
                   f"CONDITIONAL {u[COND]}, rule with an unevaluable branch {u['INCOMPLETE-RULE']}"
                   f" -> sweep {'complete' if sweep_result['complete'] else 'INCOMPLETE'}")
        out.append("")
    counts: dict = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    out.append("verdicts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    for w in meta["warnings"]:
        out.append(f"warning: {w}")
    suffix = {"MATCH": "every planned operation matches from structured schema data",
              "INCOMPLETE": "no mismatch, but some operations could not be checked from the schema (not a pass)",
              "MISMATCH": "at least one operation is narrower or broader than the plan"}[status]
    out.append(f"RESULT: {status} ({suffix})")
    return "\n".join(out)


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # exit 2 means INCOMPLETE here; usage errors use 3
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        raise SystemExit(3)


def main(argv: list[str] | None = None) -> int:
    ap = _Parser(prog="privmatrix", description=__doc__.split("\n")[0])
    ap.add_argument("--apidoc", required=True, help="path of apidoc.js (read as data, never executed)")
    ap.add_argument("--plan", help="JSON plan file replacing the embedded RBAC design")
    ap.add_argument("--sweep", action="store_true", help="also evaluate every schema operation")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args(argv)
    try:
        plan = load_plan(args.plan)
        tree, sha, size = load_apidoc(args.apidoc)
        index, warnings = index_schema(tree)
        rows = build_matrix(index, plan)
    except (InputError, OSError) as exc:
        sys.stderr.write(f"privmatrix: {exc}\n")
        return 3
    sw = sweep(index, plan) if args.sweep else None
    status, code = overall(rows, warnings, sw)
    meta = {"file": Path(args.apidoc).name, "sha256": sha, "size": size, "plan_ref": plan.get("plan_ref", ""),
            "roles_source": plan["roles"].get("_source", "plan file"), "warnings": warnings}
    if args.format == "json":
        print(json.dumps({"meta": meta, "status": status, "rows": rows, "sweep": sw}, indent=1, sort_keys=True))
    else:
        print(render_text(meta, rows, sw, status))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
