#!/usr/bin/env bash
# Network-less acceptance run of the whole unit suite. A separate command: it is NOT part of
# tests/run.sh. It shows that the suite cannot make a real network connection, including from
# child processes and native code, which no Python-level guard can guarantee: the tests run in
# a container that has no network namespace peers at all (--network none, loopback only).
#
# Inside the container, BEFORE any test, a proof program checks that
#   - the only network interface is lo, and
#   - a connect to a routable test address (RFC 5737 / RFC 3849) fails at once, not by timeout.
# If either proof fails the run is FAIL and the tests are not started.
#
# The script never pulls, builds or installs: a missing docker, daemon or local image is
# INCOMPLETE. It mounts nothing writable from the host (the repository, /usr, the synthetic
# user files and the proof directory are all read-only) and never the docker socket. The
# container is removed by --rm; the script checks that none is left and removes a leftover.
#
# Exit status:
#   0  RESULT: PASS        proofs held, every test ran and passed (none skipped), no container left
#   1  RESULT: FAIL        a proof failed, a test failed or no test ran, or a container was left
#   2  RESULT: INCOMPLETE  nothing failed, but docker, the daemon or the image is absent, or a
#                          test was skipped; the run says what is missing
set -uo pipefail

here=$(cd "$(dirname "$0")/.." && pwd)   # lab-agent/
repo=$(cd "$here/.." && pwd)             # mounted read-only as /work
IMAGE="python:3.12.14-slim"
label="corelab-netless=$$.$RANDOM"

if ! scratch=$(mktemp -d "${TMPDIR:-/tmp}/corelab-netless.XXXXXXXX"); then
  echo "FAIL   cannot create a private temporary directory"; echo; echo "RESULT: FAIL"; exit 1
fi

# Remove our own container if it is still there (interrupt, daemon trouble), then the scratch.
remove_ours() {
  command -v docker >/dev/null 2>&1 || return 0
  local ids
  ids=$(docker ps -a -q --filter "label=$label" 2>/dev/null) || return 0
  [ -z "$ids" ] || docker rm -f $ids >/dev/null 2>&1
}
cleanup() { remove_ours; rm -rf "$scratch"; }
trap cleanup EXIT
trap 'exit 130' INT TERM

incomplete() {   # incomplete REASON...
  echo "INCOMPLETE  $*"
  echo
  echo "RESULT: INCOMPLETE (not a pass; $*)"
  exit 2
}

if ! command -v docker >/dev/null 2>&1; then
  incomplete "docker not found on PATH"
fi
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  incomplete "image $IMAGE not present locally or docker daemon unreachable (this script does not pull)"
fi

uid=$(id -u); gid=$(id -g)

# Synthetic user files: root and one user with the caller's numeric ids (ssh refuses to run
# without a user entry). No real account data is copied.
{ echo "root:x:0:0:root:/root:/bin/sh"
  [ "$uid" -eq 0 ] || echo "tester:x:$uid:$gid:synthetic user:/tmp/home:/bin/sh"; } >"$scratch/passwd"
{ echo "root:x:0:"
  [ "$gid" -eq 0 ] || echo "tester:x:$gid:"; } >"$scratch/group"

# The proof program, run inside the container before the tests.
cat >"$scratch/proof.py" <<'PY'
import errno
import socket
import sys
import time

problems = []
ifaces = sorted(name for _, name in socket.if_nameindex())
print("NETLESS-PROOF interfaces: " + ",".join(ifaces))
if ifaces != ["lo"]:
    problems.append("interfaces other than lo: " + ",".join(n for n in ifaces if n != "lo"))

for family, addr in ((socket.AF_INET, "192.0.2.1"), (socket.AF_INET6, "2001:db8::1")):
    t0 = time.monotonic()
    try:
        s = socket.socket(family, socket.SOCK_STREAM)
    except OSError as exc:
        print(f"NETLESS-PROOF connect {addr}: no socket of this family ({errno.errorcode.get(exc.errno, exc.errno)})")
        continue
    s.settimeout(3)
    try:
        s.connect((addr, 9))
        problems.append(f"connect to {addr} succeeded")
        print(f"NETLESS-PROOF connect {addr}: SUCCEEDED")
    except TimeoutError:
        problems.append(f"connect to {addr} timed out instead of failing at once")
        print(f"NETLESS-PROOF connect {addr}: TIMEOUT")
    except OSError as exc:
        took = time.monotonic() - t0
        print(f"NETLESS-PROOF connect {addr}: refused {errno.errorcode.get(exc.errno, exc.errno)} in {took:.2f}s")
        if took > 1.0:
            problems.append(f"connect to {addr} took {took:.2f}s to fail")
    finally:
        s.close()

