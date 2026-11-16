# shellcheck shell=bash
# Action: sentinel
# Creates the fixtures the negative RBAC tests aim at, all OUTSIDE the pool:
#   - guest CL_SENTINEL_VMID: 1 GiB disk, no NIC, never started
#   - one vzdump of it on CL_SENTINEL_BACKUP_STORAGE (not the project storage)
#   - a 1 MiB dummy ISO on the project storage
# The aim is that an unexpected success of a negative test costs nothing. That only holds
# if these objects are the ones this script made, so identity comes from a record, not from
# a shape.
#
# The record (one file per VMID in the configuration directory) is read only if root owns it
# and neither group nor others can write it, it ends in a newline and every line is a plain
# key=value (it is never executed). It holds the host's machine id, the VMID, the node, the
# storages and the canonical ISO path it was made for, the guest's config digest and disk
# line, the volume id of the one backup, and the ISO's sha256 and file identity (device and
# inode), each written when the script made that object. A run creates a guest, backup or ISO
# only when none exists; it accepts an existing one only if it matches the record (including
# host, storages and ISO location) AND the fixture shape (stopped qemu guest on this node, not
# a template, in no pool, description marker, only the keys this script sets, only scsi0 of
# exactly <storage>:vm-<VMID>-disk-<n>,size=1G). Anything else is refused with exit 3 and a
# message that says what to check by hand.
# What a match shows: the guest, backup and ISO are the ones recorded on this host, and the
# guest's configuration and the ISO file are unchanged since. What it does NOT show: that the
# record was written by this script rather than by someone who can write as root (the record
# is only as trustworthy as root's files and the machine id; a cloned machine id defeats the
# host binding); that the guest's disk is still empty (data in a disk does not change the
# config digest); that the backup is intact or was taken from an empty disk; that the guest
# is worthless. Those need the owner.
#
# Parameters: CL_SENTINEL_VMID CL_VM_STORAGE CL_SENTINEL_BACKUP_STORAGE CL_LAB_STORAGE_PATH CL_LAB_STORAGE

: "${CL_SENTINEL_VMID:?}" "${CL_VM_STORAGE:?}" "${CL_SENTINEL_BACKUP_STORAGE:?}" "${CL_LAB_STORAGE_PATH:?}"
: "${CL_LAB_STORAGE:?}"
export LC_ALL=C

la_cfgdir=/etc/corelab
la_machine_id=/etc/machine-id
la_tmps=()
trap 'rm -f -- "${la_tmps[@]}"' EXIT

