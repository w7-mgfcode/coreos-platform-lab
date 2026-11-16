#!/usr/bin/bash
# O-4 harness, inner half. Runs as container root in a container that has the workstation's own
# sshd, ssh and perl laid over /usr (read-only), with the container's loopback as its only network.
# Started by run-o4.sh, never by hand. Everything here is synthetic: throwaway host and user
# keys, throwaway users, tmpfs-only state. It prints one line per case:
#   CASE <id> PASS|FAIL <text>      NOTE <text>      and finally  INNER-DONE ...
# Exit: 0 all cases passed, 1 a case failed or did not run, 2 a prerequisite is missing.
#
# Fidelity: the real writer, the real config template and the real "snippet writer" section of
# prepare.sh (extracted, not retyped) are used. See run-o4.sh and the report for what a
# container root does not reproduce compared with the Proxmox host.
set -uo pipefail

O4=/o4                       # read-only inputs: writer, template, prepare.sh, this script
W=/tmp/o4                    # scratch (tmpfs)
LAB=/srv/corelab-lab         # stands for CL_LAB_STORAGE_PATH
SNIPDIR=$LAB/snippets
WRITER=/usr/local/sbin/corelab-snippet-put
PORT=2222
SRC_OK=127.0.0.2             # stands for the workstation address in from="..."
SRC_BAD=127.0.0.3
export PATH=/usr/bin:/usr/sbin

pass=0; fail=0
declare -a failed_ids=()
c_ok()  { printf 'CASE %s PASS %s\n' "$1" "$2"; pass=$((pass+1)); }
c_bad() { printf 'CASE %s FAIL %s%s\n' "$1" "$2" "${3:+ -- $3}"; fail=$((fail+1)); failed_ids+=("$1"); }
note()  { printf 'NOTE %s\n' "$*"; }
# check ID TEXT -- evaluates the remaining command line; PASS if it succeeds
check() { local id=$1 text=$2; shift 2; if "$@"; then c_ok "$id" "$text"; else c_bad "$id" "$text" "$(declare -p OUT ERR RC 2>/dev/null | tr '\n' ' ' | cut -c1-300)"; fi; }
incomplete() { printf 'INCOMPLETE %s\n' "$*"; exit 2; }
[ -c /dev/null ] && [ -c /dev/urandom ] && [ -r /proc/self/status ] || { echo "INCOMPLETE container lacks /dev/null, /dev/urandom or /proc"; exit 2; }
need() { command -v "$1" >/dev/null 2>&1 || incomplete "tool missing inside the harness container: $1"; }

for t in ssh ssh-keygen ssh-agent ssh-add perl setpriv useradd usermod passwd sha256sum stat install timeout ln od ss; do need "$t"; done
[ -x /usr/sbin/sshd ] || incomplete "sshd missing inside the harness container"
[ -x /usr/lib/openssh/sshd-session ] || [ -x /usr/lib/openssh/sshd-auth ] || incomplete "sshd helper programs missing"

# ---------------------------------------------------------------- base system (tmpfs only)
mkdir -p /var/log /var/run /etc/ssh /etc/corelab /etc/skel /etc/default /etc/pve /run/sshd /var/lib /var/mail \
         /var/lib/vz/snippets "$W" "$LAB"
chmod 0755 /etc/pve /var/lib/vz/snippets /run/sshd /usr/local/sbin
cat > /etc/passwd <<'EOF'
root:x:0:0:root:/root:/bin/sh
sshd:x:100:65534:privilege separation:/run/sshd:/usr/sbin/nologin
nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin
EOF
cat > /etc/group <<'EOF'
root:x:0:
nogroup:x:65534:
EOF
printf 'root:*:19000:0:99999:7:::\nsshd:*:19000:0:99999:7:::\nnobody:*:19000:0:99999:7:::\n' > /etc/shadow
printf 'root:*::\nnogroup:*::\n' > /etc/gshadow
chmod 0640 /etc/shadow /etc/gshadow
cat > /etc/login.defs <<'EOF'
MAIL_DIR /var/mail
UID_MIN 1000
UID_MAX 60000
SYS_UID_MIN 100
SYS_UID_MAX 999
GID_MIN 1000
GID_MAX 60000
SYS_GID_MIN 100
SYS_GID_MAX 999
CREATE_HOME no
USERGROUPS_ENAB yes
UMASK 022
ENCRYPT_METHOD SHA512
EOF
echo 'secret-owned-by-root' > /srv/o4-root-owned; chmod 0600 /srv/o4-root-owned
SENTINEL_SHA=$(sha256sum < /srv/o4-root-owned)

# ---------------------------------------------------------------- keys
mkdir -p /etc/o4; chmod 0700 /etc/o4
ssh-keygen -q -t ed25519 -N '' -C o4-snip      -f /etc/o4/id_snip   || incomplete "ssh-keygen failed"
ssh-keygen -q -t ed25519 -N '' -C o4-open      -f /etc/o4/id_open   || incomplete "ssh-keygen failed"
ssh-keygen -q -t ed25519 -N '' -C o4-nologin   -f /etc/o4/id_nolog  || incomplete "ssh-keygen failed"
ssh-keygen -q -t ed25519 -N '' -C o4-hostkey   -f /etc/ssh/ssh_host_ed25519_key || incomplete "ssh-keygen failed"
printf '[127.0.0.1]:%s %s\n' "$PORT" "$(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)" > /etc/o4/known_hosts

