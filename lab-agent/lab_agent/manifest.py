"""Cleanup manifests: schema, validation, canonical hash, dry-run, revalidation, rendering.

A manifest is JSON. It may only remove resources the classification marks
REMOVE_CANDIDATE, and every value that reaches the host script is checked against a
strict pattern and shell-quoted, so the rendered script contains no agent-chosen
command text: only fixed operations on validated identifiers.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from typing import Any

from .classify import BINDING_ID, CLASSES, ClassificationError, sentinel_vmid
from .classify import classify as _classify
from .inventory import canonical, digest, require_complete, resources, volid_vmids

MANIFEST_VERSION = 1

GUEST_OPS = {"delete-purge", "stop-and-delete-purge"}
VOLUME_OPS = {"free"}
BACKUPS = {"vzdump", "config-only", "none"}
REVERSIBLE = {"from-backup", "no"}

# All patterns are applied with fullmatch: no trailing newline or other whitespace gets through.
_ID = re.compile(r"(vm|ct)/([1-9]\d{2,8})|volume/([A-Za-z0-9][A-Za-z0-9_.-]*:[A-Za-z0-9_][A-Za-z0-9_./+-]*)")
_NODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,62}")
_NAME = re.compile(r"[A-Za-z0-9._-]{0,128}")
_STORAGE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,62}")
# A guest's config digest is never empty: an empty one would match an unreadable config on the host.
_DIGEST = re.compile(r"[0-9a-f]{40,64}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_STATUS = {"running", "stopped", "paused", "suspended", "unknown"}

REQUIRED = ("id", "type", "current_state", "operation", "reason", "dependencies", "backup",
            "reversible", "expected_result", "verify")


class ManifestError(Exception):
    pass


def load(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def manifest_hash(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(manifest)).hexdigest()


def check_classification(classification: Any) -> dict[str, dict[str, str]]:
    """A classification is {id: {"class": str, "reason": str}}; anything else is refused."""
    if not isinstance(classification, dict) or not all(
            isinstance(v, dict) and v.get("class") in CLASSES and isinstance(v.get("reason", ""), str)
            for v in classification.values()):
        raise ManifestError("classification must be a JSON object of {id: {class, reason}}")
    return classification


def recomputed_classification(inventory: dict[str, Any], classification: Any, overrides: Any,
                              context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The classification that settings, inventory and overrides give, refused unless the file
    ``classification`` is exactly that (X1-a).

    A classification file is editable metadata, and so is its binding entry: nothing in it proves
    how it was made. ``context`` is ``classify.config_context(cfg)`` (strict: a missing or invalid
    sentinel setting is refused there, and the no-sentinel mode is refused here). The returned
    classification is the recomputed one, never the file."""
    check_classification(classification)
    if context.get("no_sentinel"):
        raise ManifestError("a manifest cannot be built or checked in the no-sentinel mode")
    fresh = _classify(inventory, overrides=overrides, **context)
    if canonical(fresh) != canonical(classification):
        differing = sorted(k for k in set(fresh) | set(classification)
                           if canonical(fresh.get(k)) != canonical(classification.get(k)))
        raise ManifestError("the classification file is not what the settings, the inventory and the overrides "
                            f"give (differs at: {', '.join(differing[:6])}{' ...' if len(differing) > 6 else ''}); "
                            "run lab-agent classify again")
    return fresh


def build_trusted(inventory: dict[str, Any], classification: Any, overrides: Any, context: dict[str, Any],
                  backup_storage: str | None = None) -> dict[str, Any]:
    """``build`` from a classification that was recomputed and compared (X1-a). This is the call
    for the command line; ``build`` itself takes the classification it is given."""
    fresh = recomputed_classification(inventory, classification, overrides, context)
    return build(inventory, fresh, backup_storage)


def check_trusted(manifest: dict[str, Any], inventory: dict[str, Any], classification: Any, overrides: Any,
                  context: dict[str, Any]) -> None:
    """``validate`` against a classification that was recomputed and compared (X1-a)."""
    fresh = recomputed_classification(inventory, classification, overrides, context)
    validate(manifest, inventory, fresh)


