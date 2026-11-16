"""Baseline: the prepared state, recorded once and compared later (read-only).

Only host-level, slow-moving facts are recorded. Project guests come and go during
routine work, so they are excluded; everything else should not drift without a decision.
"""

from __future__ import annotations

from typing import Any

from .inventory import require_complete

BASELINE_VERSION = 1


class BaselineError(ValueError):
    """A stored baseline is not a usable baseline. A ValueError, so every caller that already
    maps bad JSON to the documented refusal (exit 2) maps this one too."""


def snapshot(inventory: dict[str, Any], pool: str) -> dict[str, Any]:
    require_complete(inventory, "baseline")
    return {
        "baseline_version": BASELINE_VERSION,
        "node": inventory["node"],
        "pve_version": inventory.get("pve_version", ""),
        "pools": inventory.get("pools", []),
        "users": inventory.get("users", []),
        "tokens": sorted(t["id"] for t in inventory.get("tokens", [])),
        "acl": [list(a) for a in inventory.get("acl", [])],
        "storages": [{k: s[k] for k in ("storage", "type", "content", "path", "shared")}
                     for s in inventory.get("storages", [])],
        "network": [{k: n[k] for k in ("iface", "type", "address", "gateway", "bridge_ports")}
                    for n in inventory.get("network", [])],
        "non_project_guests": sorted([g["id"], g["name"], g["template"]]
                                     for g in inventory.get("guests", []) if g.get("pool") != pool),
        "project_templates": sorted([g["id"], g["name"]] for g in inventory.get("guests", [])
                                    if g.get("pool") == pool and g.get("template")),
        "certificate_fingerprints": sorted(str(c.get("fingerprint") or "") for c in inventory.get("certificates", [])),
    }


def compare(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Differences between a stored baseline and a fresh snapshot. Empty list = no drift.

    A stored baseline that is not a baseline (not an object, no or another version) is refused,
    never read as "everything was added"."""
    for name, doc in (("stored baseline", baseline), ("current snapshot", current)):
        if not isinstance(doc, dict):
            raise BaselineError(f"{name} must be a JSON object")
        if doc.get("baseline_version") != BASELINE_VERSION or isinstance(doc.get("baseline_version"), bool):
            raise BaselineError(f"{name}: baseline_version must be {BASELINE_VERSION}")
    diffs = []
    for key in sorted(set(baseline) | set(current)):
        if key == "baseline_version":
            continue
        old, new = baseline.get(key), current.get(key)
        if old == new:
            continue
        if isinstance(old, list) and isinstance(new, list):
            norm = lambda xs: {repr(x) for x in xs}  # noqa: E731
            gone, added = sorted(norm(old) - norm(new)), sorted(norm(new) - norm(old))
            for g in gone:
                diffs.append(f"{key}: removed {g}")
            for a in added:
                diffs.append(f"{key}: added {a}")
        else:
            diffs.append(f"{key}: {old!r} -> {new!r}")
    return diffs