# ---------------------------------------------------------------- the real prepare.sh section
# Everything between "# 3. snippet writer" and "# 4. routine ACLs", run with the same inputs
# the owner-run action would have, with the writer and template read from the repository.
cl_die() { echo "cl_die $1: $2"; exit "$1"; }
cl_log() { echo "cl_log: $*"; }
cl_file_snippet_writer() { cat "$O4/snippet-writer/corelab-snippet-put"; }
cl_file_snippet_writer_conf() { cat "$O4/snippet-writer/snippet-writer.conf"; }
# The pieces of prepare.sh that the snippet-writer part needs, cut out by their own markers:
# the fixed-location assignments, the block from "# snippet writer:" up to "# 4. routine ACLs",
# and every la_* helper function that block calls (found by name, transitively). Nothing is
# retyped. A missing start or end marker, or a helper that cannot be found, is INCOMPLETE and
# names what is missing; it is never read as a result.
grep -q '^# snippet writer:' "$O4/prepare.sh" || incomplete "prepare.sh has no '# snippet writer:' start marker"
grep -q '^# 4\. routine ACLs' "$O4/prepare.sh" || incomplete "prepare.sh has no '# 4. routine ACLs' end marker"
sed -n '/^# snippet writer:/,/^# 4\. routine ACLs/{/^# 4\. routine ACLs/!p}' "$O4/prepare.sh" > "$W/block.sh"
[ -s "$W/block.sh" ] || incomplete "the snippet-writer block of prepare.sh is empty"
grep -q 'command="/usr/local/sbin/corelab-snippet-put"' "$W/block.sh" || incomplete "the snippet-writer block of prepare.sh writes no authorized_keys line"
{
  echo 'export LC_ALL=C'
  sed -n -e '/^la_sbin=/p' -e '/^la_cfgdir=/p' -e '/^la_home=/p' "$O4/prepare.sh"
  echo 'la_tmps=()'
  echo 'la_hint=""'
} > "$W/helpers.sh"
for marker in '^la_sbin=' '^la_cfgdir=' '^la_home='; do
  grep -q -e "$marker" "$W/helpers.sh" || incomplete "cannot extract from prepare.sh: $marker not found"
done
: > "$W/funcs.sh"; added=" "
while :; do
  changed=0
  for n in $(cat "$W/block.sh" "$W/funcs.sh" | grep -oE '\bla_[a-z_]+' | sort -u); do
    case "$added" in *" $n "*) continue ;; esac
    if grep -q "^$n() {" "$O4/prepare.sh"; then
      sed -n "/^$n() {/,/^}/p" "$O4/prepare.sh" >> "$W/funcs.sh"; added="$added$n "; changed=1
    fi
  done
  [ "$changed" -eq 1 ] || break
done
grep -q '^la_root_dir() {' "$W/funcs.sh" || incomplete "cannot extract from prepare.sh: la_root_dir not found"
{ cat "$W/helpers.sh" "$W/funcs.sh"; echo 'snip_dir="$CL_LAB_STORAGE_PATH/snippets"'; cat "$W/block.sh"; } > "$W/section3.sh"
echo "NOTE extracted from prepare.sh: block $(wc -l < "$W/block.sh") lines, helpers:$added"
install -d -m 0755 -o root -g root "$LAB"
install -d -m 0755 "$SNIPDIR"
export CL_LAB_STORAGE_PATH=$LAB CL_WORKSTATION_ADDR=$SRC_OK
CL_SNIP_PUBKEY=$(cut -d' ' -f1,2 /etc/o4/id_snip.pub); export CL_SNIP_PUBKEY
# shellcheck disable=SC1091,SC1090
( set -euo pipefail; . "$W/section3.sh" ) > "$W/prepare-section.log" 2>&1
prc=$?
sed 's/^/  prepare.sh§3: /' "$W/prepare-section.log"
if [ "$prc" -ne 0 ]; then
  c_bad I0 "the real prepare.sh snippet-writer section ran in the harness" "exit $prc; no further case can run"
  printf 'INNER-DONE pass=%d fail=%d failed=%s\n' "$pass" "$fail" "${failed_ids[*]:-none}"
  exit 1
fi
c_ok I0 "the real prepare.sh snippet-writer section ran in the harness (exit 0)"
SNIP_UID=$(id -u corelab-snip 2>/dev/null) || incomplete "corelab-snip was not created by the extracted prepare.sh section"
SNIP_GID=$(id -g corelab-snip)

# Control users, created next to the real one:
#   corelab-open    same forced command, same key options but WITHOUT restrict (control)
#   corelab-nologin same as the real user but with a nologin shell (checks the plan's inference)
useradd --system --create-home --home-dir /var/lib/corelab-open --shell /bin/sh corelab-open
useradd --system --create-home --home-dir /var/lib/corelab-nologin --shell /usr/sbin/nologin corelab-nologin
for u in open nologin; do
  install -d -m 0700 -o "corelab-$u" -g "corelab-$u" "/var/lib/corelab-$u/.ssh"
done
[ -s /var/lib/corelab-snip/.ssh/authorized_keys ] || { c_bad I0 "prepare.sh section wrote no authorized_keys"; printf 'INNER-DONE pass=%d fail=%d failed=%s\n' "$pass" "$fail" "${failed_ids[*]:-none}"; exit 1; }
# The same line as prepare.sh writes, with the key of the user (nologin), or without "restrict" (open).
sed "s#^restrict,#restrict,#; s# ssh-ed25519 .*# $(cut -d' ' -f1,2 /etc/o4/id_nolog.pub)#" \
    /var/lib/corelab-snip/.ssh/authorized_keys > /var/lib/corelab-nologin/.ssh/authorized_keys
sed "s#^restrict,##; s# ssh-ed25519 .*# $(cut -d' ' -f1,2 /etc/o4/id_open.pub)#" \
    /var/lib/corelab-snip/.ssh/authorized_keys > /var/lib/corelab-open/.ssh/authorized_keys
for u in open nologin; do
  chown "corelab-$u:corelab-$u" "/var/lib/corelab-$u/.ssh/authorized_keys"; chmod 0600 "/var/lib/corelab-$u/.ssh/authorized_keys"
done
# the open and nologin users write into the same snippet directory group, as a control for modes only
passwd -l corelab-open >/dev/null 2>&1; passwd -l corelab-nologin >/dev/null 2>&1
# corelab-plain: an ordinary login (no forced command, no key options); control for the sftp subsystem
ssh-keygen -q -t ed25519 -N '' -C o4-plain -f /etc/o4/id_plain || incomplete "ssh-keygen failed"
useradd --system --create-home --home-dir /var/lib/corelab-plain --shell /bin/sh corelab-plain
install -d -m 0700 -o corelab-plain -g corelab-plain /var/lib/corelab-plain/.ssh
cut -d' ' -f1,2 /etc/o4/id_plain.pub > /var/lib/corelab-plain/.ssh/authorized_keys
chown corelab-plain:corelab-plain /var/lib/corelab-plain/.ssh/authorized_keys; chmod 0600 /var/lib/corelab-plain/.ssh/authorized_keys
passwd -l corelab-plain >/dev/null 2>&1