def classification_binding(classification: dict[str, dict[str, Any]]) -> tuple[int, str]:
    """The sentinel VMID and the overrides digest a classification was made with.

    This is metadata in an editable file, not proof: ``build``, ``validate`` and this function
    take it as given. The trusted entry points are ``build_trusted`` and ``check_trusted``, which
    recompute the classification first; the owner path recomputes it as well.

    Refused (so exit 2 for the callers) when the reserved entry is missing, was made in the
    no-sentinel mode, or does not hold a valid sentinel VMID and a sha256: such a
    classification can never feed a manifest (R3-1, OVR)."""
    entry = classification.get(BINDING_ID)
    if not isinstance(entry, dict) or entry.get("class") != "PRESERVE":
        raise ManifestError("classification carries no sentinel binding (made without a sentinel VMID, or by "
                            "an older lab-agent); run lab-agent classify again with PVE_SENTINEL_VMID set")
    try:
        sentinel = _int_vmid(entry.get("sentinel_vmid"))
    except ClassificationError as exc:
        raise ManifestError(f"classification binding: {exc}") from None
    bound = entry.get("overrides_digest")
    if not isinstance(bound, str) or not _SHA256.fullmatch(bound):
        raise ManifestError("classification binding has no valid overrides_digest")
    return sentinel, bound


def _int_vmid(value: Any) -> int:
    """A sentinel VMID as stored in a manifest or a classification: a JSON integer, not text."""
    if not isinstance(value, int):
        raise ClassificationError(f"sentinel VMID {value!r} is not an integer")
    return sentinel_vmid(value)


def _one_of(value: Any, allowed: Any) -> bool:
    """Membership that cannot raise: a list or an object is simply not a member."""
    return isinstance(value, str) and value in allowed


def _sentinel_problem(rid: str, m: re.Match[str], sentinel: int) -> str | None:
    """Why this item may never be removed: the sentinel guest, or a volume whose name carries the
    sentinel's VMID anywhere (the host guard reads every VMID in a name; so does this)."""
    if m.group(1):
        if int(m.group(2)) == sentinel:
            return f"{rid}: classified PRESERVE (it is the sentinel guest {sentinel}; never removable)"
    elif sentinel in volid_vmids(m.group(3)):
        return f"{rid}: classified PRESERVE (its name carries the sentinel VMID {sentinel}; never removable)"
    return None


