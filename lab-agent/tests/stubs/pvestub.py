#!/usr/bin/env python3
"""Offline stand-in for pvesh, qm, pct, pvesm, pveum and vzdump.

Each tool is a symlink to this file. State lives in $STUB_STATE (JSON); every call is
appended to $STUB_LOG. Only the subcommands the host scripts use are implemented; any
other call fails loudly so a test cannot pass by accident.

What it models (from the Proxmox documentation as the author understands it, NOT observed on a
real host): the resource, storage and content listings; a guest's active config (``configs``) and
the pending changes on top of it (``pending_changes``): the default config view is the active
config with the pending values applied, ``--current 1`` is the active config alone, ``/pending``
lists each key's current and pending value; snapshots with their own configs (``snapshots``); a
node task list (``tasks``); a config ``lock`` key; ``destroy`` deleting the guest's configured and
snapshot volumes and every volume owned by its VMID, recorded in ``deleted_volumes``; and
``triggers``, which change the state after a matching call, to model another actor acting
between a check and a command.

``destroy_extra`` (per VMID) lists volumes that destroy deletes although no config, snapshot or name
says so (a stand-in for backing-chain or storage-level dependencies; it exists to show what the guard
cannot see). Ownership for the deletion model is the listing's vmid or ``-<id>-`` inside the volume name,
written differently from the guard's prefix-based rule, so the model does not just echo the guard; the
config-volume selection (disk keys, no iso/vztmpl/snippets/import/backup) is still the same idea as the
guard's and is NOT independent evidence that the real deletion set is complete.

What it does NOT model: backing-chain or linked-clone dependencies between volumes, replication,
HA or backup jobs, storage-level locks, the real error text and exit codes of the tools, partial
failure of a destroy, tasks that appear by themselves, a listing whose records differ from the
shapes above, API permissions, or how `vzdump`, `qm stop` or `destroy` change a config digest on
a real host (here they do not). A stub PASS therefore proves the script's logic against these
models, never the host's behaviour.
"""

import json
import os
import re
import sys

tool = os.path.basename(sys.argv[0])
args = sys.argv[1:]
state_path = os.environ["STUB_STATE"]
with open(state_path) as fh:
    state = json.load(fh)
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(json.dumps([tool] + args) + "\n")

DISK_KEY = re.compile(r"^(?:(?:scsi|virtio|ide|sata|efidisk|tpmstate|unused|mp)\d*|rootfs|vmstate)$")
VOLUME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*:[^\s,]+$")
NOT_OWNED = re.compile(r"^[^:]+:(?:iso|vztmpl|snippets|import|backup)/")
NAMED = re.compile(r"(?:^|[/:])(?:vm|base|subvol|basevol)-(\d+)-|vzdump-(?:qemu|lxc)-(\d+)-")


def save():
    with open(state_path, "w") as fh:
        json.dump(state, fh)


def out(obj):
    sys.stdout.write(json.dumps(obj))


def fail(msg):
    sys.stderr.write(f"{tool} stub: {msg}\n")
    sys.exit(9)


def active_config(vmid):
    cfg = state["configs"].get(str(vmid))
    if cfg is None:
        fail("no such config")
    return cfg


def default_config(vmid):
    cfg = dict(active_config(vmid))
    cfg.update(state.get("pending_changes", {}).get(str(vmid), {}))
    return cfg


def volumes_of(vmid):
    """Every volume destroying the guest deletes in the model: configured and snapshot volumes
    that are not iso/vztmpl/snippets/import/backup files, plus everything owned by the VMID."""
    found = []
    docs = [active_config(vmid)] + list(state.get("snapshots", {}).get(str(vmid), {}).values())
    for doc in docs:
        for key, value in doc.items():
            if not DISK_KEY.match(key) or not isinstance(value, str):
                continue
            for item in value.split(","):
                item = re.sub(r"^[A-Za-z][A-Za-z0-9_-]*=", "", item.strip())
                if VOLUME.match(item) and not NOT_OWNED.match(item) and item not in found:
                    found.append(item)
    for items in state["content"].values():
        for v in items:
            named = [int(a or b) for a, b in NAMED.findall(v["volid"])]
            if NOT_OWNED.match(v["volid"]):
                continue
            # ownership as the stub sees it: the listing's vmid, or the id between dashes anywhere in the
            # volume name (written differently from the guard's own prefix-based rule on purpose)
            owned = v.get("vmid") == int(vmid) or re.search(rf"-{int(vmid)}-", v["volid"].split(":", 1)[1])
            if (owned or int(vmid) in named) and v["volid"] not in found:
                found.append(v["volid"])
    for extra in state.get("destroy_extra", {}).get(str(vmid), []):  # dependencies nobody enumerated
        if extra not in found:
            found.append(extra)
    return found