# ---------------------------------------------------------------- sshd (host's own binary)
cat > /etc/ssh/sshd_config <<EOF
# Minimal, deliberately permissive defaults: forwarding, agent and tty stay ON server-wide,
# so only "restrict" in authorized_keys can be what refuses them. UsePAM yes like Debian's
# default (needed: prepare.sh locks the password, and sshd refuses a locked account without
# PAM), but with a minimal PAM stack, not the host's.
ListenAddress 127.0.0.1
Port $PORT
HostKey /etc/ssh/ssh_host_ed25519_key
PidFile /run/sshd.pid
UsePAM yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
StrictModes yes
AllowTcpForwarding yes
AllowAgentForwarding yes
PermitTTY yes
PrintLastLog no
Subsystem sftp /usr/lib/openssh/sftp-server
LogLevel DEBUG1
EOF
mkdir -p /etc/pam.d
cat > /etc/pam.d/sshd <<'EOF2'
auth    required pam_permit.so
account required pam_unix.so
account required pam_permit.so
session required pam_permit.so
EOF2
/usr/sbin/sshd -t -f /etc/ssh/sshd_config || incomplete "sshd rejects the harness configuration"
/usr/sbin/sshd -D -e -f /etc/ssh/sshd_config > "$W/sshd.log" 2>&1 &
SSHD_PID=$!
up=0
for _ in $(seq 1 50); do
  if (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null; then up=1; break; fi
  kill -0 "$SSHD_PID" 2>/dev/null || incomplete "sshd exited at start: $(tail -n 3 "$W/sshd.log" | tr '\n' ' ')"
  sleep 0.2
done
[ "$up" -eq 1 ] || incomplete "sshd did not listen on the container loopback"

# ---------------------------------------------------------------- client helpers
KEY_SNIP=/etc/o4/id_snip
SSHBASE=(ssh -F /dev/null -o BatchMode=yes -o IdentitiesOnly=yes -o UserKnownHostsFile=/etc/o4/known_hosts
         -o StrictHostKeyChecking=yes -o ConnectTimeout=10)
OUT=; ERR=; RC=
# rssh STDIN-FILE REMOTE-COMMAND [extra ssh options...]   (REMOTE-COMMAND "-" = no command)
# Variables USER_, SRC and KEY choose identity, source address and key.
rssh() {
  local in=$1 cmd=$2; shift 2
  local args=("${SSHBASE[@]}" -p "${PORT_:-$PORT}" -b "${SRC:-$SRC_OK}" -i "${KEY:-$KEY_SNIP}" "$@" "${USER_:-corelab-snip}@127.0.0.1")
  [ "$cmd" = "-" ] || args+=(-- "$cmd")
  OUT=$(timeout 30 "${args[@]}" < "$in" 2> "$W/err"); RC=$?
  ERR=$(cat "$W/err")
}
logmark() { LOGMARK=$(wc -l < "$W/sshd.log"); }
logsince() { sleep 0.4; tail -n +"$((LOGMARK + 1))" "$W/sshd.log"; }
files_in_dir() { ls -A "$SNIPDIR" | sort | tr '\n' ' '; }

mk_ign() { # mk_ign FILE [PADBYTES]  -- a valid Ignition 3.4.0 document; PAD makes it that many bytes larger
  perl -e 'my $pad = $ARGV[1] // 0; my $d = q({"ignition":{"version":"3.4.0"},"pad":") . ("x" x $pad) . q("}); print $d' x "$2" > "$1"
}
: > "$W/empty"
mk_ign "$W/ign.json" 0
IGN_SHA=$(sha256sum < "$W/ign.json" | cut -d' ' -f1)

as_snip() { setpriv --reuid="$SNIP_UID" --regid="$SNIP_GID" --init-groups "$@"; }

# ================================================================ I: install fidelity
I1() {
  [ "$SNIP_UID" -ne 0 ] && [ "$(id -u)" -eq 0 ] &&
  [ "$(getent passwd corelab-snip | cut -d: -f7)" = /bin/sh ] &&
  grep -q '^corelab-snip:!' /etc/shadow &&
  ! id -nG corelab-snip | tr ' ' '\n' | grep -qx root &&
  [ ! -e /etc/sudoers ] && [ ! -d /etc/sudoers.d ]
}
check I1 "writer identity: corelab-snip uid $SNIP_UID is not root, shell /bin/sh, password locked, no sudo; the caller is uid 0" I1
I2() {
  [ "$(stat -c '%U:%G %a' "$WRITER")" = "root:root 755" ] &&
  [ "$(stat -c '%U:%G %a' /etc/corelab/snippet-writer.conf)" = "root:root 644" ] &&
  [ "$(stat -c '%U:%G %a' "$SNIPDIR")" = "root:corelab-snip 2770" ] &&
  [ "$(stat -c '%U' /var/lib/corelab-snip)" = root ] && [ "$(stat -c '%U' /var/lib/corelab-snip/.ssh)" = root ] &&
  [ "$(stat -c '%U:%G' /var/lib/corelab-snip/.ssh/authorized_keys)" = "root:root" ] &&
  grep -q "^dir = $SNIPDIR\$" /etc/corelab/snippet-writer.conf &&
  [ "$(cat /var/lib/corelab-snip/.ssh/authorized_keys | cut -d' ' -f1)" = "restrict,from=\"$SRC_OK\",command=\"/usr/local/sbin/corelab-snippet-put\"" ]
}
check I2 "installed owners, modes and authorized_keys options are those prepare.sh writes (home, .ssh and authorized_keys root-owned)" I2
# no parent directory of the snippet directory is writable by corelab-snip (plan section 7)
I3() {
  local d=$SNIPDIR
  while [ "$d" != / ]; do d=$(dirname "$d"); [ "$d" = / ] && break
    ! as_snip sh -c ": > '$d/o4-parent-probe'" 2>/dev/null || return 1
  done
  as_snip sh -c ": > '$SNIPDIR/o4-ctl' && rm -f '$SNIPDIR/o4-ctl'"      # the positive control
}
check I3 "no parent of the snippet directory is writable by corelab-snip (control: the directory itself is)" I3

# ================================================================ S1
logmark
rssh "$W/ign.json" "put demo-1"
check S1.1 "put over sshd is accepted: file owned by corelab-snip, group corelab-snip, mode 0644, identical content, reply carries the sha256" bash -c '
  [ "$0" = 0 ] && f='"$SNIPDIR"'/corelab-demo-1.ign && [ "$(stat -c "%u:%g %a" "$f")" = "'"$SNIP_UID:$SNIP_GID"' 644" ] &&
  [ "$(sha256sum < "$f" | cut -d" " -f1)" = "'"$IGN_SHA"'" ] && case $1 in *"ok put corelab-demo-1.ign bytes="*"sha256='"$IGN_SHA"'"*) ;; *) exit 1;; esac' "$RC" "$OUT"