def _check_item(item: dict[str, Any], seen: set[str]) -> None:
    missing = [k for k in REQUIRED if k not in item]
    if missing:
        raise ManifestError(f"{item.get('id', '?')}: missing {', '.join(missing)}")
    rid = item["id"]
    if not isinstance(rid, str) or not isinstance(item["current_state"], dict) \
            or not isinstance(item["dependencies"], list):
        raise ManifestError(f"{rid!r}: id, current_state or dependencies has the wrong type")
    m = _ID.fullmatch(rid)
    if not m:
        raise ManifestError(f"{rid!r}: not a supported resource id")
    if rid in seen:
        raise ManifestError(f"{rid}: listed twice")
    state = item["current_state"]
    if m.group(1):  # guest
        expected_type = "qemu" if m.group(1) == "vm" else "lxc"
        if item["type"] != expected_type:
            raise ManifestError(f"{rid}: type must be {expected_type}")
        if not _one_of(item["operation"], GUEST_OPS):
            raise ManifestError(f"{rid}: operation must be one of {sorted(GUEST_OPS)}")
        for key, pattern in (("node", _NODE), ("name", _NAME), ("digest", _DIGEST)):
            if not isinstance(state.get(key), str) or not pattern.fullmatch(state[key]):
                raise ManifestError(f"{rid}: current_state.{key} is missing or malformed")
        if not _one_of(state.get("status"), _STATUS):
            raise ManifestError(f"{rid}: current_state.status is not a known state")
        if not isinstance(state.get("template"), bool):
            raise ManifestError(f"{rid}: current_state.template must be true or false")
        if item["operation"] == "delete-purge" and state["status"] != "stopped":
            raise ManifestError(f"{rid}: running guest needs stop-and-delete-purge")
        if item["backup"] == "vzdump" and not _STORAGE.fullmatch(str(item.get("backup_storage", ""))):
            raise ManifestError(f"{rid}: vzdump backup needs a valid backup_storage")
    else:  # volume
        if item["type"] != "volume":
            raise ManifestError(f"{rid}: type must be volume")
        if not _one_of(item["operation"], VOLUME_OPS):
            raise ManifestError(f"{rid}: operation must be one of {sorted(VOLUME_OPS)}")
        if item["backup"] == "vzdump":
            raise ManifestError(f"{rid}: volumes cannot be backed up with vzdump")
        if not (isinstance(state.get("node"), str) and _NODE.fullmatch(state["node"])
                and isinstance(state.get("storage"), str) and _STORAGE.fullmatch(state["storage"])):
            raise ManifestError(f"{rid}: current_state needs node and storage")
        if not isinstance(state.get("size"), int) or isinstance(state.get("size"), bool):
            raise ManifestError(f"{rid}: current_state.size must be an integer")
    if not _one_of(item["backup"], BACKUPS):
        raise ManifestError(f"{rid}: backup must be one of {sorted(BACKUPS)}")
    if not _one_of(item["reversible"], REVERSIBLE):
        raise ManifestError(f"{rid}: reversible must be one of {sorted(REVERSIBLE)}")
    if item["backup"] == "none" and item["reversible"] != "no":
        raise ManifestError(f"{rid}: without a backup it cannot be reversible")
    if not str(item["reason"]).strip():
        raise ManifestError(f"{rid}: reason is empty")
    for dep in item["dependencies"]:
        if not isinstance(dep, str) or dep not in seen:
            raise ManifestError(f"{rid}: dependency {dep} must be an earlier item")


def validate_structure(manifest: dict[str, Any]) -> None:
    """Schema and format checks that need no inventory (the owner path uses these).

    A manifest names the sentinel VMID it was built for and the digest of the overrides it was
    classified with; without a valid sentinel VMID it is refused here, so no dry-run, check or
    render proceeds (R3-1). No item may be the sentinel guest or carry its VMID in a volume name."""
    if not isinstance(manifest, dict):
        raise ManifestError("a manifest must be a JSON object")
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ManifestError("manifest_version must be 1")
    if not (isinstance(manifest.get("node"), str) and _NODE.fullmatch(manifest["node"])):
        raise ManifestError("node is missing or malformed")
    try:
        sentinel = _int_vmid(manifest.get("sentinel_vmid"))
    except ClassificationError as exc:
        raise ManifestError(f"manifest has no valid sentinel_vmid ({exc}); rebuild it with manifest build") from None
    odigest = manifest.get("overrides_digest")
    if not isinstance(odigest, str) or not _SHA256.fullmatch(odigest):
        raise ManifestError("manifest has no valid overrides_digest; rebuild it with manifest build")
    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        raise ManifestError("items must be a non-empty list")
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ManifestError("every item must be an object")
        _check_item(item, seen)
        problem = _sentinel_problem(item["id"], _ID.fullmatch(item["id"]), sentinel)
        if problem:
            raise ManifestError(problem)
        if item["current_state"].get("node") != manifest["node"]:
            raise ManifestError(f"{item['id']}: node differs from the manifest node")
        seen.add(item["id"])


