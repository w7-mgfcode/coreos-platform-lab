#!/usr/bin/env bash
# O-4 harness: the real snippet writer behind a real sshd, with a separate identity.
#
# What it does
#   Starts ONE throwaway container from an image that is already present locally, with
#   --network none (loopback only), a read-only root file system, no host mounts except
#   read-only copies of this workstation's own sshd, ssh and perl, and tmpfs for all state. In
#   it, container root plays the host's root: the extracted "snippet writer" section of
#   host/actions/prepare.sh creates the non-root user corelab-snip, the root-owned
#   snippet directory (2770, root:corelab-snip), the writer and its config and the
#   authorized_keys line (restrict,from=...,command=...). The workstation's sshd then serves
#   that user on the container's loopback and the cases S1-S9 of plan 9.5 run through it
#   with a real ssh client. Each negative case has a control in the same run (the allowed
#   command, a key without restrict, a nologin shell). See tests/o4/README-style notes in
#   the L1B report for what this does and does not prove.
#
# Never pulls, builds, installs or downloads. No real host, address or credential is used.
#
# Result contract (same as tests/run.sh):
#   0  RESULT: PASS        every case ran and passed
#   1  RESULT: FAIL        a case failed or did not run
#   2  RESULT: INCOMPLETE  a prerequisite is missing; it is named
#
# Environment: O4_IMAGE       any local image; it only supplies the empty container
#              O4_WRITER_DIR  directory with corelab-snippet-put and snippet-writer.conf (default: repository)
#              O4_PREPARE     prepare.sh to extract the snippet-writer section from (default: repository)
#              The last two exist so a mutation of the writer or of prepare.sh can be checked on a scratch copy.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
la=$(cd "$here/../.." && pwd)
IMAGE=${O4_IMAGE:-python:3.12.14-slim}
# Inputs under test. The defaults are the repository files; mutation checks point these at scratch copies.
WRITER_DIR=${O4_WRITER_DIR:-$la/host/snippet-writer}
PREPARE=${O4_PREPARE:-$la/host/actions/prepare.sh}

# The cases the inner script must report as PASS (a missing one is a FAIL, not a pass).
EXPECTED_CASES="I0 I1 I2 I3 S1.1 S1.2 S1.3 S1.4 S2.1 S2.2 S3.1 S4.1 S4.2 S5.1 S5.2 S5.3 S5.4 S5.5 S6.1 S6.2 \
S7.1 S7.2 S7.3 S7.4 S7.5 S7.6 S7.7 S7.8 S7.9 S7.10 S8.1 S8.2 S8.3 S8.4 S9.1 S9.2 D1 D2 X1 X2 X3"

missing=()
need_file() { [ -e "$1" ] || missing+=("$2: $1 not found"); }
need_exec() { [ -x "$1" ] || missing+=("$2: $1 not executable"); }
for t in sshd:/usr/sbin/sshd ssh:/usr/bin/ssh ssh-keygen:/usr/bin/ssh-keygen ssh-agent:/usr/bin/ssh-agent \
         ssh-add:/usr/bin/ssh-add perl:/usr/bin/perl setpriv:/usr/bin/setpriv bash:/usr/bin/bash \
         useradd:/usr/sbin/useradd usermod:/usr/sbin/usermod passwd:/usr/bin/passwd ss:/usr/bin/ss od:/usr/bin/od; do
  need_exec "${t#*:}" "workstation tool ${t%%:*}"
done
[ -d /usr/lib/openssh ] || missing+=("workstation tool sshd helpers: /usr/lib/openssh not found")
[ -d /usr/lib64 ] || missing+=("workstation layout: /usr/lib64 not found")
perl -MJSON::PP -MDigest::SHA -e1 2>/dev/null || missing+=("perl modules JSON::PP and Digest::SHA")
for f in "$WRITER_DIR/corelab-snippet-put" "$WRITER_DIR/snippet-writer.conf" "$PREPARE" "$here/inner.sh"; do
  [ -r "$f" ] || missing+=("repository file $f is not readable")
done
if ! command -v docker >/dev/null 2>&1; then
  missing+=("docker not found on PATH")
elif ! docker info >/dev/null 2>&1; then
  missing+=("docker daemon not reachable")