rssh "$W/empty" "list"
check S1.2 "list over sshd returns the stored file and exits 0" bash -c '[ "$0" = 0 ] && case $1 in *"corelab-demo-1.ign "*) ;; *) exit 1;; esac' "$RC" "$OUT"
ino=$(stat -c %i "$SNIPDIR/corelab-demo-1.ign")
mk_ign "$W/ign2.json" 40
rssh "$W/ign2.json" "put demo-1"
check S1.3 "replacing is atomic: new content, new inode, no temp file, still not executable" bash -c '
  [ "$0" = 0 ] && f='"$SNIPDIR"'/corelab-demo-1.ign && [ "$(stat -c %i "$f")" != "'"$ino"'" ] &&
  [ "$(stat -c %s "$f")" = "$(stat -c %s '"$W"'/ign2.json)" ] && [ "$(( 8#$(stat -c %a "$f") & 8#111 ))" = 0 ] &&
  [ "$(ls -A '"$SNIPDIR"' | grep -c "^\\.corelab-tmp-")" = 0 ]' "$RC"
rssh "$W/empty" "rm demo-1"; rm1=$RC
rssh "$W/empty" "rm demo-1"
check S1.4 "rm removes the file; a second rm is idempotent (ok absent)" bash -c '
  [ "$0" = 0 ] && [ "$1" = 0 ] && [ ! -e '"$SNIPDIR"'/corelab-demo-1.ign ] && case $2 in *"ok absent"*) ;; *) exit 1;; esac' "$rm1" "$RC" "$OUT"

# ================================================================ S2
S2() {
  local bad=(  "put ../x" "put /etc/x" "put a/b" "put A" "put " "put" "put $(printf 'a%.0s' $(seq 1 49))" "put -x" "put x.ign" "get x" "put x y" "rm ../../etc/passwd" "rm" "list x" )
  local c
  for c in "${bad[@]}"; do
    rssh "$W/ign.json" "$c"
    [ "$RC" -eq 2 ] || { echo "not refused with 2: [$c] rc=$RC"; return 1; }
  done
  [ -z "$(files_in_dir)" ] || return 1
  [ ! -e /etc/x ] && [ ! -e /x ] && [ "$(sha256sum < /srv/o4-root-owned)" = "$SENTINEL_SHA" ]
}
check S2.1 "bad slugs and names are refused with exit 2 (14 forms), nothing written, nothing outside the directory touched" S2
S2b() {
  local ok48; ok48=$(printf 'a%.0s' $(seq 1 48))
  rssh "$W/ign.json" "put $ok48"; [ "$RC" -eq 0 ] && [ -f "$SNIPDIR/corelab-$ok48.ign" ] || return 1
  rssh "$W/empty" "rm $ok48"; [ "$RC" -eq 0 ] && [ -z "$(files_in_dir)" ]
}
check S2.2 "control: a 48-character slug is accepted and removed (49 is refused above)" S2b

# ================================================================ S3
S3() {
  local n=0 want
  while IFS='|' read -r label data want; do
    printf '%s' "$data" > "$W/s3.json"
    rssh "$W/s3.json" "put demo"
    [ "$RC" -eq 3 ] && case $ERR in *"$want"*) ;; *) echo "wrong reason for $label: $ERR"; return 1;; esac || { echo "$label rc=$RC"; return 1; }
    n=$((n+1))
  done <<'EOF'
empty||empty content
text|not json|not a JSON object
array|[]|not a JSON object
no-version|{"ignition":{}}|not an Ignition 3.x document
v2|{"ignition":{"version":"2.2.0"}}|not an Ignition 3.x document
version-array|{"ignition":{"version":["3.4.0"]}}|not an Ignition 3.x document
trailing-text|{"ignition":{"version":"3.4.0"}} x|not a JSON object
EOF
  [ "$n" -eq 7 ] && [ -z "$(files_in_dir)" ]
}
check S3.1 "invalid content is refused with exit 3 and the right reason (7 forms); nothing written" S3

# ================================================================ S4
mk_ign "$W/big.json" 263168      # 257 KiB of padding plus the document: larger than 262144 bytes
rssh "$W/big.json" "put big"
check S4.1 "a document over 256 KiB is refused with exit 3 ('larger than') and nothing is written" bash -c '[ "$0" = 3 ] || exit 1; case $1 in *"larger than 262144 bytes"*) ;; *) exit 1;; esac; [ -z "$(ls -A '"$SNIPDIR"')" ]' "$RC" "$ERR"
base=$(wc -c < "$W/ign.json")
mk_ign "$W/edge.json" $((262144 - base))
rssh "$W/edge.json" "put edge"
check S4.2 "control: a document of exactly 262144 bytes is accepted (size $(wc -c < "$W/edge.json"))" bash -c '[ "$0" = 0 ] && [ "$(stat -c %s '"$SNIPDIR"'/corelab-edge.ign)" = 262144 ]' "$RC"
rssh "$W/empty" "rm edge"

# ================================================================ S5 (symlinks and hard links)
ln -s /srv/o4-root-owned "$SNIPDIR/corelab-x.ign"
ln -s /etc/o4-never-created "$SNIPDIR/corelab-dangling.ign"
ln /srv/o4-root-owned "$SNIPDIR/corelab-hard.ign" || incomplete "cannot plant the hard link (sentinel and snippet directory must be on one file system)"
rssh "$W/ign.json" "put x"; r1=$RC; e1=$ERR
rssh "$W/empty" "rm x"; r2=$RC
rssh "$W/ign.json" "put dangling"; r3=$RC
rssh "$W/ign.json" "put hard"; r4=$RC
rssh "$W/ign.json" "put okay"; r5=$RC
check S5.1 "pre-placed symlink to a root-owned file: put and rm refused (exit 3, 'symlink'), target unchanged, link still a link" bash -c '
  [ "$0" = 3 ] && [ "$1" = 3 ] || exit 1; case $2 in *symlink*) ;; *) exit 1;; esac
  [ "$(sha256sum < /srv/o4-root-owned)" = "'"$SENTINEL_SHA"'" ] && [ -L '"$SNIPDIR"'/corelab-x.ign ]' "$r1" "$r2" "$e1"
