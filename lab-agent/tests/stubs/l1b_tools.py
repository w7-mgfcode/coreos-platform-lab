#!/usr/bin/env python3
"""Offline stand-ins for the host tools the action scripts call as root.

One file, many names: the test harness symlinks it as pvesh, qm, pveum, pvesm, vzdump, curl,
useradd, passwd, getent, id, hostname, chown, install and stat inside a temporary directory
that comes first on PATH. State is JSON in $STUB_STATE, every call is appended to $STUB_LOG.

The shapes it returns are the ones the scripts parse; they were chosen by the test author,
not observed on a Proxmox host. Passing against this stub says nothing about live shapes.

State keys (all optional): resources, configs, content, pools, storages, users, tokens,
acl, acl_list, passwd, foreign (paths reported as owned by another user), writable (paths
reported as mode 777), real_modes (paths whose real mode bits are shown unmasked), fail (list of "tool arg arg" prefixes that exit 9), garbage (map of
such prefixes to text printed instead of the normal answer), curl_src, curl_fail.
"""

import json
import os
import subprocess
import sys

tool = os.path.basename(sys.argv[0])
args = sys.argv[1:]
state_path = os.environ["STUB_STATE"]
with open(state_path, encoding="utf-8") as fh:
    state = json.load(fh)
with open(os.environ["STUB_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps([tool] + args) + "\n")
NODE = state.get("node", "pve1")


def save():
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def fail(msg, code=9):
    sys.stderr.write(f"{tool} stub: {msg}\n")
    sys.exit(code)


def out(obj):
    sys.stdout.write(json.dumps(obj))


call = " ".join([tool] + args)
for prefix in state.get("fail", []):
    if call.startswith(prefix):
        fail(f"injected failure for '{prefix}'")
for prefix, text in state.get("garbage", {}).items():
    if call.startswith(prefix):
        sys.stdout.write(text)
        sys.exit(0)


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


def find_resource(vmid):
    return next((r for r in state.setdefault("resources", []) if r.get("vmid") == vmid), None)


def add_volume(storage, volid, vmid, content="images"):
    state.setdefault("content", {}).setdefault(storage, []).append(
        {"volid": volid, "vmid": vmid, "content": content, "size": 1073741824})


if tool == "pvesh" and args[:1] == ["get"]:
    path = args[1]
    parts = path.strip("/").split("/")
    if path == "/cluster/resources":
        out(state.get("resources", []))
    elif path == "/pools":
        out(state.get("pools", []))
    elif path == "/storage":
        out(state.get("storages", []))
    elif len(parts) == 5 and parts[0] == "nodes" and parts[2] == "qemu" and parts[4] == "config":
        cfg = state.get("configs", {}).get(parts[3])
        if cfg is None:
            fail("no such config")
        out(cfg)
    elif len(parts) == 5 and parts[0] == "nodes" and parts[2] == "storage" and parts[4] == "content":
        items = state.get("content", {}).get(parts[3], [])
        if "--vmid" in args:
            items = [i for i in items if str(i.get("vmid")) == opt("--vmid")]
        if "--content" in args:
            items = [i for i in items if i.get("content") == opt("--content")]
        out(items)
    else:
        fail(f"unsupported path {path}")
elif tool == "pveum" and args[:2] == ["user", "list"]:
    out(state.get("users", []))
elif tool == "pveum" and args[:2] == ["user", "add"]:
    state.setdefault("users", []).append({"userid": args[2]})
    save()
elif tool == "pveum" and args[:3] == ["user", "token", "list"]:
    out(state.get("tokens", {}).get(args[3], []))
elif tool == "pveum" and args[:3] == ["user", "token", "add"]:
    state.setdefault("tokens", {}).setdefault(args[3], []).append({"tokenid": args[4]})
    save()
    out({"full-tokenid": f"{args[3]}!{args[4]}", "value": "test-only-token-value-not-a-secret"})
elif tool == "pveum" and args[:2] == ["acl", "modify"]:
    state.setdefault("acl", []).append(args[2:])
    save()
elif tool == "pveum" and args[:2] == ["acl", "list"]:
    out(state.get("acl_list", []))
elif tool == "pveum" and args[:2] == ["pool", "add"]:
    state.setdefault("pools", []).append({"poolid": args[2]})
    save()
elif tool == "pvesm" and args[:2] == ["add", "dir"]:
    state.setdefault("storages", []).append(
        {"storage": args[2], "type": "dir", "path": opt("--path"), "content": opt("--content")})
    save()
elif tool == "pvesm" and args[:1] == ["status"]:
    print(f"Name Type Status\n{opt('--storage')} dir active")
elif tool == "vzdump":
    add_volume(opt("--storage"), f"{opt('--storage')}:backup/vzdump-qemu-{args[0]}.vma.zst", int(args[0]), "backup")
    save()
elif tool == "qm" and args[:1] == ["create"]:
    vmid = int(args[1])
    if find_resource(vmid):
        fail("VMID exists")
    cfg = {"digest": "f" * 40, "name": opt("--name"), "memory": opt("--memory"), "cores": opt("--cores")}
    for key in ("description", "net0", "serial0", "vga", "scsihw", "ostype", "cpu"):
        if opt("--" + key) is not None:
            cfg[key] = opt("--" + key)
    disk = opt("--scsi0")
    if disk:
        storage = disk.split(":", 1)[0]
        cfg["scsi0"] = f"{storage}:vm-{vmid}-disk-0,size=1G"
        add_volume(storage, f"{storage}:vm-{vmid}-disk-0", vmid)
    state.setdefault("configs", {})[str(vmid)] = cfg
    state["resources"].append({"id": f"qemu/{vmid}", "type": "qemu", "vmid": vmid, "node": NODE,
                               "name": opt("--name"), "status": "stopped", "template": 0,
                               **({"pool": opt("--pool")} if opt("--pool") else {})})
    save()
elif tool == "qm" and args[:2] == ["disk", "import"]:
    vmid, src, storage = int(args[2]), args[3], args[4]
    with open(src, "rb") as fh:  # the image must exist and be readable at import time
        state.setdefault("imported", []).append({"vmid": vmid, "bytes": len(fh.read()), "src": os.path.basename(src)})
    state["configs"][str(vmid)]["scsi0"] = f"{storage}:vm-{vmid}-disk-0,size=10G"
    add_volume(storage, f"{storage}:vm-{vmid}-disk-0", vmid)
    save()
elif tool == "qm" and args[:1] == ["set"]:
    vmid = int(args[1])
    cfg = state["configs"][str(vmid)]
    if opt("--ide2"):
        storage = opt("--ide2").split(":", 1)[0]
        cfg["ide2"] = f"{storage}:vm-{vmid}-cloudinit,media=cdrom"
        add_volume(storage, f"{storage}:vm-{vmid}-cloudinit", vmid)
    if opt("--boot"):
        cfg["boot"] = opt("--boot")
    save()
elif tool == "qm" and args[:1] == ["template"]:
    vmid = int(args[1])
    cfg = state["configs"][str(vmid)]
    cfg["template"] = "1"
    cfg["scsi0"] = cfg["scsi0"].replace(":vm-", ":base-")
    find_resource(vmid)["template"] = 1
    save()
elif tool == "curl":
    if state.get("curl_fail"):
        fail("curl: (22) simulated failure", 22)
    target = opt("-o")
    with open(state["curl_src"], "rb") as src, open(target, "wb") as dst:
        dst.write(src.read())
elif tool == "useradd":
    state.setdefault("passwd", {})[args[-1]] = f"{args[-1]}:x:900:900:{opt('--comment')}:{opt('--home-dir')}:{opt('--shell')}"
    save()
elif tool == "passwd":
    pass
elif tool == "getent" and args[:1] == ["passwd"]:
    line = state.get("passwd", {}).get(args[1])
    if line is None:
        sys.exit(2)
    print(line)
elif tool == "id":
    sys.exit(0 if args[-1] in state.get("passwd", {}) else 1)
elif tool == "hostname":
    print(NODE)
elif tool == "chown":
    pass  # logged only: the test user cannot chown to root
elif tool == "install":
    # Same call without -o/-g: the test user is not root. Everything else is the real install.
    real, skip = ["/usr/bin/install"], False
    for a in args:
        if skip:
            skip = False
        elif a in ("-o", "-g"):
            skip = True
        else:
            real.append(a)
    sys.exit(subprocess.run(real, check=False).returncode)
elif tool == "stat":
    # Ownership and mode as root would see a correctly set up host, unless the state says
    # otherwise: owner 0 and no group/other write bit, except for the listed paths.
    real_stat = "/usr/bin/stat"
    if "-c" in args and args[args.index("-c") + 1] in ("%u", "%a") and not args[-1].startswith("-"):
        fmt, path = args[args.index("-c") + 1], args[-1]
        if fmt == "%u":
            print(1000 if path in state.get("foreign", []) else 0)
        else:
            real = subprocess.run([real_stat, "-c", "%a", "--", path], capture_output=True, text=True, check=True)
            mode = int(real.stdout.strip(), 8)
            if path in state.get("writable", []):
                print("777")
            elif path in state.get("real_modes", []):
                print(format(mode, "o"))  # the file's real mode bits, not masked
            else:
                print(format(mode & ~0o022, "o"))
    else:
        sys.exit(subprocess.run([real_stat] + args, check=False).returncode)
else:
    fail(f"unsupported call {call}")
