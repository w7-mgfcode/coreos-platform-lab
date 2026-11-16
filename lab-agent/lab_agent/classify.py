"""Resource classification: PRESERVE, REUSE, MODIFY, REMOVE_CANDIDATE, UNKNOWN.

Rules are deliberately conservative. Nothing becomes REMOVE_CANDIDATE by default: only an
explicit override with written evidence can propose it, and never for a resource the
rules mark PRESERVE. Being outside the project pool is not evidence.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .inventory import canonical, require_complete, resources, volid_vmids

CLASSES = ("PRESERVE", "REUSE", "MODIFY", "REMOVE_CANDIDATE", "UNKNOWN")

# A VMID in the form every other check uses: 100 .. 999999999, no sign, no leading zero.
_VMID = re.compile(r"[1-9]\d{2,8}")

# The classification carries one reserved entry that records which sentinel VMID and which
# overrides it was made with. A manifest is built only from, and checked only against, a
# classification that carries a valid one. It is not a resource id: overrides cannot name it.
BINDING_ID = "binding/classification"


class ClassificationError(Exception):
    pass


def sentinel_vmid(value: Any) -> int:
    """A sentinel VMID, strictly: an int or the canonical decimal text of one, 100 .. 999999999.

    Missing, ``0``, negative, a float, a bool, ``09050``, ``9050 `` or any other text is refused
    (R3-1): a sentinel that protects nothing is worse than none."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ClassificationError(f"sentinel VMID {value!r} is not a VMID (an integer, 100 to 999999999)")
    text = str(value)
    if not _VMID.fullmatch(text):
        raise ClassificationError(f"sentinel VMID {value!r} is not a VMID (an integer, 100 to 999999999, "
                                  "no sign, no leading zero)")
    return int(text)


def config_context(cfg: Any, *, no_sentinel: bool = False) -> dict[str, Any]:
    """The classify() keyword arguments from the settings (shared by lab-agent and the owner path).

    ``PVE_SENTINEL_VMID`` is required and strictly checked. ``no_sentinel=True`` is the one named
    exception, for the stage that runs before a sentinel is chosen (a VMID-range look at a host
    without one): the classification it makes is marked so that no manifest can be built from it.
    A value that is set but invalid is refused in that mode too."""
    raw = cfg.values.get("PVE_SENTINEL_VMID") or ""
    if raw:
        sentinel: int | None = sentinel_vmid(raw)
    elif no_sentinel:
        sentinel = None
    else:
        raise ClassificationError("PVE_SENTINEL_VMID is not set (VMID of the sentinel guest outside the pool); "
                                  "classification for removal needs it")
    return {"pool": cfg.get("PVE_POOL"), "agent_user": cfg.token_id().split("!", 1)[0],
            "lab_storage": cfg.get("PVE_LAB_STORAGE"), "sentinel": sentinel, "no_sentinel": no_sentinel}


def overrides_digest(overrides: Any) -> str:
    """sha256 of the overrides in canonical JSON; no overrides is the same as an empty object."""
    return hashlib.sha256(canonical({} if overrides is None else overrides)).hexdigest()


def _rule(kind: str, item: dict[str, Any], ctx: dict[str, Any]) -> tuple[str, str]:
    """``kind`` comes from the inventory section the entry is in, never from its id.
    Every rule that can meet the sentinel tests it first."""
    if kind == "guest":
        if item["vmid"] == ctx.get("sentinel"):
            return "PRESERVE", "sentinel guest for negative RBAC tests"
        if item.get("pool") == ctx["pool"]:
            return "REUSE", "project pool member"
        return "UNKNOWN", "not project-owned; no evidence either way"
    if kind == "storage":
        if item["storage"] == ctx.get("lab_storage"):
            return "REUSE", "dedicated project storage"
        return "PRESERVE", "storage definitions are never removed by cleanup"
    if kind == "volume":
        # Every VMID the name carries counts, as on the host (R3-4): stricter than the owner alone.
        named = volid_vmids(item["volid"]) if isinstance(item.get("volid"), str) else []
        sentinel = ctx.get("sentinel")
        if sentinel is not None and (item.get("vmid") == sentinel or sentinel in named):
            return "PRESERVE", "sentinel volume"
        if item.get("vmid") in ctx["pool_vmids"] and all(v in ctx["pool_vmids"] for v in named):
            return "REUSE", "belongs to a project guest"
        return "UNKNOWN", "not project-owned"
    if kind == "iface":
        if item.get("address") or item.get("gateway"):
            return "PRESERVE", "carries a host address (management path)"
        return "UNKNOWN", "no address; role unknown"
    if kind == "disk":
        if item.get("used"):
            return "PRESERVE", f"in use ({item['used']})"
        return "UNKNOWN", "unused disk; never wiped by the agent"
    if kind == "user":
        if item["userid"] in ("root@pam", ctx["agent_user"]):
            return "PRESERVE", "management or agent credential"
        return "UNKNOWN", "owner decides"
    if kind == "token":
        if item["id"].startswith(f"token/{ctx['agent_user']}!"):
            return "PRESERVE", "agent credential"
        return "UNKNOWN", "owner decides"
    if kind == "pool":
        if item["poolid"] == ctx["pool"]:
            return "REUSE", "project pool"
        return "UNKNOWN", "owner decides"
    return "UNKNOWN", "no rule"