check S5.2 "a dangling symlink is refused and its target is not created" bash -c '[ "$0" = 3 ] && [ ! -e /etc/o4-never-created ] && [ -L '"$SNIPDIR"'/corelab-dangling.ign ]' "$r3"
check S5.3 "a hard link to a root-owned file is refused and the file is unchanged" bash -c '
  [ "$0" = 3 ] && [ "$(sha256sum < /srv/o4-root-owned)" = "'"$SENTINEL_SHA"'" ]' "$r4"
check S5.4 "control, same run: an ordinary put next to the planted links works" bash -c '[ "$0" = 0 ] && [ -f '"$SNIPDIR"'/corelab-okay.ign ]' "$r5"

rssh "$W/ign.json" "put hl-a"
ln "$SNIPDIR/corelab-hl-a.ign" /srv/o4-hl-extra 2>/dev/null || note "S5.5: the first put left no file to link; the case below fails"
rssh "$W/empty" "list"; hl_list=$OUT
rssh "$W/ign.json" "put hl-a"; h1=$RC; h1e=$ERR
rssh "$W/empty" "rm hl-a"; h2=$RC; h2e=$ERR
rm -f /srv/o4-hl-extra
rssh "$W/ign.json" "put hl-a"; h3=$RC
rssh "$W/empty" "list"; hl_list2=$OUT
rssh "$W/empty" "rm hl-a"
check S5.5 "a file of its own with a second hard link is refused for put and rm (exit 3, 'more than one link') and is not listed; with the link gone, put works and it is listed again" bash -c '
  [ "$0" = 3 ] && [ "$1" = 3 ] || exit 1; case "$2$3" in *"more than one link"*) ;; *) exit 1;; esac; [ "$4" = 0 ] || exit 1
  case $5 in *"corelab-hl-a.ign"*) exit 1;; esac; case $6 in *"corelab-hl-a.ign "*) ;; *) exit 1;; esac' "$h1" "$h2" "$h1e" "$h2e" "$h3" "$hl_list" "$hl_list2"

# ================================================================ S6
rm -f /tmp/o4-pwn
S6() {
  local cmds=( "put x; touch /tmp/o4-pwn" "put x && touch /tmp/o4-pwn" 'put $(touch /tmp/o4-pwn)' 'put `touch /tmp/o4-pwn`'
               "put x|touch /tmp/o4-pwn" "put x > /tmp/o4-pwn" $'put x\ntouch /tmp/o4-pwn' "  put x" "put x " "list -a" "put x y" "list; id" )
  local c
  for c in "${cmds[@]}"; do
    rssh "$W/ign.json" "$c"
    [ "$RC" -eq 2 ] || { echo "not refused with 2: [$c] rc=$RC"; return 1; }
    [ ! -e /tmp/o4-pwn ] || { echo "canary exists after [$c]"; return 1; }
  done
}
check S6.1 "shell metacharacters, newline, padding and extra arguments are refused with exit 2 (12 forms); no injected command ran" S6
rssh "$W/empty" "list"
check S6.2 "control: the plain allowed command still works afterwards" bash -c '[ "$0" = 0 ]' "$RC"

# ================================================================ S7
logmark
printf 'id\ncat /srv/o4-root-owned\n' > "$W/shellcmds"
rssh "$W/shellcmds" -
logsince > /dev/null   # let sshd finish logging this connection before the next mark
check S7.1 "interactive login (no command, shell commands on stdin): the forced command refuses with exit 2; no shell, no 'uid='" bash -c '
  [ "$0" = 2 ] || exit 1; case "$1$2" in *uid=*|*secret-owned*) exit 1;; esac; case $2 in *refused*) ;; *) exit 1;; esac' "$RC" "$OUT" "$ERR"
S7_2() {
  local c
  for c in "id" "sh -c id" "/bin/sh" "cat /srv/o4-root-owned" "scp -t /etc/o4-scp" "ls /"; do
    rssh "$W/empty" "$c"
    [ "$RC" -eq 2 ] || { echo "not refused: [$c] rc=$RC"; return 1; }
    case "$OUT$ERR" in *uid=*|*secret-owned*|*bin*) echo "output leak for [$c]"; return 1;; esac
  done
  [ ! -e /etc/o4-scp ]
}
check S7.2 "other commands (id, sh, cat, scp -t, ls) are refused with exit 2 and print nothing" S7_2
# sftp: send a real SFTP INIT packet (version 3). An ordinary login answers with a VERSION packet
# (a length, then type 02 and version 3); the forced-command user must get no SFTP reply and the writer's own
# refusal status (2), which an sftp-server never returns.
printf '\000\000\000\005\001\000\000\000\003' > "$W/sftp-init"
sftp_try() { # sftp_try USER KEY -> SFTP_RC, SFTP_HEX
  { cat "$W/sftp-init"; sleep 1; } | timeout 30 "${SSHBASE[@]}" -p "$PORT" -b "$SRC_OK" -i "$2" -s "$1@127.0.0.1" sftp > "$W/sftp.out" 2> "$W/sftp.err"
  SFTP_RC=${PIPESTATUS[1]}; SFTP_HEX=$(od -An -tx1 -N9 "$W/sftp.out" | tr -s ' \n' ' ' | sed 's/^ //; s/ $//')
}
sftp_try corelab-plain /etc/o4/id_plain; plain_rc=$SFTP_RC; plain_hex=$SFTP_HEX
sftp_try corelab-snip /etc/o4/id_snip; forced_rc=$SFTP_RC; forced_hex=$SFTP_HEX
note "S7.3 detail: ordinary login rc=$plain_rc reply='$plain_hex'; forced-command login rc=$forced_rc reply='$forced_hex'"
check S7.3 "sftp subsystem: an ordinary login answers the SFTP INIT with a VERSION packet (control, rc 0); the forced-command login gets no SFTP reply and exits with the writer's refusal status 2" bash -c '
  [ "$0" = 0 ] || exit 1; case $1 in "00 00 "*" 02 00 00 00 03") ;; *) exit 1;; esac; [ "$2" = 2 ] && [ -z "$3" ]' "$plain_rc" "$plain_hex" "$forced_rc" "$forced_hex"