def validate(manifest: dict[str, Any], inventory: dict[str, Any],
             classification: dict[str, dict[str, str]]) -> None:
    """Full check: structure, every item is a REMOVE_CANDIDATE, state matches the inventory."""
    validate_structure(manifest)
    require_complete(inventory, "manifest")
    check_classification(classification)
    for item in manifest["items"]:
        cls = classification.get(item["id"], {}).get("class", "UNKNOWN")
        if cls != "REMOVE_CANDIDATE":
            raise ManifestError(f"{item['id']}: classified {cls}; only REMOVE_CANDIDATE may be removed")
    # The classification must come from the same sentinel and the same overrides as the manifest.
    # On the owner path the classification is recomputed from the settings and the overrides file
    # given at apply time, so a changed settings value or a changed overrides file is refused here.
    sentinel, overrides = classification_binding(classification)
    if sentinel != manifest["sentinel_vmid"]:
        raise ManifestError(f"manifest was built for sentinel VMID {manifest['sentinel_vmid']}, but the "
                            f"classification has {sentinel}")
    if overrides != manifest["overrides_digest"]:
        raise ManifestError(f"overrides digest is {overrides}, but the manifest was classified with "
                            f"{manifest['overrides_digest']}; the overrides file changed since the manifest was built")
    mismatches = revalidate(manifest, inventory)
    if mismatches:
        raise ManifestError("state differs from the inventory: " + "; ".join(mismatches))


def validate_for_apply(manifest: dict[str, Any], inventory: dict[str, Any],
                       classification: dict[str, dict[str, str]]) -> None:
    """The check before a manifest may be rendered for the host: the manifest must be bound
    to this inventory by its inventory_digest, and the full validation must pass."""
    validate_structure(manifest)
    require_complete(inventory, "manifest")  # also refuses an inventory that is not an object
    bound = manifest.get("inventory_digest")
    if not isinstance(bound, str) or not bound:
        raise ManifestError("manifest has no inventory_digest; rebuild it with manifest build")
    actual = digest(inventory)
    if bound != actual:
        raise ManifestError(f"inventory digest is {actual}, but the manifest was built from {bound}")
    validate(manifest, inventory, classification)


def _actual_state(item: dict[str, Any], index: dict[str, tuple[str, dict[str, Any]]],
                  node: str) -> dict[str, Any] | None:
    kind, res = index.get(item["id"], (None, None))
    if res is None or kind != ("guest" if item["type"] in ("qemu", "lxc") else "volume"):
        return None
    if kind == "guest":
        return {"node": res.get("node"), "name": res.get("name"), "status": res.get("status"),
                "digest": res.get("digest"), "template": bool(res.get("template"))}
    return {"node": node, "storage": res.get("storage"), "size": res.get("size")}


def revalidate(manifest: dict[str, Any], inventory: dict[str, Any]) -> list[str]:
    """Compare every item's recorded state with a fresh inventory. Empty list = unchanged."""
    index = resources(inventory)
    problems = []
    for item in manifest["items"]:
        actual = _actual_state(item, index, inventory.get("node", ""))
        if actual is None:
            problems.append(f"{item['id']}: no longer exists")
            continue
        for key, expected in item["current_state"].items():
            if key in actual and actual[key] != expected:
                problems.append(f"{item['id']}: {key} was {expected!r}, now {actual[key]!r}")
    return problems