elif ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  missing+=("image $IMAGE not present locally (the harness does not pull; set O4_IMAGE to any local image)")
fi
if [ "${#missing[@]}" -gt 0 ]; then
  for m in "${missing[@]}"; do echo "MISSING $m"; done
  echo
  echo "RESULT: INCOMPLETE (${#missing[@]} prerequisite(s) missing; no case ran; not a pass)"
  exit 2
fi

scratch=$(mktemp -d "${TMPDIR:-/tmp}/corelab-o4.XXXXXXXX") || { echo "RESULT: FAIL (no scratch directory)"; exit 1; }
name="corelab-o4-$$-$RANDOM"
# Last-resort cleanup (interrupt, early exit). The normal path cleans up explicitly below and
# checks the outcome.
trap 'docker rm -f "$name" >/dev/null 2>&1; rm -rf "$scratch"' EXIT
trap 'exit 130' INT TERM

listeners() { ss -ltnH 2>/dev/null | awk '{print $4}' | sort | sha256sum | cut -c1-16; }
before=$(listeners)

# Capabilities: only what a root-run sshd, useradd and setpriv need. No NET_ADMIN, SYS_ADMIN
# or NET_RAW; no privileged mode; no device; no host network; no docker socket.
caps=(CHOWN DAC_OVERRIDE FOWNER FSETID KILL SETGID SETUID SETPCAP SYS_CHROOT)
capargs=(--cap-drop ALL); for c in "${caps[@]}"; do capargs+=(--cap-add "$c"); done

# The image supplies only the empty container (its own /proc, /dev, /dev/pts and mounts).
# The workstation's userland is laid over /usr read-only, so sshd, ssh, perl, useradd and the
# shell are the ones installed here. /etc, /var, /run, /root, /home, /srv and /usr/local/sbin
# are tmpfs: they start empty and vanish with the container.
log="$scratch/container.log"
envargs=(); for v in O4_SHOW_SSHD_LOG O4_SSHD_LOG_LINES; do [ -z "${!v:-}" ] || envargs+=(-e "$v=${!v}"); done
# --pull=never: the image was inspected above, but if the tag vanished since, docker must fail
# instead of pulling it.
docker run --rm --pull=never --name "$name" --label corelab.o4=1 --network none --read-only "${capargs[@]}" "${envargs[@]}" \
  --security-opt no-new-privileges --pids-limit 256 --memory 512m --cpus 2 \
  --tmpfs /etc:rw,exec,suid,mode=0755,size=16m --tmpfs /var:rw,exec,mode=0755,size=64m --tmpfs /run:rw,mode=0755,size=16m \
  --tmpfs /root:rw,mode=0700 --tmpfs /home:rw,mode=0755 --tmpfs /srv:rw,mode=0755 --tmpfs /tmp:rw,exec,size=256m \
  --tmpfs /usr/local/sbin:rw,exec,mode=0755 \
  -v /usr/bin:/usr/bin:ro -v /usr/sbin:/usr/sbin:ro -v /usr/lib:/usr/lib:ro \
  -v /usr/lib64:/usr/lib64:ro -v /usr/share:/usr/share:ro \
  -v "$WRITER_DIR:/o4/snippet-writer:ro" -v "$PREPARE:/o4/prepare.sh:ro" -v "$here/inner.sh:/o4/inner.sh:ro" \
  --entrypoint /usr/bin/bash "$IMAGE" /o4/inner.sh > "$log" 2>&1
rc=$?

after=$(listeners)

# Cleanup, verified: the container is gone (it was started with --rm; if it is not, remove it),
# and the scratch directory is gone. A cleanup that cannot be verified is a FAIL.
cleanup_problems=()
ids=$(docker ps -a --filter "name=^/${name}\$" -q 2>/dev/null) || { cleanup_problems+=("cannot query docker for the container"); ids=""; }
if [ -n "$ids" ]; then
  docker rm -f "$name" >/dev/null 2>&1 || cleanup_problems+=("docker rm -f $name failed")
  ids=$(docker ps -a --filter "name=^/${name}\$" -q 2>/dev/null) || ids="unknown"
  [ -z "$ids" ] || cleanup_problems+=("container $name still present")
fi
leftover=${cleanup_problems[*]:-}

# Show the report, then evaluate it. The container's own verdict is not trusted: every case line
# is parsed, counted and compared with the expected list.
cat "$log"
echo
echo "container exit status: $rc"