def run():
    if tool == "pvesh" and args[:1] == ["get"]:
        path = args[1]
        current = "--current" in args and args[args.index("--current") + 1] in ("1", "true")
        parts = path.split("/")  # '', nodes, NODE, TYPE, VMID, ...
        if path in state.get("raw", {}):
            # A test can make any listing come back as exactly this text with exit status 0
            # ("null", "", "[]", "{not json"), to prove a caller does not read it as "nothing found".
            sys.stdout.write(state["raw"][path])
        elif "/snapshot" in path:
            snaps = state.get("snapshots", {}).get(parts[4], {})
            if len(parts) == 6:
                out([{"name": "current"}] + [{"name": n} for n in snaps])
            elif len(parts) == 8 and parts[7] == "config" and parts[6] in snaps:
                out(snaps[parts[6]])
            else:
                fail("no such snapshot")
        elif path == "/cluster/resources":
            kind = args[args.index("--type") + 1] if "--type" in args else None
            # --type vm lists guests only (qemu and lxc), as the real endpoint does
            out([r for r in state["resources"] if kind != "vm" or r.get("type") in ("qemu", "lxc")])
        elif path.endswith("/pending") and len(parts) == 6:
            changes = state.get("pending_changes", {}).get(parts[4], {})
            rows = []
            for key, value in active_config(parts[4]).items():
                row = {"key": key, "value": value}
                if key in changes:
                    row["pending"] = changes[key]
                rows.append(row)
            rows += [{"key": k, "pending": v} for k, v in changes.items() if k not in active_config(parts[4])]
            out(rows)
        elif path.endswith("/config"):
            out(active_config(parts[4]) if current else default_config(parts[4]))  # /nodes/N/TYPE/VMID/config
        elif path.endswith("/content"):
            out(state["content"].get(parts[4], []))
        elif len(parts) == 4 and parts[3] == "storage":  # /nodes/N/storage
            out(state.get("node_storages") or [{"storage": s, "active": 1} for s in state["content"]])
        elif len(parts) == 4 and parts[3] == "tasks":  # /nodes/N/tasks
            tasks = state.get("tasks", [])
            if "--source" in args and args[args.index("--source") + 1] == "active":
                tasks = [t for t in tasks if "endtime" not in t]  # a task with an endtime is finished
            out(tasks)
        elif path == "/pools":
            out(state.get("pools", []))
        elif path == "/storage":
            out(state.get("storages", []))
        else:
            fail(f"unsupported path {path}")
    elif tool in ("qm", "pct") and args[:1] == ["destroy"]:
        vmid = int(args[1])
        if state["configs"].get(str(vmid), {}).get("lock") and "--skiplock" not in args:
            fail("can't destroy a locked guest")
        gone = volumes_of(vmid)
        for st in state["content"]:
            state["content"][st] = [v for v in state["content"][st] if v["volid"] not in gone]
        state.setdefault("deleted_volumes", []).extend(gone)
        state["resources"] = [r for r in state["resources"] if r.get("vmid") != vmid]
        state["configs"].pop(str(vmid), None)
        state.get("snapshots", {}).pop(str(vmid), None)
        state.get("pending_changes", {}).pop(str(vmid), None)
    elif tool in ("qm", "pct") and args[:1] == ["stop"]:
        if state["configs"].get(args[1], {}).get("lock"):
            fail("can't stop a locked guest")
        for r in state["resources"]:
            if r.get("vmid") == int(args[1]):
                r["status"] = "stopped"
    elif tool == "vzdump":
        pass
    elif tool == "pvesm" and args[:1] == ["free"]:
        volid = args[1]
        for st in state["content"]:
            state["content"][st] = [v for v in state["content"][st] if v["volid"] != volid]
        state.setdefault("deleted_volumes", []).append(volid)
    elif tool == "pveum" and args[:2] == ["user", "list"]:
        out(state.get("users", []))
    elif tool == "pveum" and args[:2] == ["user", "add"]:
        state.setdefault("users", []).append({"userid": args[2]})
    elif tool == "pveum" and args[:3] == ["user", "token", "list"]:
        out(state.get("tokens", {}).get(args[3], []))
    elif tool == "pveum" and args[:3] == ["user", "token", "add"]:
        state.setdefault("tokens", {}).setdefault(args[3], []).append({"tokenid": args[4]})
        out({"full-tokenid": f"{args[3]}!{args[4]}", "value": "11111111-2222-3333-4444-555555555555"})
    elif tool == "pveum" and args[:2] == ["acl", "modify"]:
        state.setdefault("acl", []).append(args[2:])
    else:
        fail(f"unsupported call {args}")


def fire_triggers():
    """Another actor acting right after a call: each trigger fires once, after the first call
    whose [tool, *args] starts with its ``on`` list. It can change an active config, add pending
    changes, add or replace snapshots, set the task list, or add a content record."""
    call = [tool] + args
    for trig in state.get("triggers", []):
        if trig.get("fired") or call[: len(trig["on"])] != trig["on"]:
            continue
        trig["fired"] = True
        for vmid, changes in trig.get("config", {}).items():
            state["configs"].setdefault(vmid, {}).update(changes)
        for vmid, changes in trig.get("pending", {}).items():
            state.setdefault("pending_changes", {}).setdefault(vmid, {}).update(changes)
        for vmid, snaps in trig.get("snapshots", {}).items():
            state.setdefault("snapshots", {}).setdefault(vmid, {}).update(snaps)
        if "tasks" in trig:
            state["tasks"] = trig["tasks"]
        for st, rec in trig.get("content", {}).items():
            state["content"].setdefault(st, []).append(rec)


run()
fire_triggers()
save()