def build(inventory: dict[str, Any], classification: dict[str, dict[str, str]],
          backup_storage: str | None = None) -> dict[str, Any]:
    """Draft a manifest from every REMOVE_CANDIDATE. The owner reviews and edits it."""
    require_complete(inventory, "manifest")
    index = resources(inventory)
    check_classification(classification)
    sentinel, overrides = classification_binding(classification)
    items = []
    for rid in sorted(classification):
        if classification[rid]["class"] != "REMOVE_CANDIDATE":
            continue
        kind, res = index.get(rid, (None, None))
        if res is None:
            raise ManifestError(f"{rid}: classified REMOVE_CANDIDATE but not in the inventory")
        # Never drop a requested removal silently: the owner would believe it is in the manifest.
        if kind not in ("guest", "volume"):
            raise ManifestError(f"{rid}: classified REMOVE_CANDIDATE, but a manifest removes only guests and "
                                "volumes; remove it by hand or classify it differently")
        if not _ID.fullmatch(rid):
            raise ManifestError(f"{rid}: classified REMOVE_CANDIDATE, but its id is not a form a manifest can "
                                "carry safely; remove it by hand")
        if kind == "guest":
            state = {"node": res["node"], "name": res["name"], "status": res["status"],
                     "digest": res["digest"], "template": bool(res["template"])}
            op = "delete-purge" if res["status"] == "stopped" else "stop-and-delete-purge"
            item = {"id": rid, "type": res["type"], "current_state": state, "operation": op,
                    "backup": "vzdump" if backup_storage else "config-only",
                    "reversible": "from-backup" if backup_storage else "no",
                    "expected_result": f"{rid} absent",
                    "verify": f"{rid} not in /cluster/resources"}
            if backup_storage:
                item["backup_storage"] = backup_storage
        else:
            state = {"node": inventory["node"], "storage": res["storage"], "size": res["size"]}
            item = {"id": rid, "type": "volume", "current_state": state, "operation": "free",
                    "backup": "none", "reversible": "no", "expected_result": f"{rid} absent",
                    "verify": f"{res['volid']} not in storage content"}
        item.update({"reason": classification[rid].get("reason", ""), "dependencies": []})
        items.append(item)
    if not items:
        raise ManifestError("no REMOVE_CANDIDATE resources; nothing to put in a manifest")
    built = {"manifest_version": MANIFEST_VERSION, "node": inventory["node"],
             "sentinel_vmid": sentinel, "overrides_digest": overrides,
             "inventory_digest": digest(inventory), "items": items}
    validate_structure(built)  # a draft that could not pass the check is refused now, not later
    return built


def dry_run(manifest: dict[str, Any]) -> str:
    """Human-readable plan. Pure: no I/O, no side effects."""
    lines = [f"Manifest for node {manifest['node']}: {len(manifest['items'])} item(s)",
             f"sha256 {manifest_hash(manifest)}",
             f"sentinel VMID {manifest.get('sentinel_vmid')} (never removed); "
             f"overrides sha256 {manifest.get('overrides_digest')}", ""]
    for n, item in enumerate(manifest["items"], start=1):
        state = ", ".join(f"{k}={v}" for k, v in sorted(item["current_state"].items()))
        lines += [f"{n}. {item['id']} [{item['type']}] -> {item['operation']}",
                  f"   requires: {state}",
                  f"   backup: {item['backup']}{' to ' + item['backup_storage'] if item.get('backup_storage') else ''}"
                  f"; reversible: {item['reversible']}",
                  f"   reason: {item['reason']}",
                  f"   expect: {item['expected_result']}; verify: {item['verify']}"]
    return "\n".join(lines)