# pty (-tt). Evidence is taken from sshd for both keys: authentication accepted, then either
# "Allocating a pty not permitted" (restrict) or an allocated pty ("Allocating pty." and its
# release). The client's own output is not used: with a non-terminal stdin and -tt the client
# closed the session before the command answered, for the restricted and the control key alike
# (cause not established), so no case relies on it.
logmark
SRC=$SRC_OK rssh "$W/empty" "rm pty-probe" -tt
lp=$(logsince); pty_err=$ERR
logmark
USER_=corelab-open KEY=/etc/o4/id_open rssh "$W/empty" "rm pty-probe" -tt
lpo=$(logsince); ctl_pty_err=$ERR
check S7.4 "pty request (-tt): restricted key: authenticated, client says 'PTY allocation request failed', sshd logs 'Allocating a pty not permitted' and never allocates one; control key without restrict: authenticated, sshd logs 'Allocating pty.' and releases /dev/pts/N, the client reports no failure" bash -c '
  case $2 in *"Accepted publickey for corelab-snip"*) ;; *) exit 1;; esac
  case $0 in *"PTY allocation request failed"*) ;; *) exit 1;; esac
  case $2 in *"Allocating a pty not permitted"*) ;; *) exit 1;; esac; case $2 in *"Allocating pty."*) exit 1;; esac
  case $3 in *"Accepted publickey for corelab-open"*) ;; *) exit 1;; esac
  case $1 in *"PTY allocation request failed"*) exit 1;; esac
  case $3 in *"Allocating pty."*) ;; *) exit 1;; esac; case $3 in *"release /dev/pts/"*) ;; *) exit 1;; esac
  case $3 in *"Allocating a pty not permitted"*) exit 1;; esac' "$pty_err" "$ctl_pty_err" "$lp" "$lpo"

# port forwarding and agent forwarding
fwd_test() { # fwd_test USER KEY  -> sets FWD_GOT (listener received the data) and FWD_ERR
  local user=$1 key=$2
  rm -f "$W/fwd.rx"
  perl -MIO::Socket::INET -e '$|=1; my $l=IO::Socket::INET->new(Listen=>1,LocalAddr=>"127.0.0.1",LocalPort=>5002,ReuseAddr=>1) or die; alarm 8; my $c=$l->accept; my $d=<$c>; open(my $o,">","$ARGV[0]") or die; print $o $d; close $o;' "$W/fwd.rx" &
  local lp=$!
  for _ in $(seq 1 30); do [ -n "$(ss -ltnH 'sport = :5002')" ] && break; sleep 0.1; done
  timeout 8 "${SSHBASE[@]}" -p "$PORT" -b "$SRC_OK" -i "$key" -N -L 127.0.0.1:5001:127.0.0.1:5002 "$user@127.0.0.1" 2> "$W/fwd.err" &
  local sp=$!
  for _ in $(seq 1 30); do [ -n "$(ss -ltnH 'sport = :5001')" ] && break; sleep 0.2; done
  ( exec 3<>/dev/tcp/127.0.0.1/5001; echo hello >&3; sleep 0.5 ) 2>/dev/null
  sleep 0.7
  FWD_GOT=$(cat "$W/fwd.rx" 2>/dev/null); FWD_ERR=$(cat "$W/fwd.err")
  kill "$sp" "$lp" 2>/dev/null; wait "$sp" "$lp" 2>/dev/null
}
fwd_test corelab-snip /etc/o4/id_snip; got_r=$FWD_GOT; err_r=$FWD_ERR
fwd_test corelab-open /etc/o4/id_open; got_o=$FWD_GOT
note "S7.5 detail: restricted listener got='$got_r' ssh stderr='$(printf %s "$err_r" | tr '\r\n' '  ' | head -c 200)'; control listener got='$got_o' control stderr='$(printf %s "$FWD_ERR" | tr '\r\n' '  ' | head -c 200)'"
check S7.5 "local forward (-L) is refused by restrict ('administratively prohibited', nothing arrives); control without restrict forwards 'hello'" bash -c '
  [ -z "$0" ] || exit 1; case $1 in *"administratively prohibited"*) ;; *) exit 1;; esac; [ "$2" = hello ]' "$got_r" "$err_r" "$got_o"

rfwd_test() { # rfwd_test USER KEY -> RFWD_ALIVE (1/0), RFWD_PORT (1 if 5003 accepts), RFWD_ERR
  local user=$1 key=$2
  timeout 6 "${SSHBASE[@]}" -p "$PORT" -b "$SRC_OK" -i "$key" -N -o ExitOnForwardFailure=yes -R 127.0.0.1:5003:127.0.0.1:5002 "$user@127.0.0.1" 2> "$W/rfwd.err" &
  local sp=$!
  sleep 2
  RFWD_ALIVE=0; kill -0 "$sp" 2>/dev/null && RFWD_ALIVE=1
  RFWD_PORT=0; (exec 3<>/dev/tcp/127.0.0.1/5003) 2>/dev/null && RFWD_PORT=1
  RFWD_ERR=$(cat "$W/rfwd.err")
  kill "$sp" 2>/dev/null; wait "$sp" 2>/dev/null
}
rfwd_test corelab-snip /etc/o4/id_snip; ra=$RFWD_ALIVE; rp=$RFWD_PORT; re=$RFWD_ERR
rfwd_test corelab-open /etc/o4/id_open; oa=$RFWD_ALIVE; op=$RFWD_PORT
note "S7.6 detail: restricted alive=$ra port=$rp stderr='$(printf %s "$re" | tr -d '\r' | head -c 200)'; control alive=$oa port=$op"
check S7.6 "remote forward (-R) is refused by restrict (ssh exits, port 5003 not opened); control without restrict opens it" bash -c '
  [ "$0" = 0 ] && [ "$1" = 0 ] || exit 1; case $2 in *"forwarding failed"*|*"Could not request remote forwarding"*) ;; *) exit 1;; esac; [ "$3" = 1 ] && [ "$4" = 1 ]' "$ra" "$rp" "$re" "$oa" "$op"