if problems:
    print("NETLESS-PROOF: FAILED " + "; ".join(problems))
    sys.exit(1)
print("NETLESS-PROOF: HELD")
PY
chmod 0755 "$scratch"; chmod 0644 "$scratch"/*

log="$scratch/run.log"
echo "running the unit suite in $IMAGE with --network none (loopback only)"
docker run --rm --pull=never --label "$label" \
  --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 512 --memory 2g --user "$uid:$gid" \
  -v /usr:/usr:ro -v "$repo:/work:ro" -v "$scratch:/netless:ro" \
  -v "$scratch/passwd:/etc/passwd:ro" -v "$scratch/group:/etc/group:ro" \
  --tmpfs /tmp:exec,mode=1777 \
  -e HOME=/tmp/home -e PYTHONDONTWRITEBYTECODE=1 -e TMPDIR=/tmp \
  -w /work/lab-agent "$IMAGE" /usr/bin/sh -c \
  'mkdir -p /tmp/home && /usr/bin/python3 /netless/proof.py && /usr/bin/python3 -m unittest discover -v -s tests -t .' \
  >"$log" 2>&1
run_rc=$?

failed=()
skipped=()

# Proofs. Their lines are shown either way.
grep -E '^NETLESS-PROOF' "$log" | sed 's/^/  /'
if grep -q '^NETLESS-PROOF: HELD$' "$log"; then
  proofs_held=1
else
  proofs_held=0
  failed+=("network-less proof did not hold: the tests ran (or not) without it")
fi

# Unit tests.
ran=$(grep -Eo '^Ran [0-9]+ tests?' "$log" | tail -n 1)
summary=$(grep -E '^(OK|FAILED)( \(.*\))?$' "$log" | tail -n 1)
nran=$(printf '%s' "$ran" | grep -Eo '[0-9]+' || true)
nskip=$(printf '%s' "$summary" | grep -Eo 'skipped=[0-9]+' | cut -d= -f2 || true)
if [ "$proofs_held" -eq 1 ]; then
  if [ "$run_rc" -ne 0 ] || [ "${summary%% *}" != OK ] || [ -z "$nran" ] || [ "$nran" -eq 0 ]; then
    failed+=("python unit tests (${ran:-no tests ran}; ${summary:-no summary line}; exit $run_rc)")
  elif [ -n "$nskip" ] && [ "$nskip" -gt 0 ]; then
    skipped+=("python unit tests ($ran; $summary): $nskip test(s) skipped")
  fi
fi
echo "  ${ran:-no unittest summary} / ${summary:-no result line}"
grep -E '\.\.\. skipped' "$log" | sed 's/^/  skipped test: /'

if [ "${#failed[@]}" -gt 0 ]; then
  echo "  --- output without passing tests ---"
  grep -v -E ' \.\.\. ok$' "$log" | sed 's/^/  /'
fi

# No container left behind.
left=$(docker ps -a -q --filter "label=$label" 2>/dev/null || true)
if [ -n "$left" ]; then
  failed+=("a container with label $label was left behind (removed now)")
  remove_ours
else
  echo "  no container left behind"
fi

echo
for c in "${failed[@]}"; do echo "failed:  $c"; done
for c in "${skipped[@]}"; do echo "skipped: $c"; done
if [ "${#failed[@]}" -gt 0 ]; then
  echo "RESULT: FAIL (${#failed[@]} failed, ${#skipped[@]} skipped)"
  exit 1
elif [ "${#skipped[@]}" -gt 0 ]; then
  echo "RESULT: INCOMPLETE (${#skipped[@]} skipped; not a pass)"
  exit 2
fi
echo "RESULT: PASS (network-less proofs held; $ran; $summary)"
exit 0