la_uint() { # LABEL VALUE MIN MAX — canonical positive decimal inside MIN..MAX
  [[ "$2" =~ ^[1-9][0-9]{0,8}$ ]] || cl_die 3 "$1 must be a positive decimal integer (no sign, no leading zero)"
  [ "$2" -ge "$3" ] && [ "$2" -le "$4" ] || cl_die 3 "$1=$2 is outside $3..$4"
}
la_id() { # LABEL VALUE — a plain PVE identifier
  [[ "$2" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || cl_die 3 "$1 is not a plain identifier"
}
la_root_dir() { # PATH — a real directory owned by root, not writable by group or others
  local mode
  [ ! -L "$1" ] && [ -d "$1" ] || cl_die 3 "$1 is not a real directory"
  [ "$(stat -c %u -- "$1")" = 0 ] || cl_die 3 "$1 is not owned by root"
  mode=$(stat -c %a -- "$1")
  [[ "$mode" =~ ^[0-7]{3,4}$ ]] || cl_die 3 "unexpected mode text for $1"
  (( (8#$mode & 8#022) == 0 )) || cl_die 3 "$1 is writable by group or others (mode $mode)"
}
la_root_chain() { # PATH — every ancestor is an existing root-owned real directory
  local cur="" comp
  local -a parts
  IFS=/ read -ra parts <<<"${1#/}"
  for comp in "${parts[@]:0:${#parts[@]}-1}"; do
    cur="$cur/$comp"
    [ -e "$cur" ] || cl_die 3 "$cur does not exist"
    la_root_dir "$cur"
  done
}
la_ensure_root_dir() { # PATH — validate ancestors and destination first, then create
  la_root_chain "$1"
  [ ! -L "$1" ] || cl_die 3 "$1 is a symbolic link"
  if [ ! -e "$1" ]; then install -d -m 0755 -o root -g root "$1"; fi
  la_root_dir "$1"
}
# la_records JSON KEY [FIELD[#]...] — an array of objects, each with KEY and every FIELD as a
# non-empty scalar (# = a canonical VMID: 100..999999999, no sign, no leading zero, so that
# "9050" and "09050" cannot be two identities), KEY unique. Prints the count; anything else fails.
la_records() {
  local json=$1; shift
  printf '%s' "$json" | cl_shape_ok list || return 1
  printf '%s' "$json" | CL_SPEC="$*" cl_json_get '
    my @spec = split " ", $ENV{CL_SPEC}; my %seen;
    for my $r (@$d) {
      die "element is not an object\n" unless ref $r eq "HASH";
      for my $s (@spec) {
        my $f = $s; $f =~ s/#\z//; my $v = $r->{$f};
        die "record without a usable $f\n" unless defined $v && !ref $v && length $v;
        die "$f is not a canonical VMID\n" if $s =~ /#\z/ && $v !~ /\A[1-9][0-9]{2,8}\z/;
      }
      my $k = $spec[0]; $k =~ s/#\z//;
      die "duplicate record\n" if $seen{$r->{$k}}++;
    }
    scalar @$d'
}
la_trusted_file() { # FILE — a regular file (not a link) owned by root that group and others cannot write
  local mode
  [ ! -L "$1" ] && [ -f "$1" ] || cl_die 3 "$1 is not a regular file"
  [ "$(stat -c %u -- "$1")" = 0 ] || cl_die 3 "$1 is not owned by root"
  mode=$(stat -c %a -- "$1")
  [[ "$mode" =~ ^[0-7]{3,4}$ ]] || cl_die 3 "unexpected mode text for $1"
  (( (8#$mode & 8#022) == 0 )) || cl_die 3 "$1 is writable by group or others (mode $mode); not trusting it"
}
la_host_id() { # the machine id: a stable identity of this host that needs no network
  local id
  la_trusted_file "$la_machine_id"
  id=$(<"$la_machine_id") || cl_die 4 "cannot read $la_machine_id"
  [[ "$id" =~ ^[0-9a-f]{32}$ ]] || cl_die 3 "$la_machine_id does not hold a machine id"
  printf '%s' "$id"
}
la_sha256() { # FILE — print the sha256 of a regular file
  local out
  out=$(sha256sum -- "$1") || cl_die 4 "cannot hash $1"
  out=${out%% *}
  [[ "$out" =~ ^[0-9a-f]{64}$ ]] || cl_die 4 "unexpected sha256sum output"
  printf '%s' "$out"
}

la_uint CL_SENTINEL_VMID "$CL_SENTINEL_VMID" 100 999999999
la_id CL_VM_STORAGE "$CL_VM_STORAGE"
la_id CL_SENTINEL_BACKUP_STORAGE "$CL_SENTINEL_BACKUP_STORAGE"
la_id CL_LAB_STORAGE "$CL_LAB_STORAGE"
[ "$CL_SENTINEL_BACKUP_STORAGE" != "$CL_LAB_STORAGE" ] \
  || cl_die 3 "the sentinel backup must not live on the project storage"

p=$CL_LAB_STORAGE_PATH
[[ "$p" =~ ^/[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)+$ ]] || cl_die 3 "CL_LAB_STORAGE_PATH must be a plain absolute path"
case "$p/" in */./*|*/../*) cl_die 3 "CL_LAB_STORAGE_PATH must not contain '.' or '..' components" ;; esac
IFS=/ read -ra parts <<<"${p#/}"
cur=""
for comp in "${parts[@]}"; do
  cur="$cur/$comp"
  [ ! -L "$cur" ] || cl_die 3 "$cur is a symbolic link"
  la_root_dir "$cur"
done
[ "$(realpath -e -- "$p")" = "$p" ] || cl_die 3 "$p is not its own real path"

node=$(hostname -s)
[[ "$node" =~ ^[A-Za-z0-9][A-Za-z0-9-]*$ ]] || cl_die 4 "unexpected node name"

# The project storage must be the registered directory storage at exactly this path.
storage_list=$(pvesh get /storage --output-format json) || cl_die 4 "cannot list storages"
la_records "$storage_list" storage type >/dev/null || cl_die 4 "the storage list is not an array of records with unique ids and types"
registered=$(printf '%s' "$storage_list" | CL_S="$CL_LAB_STORAGE" cl_json_get '
  my ($s) = grep { $_->{storage} eq $ENV{CL_S} } @$d;
  $s ? "$s->{type}|" . (ref $s->{path} ? "" : ($s->{path} // "")) : "absent"') || cl_die 4 "cannot read the storage list"
[ "$registered" != absent ] || cl_die 3 "storage $CL_LAB_STORAGE does not exist; run prepare first"
[ "$registered" = "dir|$p" ] || cl_die 3 "storage $CL_LAB_STORAGE is not a directory storage at $p"

fixture_desc="Negative RBAC test fixture. Worthless by design. [corelab-fixture sentinel-v1 vmid=$CL_SENTINEL_VMID]"
expected_disk_re="^${CL_VM_STORAGE//./\\.}:vm-$CL_SENTINEL_VMID-disk-[0-9]+,size=1G\$"

# --- the record -----------------------------------------------------------------------
host_id=$(la_host_id)
iso_dir="$p/template/iso"
iso="$iso_dir/corelab-dummy.iso"
la_record="$la_cfgdir/sentinel-$CL_SENTINEL_VMID.record"
rec_keys="vmid node host lab_storage lab_path vm_storage backup_storage iso_path digest disk backup_volid iso_sha256 iso_id"
declare -A rec=()
have_record=0
[ ! -L "$la_cfgdir" ] || cl_die 3 "$la_cfgdir is a symbolic link"
if [ -e "$la_cfgdir" ]; then
  la_root_chain "$la_cfgdir"
  la_root_dir "$la_cfgdir"
  [ ! -L "$la_record" ] || cl_die 3 "$la_record is a symbolic link"
  if [ -e "$la_record" ]; then
    la_trusted_file "$la_record"
    [ -s "$la_record" ] || cl_die 3 "$la_record is empty"
    last=$(tail -c1 -- "$la_record" | od -An -tx1) || cl_die 4 "cannot read $la_record"
    [ "${last// /}" = 0a ] || cl_die 3 "$la_record does not end with a newline (cut short or appended to)"
    while IFS= read -r line; do
      [[ "$line" =~ ^([a-z0-9_]+)=([A-Za-z0-9._:/+@=,_-]*)$ ]] || cl_die 3 "$la_record is malformed"
      key=${BASH_REMATCH[1]}; val=${BASH_REMATCH[2]}
      case " $rec_keys " in *" $key "*) ;; *) cl_die 3 "$la_record has an unknown key" ;; esac
      [ -z "${rec[$key]+x}" ] || cl_die 3 "$la_record repeats a key"
      rec[$key]=$val
    done < "$la_record"
    [ "${rec[vmid]:-}" = "$CL_SENTINEL_VMID" ] && [ "${rec[node]:-}" = "$node" ] \
      || cl_die 3 "$la_record belongs to another VMID or node; not touching anything"
    [ "${rec[host]:-}" = "$host_id" ] || cl_die 3 "$la_record was written on another host; not trusting it"
    [ "${rec[lab_storage]:-}" = "$CL_LAB_STORAGE" ] && [ "${rec[lab_path]:-}" = "$p" ] \
      && [ "${rec[vm_storage]:-}" = "$CL_VM_STORAGE" ] && [ "${rec[backup_storage]:-}" = "$CL_SENTINEL_BACKUP_STORAGE" ] \
      && [ "${rec[iso_path]:-}" = "$iso" ] \
      || cl_die 3 "$la_record was made for other storages or another ISO location than this run uses; not touching anything"
    [[ "${rec[digest]:-}" =~ ^[0-9a-f]{32,64}$ ]] || cl_die 3 "$la_record has no usable digest"
    [[ "${rec[disk]:-}" =~ $expected_disk_re ]] || cl_die 3 "$la_record has no usable disk line"
    if [ -n "${rec[iso_sha256]:-}" ]; then
      [[ "${rec[iso_sha256]}" =~ ^[0-9a-f]{64}$ ]] && [[ "${rec[iso_id]:-}" =~ ^[0-9]+:[0-9]+$ ]] \
        || cl_die 3 "$la_record has a bad ISO identity"
    fi
    have_record=1
  fi
fi
la_save_record() {
  local k tmp
  la_ensure_root_dir "$la_cfgdir"
  tmp=$(mktemp "$la_cfgdir/.sentinel-record.XXXXXXXX")
  la_tmps+=("$tmp")
  for k in $rec_keys; do
    [ -z "${rec[$k]:-}" ] || printf '%s=%s\n' "$k" "${rec[$k]}"
  done > "$tmp"
  chmod 0644 "$tmp"
  mv -fT -- "$tmp" "$la_record"
}

# --- reading the guest -----------------------------------------------------------------
# la_guest_row — "type|node|status|template|pool" of the guest with the sentinel VMID, or absent.
la_guest_row() {
  local resources
  resources=$(pvesh get /cluster/resources --type vm --output-format json) || cl_die 4 "cannot list guests"
  la_records "$resources" vmid# type >/dev/null || cl_die 4 "the guest list is not an array of records with unique numeric VMIDs"
  printf '%s' "$resources" | CL_V="$CL_SENTINEL_VMID" cl_json_get '
    my ($r) = grep { $_->{vmid} == $ENV{CL_V} } @$d;
    $r ? join("|", $r->{type} // "", $r->{node} // "", $r->{status} // "", $r->{template} ? 1 : 0, $r->{pool} // "") : "absent"' \
    || cl_die 4 "cannot read the guest list"
}

# la_verify_fixture CODE — refuse (exit CODE) unless the guest has exactly the fixture shape.
# Sets la_disk to the disk line it found.
la_verify_fixture() {
  local code=$1 row cfg problems
  row=$(la_guest_row)
  [ "$row" != absent ] || cl_die "$code" "guest $CL_SENTINEL_VMID is not there"
  [ "$row" = "qemu|$node|stopped|0|" ] \
    || cl_die "$code" "guest $CL_SENTINEL_VMID does not have the fixture shape: (type|node|status|template|pool) is '$row', expected 'qemu|$node|stopped|0|' (stopped, no template, no pool)"
  cfg=$(pvesh get "/nodes/$node/qemu/$CL_SENTINEL_VMID/config" --output-format json) \
    || cl_die 4 "cannot read the config of guest $CL_SENTINEL_VMID"
  problems=$(printf '%s' "$cfg" | CL_V="$CL_SENTINEL_VMID" CL_S="$CL_VM_STORAGE" CL_D="$fixture_desc" cl_json_get '
    die "config is not an object\n" unless ref $d eq "HASH";
    my %ok = map { $_ => 1 } qw(digest name memory cores sockets scsi0 scsihw description boot ostype numa smbios1 vmgenid meta);
    my @p = map { "unexpected key $_" } grep { !$ok{$_} } sort keys %$d;
    my $desc = $d->{description} // ""; $desc = "" if ref $desc; $desc =~ s/\s+\z//;
    push @p, "name" unless !ref($d->{name}) && ($d->{name} // "") eq "corelab-sentinel";
    push @p, "description marker" unless $desc eq $ENV{CL_D};
    push @p, "scsi0" unless !ref($d->{scsi0}) && ($d->{scsi0} // "") =~ /\A\Q$ENV{CL_S}\E:vm-\Q$ENV{CL_V}\E-disk-[0-9]+,size=1G\z/;
    join("; ", @p)') || cl_die 4 "the guest config is not a JSON object"
  [ -z "$problems" ] || cl_die "$code" "guest $CL_SENTINEL_VMID does not have the fixture shape: $problems"
  la_disk=$(printf '%s' "$cfg" | cl_json_get '$d->{scsi0}') || cl_die 4 "cannot read the disk line"
}

# la_digest — the guest's config digest, checked.
la_digest() {
  local d
  d=$(cl_guest_digest qemu "$CL_SENTINEL_VMID" "$node") || cl_die 4 "cannot read the config digest"
  [[ "$d" =~ ^[0-9a-f]{32,64}$ ]] || cl_die 4 "the config digest has an unexpected form"
  printf '%s' "$d"
}

# la_backup_volids — the volume ids of backups of the sentinel on the backup storage, one per line.
la_backup_volids() {
  local backups
  backups=$(pvesh get "/nodes/$node/storage/$CL_SENTINEL_BACKUP_STORAGE/content" --content backup --output-format json) \
    || cl_die 4 "cannot list backups on $CL_SENTINEL_BACKUP_STORAGE"
  la_records "$backups" volid vmid# >/dev/null || cl_die 4 "the backup list is not an array of records with unique volids and numeric VMIDs"
  printf '%s' "$backups" | CL_V="$CL_SENTINEL_VMID" cl_json_get '
    join("\n", map { $_->{volid} } grep { $_->{vmid} == $ENV{CL_V} } @$d)' || cl_die 4 "cannot read the backup list"
}

row=$(la_guest_row)
if [ "$have_record" = 1 ]; then
  [ "$row" != absent ] || cl_die 3 "the record says guest $CL_SENTINEL_VMID was created here, but it is gone; not recreating it. Check by hand what happened to it"
  la_verify_fixture 3
  now_digest=$(la_digest)
  [ "$now_digest" = "${rec[digest]}" ] || cl_die 3 "the config of guest $CL_SENTINEL_VMID changed since the record was written; check what changed by hand"
  [ "$la_disk" = "${rec[disk]}" ] || cl_die 3 "the disk line of guest $CL_SENTINEL_VMID differs from the record"
  cl_log "sentinel $CL_SENTINEL_VMID matches the record and the fixture shape"
  cl_log "NOT PROVEN: that its disk is still empty or that the backup is intact; check by hand if it matters"
else
  [ "$row" = absent ] || cl_die 3 "VMID $CL_SENTINEL_VMID is used by a guest this script has no record of creating ('$row'). It may be a real guest. Check by hand: its config, disks, pool and backups; if it is a leftover fixture of yours, remove it yourself or choose another VMID"
  unrecorded=$(la_backup_volids)
  [ -z "$unrecorded" ] || cl_die 3 "backups of VMID $CL_SENTINEL_VMID already exist on $CL_SENTINEL_BACKUP_STORAGE and nothing records them; they may belong to a real guest. Check by hand"
  { [ ! -e "$iso" ] && [ ! -L "$iso" ]; } || cl_die 3 "$iso exists and nothing records it; check by hand whether it is yours"
  orphans=$(pvesh get "/nodes/$node/storage/$CL_VM_STORAGE/content" --vmid "$CL_SENTINEL_VMID" --output-format json) \
    || cl_die 4 "cannot list volumes on $CL_VM_STORAGE"
  found=$(la_records "$orphans" volid) || cl_die 4 "the volume list is not an array of records with unique volids"
  [ "$found" = 0 ] || cl_die 3 "$CL_VM_STORAGE holds $found volume(s) of VMID $CL_SENTINEL_VMID but no guest uses them; not creating over them. Check by hand"
  qm create "$CL_SENTINEL_VMID" --name corelab-sentinel --memory 64 --cores 1 \
    --scsi0 "$CL_VM_STORAGE:1" --description "$fixture_desc" \
    || cl_die 4 "sentinel create failed; check guest $CL_SENTINEL_VMID by hand (nothing was removed)"
  cl_log "sentinel $CL_SENTINEL_VMID created"
  la_verify_fixture 5
  rec[vmid]=$CL_SENTINEL_VMID
  rec[node]=$node
  rec[host]=$host_id
  rec[lab_storage]=$CL_LAB_STORAGE
  rec[lab_path]=$p
  rec[vm_storage]=$CL_VM_STORAGE
  rec[backup_storage]=$CL_SENTINEL_BACKUP_STORAGE
  rec[iso_path]=$iso
  rec[digest]=$(la_digest)
  rec[disk]=$la_disk
  [[ "${rec[disk]}" =~ $expected_disk_re ]] || cl_die 5 "the new guest's disk line has an unexpected form"
  la_save_record
fi

# --- the backup ----------------------------------------------------------------------
vols=$(la_backup_volids)
if [ -n "${rec[backup_volid]:-}" ]; then
  [ "$vols" = "${rec[backup_volid]}" ] \
    || cl_die 3 "the backups of VMID $CL_SENTINEL_VMID on $CL_SENTINEL_BACKUP_STORAGE are not exactly the recorded one (recorded: ${rec[backup_volid]}); check by hand"
else
  [ -z "$vols" ] || cl_die 3 "backups of VMID $CL_SENTINEL_VMID exist on $CL_SENTINEL_BACKUP_STORAGE and nothing records them; check by hand"
  vzdump "$CL_SENTINEL_VMID" --storage "$CL_SENTINEL_BACKUP_STORAGE" --mode stop --compress zstd \
    || cl_die 4 "sentinel backup failed"
  vols=$(la_backup_volids)
  { [ -n "$vols" ] && [[ "$vols" != *$'\n'* ]]; } || cl_die 5 "expected exactly one backup of VMID $CL_SENTINEL_VMID after the dump; check by hand"
  [[ "$vols" =~ ^[A-Za-z0-9._:/+@=,_-]+$ ]] || cl_die 5 "the backup's volume id has an unexpected form"
  rec[backup_volid]=$vols
  la_save_record
fi

# --- the dummy ISO -------------------------------------------------------------------
la_ensure_template_dirs() {
  [ ! -e "$p/template" ] || [ -d "$p/template" ] || cl_die 3 "$p/template is not a directory"
  if [ ! -e "$p/template" ]; then install -d -m 0755 -o root -g root "$p/template"; fi
  la_root_dir "$p/template"
  if [ ! -e "$iso_dir" ]; then install -d -m 0755 -o root -g root "$iso_dir"; fi
  la_root_dir "$iso_dir"
}
la_ensure_template_dirs
if [ -n "${rec[iso_sha256]:-}" ]; then
  { [ ! -L "$iso" ] && [ -f "$iso" ] && [ "$(stat -c %s -- "$iso")" = 1048576 ]; } \
    || cl_die 3 "$iso is not the dummy ISO this script recorded; check by hand"
  iso_now=$(la_sha256 "$iso")
  [ "$iso_now" = "${rec[iso_sha256]}" ] || cl_die 3 "$iso differs from the dummy ISO this script recorded; check by hand"
  iso_ids=$(stat -c %d:%i -- "$iso") || cl_die 4 "cannot stat $iso"
  [ "$iso_ids" = "${rec[iso_id]}" ] || cl_die 3 "$iso is not the same file (device and inode) as the recorded dummy ISO; check by hand"
else
  { [ ! -e "$iso" ] && [ ! -L "$iso" ]; } || cl_die 3 "$iso exists and nothing records it; check by hand whether it is yours"
  # noclobber: the shell creates the file with O_EXCL, so it never writes through a link.
  ( set -o noclobber; head -c 1048576 /dev/zero > "$iso" ) || cl_die 4 "cannot create $iso"
  rec[iso_sha256]=$(la_sha256 "$iso")
  rec[iso_id]=$(stat -c %d:%i -- "$iso") || cl_die 4 "cannot stat $iso"
  la_save_record
fi

digest=$(la_digest)
[ "$digest" = "${rec[digest]}" ] || cl_die 5 "the config digest changed while the fixtures were being made"
echo "sentinel config digest: $digest"
cl_log "sentinel fixtures ready"