eval "$(ssh-agent -a "$W/agent.sock" -s)" >/dev/null
SSH_AUTH_SOCK=$W/agent.sock ssh-add /etc/o4/id_snip >/dev/null 2>&1 || SSH_AUTH_SOCK=$W/agent.sock ssh-add /etc/o4/id_snip
logmark
SSH_AUTH_SOCK=$W/agent.sock rssh "$W/empty" "rm agent-probe" -A
la=$(logsince); ag_rc=$RC; ag_out=$OUT
logmark
SSH_AUTH_SOCK=$W/agent.sock USER_=corelab-open KEY=/etc/o4/id_open rssh "$W/empty" "rm agent-probe" -A
lao=$(logsince); ago_rc=$RC; ago_out=$OUT
kill "$SSH_AGENT_PID" 2>/dev/null
check S7.7 "agent forwarding (-A): restricted key: the command ran (rc 0, 'ok absent') and sshd logs 'agent forwarding disabled' with no agent socket created; control key without restrict: rc 0 and sshd creates the agent socket (unix_listener_tmp under .ssh/agent), no refusal logged" bash -c '
  [ "$0" = 0 ] && [ "$3" = 0 ] || exit 1
  case $1 in *"ok absent"*) ;; *) exit 1;; esac; case $4 in *"ok absent"*) ;; *) exit 1;; esac
  case $2 in *"agent forwarding disabled"*) ;; *) exit 1;; esac; case $2 in *"unix_listener_tmp"*) exit 1;; esac
  case $5 in *"unix_listener_tmp"*"/agent/"*) ;; *) exit 1;; esac; case $5 in *"agent forwarding disabled"*) exit 1;; esac' \
  "$ag_rc" "$ag_out" "$la" "$ago_rc" "$ago_out" "$lao"

SRC=$SRC_BAD rssh "$W/empty" "list"; bad_rc=$RC; bad_err=$ERR
logmark
SRC=$SRC_BAD rssh "$W/empty" "list" -v 2>/dev/null
lb=$(logsince)
check S7.8 "from= is effective: the right key from a source other than $SRC_OK is refused (255, publickey); same key from $SRC_OK works (S1)" bash -c '
  [ "$0" = 255 ] || exit 1; case $1 in *"Permission denied"*) ;; *) exit 1;; esac; case $2 in *"not from a permitted host"*|*"not permitted"*|*"from="*) ;; *) exit 1;; esac' "$bad_rc" "$bad_err" "$lb"

USER_=corelab-nologin KEY=/etc/o4/id_nolog rssh "$W/ign.json" "put nologin-try"
nl_rc=$RC; nl_out=$OUT$ERR
check S7.9 "plan inference confirmed: with a nologin shell the forced command does not run (nothing written); with /bin/sh it does (S1)" bash -c '
  [ "$0" != 0 ] || exit 1; case $1 in *"not available"*) ;; *) exit 1;; esac; [ ! -e '"$SNIPDIR"'/corelab-nologin-try.ign ]' "$nl_rc" "$nl_out"

# ================================================================ S8
echo foreign > "$SNIPDIR/corelab-r.ign"                 # root-owned regular file, as a foreign file
echo notes > "$SNIPDIR/notes.txt"                        # not matching corelab-*.ign
rssh "$W/ign.json" "put mine"; rssh "$W/empty" "list"; l_out=$OUT
rssh "$W/empty" "rm r"; s8a=$RC; s8e=$ERR
rssh "$W/ign.json" "put r"; s8b=$RC
S8c() {
  local c
  for c in "rm notes.txt" "rm corelab-r.ign" "rm ../notes" "rm A" "rm x/y" "rm *"; do
    rssh "$W/empty" "$c"; [ "$RC" -eq 2 ] || { echo "not refused: [$c] rc=$RC"; return 1; }
  done
  [ -f "$SNIPDIR/notes.txt" ] && [ -f "$SNIPDIR/corelab-r.ign" ]
}
check S8.1 "rm and put of a file not owned by corelab-snip are refused (exit 3, 'another user'); the file survives" bash -c '
  [ "$0" = 3 ] && [ "$1" = 3 ] || exit 1; case $2 in *"owned by another user"*) ;; *) exit 1;; esac; grep -qx foreign '"$SNIPDIR"'/corelab-r.ign' "$s8a" "$s8b" "$s8e"
check S8.2 "non-matching names (notes.txt, full file name, path parts, wildcard) are refused with exit 2; files survive" S8c
check S8.3 "list shows only own regular files (not the foreign file, the symlinks or the hard link)" bash -c '
  case $0 in *"corelab-mine.ign "*) ;; *) exit 1;; esac; case $0 in *corelab-r.ign*|*corelab-x.ign*|*corelab-dangling*|*corelab-hard*|*notes*) exit 1;; esac' "$l_out"
rssh "$W/empty" "rm mine"
check S8.4 "control: own file is removed" bash -c '[ "$0" = 0 ] && [ ! -e '"$SNIPDIR"'/corelab-mine.ign ]' "$RC"

# ================================================================ S9 (setpriv stands in for sudo -u)
S9() {
  local p ok=0
  for p in /etc/pve/o4-probe /root/o4-probe /usr/local/sbin/o4-probe /var/lib/vz/snippets/o4-probe /etc/corelab/o4-probe \
           "$LAB/o4-probe" /etc/o4-probe /etc/passwd; do
    if as_snip sh -c ": >> '$p'" 2>/dev/null; then echo "WRITABLE: $p"; return 1; fi
    ok=$((ok+1))
  done
  as_snip sh -c ": >> $WRITER" 2>/dev/null && { echo "writer script writable"; return 1; }
  as_snip sh -c ": >> /etc/corelab/snippet-writer.conf" 2>/dev/null && { echo "config writable"; return 1; }
  as_snip sh -c "cat /etc/ssh/ssh_host_ed25519_key" >/dev/null 2>&1 && { echo "host key readable"; return 1; }
  as_snip sh -c "cat /srv/o4-root-owned" >/dev/null 2>&1 && { echo "root-only file readable"; return 1; }
  as_snip sh -c ": > '$SNIPDIR/o4-ctl' && rm -f '$SNIPDIR/o4-ctl'"      # control: its own directory is writable
}
check S9.1 "as corelab-snip (setpriv, standing in for sudo -u): /etc/pve, /root, /usr/local/sbin, the default snippets directory, /etc/corelab, the writer, its config, the host key and the parent of its directory are not writable/readable; its own directory is" S9
S9b() {
  local f=/var/lib/corelab-snip/.ssh/authorized_keys before; before=$(sha256sum < $f)
  as_snip sh -c ": >> $f" 2>/dev/null && return 1
  as_snip sh -c "echo x > $f" 2>/dev/null && return 1
  as_snip sh -c "mv /var/lib/corelab-snip/.ssh /var/lib/corelab-snip/.ssh.old" 2>/dev/null && return 1
  as_snip sh -c "ln -s /srv/o4-root-owned /var/lib/corelab-snip/.ssh/extra" 2>/dev/null && return 1
  as_snip sh -c "mv $f $f.old" 2>/dev/null && return 1
  [ "$(sha256sum < $f)" = "$before" ] && as_snip sh -c "cat $f" >/dev/null     # control: it can read it
}
check S9.2 "as corelab-snip: its own authorized_keys, .ssh and home cannot be changed, renamed or linked into (control: it can read the key line)" S9b

