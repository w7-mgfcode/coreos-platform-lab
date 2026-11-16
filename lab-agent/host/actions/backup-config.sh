# shellcheck shell=bash
# Action: backup-config (changes nothing on the host except one private temporary directory)
# Writes a tar.gz of the host configuration to stdout; the runner stores it locally in
# ${PVE_LAB_STATE}/host-backup/ with mode 600. Run it first, and before every host-critical
# action.
# The archive contains secrets (ssh host private keys, /etc/pve/priv): it is binary output
# for a mode-600 local file, never shown, never committed.
# The archive is built in the private temporary directory and checked before any byte goes
# to stdout, so a failed run delivers nothing that could be mistaken for a backup. tar exit
# 1 ("a file changed while read") is delivered with a WARNING on stderr; any other failure
# delivers nothing and exits 4.
#
# config.db is the pmxcfs database behind /etc/pve. sqlite3 makes a consistent copy;
# without it a plain copy is taken and flagged (consistency: LIVE validation).

export LC_ALL=C
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT

if command -v sqlite3 >/dev/null; then
  sqlite3 /var/lib/pve-cluster/config.db ".backup '$work/config.db'" || cl_die 4 "sqlite backup failed"
  echo "sqlite3 .backup" > "$work/config.db.method"
else
  cp /var/lib/pve-cluster/config.db "$work/config.db" || cl_die 4 "copy of config.db failed"
  echo "plain copy (not guaranteed consistent)" > "$work/config.db.method"
  cl_log "WARNING: sqlite3 missing; config.db copied without a consistency guarantee"
fi

paths=(etc/pve etc/network etc/hosts etc/hostname etc/ssh etc/apt)
for f in "${paths[@]}"; do
  [ -e "/$f" ] || cl_die 4 "/$f does not exist; not making a partial backup"
done
if [ -e /root/.ssh/authorized_keys ]; then
  paths+=(root/.ssh/authorized_keys)
else
  cl_log "no /root/.ssh/authorized_keys; not included"
fi

rc=0
tar -czf "$work/backup.tar.gz" -C / "${paths[@]}" -C "$work" config.db config.db.method || rc=$?
if [ "$rc" -eq 1 ]; then
  cl_log "WARNING: tar reported that a file changed while it was read (exit 1); the archive may be inconsistent"
elif [ "$rc" -ne 0 ]; then
  cl_die 4 "tar failed (exit $rc); nothing was written to the output"
fi
tar -tzf "$work/backup.tar.gz" >/dev/null || cl_die 4 "the archive does not read back; nothing was written to the output"
cat "$work/backup.tar.gz"