def render_host_script(manifest: dict[str, Any], inventory: dict[str, Any],
                       classification: dict[str, dict[str, str]]) -> str:
    """Bash body for host-run: fixed operations, validated and quoted arguments only.

    Rendering is reachable only through the full, inventory-bound validation.

    DISABLED FOR EXECUTION in this version, by two independent means. The body's first command is
    ``cl_destructive_gate`` (``host/lib.sh``): in an ordinary shell it exits 7 before anything on the
    host is read or changed. A shell in which ``exit`` has been replaced runs past it and does read
    the host; what holds then is that the stop, backup, destroy and free commands are not in the
    library text at all. The text after the gate is a preview of what an enabled version would run;
    it is not a script that can be applied."""
    validate_for_apply(manifest, inventory, classification)
    q = shlex.quote
    index = resources(inventory)

    def guard(item: dict[str, Any]) -> str:
        # Live checks on the host against CL_SENTINEL_VMID and CL_POOL (from the settings):
        # never the sentinel; a guest's live pool is the one it was inventoried in; a volume is
        # not the sentinel's and no guest outside the pool references it.
        if item["type"] in ("qemu", "lxc"):
            return " ".join(["cl_guard_guest", q(item["type"]), q(item["id"].split("/", 1)[1]),
                             q(index[item["id"]][1]["pool"])])
        return " ".join(["cl_guard_volume", q(item["current_state"]["storage"]), q(item["id"].split("/", 1)[1])])

    # Every guest and storage the manifest names must be found by the listings the guards rely on,
    # and the sentinel must be in the guest listing: exit 6. These are controls that detect SOME
    # truncated listings; they do not prove that a listing is complete (UNPROVEN, see the report).
    guests = sorted({f"{i['type']}/{i['id'].split('/', 1)[1]}" for i in manifest["items"]
                     if i["type"] in ("qemu", "lxc")})
    storages = sorted({i["current_state"]["storage"] for i in manifest["items"] if i["type"] == "volume"}
                      | {i["backup_storage"] for i in manifest["items"] if i.get("backup") == "vzdump"})
    out = ["# DISABLED: destructive execution is not available in this version. In an ordinary shell the next",
           "# command exits 7 before anything is read or changed, and the stop, backup, destroy and free",
           "# commands are not in this script at all. The rest of it is a preview only.",
           "cl_destructive_gate apply-manifest",
           f"CL_NODE={q(manifest['node'])}",
           f"cl_expect_sentinel {q(str(manifest['sentinel_vmid']))}",  # before anything else: exit 6
           f"cl_require_listed {q(' '.join(guests))} {q(' '.join(storages))}",
           f"CL_MANIFEST_SHA256={q(manifest_hash(manifest))}",
           'cl_log "manifest $CL_MANIFEST_SHA256 on node $CL_NODE"',
           'cl_log "live safety checks for every item, before any change"']
    out += [guard(item) for item in manifest["items"]]
    out.append('cl_log "live safety checks passed"')
    for n, item in enumerate(manifest["items"], start=1):
        s = item["current_state"]
        label = f"item {n}: {item['id']} {item['operation']}"
        out.append(f"cl_log {q(label)}")
        if item["type"] in ("qemu", "lxc"):
            vmid = item["id"].split("/", 1)[1]
            out.append(" ".join(["cl_expect_guest", q(item["type"]), q(vmid), q(s["node"]), q(s["name"]),
                                 q(s["status"]), q(s["digest"]), "1" if s["template"] else "0"]))
            if item["backup"] == "vzdump":
                # vzdump --mode stop stops and restarts a guest: same approved-state, lock and task
                # checks as before stop and destroy, right before it
                out.append(" ".join(["cl_backup_guest", q(item["type"]), q(vmid), q(s["node"]), q(s["name"]),
                                     q(s["status"]), q(s["digest"]), "1" if s["template"] else "0",
                                     q(item["backup_storage"])]))
            elif item["backup"] == "config-only":
                out.append(" ".join(["cl_dump_config", q(item["type"]), q(vmid)]))
            # Each destructive command re-checks the whole approved state itself (digest included),
            # that no lock and no task is active, and every volume the destruction would delete.
            # The check and the command are still two steps: see the note above cl_prestate.
            if item["operation"] == "stop-and-delete-purge":
                out.append(guard(item))
                out.append(" ".join(["cl_stop_guest", q(item["type"]), q(vmid), q(s["node"]), q(s["name"]),
                                     q(s["status"]), q(s["digest"]), "1" if s["template"] else "0"]))
            out.append(guard(item))
            out.append(" ".join(["cl_destroy_guest", q(item["type"]), q(vmid), q(s["node"]), q(s["name"]),
                                 "stopped", q(s["digest"]), "1" if s["template"] else "0"]))
            out.append(" ".join(["cl_verify_guest_absent", q(vmid)]))
        else:
            volid = item["id"].split("/", 1)[1]
            out.append(" ".join(["cl_expect_volume", q(s["storage"]), q(volid), q(str(s["size"]))]))
            out.append(guard(item))
            out.append(" ".join(["cl_free_volume", q(s["storage"]), q(volid), q(str(s["size"]))]))
            out.append(" ".join(["cl_verify_volume_absent", q(s["storage"]), q(volid)]))
        out.append(f"cl_log {q(f'item {n}: done')}")
    out.append('cl_log "manifest complete"')
    return "\n".join(out) + "\n"