declare -A seen=()
dups=(); unexpected=(); nlogfail=0; nlogpass=0; other=()
while read -r kind id verdict _; do
  [ "$kind" = CASE ] || continue
  if [ -n "${seen[$id]+x}" ]; then dups+=("$id"); fi
  case " $EXPECTED_CASES " in *" $id "*) ;; *) unexpected+=("$id") ;; esac
  case "$verdict" in
    PASS) nlogpass=$((nlogpass+1)) ;;
    FAIL) nlogfail=$((nlogfail+1)) ;;
    *)    other+=("$id:$verdict") ;;
  esac
  # a FAIL is never overwritten by a later verdict for the same case
  if [ "${seen[$id]:-}" != FAIL ]; then seen[$id]=$verdict; fi
done < "$log"
nfail=0; nmiss=0; npass=0
for id in $EXPECTED_CASES; do
  case "${seen[$id]:-}" in
    PASS) npass=$((npass+1)) ;;
    FAIL) nfail=$((nfail+1)) ;;
    *)    nmiss=$((nmiss+1)); echo "case did not run: $id" ;;
  esac
done
[ "${#dups[@]}" -eq 0 ] || echo "duplicate verdicts for: ${dups[*]}"
[ "${#unexpected[@]}" -eq 0 ] || echo "unexpected cases reported: ${unexpected[*]}"
[ "${#other[@]}" -eq 0 ] || echo "unrecognised verdicts: ${other[*]}"

# Completion line: exactly one, last in the log, and its counts equal what was parsed.
done_line=$(grep -c '^INNER-DONE ' "$log")
done_ok=0
if [ "$done_line" -eq 1 ] && [ "$(grep -v '^$' "$log" | tail -n 1 | cut -c1-11)" = "INNER-DONE " ]; then
  dl=$(grep '^INNER-DONE ' "$log")
  dpass=${dl#*pass=}; dpass=${dpass%% *}
  dfail=${dl#*fail=}; dfail=${dfail%% *}
  if [ "$dpass" = "$nlogpass" ] && [ "$dfail" = "$nlogfail" ] && [ "$nlogpass" -eq "$npass" ]; then done_ok=1
  else echo "INNER-DONE counts (pass=$dpass fail=$dfail) do not match the case lines (pass=$nlogpass fail=$nlogfail; expected passes $npass)"; fi
else
  echo "completion line missing, repeated or not last (found $done_line)"
fi
echo "host listeners before/after (hash of 'ss -ltn', informational): $before / $after"
echo "cleanup: ${leftover:-container and scratch verified gone}"

# An explicit case FAIL outranks INCOMPLETE: a run that recorded a failure and then hit a missing
# prerequisite is reported as FAIL (the INCOMPLETE lines are still shown).
if grep -q '^INCOMPLETE ' "$log"; then
  grep '^INCOMPLETE ' "$log" | sed 's/^INCOMPLETE /MISSING /'
  if [ "$nlogfail" -eq 0 ]; then
    echo; echo "RESULT: INCOMPLETE (a prerequisite inside the container is missing; not a pass)"; exit 2
  fi
fi
rm -rf "$scratch"
[ ! -e "$scratch" ] || cleanup_problems+=("scratch directory $scratch not removed")
leftover=${cleanup_problems[*]:-}
# The host listener hash is informational: other processes on a shared workstation may open or
# close sockets while this runs. The evidence that the container had no network is the --network
# none flag above plus cases X2 and X3 (only loopback, every listener on 127.0.0.1).
if [ "$rc" -ne 0 ] || [ "$nfail" -gt 0 ] || [ "$nmiss" -gt 0 ] || [ "$done_ok" -ne 1 ] || [ "${#dups[@]}" -gt 0 ] \
   || [ "${#unexpected[@]}" -gt 0 ] || [ "${#other[@]}" -gt 0 ] || [ "$nlogfail" -gt 0 ] || [ -n "$leftover" ]; then
  echo
  echo "RESULT: FAIL (container exit $rc, $nfail case(s) failed, $nmiss did not run, ${#dups[@]} duplicate, ${#unexpected[@]} unexpected, completion ok=$done_ok, cleanup=${leftover:-ok})"
  exit 1
fi
echo
echo "RESULT: PASS (all $npass cases ran and passed once each, container exit 0; offline, container root, not the Proxmox host)"
exit 0
