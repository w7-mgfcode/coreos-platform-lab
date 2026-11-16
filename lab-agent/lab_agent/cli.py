"""lab-agent: the routine (Mode A) command line. Read-only against the host, except
through the pinned MCP server it launches. Every output file goes to PVE_LAB_STATE,
outside the repository, with mode 600.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import stat
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from . import baseline as bl
from . import classify as cl
from . import inventory as inv
from . import manifest as mf
from . import mcp
from .config import ConfigError, is_refusal, load
from .hostrun import write_private
from .pveapi import Client
from .redact import redact, redact_uuids, sanitize, scan


def _read_json(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except RecursionError:  # a deeply nested file is a bad input, not a crash
        raise ValueError(f"{Path(path).name}: JSON nested too deeply") from None


def _write_json(path: Path, obj: Any) -> None:
    """Write ``obj`` as JSON, mode 600, through the private-write path of the owner tooling: the
    parent is created 700 (with its ancestors) or must already be a private directory of this
    user, a symlink at the destination is refused rather than followed, and the file is replaced
    atomically."""
    write_private(path, (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _write_public_text(path: Path, text: str) -> None:
    """Write sanitized evidence that is meant to be published. Not private, but written by atomic
    replacement: a temporary file next to the destination, created exclusively and without
    following a link, then renamed over the destination name. The rename replaces the *name*, so
    a symlink or a hard link at the destination can never make this write into the file it points
    at; a symlink or directory at the destination is refused outright."""
    path = Path(path)
    try:
        existing = os.lstat(path)
    except FileNotFoundError:
        existing = None
    if existing is not None and not stat.S_ISREG(existing.st_mode):
        raise ConfigError(f"{path.name}: exists and is not a regular file (symlink?); refusing to replace it")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    for _ in range(16):
        tmp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
        try:
            fd = os.open(tmp, flags, 0o666)  # the umask decides the mode of published evidence
            break
        except FileExistsError:
            continue
    else:
        raise ConfigError(f"{path.name}: could not create a temporary file next to it")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def cmd_discover(args, cfg) -> int:
    """Exit 0 when every endpoint was read, 1 when the written inventory is incomplete."""
    client = Client.from_config(cfg)
    collected = inv.collect(client, cfg.get("PVE_NODE"))
    normal = inv.normalize(collected)
    out = Path(args.out_dir) if args.out_dir else cfg.state_dir() / f"inventory-{datetime.now():%Y%m%dT%H%M%S}"
    _write_json(out / "raw.json", collected)
    _write_json(out / "inventory.json", normal)
    print(f"inventory {out / 'inventory.json'}: {len(normal['guests'])} guests, "
          f"{len(normal['storages'])} storages, {len(normal['volumes'])} volumes, "
          f"{len(normal['errors'])} endpoint errors; digest {inv.digest(normal)[:16]}")
    for path, err in sorted(normal["errors"].items()):
        print(f"  not read: {path}: {redact_uuids(redact(str(err)))}")
    if normal["errors"]:
        print(f"INCOMPLETE: {len(normal['errors'])} endpoint(s) not read; classify, manifest and baseline "
              "refuse when they depend on one of them")
        return 1
    return 0


def cmd_classify(args, cfg) -> int:
    inventory = _read_json(args.inventory)
    overrides = _read_json(args.overrides) if args.overrides else None
    no_sentinel = bool(getattr(args, "no_sentinel", False))
    result = cl.classify(inventory, overrides=overrides, **cl.config_context(cfg, no_sentinel=no_sentinel))
    _write_json(Path(args.out), result)
    if no_sentinel:
        print("no-sentinel mode: this classification cannot feed a manifest")
    counts: dict[str, int] = {}
    for rid, v in result.items():
        if rid == cl.BINDING_ID:  # the reserved binding entry is not a resource
            continue
        counts[v["class"]] = counts.get(v["class"], 0) + 1
    print(" ".join(f"{k}={counts.get(k, 0)}" for k in cl.CLASSES))
    lo, hi = cfg.vmid_range()
    conflicts = cl.vmid_range_conflicts(inventory, lo, hi, cfg.get("PVE_POOL"))
    for c in conflicts:
        print(f"VMID range conflict: {c}")
    return 1 if conflicts else 0


def cmd_inventory(args, cfg) -> int:
    """``inventory verify``: is this inventory exactly what ``normalize`` makes of that raw data?
    Exit 0 when it is, 2 on any difference (a refusal: the inventory is not trustworthy)."""
    inventory, raw = _read_json(args.inventory), _read_json(args.raw)
    problems = inv.verify_against_raw(inventory, raw)
    for problem in problems:
        print(f"inventory verify: {problem}")
    if problems:
        print(f"inventory verify: {len(problems)} difference(s); do not use this inventory", file=sys.stderr)
        return 2
    print("inventory verify: the inventory is exactly what its raw data gives")
    return 0


def cmd_manifest(args, cfg) -> int:
    if args.action == "build":
        # The classification file is checked, not trusted: it is recomputed from the settings, the
        # inventory and the overrides, and any difference is a refusal (exit 2).
        overrides = _read_json(args.overrides) if args.overrides else None
        m = mf.build_trusted(_read_json(args.inventory), _read_json(args.classification), overrides,
                             cl.config_context(cfg), args.backup_storage)
        _write_json(Path(args.out), m)
        print(f"draft manifest {args.out}: {len(m['items'])} item(s); sha256 {mf.manifest_hash(m)}")
        return 0
    m = mf.load(args.file)
    if args.action == "hash":
        print(mf.manifest_hash(m))
    elif args.action == "dry-run":
        mf.validate_structure(m)
        print(mf.dry_run(m))
    elif args.action == "check":
        overrides = _read_json(args.overrides) if args.overrides else None
        mf.check_trusted(m, _read_json(args.inventory), _read_json(args.classification), overrides,
                         cl.config_context(cfg))
        print(f"manifest checked against inventory {args.inventory}; the classification file "
              f"{args.classification} matches the classification recomputed from the settings, the inventory "
              f"and the overrides; sha256 {mf.manifest_hash(m)}")
    return 0


def cmd_baseline(args, cfg) -> int:
    pool = cfg.get("PVE_POOL")
    if args.action == "save":
        _write_json(Path(args.out), bl.snapshot(_read_json(args.inventory), pool))
        print(f"baseline written to {args.out}")
        return 0
    stored = _read_json(args.baseline)
    if args.inventory:
        current = _read_json(args.inventory)
    else:
        current = inv.normalize(inv.collect(Client.from_config(cfg), cfg.get("PVE_NODE")))
    diffs = bl.compare(stored, bl.snapshot(current, pool))
    for d in diffs:
        print(d)
    print("baseline: no drift" if not diffs else f"baseline: {len(diffs)} difference(s)")
    return 1 if diffs else 0


def cmd_sanitize(args, cfg) -> int:
    text = Path(args.input).read_text(encoding="utf-8")
    clean = sanitize(text, cfg.sanitize_map())
    findings = scan(clean, cfg.sanitize_map())
    if findings:
        print("refusing to write: " + "; ".join(findings), file=sys.stderr)
        return 1
    _write_public_text(Path(args.output), clean)
    print(f"sanitized {args.input} -> {args.output}")
    return 0


def cmd_scan(args, cfg) -> int:
    mapping = cfg.sanitize_map() if cfg else {}
    bad = 0
    for name in args.files:
        findings = scan(Path(name).read_text(encoding="utf-8", errors="replace"), mapping)
        for f in findings:
            print(f"{name}: {f}")
        bad += bool(findings)
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lab-agent", description="Routine Proxmox lab tooling (Mode A).")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover", help="read-only API inventory")
    d.add_argument("--out-dir")
    c = sub.add_parser("classify", help="classify an inventory and check the VMID range")
    c.add_argument("--inventory", required=True)
    c.add_argument("--overrides")
    c.add_argument("--out", required=True)
    c.add_argument("--no-sentinel", action="store_true",
                   help="classify before a sentinel exists: no removal can be proposed and the result "
                        "cannot feed a manifest")
    iv = sub.add_parser("inventory", help="inventory checks")
    ivsub = iv.add_subparsers(dest="action", required=True)
    ivv = ivsub.add_parser("verify", help="check an inventory against the raw data it was made from")
    ivv.add_argument("--inventory", required=True)
    ivv.add_argument("--raw", required=True)
    m = sub.add_parser("manifest", help="cleanup manifest tools")
    msub = m.add_subparsers(dest="action", required=True)
    mb = msub.add_parser("build")
    mb.add_argument("--inventory", required=True)
    mb.add_argument("--classification", required=True)
    mb.add_argument("--overrides", help="the overrides the classification was made with (optional)")
    mb.add_argument("--backup-storage")
    mb.add_argument("--out", required=True)
    for name in ("hash", "dry-run"):
        msub.add_parser(name).add_argument("file")
    mc = msub.add_parser("check")
    mc.add_argument("file")
    mc.add_argument("--inventory", required=True)
    mc.add_argument("--classification", required=True)
    mc.add_argument("--overrides", help="the overrides the classification was made with (optional)")
    b = sub.add_parser("baseline", help="record or verify the prepared state")
    bsub = b.add_subparsers(dest="action", required=True)
    bs = bsub.add_parser("save")
    bs.add_argument("--inventory", required=True)
    bs.add_argument("--out", required=True)
    bv = bsub.add_parser("verify")
    bv.add_argument("--baseline", required=True)
    bv.add_argument("--inventory", help="compare with this file instead of a live read")
    s = sub.add_parser("sanitize", help="sanitize evidence for the public repository")
    s.add_argument("input")
    s.add_argument("output")
    sc = sub.add_parser("scan", help="report anything that must not be published")
    sc.add_argument("files", nargs="+")
    sub.add_parser("mcp-install", help=f"install the pinned MCP server ({mcp.PIN['commit'][:12]})")
    sub.add_parser("mcp-launch", help="start the MCP server on stdio (used by .mcp.json)")
    args = p.parse_args(argv)
    try:
        if args.cmd == "scan":
            try:
                cfg = load()
            except ConfigError:
                cfg = None
            return cmd_scan(args, cfg)
        cfg = load()
        if args.cmd == "mcp-install":
            print(f"installed {mcp.install(cfg)}")
            return 0
        if args.cmd == "mcp-launch":
            mcp.launch(cfg)
            return 0
        return {"discover": cmd_discover, "classify": cmd_classify, "manifest": cmd_manifest,
                "baseline": cmd_baseline, "sanitize": cmd_sanitize, "inventory": cmd_inventory}[args.cmd](args, cfg)
    except Exception as exc:  # noqa: BLE001
        # Every refusal type any lab_agent module raises (ConfigError, ManifestError,
        # ClassificationError, IncompleteInventoryError, PveError, HostRunError, and any added
        # later), plus OS and value errors (which include bad JSON), is an exit 2 with one
        # line. Anything else is a bug and keeps its traceback.
        if not is_refusal(exc):
            raise
        print(f"lab-agent: {redact_uuids(redact(str(exc)))}", file=sys.stderr)
        return 2