# ================================================================ D1: directory ownership (writer defence)
chown corelab-snip:corelab-snip "$SNIPDIR"
rssh "$W/ign.json" "put dirown"; d1=$RC; d1e=$ERR
rssh "$W/empty" "list"; d1l=$RC
chown root:corelab-snip "$SNIPDIR"
rssh "$W/ign.json" "put dirown"; d1c=$RC
note "D1 detail: put rc=$d1 list rc=$d1l stderr='$d1e' installed config: $(grep -c expected_dir_uid /etc/corelab/snippet-writer.conf) expected_dir_uid line(s)"
check D1 "a snippet directory owned by corelab-snip itself is refused (exit 3, 'not owned by the expected user') for put and list; once root-owned again, put works" bash -c '
  [ "$0" = 3 ] && [ "$1" = 3 ] || exit 1; case $2 in *"not owned by the expected user"*) ;; *) exit 1;; esac; [ "$3" = 0 ]' "$d1" "$d1l" "$d1e" "$d1c"
rssh "$W/empty" "rm dirown"

chmod 2777 "$SNIPDIR"
rssh "$W/ign.json" "put wide"; d2=$RC; d2e=$ERR
chmod 2770 "$SNIPDIR"
rssh "$W/ign.json" "put wide"; d2c=$RC
rssh "$W/empty" "rm wide"
check D2 "a world-writable snippet directory is refused (exit 3, 'world-writable'); back at 2770, put works" bash -c '
  [ "$0" = 3 ] || exit 1; case $1 in *"world-writable"*) ;; *) exit 1;; esac; [ "$2" = 0 ]' "$d2" "$d2e" "$d2c"

# ================================================================ S7.10: locked account needs PAM in sshd
# prepare.sh locks the password (passwd -l). sshd without PAM refuses a locked account even for
# key logins; with PAM it does not. The first sshd above uses PAM (Debian/Proxmox default).
sed 's/^UsePAM yes/UsePAM no/; s/^Port .*/Port 2223/; s#^PidFile .*#PidFile /run/sshd2.pid#' /etc/ssh/sshd_config > /etc/ssh/sshd_config.nopam
/usr/sbin/sshd -D -e -f /etc/ssh/sshd_config.nopam > "$W/sshd2.log" 2>&1 &
SSHD2_PID=$!
printf '[127.0.0.1]:2223 %s\n' "$(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)" >> /etc/o4/known_hosts
for _ in $(seq 1 50); do [ -n "$(ss -ltnH 'sport = :2223')" ] && break; sleep 0.1; done
[ -n "$(ss -ltnH 'sport = :2223')" ] || incomplete "the second sshd (UsePAM no) did not start: $(tail -n 3 "$W/sshd2.log" | tr '\n' ' ')"
PORT_=2223 rssh "$W/empty" "list"; np_rc=$RC; np_err=$ERR
sleep 0.4; np_log=$(cat "$W/sshd2.log")
usermod -p '*' corelab-open
PORT_=2223 USER_=corelab-open KEY=/etc/o4/id_open rssh "$W/empty" "rm nopam-probe"; star_rc=$RC; star_out=$OUT
kill "$SSHD2_PID" 2>/dev/null; wait "$SSHD2_PID" 2>/dev/null
check S7.10 "dependency shown (sshd with UsePAM no): the locked ('!') corelab-snip with its right key gets 'Permission denied (publickey)' (255) and sshd logs 'account is locked'; control, same sshd: a '*' password hash logs in and the writer runs (rc 0, 'ok absent'). With PAM the locked account works (S1.1)" bash -c '
  [ "$0" = 255 ] || exit 1; case $1 in *"Permission denied"*) ;; *) exit 1;; esac
  case $2 in *"not allowed because account is locked"*) ;; *) exit 1;; esac
  [ "$3" = 0 ] || exit 1; case $4 in *"ok absent"*) ;; *) exit 1;; esac' "$np_rc" "$np_err" "$np_log" "$star_rc" "$star_out"
note "S7.10 means: if the host sshd runs with UsePAM no, prepare.sh's passwd -l locks the writer out. Live check on the host: sshd -T | grep -i usepam must say yes (Debian default), or the action should set the hash with usermod -p '*' instead."

# ================================================================ X: end state
X1() {
  # no leftover temp files; only the planted fixtures and the own files from this run remain
  ! compgen -G "$SNIPDIR/.corelab-tmp-*" > /dev/null && [ "$(sha256sum < /srv/o4-root-owned)" = "$SENTINEL_SHA" ] && [ ! -e /tmp/o4-pwn ]
}
check X1 "end state: no temp file left in the snippet directory, outside sentinel unchanged, no canary" X1
X2() {
  # every TCP listener inside the container (sshd, plus whatever the cases left) is on 127.0.0.1
  ss -ltnH > "$W/listeners" 2>/dev/null || return 1
  [ -s "$W/listeners" ] && ! tr -s ' ' '\n' < "$W/listeners" | grep -E '^[0-9.*:\[\]]+:[0-9]+$' | grep -qv '^127\.0\.0\.1:'
}
check X2 "every TCP listener in the container is on 127.0.0.1 (the container network is 'none': loopback only)" X2

X3() { [ "$(tail -n +3 /proc/net/dev | cut -d: -f1 | tr -d ' ' | tr '\n' ' ')" = "lo " ]; }
check X3 "the container has no network interface but loopback ($(tail -n +3 /proc/net/dev | cut -d: -f1 | tr -d ' ' | tr '\n' ' '))" X3

kill "$SSHD_PID" 2>/dev/null; wait "$SSHD_PID" 2>/dev/null
if [ "$fail" -ne 0 ] || [ -n "${O4_SHOW_SSHD_LOG:-}" ]; then
  echo "--- sshd log (last 60 lines; synthetic keys and users only)"
  tail -n "${O4_SSHD_LOG_LINES:-60}" "$W/sshd.log" | sed 's/^/sshd: /'
fi
printf 'INNER-DONE pass=%d fail=%d failed=%s\n' "$pass" "$fail" "${failed_ids[*]:-none}"
[ "$fail" -eq 0 ]
