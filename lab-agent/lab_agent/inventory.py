"""Read-only discovery through the API, and normalisation into one inventory document.

``collect`` only issues GET requests. A refused or missing endpoint is recorded in
``errors`` instead of aborting, so a partial view is still written and its gaps are explicit.
Every conclusion drawn from an inventory first calls ``require_complete`` for its purpose:
it refuses when an endpoint that conclusion depends on was not read.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from .pveapi import Client, PveError

_BACKUP_VMID = re.compile(r"vzdump-(?:qemu|lxc)-(\d+)-")
_DISK_KEY = re.compile(r"^(?:scsi|virtio|ide|sata|efidisk|tpmstate|unused|rootfs|mp)\d*$")
INACTIVE = "storage inactive, content not read"

# The endpoints each conclusion rests on. "{node}" is the inventory's node; the rest is a
# regular expression matched against the whole path recorded in ``errors``. A parent
# endpoint is listed with its children: when it fails, the children are never attempted.
_STORAGE_CONTENT = (r"/cluster/resources", r"/nodes/{node}/storage", r"/nodes/{node}/storage/[^/]+/content")
_USERS = (r"/access/users", r"/access/users/[^/]+/token")
REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "vmid-range": _STORAGE_CONTENT,
    "classify": _STORAGE_CONTENT + _USERS + (r"/storage", r"/pools", r"/nodes/{node}/network",
                                             r"/nodes/{node}/disks/list"),
    "manifest": _STORAGE_CONTENT + _USERS + (r"/storage", r"/pools", r"/nodes/{node}/network",
                                             r"/nodes/{node}/disks/list", r"/nodes/{node}/(?:qemu|lxc)/\d+/config"),
    "baseline": _USERS + (r"/version", r"/pools", r"/access/acl", r"/storage", r"/nodes/{node}/network",
                          r"/cluster/resources", r"/nodes/{node}/certificates/info"),
}


class IncompleteInventoryError(Exception):
    """An endpoint a conclusion depends on was not read."""


def unread_endpoints(inventory: dict[str, Any], purpose: str) -> list[str]:
    """``path: reason`` for every unread endpoint the purpose depends on, sorted."""
    errors = inventory.get("errors")
    if not isinstance(errors, dict):
        raise IncompleteInventoryError("inventory has no errors record; run discover again")
    node = re.escape(str(inventory.get("node", "")))
    patterns = [re.compile(p.replace("{node}", node)) for p in REQUIREMENTS[purpose]]
    return sorted(f"{path}: {reason}" for path, reason in errors.items()
                  if any(p.fullmatch(path) for p in patterns))


INVENTORY_VERSION = 1
SECTIONS = ("guests", "storages", "volumes", "pools", "users", "tokens", "acl", "backup_jobs", "network",
            "disks", "certificates")
# A working host always has entries here (root@pam, a storage, an interface, the node
# certificate, the discovery token and its ACL). Empty means not read, not absent.
NON_EMPTY = ("storages", "users", "tokens", "acl", "network", "certificates")
# Per purpose, the sections whose emptiness means "not read" for that conclusion. The ACL and the
# certificates feed only the baseline, so an unread /access/acl or certificates endpoint no longer
# blocks the VMID-range check, classification or a manifest (F-E). Each of those purposes still
# refuses when an endpoint it depends on is recorded as unread (REQUIREMENTS above).
NON_EMPTY_BY_PURPOSE: dict[str, tuple[str, ...]] = {
    "vmid-range": ("storages", "users", "tokens", "network"),
    "classify": ("storages", "users", "tokens", "network"),
    "manifest": ("storages", "users", "tokens", "network"),
    "baseline": NON_EMPTY,
}
# Content types whose file names are free-form: a name that looks like a guest volume is no
# owner there (an ISO called vm-77-notes.iso). Only used when the API gave no owner.
_UNOWNED_CONTENT = ("iso", "vztmpl", "snippets", "import")

_GUEST_PREFIX = {"qemu": "vm", "lxc": "ct"}
# The VMID a volume name says it belongs to; the last match wins (linked clones name their base first).
_VOLID_OWNER = re.compile(r"(?:^|[/:])(?:vm|base|subvol|basevol)-(\d+)-|vzdump-(?:qemu|lxc)-(\d+)-")

# Every section accepts only ids of its own form (always matched in full, so no trailing
# newline or other whitespace gets through). The forms are what normalize() writes.
_USER = r"[^\s:/!@]+@[A-Za-z][A-Za-z0-9._-]*"
FORMS = {
    "guests": re.compile(r"(vm|ct)/([1-9]\d{0,8})"),
    "volumes": re.compile(r"volume/([A-Za-z0-9][A-Za-z0-9_.-]*:\S+)"),
    "storages": re.compile(r"storage/([A-Za-z][A-Za-z0-9_.-]*)"),
    "network": re.compile(r"iface/([A-Za-z0-9][A-Za-z0-9_.-]*)"),
    "disks": re.compile(r"disk/(/dev/[A-Za-z0-9_./-]+)"),
    "tokens": re.compile(rf"token/({_USER})!([A-Za-z][A-Za-z0-9._-]*)"),
    "users": re.compile(_USER),
    "pools": re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*"),
}
_NODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,62}")

# The fields consumers read from each entry, with their type ("?" = may be null).
FIELDS = {
    "guests": {"id": "str", "vmid": "int", "type": "str", "node": "str", "name": "str", "status": "str",
               "template": "bool", "pool": "str", "digest": "str"},
    "volumes": {"id": "str", "volid": "str", "storage": "str", "size": "int?", "vmid": "int?"},
    "storages": {"id": "str", "storage": "str", "type": "str?", "content": "list", "path": "str",
                 "shared": "bool"},
    "network": {"id": "str", "iface": "str", "type": "str?", "address": "str", "gateway": "str",
                "bridge_ports": "str"},
    "disks": {"id": "str", "devpath": "str", "used": "str"},
    "tokens": {"id": "str"},
    "certificates": {},
}

# Classification dispatches on the section an entry came from, never on its id prefix.
SECTION_KIND = (("guests", "guest"), ("storages", "storage"), ("volumes", "volume"), ("network", "iface"),
                ("disks", "disk"), ("tokens", "token"))


def volid_vmids(volid: str) -> list[int]:
    """Every VMID a volume name carries, in order (the host guard looks at all of them)."""
    return [int(m[0] or m[1]) for m in _VOLID_OWNER.findall(volid)]


def volid_owner(volid: str) -> int | None:
    """The VMID encoded in a Proxmox volume id, or None when the name carries none.

    The owner is the last VMID (a linked clone names its base first). Protection decisions
    must not use this alone: use ``volid_vmids``, which the host guard also uses (R3-4)."""
    found = volid_vmids(volid)
    return found[-1] if found else None


def _show(rid: str) -> str:
    """An id as it may be printed: quoted when it holds whitespace (a newline, say)."""
    return rid if re.fullmatch(r"\S+", rid) else repr(rid)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _typed(value: Any, kind: str) -> bool:
    if kind.endswith("?") and value is None:
        return True
    return {"str": lambda v: isinstance(v, str), "int": _is_int, "bool": lambda v: isinstance(v, bool),
            "list": lambda v: isinstance(v, list)}[kind.rstrip("?")](value)


def inconsistencies(inventory: dict[str, Any], purpose: str | None = None) -> list[str]:
    """Shape and self-consistency problems: the identity that is classified (vmid, owner,
    pool) must be the identity that is removed (the id), and every id must have the form of
    the section it is in. Empty list = consistent.

    ``purpose`` selects which sections must be non-empty (``NON_EMPTY_BY_PURPOSE``); without
    it every section in ``NON_EMPTY`` must be."""
    if not isinstance(inventory, dict):
        return ["inventory is not a JSON object"]
    if inventory.get("inventory_version") != INVENTORY_VERSION or not _is_int(inventory.get("inventory_version")):
        return [f"inventory_version must be {INVENTORY_VERSION}"]
    problems = []
    if not isinstance(inventory.get("node"), str) or not _NODE.fullmatch(inventory["node"]):
        problems.append("node is missing or malformed")
    required = NON_EMPTY_BY_PURPOSE.get(purpose, NON_EMPTY) if purpose else NON_EMPTY
    for section in SECTIONS:
        if not isinstance(inventory.get(section), list):
            problems.append(f"{section} is missing or not a list")
        elif section in required and not inventory[section]:
            problems.append(f"{section} is empty")
    if "raw_digest" in inventory and not (isinstance(inventory["raw_digest"], str)
                                          and re.fullmatch(r"[0-9a-f]{64}", inventory["raw_digest"])):
        problems.append("raw_digest is not a sha256 hex digest")
    if problems:
        return problems
    for section, fields in FIELDS.items():
        for n, item in enumerate(inventory[section]):
            if not isinstance(item, dict):
                problems.append(f"{section}[{n}]: not an object")
                continue
            for key, kind in fields.items():
                if key not in item or not _typed(item[key], kind):
                    problems.append(f"{item.get('id', f'{section}[{n}]')}: {key} is missing or not {kind}")
    for section in ("users", "pools"):
        for name in inventory[section]:
            if not isinstance(name, str) or not FORMS[section].fullmatch(name):
                problems.append(f"{section}: {name!r} is not a valid {section[:-1]} id")
    for n, entry in enumerate(inventory["acl"]):
        if not isinstance(entry, (list, tuple)) or len(entry) != 4:
            problems.append(f"acl[{n}]: not a 4-field entry")
    for n, job in enumerate(inventory["backup_jobs"]):
        if job is not None and not isinstance(job, str):
            problems.append(f"backup_jobs[{n}]: not a string")
    if problems:
        return problems

    pools, users = set(inventory["pools"]), set(inventory["users"])
    seen: set[str] = set()

    def once(rid: str) -> None:
        if rid in seen:
            problems.append(f"{rid}: listed twice")
        seen.add(rid)

    for g in inventory["guests"]:
        rid = g["id"]
        m = FORMS["guests"].fullmatch(rid)
        if not m or int(m.group(2)) != g["vmid"]:
            problems.append(f"{_show(rid)}: id does not match vmid {g['vmid']!r}")
        elif _GUEST_PREFIX.get(g["type"]) != m.group(1):
            problems.append(f"{rid}: type {g['type']} does not match the id")
        if g["pool"] and g["pool"] not in pools:
            problems.append(f"{rid}: pool {g['pool']!r} is not in pools")
        once(rid)
    for v in inventory["volumes"]:
        rid, volid = v["id"], v["volid"]
        m = FORMS["volumes"].fullmatch(rid)
        owner = volid_owner(volid)
        if not m or m.group(1) != volid:
            problems.append(f"{_show(rid)}: id does not match volid {volid!r}")
        elif v["storage"] != volid.split(":", 1)[0]:
            problems.append(f"{rid}: storage {v['storage']} does not match the volid")
        elif owner is not None and v["vmid"] != owner:
            if v["vmid"] is None and v.get("content") in _UNOWNED_CONTENT:
                pass  # F-E: a free-form file name (ISO, template, snippet) with no owner from the API
            else:
                problems.append(f"{rid}: vmid {v['vmid']!r}, but the volid names VMID {owner}")
        once(rid)
    for section, key in (("storages", "storage"), ("network", "iface"), ("disks", "devpath")):
        for item in inventory[section]:
            m = FORMS[section].fullmatch(item["id"])
            if not m or m.group(1) != item[key]:
                problems.append(f"{_show(item['id'])}: id does not match {key} {item[key]!r}")
            once(item["id"])
    for t in inventory["tokens"]:
        m = FORMS["tokens"].fullmatch(t["id"])
        if not m:
            problems.append(f"{_show(t['id'])}: not a token id (token/<user>!<tokenid>)")
        elif m.group(1) not in users:
            problems.append(f"{t['id']}: user {m.group(1)} is not in users")
        once(t["id"])
    for kind, names in (("user", inventory["users"]), ("pool", inventory["pools"])):
        for name in names:
            once(f"{kind}/{name}")
    return problems


def require_complete(inventory: dict[str, Any], purpose: str) -> None:
    """Refuse a conclusion whose input data was not fully read or does not agree with itself."""
    problems = inconsistencies(inventory, purpose)
    if problems:
        hint = ""
        errors = inventory.get("errors") if isinstance(inventory, dict) else None
        if isinstance(errors, dict) and errors:
            hint = " (endpoints recorded as not read: " + ", ".join(sorted(map(str, errors))) + ")"
        raise IncompleteInventoryError("inventory inconsistent: " + "; ".join(problems) + hint)
    missing = unread_endpoints(inventory, purpose)
    if missing:
        raise IncompleteInventoryError(f"inventory incomplete for {purpose}: not read: " + "; ".join(missing))


def _all_str(records: Any, fields: tuple[str, ...]) -> str | None:
    """None when ``records`` is a list of objects that each carry every field as non-empty text."""
    if not isinstance(records, list):
        return "not a list"
    for n, rec in enumerate(records):
        if not isinstance(rec, dict):
            return f"item {n} is not an object"
        for field in fields:
            if not isinstance(rec.get(field), str) or not rec[field]:
                return f"item {n} has no {field}"
    return None


def shape_problem(path: str, node: str, data: Any) -> str | None:
    """Why the API answer for ``path`` cannot be normalized, or None. Every endpoint whose
    records ``normalize`` indexes is checked for the fields it indexes (X1-b): a malformed
    record is a refusal (the endpoint counts as not read), never an exception."""
    n = re.escape(node)
    if path == "/cluster/resources":
        problem = _all_str(data, ())
        for rec in (data if problem is None else []):
            if rec.get("type") in ("qemu", "lxc") and (not _is_int(rec.get("vmid")) or rec["vmid"] < 1
                                                       or not isinstance(rec.get("node"), str)):
                return f"guest record {rec.get('id')!r} has no integer vmid or no node"
        return problem
    if path in ("/storage", f"/nodes/{node}/storage"):
        problem = _all_str(data, ("storage",))
        for rec in (data if problem is None else []):
            if rec.get("content") is not None and not isinstance(rec["content"], str):
                return f"storage {rec['storage']!r} has a content that is not text"
        return problem
    simple = {"/pools": ("poolid",), "/access/users": ("userid",), "/cluster/backup": ("id",),
              f"/nodes/{node}/network": ("iface",), f"/nodes/{node}/disks/list": ("devpath",),
              "/access/acl": ("path", "type", "ugid", "roleid")}
    if path in simple:
        return _all_str(data, simple[path])
    if path == f"/nodes/{node}/certificates/info":
        problem = _all_str(data, ())
        for rec in (data if problem is None else []):
            if rec.get("san") is not None and not (isinstance(rec["san"], list)
                                                   and all(isinstance(x, str) for x in rec["san"])):
                return "a certificate has a san that is not a list of text"
        return problem
    if re.fullmatch(rf"/nodes/{n}/storage/[^/]+/content", path):
        problem = _all_str(data, ("volid",))
        for rec in (data if problem is None else []):
            owner = rec.get("vmid")
            if owner is not None and not (_is_int(owner) or (isinstance(owner, str) and owner.isdigit())):
                return f"volume {rec['volid']!r} has a vmid that is not a number"
        return problem
    if re.fullmatch(r"/access/users/[^/]+/token", path):
        return _all_str(data, ("tokenid",))
    if path == "/version" or re.fullmatch(rf"/nodes/{n}/(?:qemu|lxc)/\d+/config", path):
        return None if isinstance(data, dict) else "not an object"
    return None


def validate_raw(collected: dict[str, Any]) -> None:
    """Refuse raw data that ``normalize`` could not index (hand-built or from an older run)."""
    node = collected["node"]
    problems = [f"{path}: {why}" for path, data in sorted(collected["raw"].items())
                if (why := shape_problem(path, node, data))]
    if problems:
        raise IncompleteInventoryError("raw data malformed: " + "; ".join(problems))


def _get(client: Client, path: str, raw: dict[str, Any], errors: dict[str, str], node: str = "") -> Any:
    try:
        data = client.get(path)
    except PveError as exc:
        errors[path] = f"{exc.status} {exc.message}"
        return None
    why = shape_problem(path, node, data) if node else None
    if why:
        errors[path] = f"malformed response: {why}"  # not read: dependent conclusions refuse
        return None
    raw[path] = data
    return data


def collect(client: Client, node: str) -> dict[str, Any]:
    """Fetch everything discovery needs. GET only."""
    raw: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for path in ("/version", "/cluster/status", "/cluster/resources", "/storage", "/pools",
                 "/access/users", "/access/acl", "/access/roles", "/cluster/backup",
                 f"/nodes/{node}/network", f"/nodes/{node}/storage", f"/nodes/{node}/disks/list",
                 f"/nodes/{node}/certificates/info", "/cluster/firewall/options",
                 f"/nodes/{node}/firewall/options"):
        _get(client, path, raw, errors, node)

    for res in raw.get("/cluster/resources") or []:
        if res.get("type") in ("qemu", "lxc") and res.get("node") == node:
            _get(client, f"/nodes/{node}/{res['type']}/{res['vmid']}/config", raw, errors, node)
    for st in raw.get(f"/nodes/{node}/storage") or []:
        content = f"/nodes/{node}/storage/{st['storage']}/content"
        if st.get("active"):
            _get(client, content, raw, errors, node)
        else:
            errors[content] = INACTIVE  # not read: its volumes are unknown, not absent
    for user in raw.get("/access/users") or []:
        _get(client, f"/access/users/{user['userid']}/token", raw, errors, node)

    return {"collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "node": node, "raw": raw, "errors": errors}


def _disks(config: dict[str, Any]) -> list[str]:
    vols = []
    for key, value in sorted(config.items()):
        if _DISK_KEY.match(key) and isinstance(value, str):
            volume = value.split(",", 1)[0]
            if ":" in volume and volume != "none" and "media=cdrom" not in value:
                vols.append(volume)
    return vols


def normalize(collected: dict[str, Any]) -> dict[str, Any]:
    """Turn raw API data into a stable, comparable inventory."""
    validate_raw(collected)
    raw, node = collected["raw"], collected["node"]
    guests = []
    for res in sorted(raw.get("/cluster/resources") or [], key=lambda r: str(r.get("id"))):
        if res.get("type") not in ("qemu", "lxc"):
            continue
        cfg = raw.get(f"/nodes/{res.get('node')}/{res['type']}/{res['vmid']}/config") or {}
        guests.append({
            "id": f"{'vm' if res['type'] == 'qemu' else 'ct'}/{res['vmid']}",
            "vmid": int(res["vmid"]), "type": res["type"], "node": res.get("node"),
            "name": res.get("name") or cfg.get("name") or cfg.get("hostname") or "",
            "status": res.get("status"), "template": bool(res.get("template")),
            "pool": res.get("pool") or "", "tags": res.get("tags") or "",
            "digest": cfg.get("digest") or "", "disks": _disks(cfg),
        })

    storages = []
    for st in sorted(raw.get("/storage") or [], key=lambda s: s["storage"]):
        storages.append({"id": f"storage/{st['storage']}", "storage": st["storage"],
                         "type": st.get("type"), "content": sorted((st.get("content") or "").split(",")),
                         "path": st.get("path") or "", "shared": bool(st.get("shared"))})

    volumes = []
    for path, items in sorted(raw.items()):
        m = re.fullmatch(rf"/nodes/{re.escape(node)}/storage/([^/]+)/content", path)
        if not m:
            continue
        for item in items or []:
            owner = item.get("vmid")
            if owner is None:
                bm = _BACKUP_VMID.search(item.get("volid", ""))
                owner = bm.group(1) if bm else None
            volumes.append({"id": f"volume/{item['volid']}", "volid": item["volid"],
                            "storage": m.group(1), "content": item.get("content"),
                            "size": item.get("size"), "vmid": int(owner) if owner else None})

    tokens = []
    for path, items in sorted(raw.items()):
        m = re.fullmatch(r"/access/users/([^/]+)/token", path)
        for item in (items or []) if m else []:
            tokens.append({"id": f"token/{m.group(1)}!{item['tokenid']}",
                           "privsep": bool(item.get("privsep")), "expire": item.get("expire") or 0})

    certs = []
    for c in raw.get(f"/nodes/{node}/certificates/info") or []:
        certs.append({"filename": c.get("filename"), "subject": c.get("subject"),
                      "san": sorted(c.get("san") or []), "notafter": c.get("notafter"),
                      "fingerprint": c.get("fingerprint")})

    network = []
    for n in sorted(raw.get(f"/nodes/{node}/network") or [], key=lambda i: i["iface"]):
        network.append({"id": f"iface/{n['iface']}", "iface": n["iface"], "type": n.get("type"),
                        "address": n.get("cidr") or n.get("address") or "",
                        "gateway": n.get("gateway") or "", "bridge_ports": n.get("bridge_ports") or "",
                        "active": bool(n.get("active"))})

    disks = []
    for d in sorted(raw.get(f"/nodes/{node}/disks/list") or [], key=lambda i: i["devpath"]):
        disks.append({"id": f"disk/{d['devpath']}", "devpath": d["devpath"],
                      "used": d.get("used") or "", "size": d.get("size"), "serial": d.get("serial") or "",
                      "model": d.get("model") or ""})

    version = raw.get("/version") or {}
    return {
        "inventory_version": 1,
        "collected_at": collected["collected_at"],
        "raw_digest": raw_digest(collected),
        "node": node,
        "pve_version": version.get("version", ""),
        "guests": guests,
        "storages": storages,
        "volumes": sorted(volumes, key=lambda v: v["volid"]),
        "pools": sorted(p["poolid"] for p in raw.get("/pools") or []),
        "users": sorted(u["userid"] for u in raw.get("/access/users") or []),
        "tokens": tokens,
        "acl": sorted((a.get("path"), a.get("type"), a.get("ugid"), a.get("roleid"))
                      for a in raw.get("/access/acl") or []),
        "backup_jobs": sorted(j.get("id") for j in raw.get("/cluster/backup") or []),
        "network": network,
        "disks": disks,
        "certificates": certs,
        "errors": collected.get("errors", {}),
    }


def raw_digest(collected: dict[str, Any]) -> str:
    """sha256 of what ``discover`` recorded: the node, every raw endpoint result and the errors.

    It binds an inventory to its raw.json for anyone who holds both. A same-user file can be
    rewritten together with its digest, so this detects accidental or one-sided edits, not a
    careful forger (F-F)."""
    return hashlib.sha256(canonical({"node": collected["node"], "raw": collected["raw"],
                                     "errors": collected.get("errors", {})})).hexdigest()


def verify_against_raw(inventory: dict[str, Any], collected: dict[str, Any]) -> list[str]:
    """Differences between an inventory and the raw data it claims to come from; empty = it is
    exactly what ``normalize`` makes of that raw data, so no entry, error or node was edited
    by hand on one side only."""
    try:
        again = normalize(collected)
    except IncompleteInventoryError as exc:
        return [str(exc)]
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        return [f"raw data does not normalize ({type(exc).__name__})"]
    if not isinstance(inventory, dict):
        return ["inventory is not a JSON object"]
    problems = []
    if not isinstance(inventory.get("raw_digest"), str):
        problems.append("inventory carries no raw_digest; run discover again")
    elif inventory["raw_digest"] != again["raw_digest"]:
        problems.append("raw_digest differs: the raw data is not the data this inventory was made from")
    for key in sorted(set(inventory) | set(again)):
        # Compared in JSON form: normalize() makes tuples (the ACL), a loaded file has lists.
        if key != "collected_at" and canonical(inventory.get(key)) != canonical(again.get(key)):
            problems.append(f"{key} differs from what the raw data gives")
    return problems


def digest(inventory: dict[str, Any]) -> str:
    """sha256 of the inventory's canonical JSON (collection time excluded)."""
    body = {k: v for k, v in inventory.items() if k != "collected_at"}
    return hashlib.sha256(canonical(body)).hexdigest()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def resources(inventory: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    """Every addressable resource by id, with its kind taken from the section it is in."""
    out: dict[str, tuple[str, dict[str, Any]]] = {}
    for section, kind in SECTION_KIND:
        for item in inventory.get(section, []):
            out[item["id"]] = (kind, item)
    for user in inventory.get("users", []):
        out[f"user/{user}"] = ("user", {"id": f"user/{user}", "userid": user})
    for pool in inventory.get("pools", []):
        out[f"pool/{pool}"] = ("pool", {"id": f"pool/{pool}", "poolid": pool})
    return out


def resource_index(inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every addressable resource by its id (vm/…, ct/…, volume/…, storage/…, …)."""
    return {rid: item for rid, (_kind, item) in resources(inventory).items()}