def classify(inv: dict[str, Any], *, pool: str, agent_user: str, lab_storage: str | None = None,
             sentinel: int | None = None, overrides: dict[str, dict[str, str]] | None = None,
             no_sentinel: bool = False) -> dict[str, dict[str, Any]]:
    """Return {resource id: {"class", "reason"}} for every resource in the inventory, plus the
    reserved ``BINDING_ID`` entry (sentinel VMID and overrides digest).

    A valid ``sentinel`` is required. ``no_sentinel=True`` is the explicit, named mode for use
    before a sentinel exists: it forbids REMOVE_CANDIDATE and marks the result so that no
    manifest can be built from it."""
    if sentinel is not None:
        sentinel = sentinel_vmid(sentinel)
    elif not no_sentinel:
        raise ClassificationError("a valid sentinel VMID is required to classify resources for removal "
                                  "(the explicit no_sentinel mode is for use before a sentinel exists)")
    require_complete(inv, "classify")
    index = resources(inv)
    ctx = {"pool": pool, "agent_user": agent_user, "lab_storage": lab_storage, "sentinel": sentinel,
           "pool_vmids": {g["vmid"] for g in inv.get("guests", []) if g.get("pool") == pool}}
    result = {}
    for rid, (kind, item) in sorted(index.items()):
        cls, reason = _rule(kind, item, ctx)
        result[rid] = {"class": cls, "reason": reason}

    if overrides is not None and not isinstance(overrides, dict):
        raise ClassificationError("overrides must be a JSON object of {id: {class, evidence}}")
    for rid, ov in (overrides or {}).items():
        if not isinstance(ov, dict):
            raise ClassificationError(f"{rid}: override must be an object with class and evidence")
        if rid not in result:
            raise ClassificationError(f"override for unknown resource {rid}")
        new = ov.get("class")
        if new not in CLASSES:
            raise ClassificationError(f"{rid}: invalid class {new!r}")
        if result[rid]["class"] == "PRESERVE" and new != "PRESERVE":
            raise ClassificationError(f"{rid}: PRESERVE cannot be overridden")
        for field in ("evidence", "reason"):
            if ov.get(field) is not None and not isinstance(ov[field], str):
                raise ClassificationError(f"{rid}: override {field} must be text")
        evidence = (ov.get("evidence") or "").strip()
        if new == "REMOVE_CANDIDATE" and no_sentinel:
            raise ClassificationError(f"{rid}: no-sentinel mode cannot propose a removal")
        if new == "REMOVE_CANDIDATE" and len(evidence) < 10:
            raise ClassificationError(f"{rid}: REMOVE_CANDIDATE needs written evidence")
        result[rid] = {"class": new, "reason": evidence or ov.get("reason") or "override"}
    if no_sentinel:
        result[BINDING_ID] = {"class": "UNKNOWN", "sentinel_vmid": sentinel,
                              "overrides_digest": overrides_digest(overrides),
                              "reason": "made in no-sentinel mode: cannot feed a manifest"}
    else:
        result[BINDING_ID] = {"class": "PRESERVE", "sentinel_vmid": sentinel,
                              "overrides_digest": overrides_digest(overrides),
                              "reason": f"made with sentinel VMID {sentinel}; never removable"}
    return result


def vmid_range_conflicts(inv: dict[str, Any], lo: int, hi: int, pool: str) -> list[str]:
    """VMIDs inside the project range that belong to non-project guests or to any backup.

    A conflict means a future project guest could inherit rights over an old backup
    (VMID reuse), so the range must be moved before preparation.
    """
    require_complete(inv, "vmid-range")
    conflicts = []
    pool_vmids = {g["vmid"] for g in inv.get("guests", []) if g.get("pool") == pool}
    for g in inv.get("guests", []):
        if lo <= g["vmid"] <= hi and g.get("pool") != pool:
            conflicts.append(f"{g['id']} (not in pool {pool})")
    for v in inv.get("volumes", []):
        vmid = v.get("vmid")
        if v.get("content") == "backup" and vmid is not None and lo <= vmid <= hi \
                and vmid not in pool_vmids:
            conflicts.append(f"{v['id']} (backup of VMID {vmid}, no project guest owns it)")
    return sorted(conflicts)
