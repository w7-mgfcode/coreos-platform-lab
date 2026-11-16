# shellcheck shell=bash
# Action: discover-host (read-only)
# Host facts the API does not show. The runner saves stdout to a local file outside the
# repository (mode 600); it is raw, machine-specific data (disk serials, network files,
# key fingerprints) and is never committed.
# Every section runs even if an earlier one fails: a failed read prints "FAILED: ..." in its
# section and the run ends with exit 4. A tool that is not installed prints "not installed"
# (that is the only case reported as absent).

export LC_ALL=C
failed=0
section() { printf '\n### %s\n' "$1"; }
# have TOOL — true if installed; otherwise prints the "not installed" line.
have() { command -v "$1" >/dev/null 2>&1 || { echo "$1: not installed"; return 1; }; }
# try LABEL CMD... — run CMD; a failure is printed and counted, never hidden.
try() {
  local label=$1; shift
  if ! "$@"; then echo "FAILED: $label"; failed=1; fi
}

section pveversion;       try pveversion pveversion -v
section lsblk;            try lsblk lsblk -J -o NAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINTS,SERIAL,MODEL
section findmnt;          try findmnt findmnt -J
section zpool;            if have zpool; then try zpool zpool list -H; fi
section lvs;              if have lvs; then try lvs lvs --reportformat json; fi
section interfaces;       try interfaces cat /etc/network/interfaces
section interfaces.d
shopt -s nullglob
ifd=(/etc/network/interfaces.d/*)
shopt -u nullglob
if [ "${#ifd[@]}" -eq 0 ]; then echo "none"; else try interfaces.d cat "${ifd[@]}"; fi
section sshd
if sshd_conf=$(sshd -T 2>/dev/null); then
  printf '%s\n' "$sshd_conf" | grep -Ei '^(permitrootlogin|passwordauthentication|pubkeyauthentication|allowusers|match) ' \
    || { echo "FAILED: sshd -T printed none of the expected settings"; failed=1; }
else
  echo "FAILED: sshd -T"; failed=1
fi
section root-keys
if [ -e /root/.ssh/authorized_keys ]; then try root-keys ssh-keygen -lf /root/.ssh/authorized_keys; else echo "none"; fi
section apt-sources
try apt-sources ls /etc/apt/sources.list.d/
try apt-sources grep -rhE '^(deb|Types|URIs|Suites|Components)' /etc/apt/sources.list /etc/apt/sources.list.d/
section pmxcfs;           try pmxcfs ls -l /var/lib/pve-cluster/config.db
section sqlite3;          if have sqlite3; then command -v sqlite3; fi
section snippet-dirs;     try snippet-dirs find /var/lib/vz -maxdepth 2 -type d -name snippets
[ "$failed" = 0 ] || cl_die 4 "at least one section failed; see FAILED lines in the output"
