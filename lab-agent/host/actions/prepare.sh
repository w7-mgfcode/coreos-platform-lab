# shellcheck shell=bash
# Action: prepare
#   1. pool CL_POOL
#   2. directory storage CL_LAB_STORAGE at CL_LAB_STORAGE_PATH (snippets,import,iso,backup)
#   3. host user corelab-snip, its snippet directory and the forced-command writer
#   4. routine ACLs for CL_USER and CL_USER!CL_TOKEN
# No network change, no disk change, no deletion. After an interrupted run, running it
# again continues the steps that are missing; it does not undo anything.
#
# What it checks BEFORE its first change (every refusal is exit 3, or exit 4 when the
# host's answer cannot be read):
#   * every parameter has the plain form it is later used in;
#   * every listing it relies on (pools, storages) came back, parsed, and holds only records
#     with usable scalar fields and unique ids; an unusable listing is an error, never
#     "nothing found"; a storage of an unknown type or without a path where one is required
#     is refused;
#   * the storage path is a plain absolute path, its own real path, with no symlinked
#     component, outside the system paths, and every existing component is a real
#     root-owned directory without group/other write;
#   * the path does not equal, lie inside or contain another storage's path (by path), and
#     does not sit on a different mount of the same filesystem as another storage's path
#     (same device, or same source, found through the mount table); a layout the mount
#     table cannot place is refused;
#   * the directory is created by this script or adopted only through a record. The record
#     (root-owned, mode without group/other write, checked before it is parsed, one file per
#     storage id in the configuration directory) holds: storage id, path, the host's machine
#     id, a random token, the state (pending = about to create the directory, complete =
#     created), and once complete the directory's device, inode and filesystem id. The same
#     token is also written inside the directory in a root-owned marker file. A run adopts an
#     existing directory only if the record is for this host, id and path, the marker holds
#     the record's token, and (when complete) device, inode and filesystem id still match. A
#     directory replaced by another one, a newly mounted filesystem, a record copied from
#     another host, or a pending record whose directory carries no matching marker is refused;
#   * no mount lies at or beneath the directory (this script never makes one);
#   * the record and marker prove that this script made that directory instance on this host
#     and that it has not been swapped. They do not prove its contents are unchanged, and they
#     are only as trustworthy as root's own files and the machine id (a cloned machine id
#     defeats the host binding);
#   * before any ownership or mode change, the children are inspected: only the names a
#     directory storage creates plus the marker, and in `snippets` only regular
#     `corelab-*.ign` files;
#   * the home of corelab-snip, its .ssh, /usr/local/sbin and /etc/corelab, and all their
#     ancestors, are real root-owned directories without group/other write. The script never
#     works inside a directory that corelab-snip can modify: the older layout in which that
#     user owns its home is refused, not repaired.
# Root writes: new files are created with mktemp in such a root-owned directory and moved
# with `mv -T`, which replaces a destination link instead of following it.
# Not shown by any check here: that the storage is active, that the roles and ACL paths are
# right, that sshd accepts the key file (all live checks).
#
# Parameters: CL_POOL CL_LAB_STORAGE CL_LAB_STORAGE_PATH CL_VM_STORAGE CL_BRIDGE
#             CL_USER CL_TOKEN CL_WORKSTATION_ADDR CL_SNIP_PUBKEY
# Embedded:   cl_file_snippet_writer, cl_file_snippet_writer_conf (added by the runner)

: "${CL_POOL:?}" "${CL_LAB_STORAGE:?}" "${CL_LAB_STORAGE_PATH:?}" "${CL_VM_STORAGE:?}" "${CL_BRIDGE:?}"
: "${CL_USER:?}" "${CL_TOKEN:?}" "${CL_WORKSTATION_ADDR:?}" "${CL_SNIP_PUBKEY:?}"
export LC_ALL=C

# Fixed host locations used by this script (assignments kept on their own lines).
la_sbin=/usr/local/sbin
la_cfgdir=/etc/corelab
la_home=/var/lib/corelab-snip
la_mountinfo=/proc/self/mountinfo
la_machine_id=/etc/machine-id

la_tmps=()
trap 'rm -f -- "${la_tmps[@]}"' EXIT
la_hint=""

la_id() { # LABEL VALUE — a plain PVE identifier
  [[ "$2" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || cl_die 3 "$1 is not a plain identifier"
}

# la_records JSON KEY [FIELD[#]...] — JSON must be an array of objects; every object has KEY
# and every FIELD as a non-empty scalar (a trailing # means digits only); KEY is unique.
# Prints the count. Anything else fails, so [{}] or an empty reply never reads as "absent".
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
        die "$f is not numeric\n" if $s =~ /#\z/ && $v !~ /\A[0-9]+\z/;
      }
      my $k = $spec[0]; $k =~ s/#\z//;
      die "duplicate record\n" if $seen{$r->{$k}}++;
    }
    scalar @$d'
}

# la_list_has JSON FIELD VALUE — 1 or 0, after la_records accepted the listing.
la_list_has() {
  la_records "$1" "$2" >/dev/null || return 1
  printf '%s' "$1" | CL_F="$2" CL_V="$3" cl_json_get 'scalar grep { $_->{$ENV{CL_F}} eq $ENV{CL_V} } @$d'
}

# la_root_dir PATH — a real directory (not a link), owned by root, not writable by group/other.
la_root_dir() {
  local mode
  [ ! -L "$1" ] && [ -d "$1" ] || cl_die 3 "$1 is not a real directory"
  [ "$(stat -c %u -- "$1")" = 0 ] || cl_die 3 "$1 is not owned by root.$la_hint"
  mode=$(stat -c %a -- "$1")
  [[ "$mode" =~ ^[0-7]{3,4}$ ]] || cl_die 3 "unexpected mode text for $1"
  (( (8#$mode & 8#022) == 0 )) || cl_die 3 "$1 is writable by group or others (mode $mode).$la_hint"
}

# la_root_chain PATH — every ancestor of PATH is an existing root-owned real directory.
la_root_chain() {
  local cur="" comp
  local -a parts
  IFS=/ read -ra parts <<<"${1#/}"
  for comp in "${parts[@]:0:${#parts[@]}-1}"; do
    cur="$cur/$comp"
    [ -e "$cur" ] || cl_die 3 "$cur does not exist"
    la_root_dir "$cur"
  done
}

# la_ensure_root_dir PATH — validate the ancestors and the destination first, then create it.
la_ensure_root_dir() {
  la_root_chain "$1"
  [ ! -L "$1" ] || cl_die 3 "$1 is a symbolic link"
  if [ ! -e "$1" ]; then install -d -m 0755 -o root -g root "$1"; fi
  la_root_dir "$1"
}

# la_entries DIR FORMAT — the checked directory listing (exit 4 if find fails).
la_entries() {
  local out
  out=$(find "$1" -mindepth 1 -maxdepth 1 -printf "$2") || cl_die 4 "cannot list $1"
  printf '%s' "$out"
}

# la_trusted_file FILE — a regular file (not a link) owned by root that group and others cannot write.
la_trusted_file() {
  local mode
  [ ! -L "$1" ] && [ -f "$1" ] || cl_die 3 "$1 is not a regular file"
  [ "$(stat -c %u -- "$1")" = 0 ] || cl_die 3 "$1 is not owned by root"
  mode=$(stat -c %a -- "$1")
  [[ "$mode" =~ ^[0-7]{3,4}$ ]] || cl_die 3 "unexpected mode text for $1"
  (( (8#$mode & 8#022) == 0 )) || cl_die 3 "$1 is writable by group or others (mode $mode); not trusting it"
}

# la_host_id — the machine id, a stable identity of this host that needs no network.
la_host_id() {
  local id
  la_trusted_file "$la_machine_id"
  id=$(<"$la_machine_id") || cl_die 4 "cannot read $la_machine_id"
  [[ "$id" =~ ^[0-9a-f]{32}$ ]] || cl_die 3 "$la_machine_id does not hold a machine id"
  printf '%s' "$id"
}

declare -A rec=()
# la_read_record FILE KEY... — parse a record into rec. Refuses a file that is writable by
# group or others, empty, not ending in a newline, with a line that is not key=value, an
# unknown key or a repeated key. Nothing in it is ever executed.
la_read_record() {
  local file=$1 line key val allowed=" ${*:2} " last
  la_trusted_file "$file"
  [ -s "$file" ] || cl_die 3 "$file is empty"
  last=$(tail -c1 -- "$file" | od -An -tx1) || cl_die 4 "cannot read $file"
  [ "${last// /}" = 0a ] || cl_die 3 "$file does not end with a newline (cut short or appended to)"
  while IFS= read -r line; do
    [[ "$line" =~ ^([a-z0-9_]+)=([A-Za-z0-9._:/+@=,_-]*)$ ]] || cl_die 3 "$file is malformed"
    key=${BASH_REMATCH[1]}; val=${BASH_REMATCH[2]}
    case "$allowed" in *" $key "*) ;; *) cl_die 3 "$file has an unknown key" ;; esac
    [ -z "${rec[$key]+x}" ] || cl_die 3 "$file repeats a key"
    rec[$key]=$val
  done < "$file"
}

# la_write_record FILE KEY... — write the set keys of rec atomically, mode 0644, root-owned directory.
la_write_record() {
  local file=$1 k tmp
  shift
  la_ensure_root_dir "$la_cfgdir"
  tmp=$(mktemp "$la_cfgdir/.record.XXXXXXXX")
  la_tmps+=("$tmp")
  for k in "$@"; do
    [ -z "${rec[$k]:-}" ] || printf '%s=%s\n' "$k" "${rec[$k]}"
  done > "$tmp"
  chmod 0644 "$tmp"
  mv -fT -- "$tmp" "$file"
}

# la_dir_ids PATH — "device inode filesystem-id" of a directory.
la_dir_ids() {
  local dev ino fsid
  dev=$(stat -c %d -- "$1") || cl_die 4 "cannot stat $1"
  ino=$(stat -c %i -- "$1") || cl_die 4 "cannot stat $1"
  fsid=$(stat -f -c %i -- "$1") || cl_die 4 "cannot stat the filesystem of $1"
  [[ "$dev" =~ ^[0-9]+$ && "$ino" =~ ^[0-9]+$ && "$fsid" =~ ^[0-9a-f]+$ ]] || cl_die 4 "unexpected stat output for $1"
  printf '%s %s %s' "$dev" "$ino" "$fsid"
}

# la_mounts_under PATH — every mount point at or beneath PATH (fails if the table is unreadable).
la_mounts_under() {
  perl -e '
    my ($info, $path) = @ARGV; open my $fh, "<", $info or exit 2;
    while (<$fh>) {
      my @f = split " ", ((split / - /, $_, 2)[0]); next unless @f >= 6;
      my $mp = $f[4]; $mp =~ s/\\([0-7]{3})/chr(oct($1))/ge;
      print "$mp\n" if $mp eq $path || index($mp, "$path/") == 0;
    }' -- "$la_mountinfo" "$1"
}

# la_check_marker TOKEN — the root-owned marker inside the directory carries the record's token.
la_check_marker() {
  local m="$p/.corelab-project" want
  [ -e "$m" ] || cl_die 3 "$p has no marker of this script; I cannot show that I made this directory instance"
  la_trusted_file "$m"
  want="storage=$CL_LAB_STORAGE
token=$1"
  [ "$(<"$m")" = "$want" ] || cl_die 3 "the marker in $p does not match the record; the directory is not the one this script made"
}

# la_mount_of PATH — the mount that holds PATH, read from the mount table: mount id, major:minor,
# source, fstype and mount point, separated by the unit separator (0x1f). Fails if the table
# cannot be read or no mount holds PATH.
la_mount_of() {
  perl -e '
    my ($info, $path) = @ARGV; open my $fh, "<", $info or exit 1; my $best;
    while (<$fh>) {
      chomp; my ($pre, $post) = split / - /, $_, 2; next unless defined $post;
      my @f = split " ", $pre; my @g = split " ", $post;
      next unless @f >= 6 && @g >= 2;
      my $mp = $f[4]; $mp =~ s/\\([0-7]{3})/chr(oct($1))/ge;
      next unless $mp eq "/" || $path eq $mp || index($path, "$mp/") == 0;
      my $src = $g[1]; $src =~ s/\\([0-7]{3})/chr(oct($1))/ge;
      $best = [$f[0], $f[2], $src, $g[0], $mp] if !$best || length($mp) >= length($best->[4]);
    }
    exit 1 unless $best; print join("\x1f", @$best), "\n";' -- "$la_mountinfo" "$1"
}

# la_check_storage_path PATH — lexical and ownership checks of the path and its ancestors.
la_check_storage_path() {
  local p=$1 d cur comp parent
  local -a parts
  local denied="/bin /boot /dev /etc /home /lib /lib32 /lib64 /mnt/pve /proc /root /run /sbin /sys /tmp /usr /var/lib/corelab-snip /var/lib/pve-cluster /var/lib/vz /var/log /var/run /var/tmp"
  [ "${#p}" -le 200 ] || cl_die 3 "CL_LAB_STORAGE_PATH is longer than 200 characters"
  [[ "$p" =~ ^/[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)+$ ]] \
    || cl_die 3 "CL_LAB_STORAGE_PATH must be an absolute path of at least two plain components (letters, digits, . _ -), without '//' or a trailing '/'"
  case "$p/" in */./*|*/../*) cl_die 3 "CL_LAB_STORAGE_PATH must not contain '.' or '..' components" ;; esac
  for d in $denied; do
    if [ "$p" = "$d" ] || [[ "$p" == "$d"/* ]] || [[ "$d" == "$p"/* ]]; then
      cl_die 3 "refusing $p: it equals, lies inside or contains the system path $d"
    fi
  done
  IFS=/ read -ra parts <<<"${p#/}"
  cur=""
  for comp in "${parts[@]}"; do
    cur="$cur/$comp"
    [ ! -L "$cur" ] || cl_die 3 "$cur is a symbolic link; use the real path"
    if [ -e "$cur" ] && [ "$cur" != "$p" ]; then la_root_dir "$cur"; fi
  done
  parent=${p%/*}
  [ -d "$parent" ] || cl_die 3 "parent directory $parent does not exist; create it first"
  if [ -e "$p" ]; then
    la_root_dir "$p"
    [ "$(realpath -e -- "$p")" = "$p" ] || cl_die 3 "$p is not its own real path"
  fi
}

# la_inspect_storage_dir PATH — the children of an adopted directory, before any change.
la_inspect_storage_dir() {
  local p=$1 entries comp kind name
  entries=$(la_entries "$p" '%f\n')
  while IFS= read -r comp; do
    [ -n "$comp" ] || continue
    case "$comp" in
      dump|images|private|snippets|import|template|lost+found|.corelab-project) ;;
      *) cl_die 3 "$p holds '$comp', which a project storage does not contain; refusing to adopt it" ;;
    esac
  done <<<"$entries"
  if [ -e "$p/snippets" ]; then
    [ ! -L "$p/snippets" ] && [ -d "$p/snippets" ] || cl_die 3 "$p/snippets is not a real directory"
    entries=$(la_entries "$p/snippets" '%y %f\n')
    while read -r kind name; do
      [ -n "$kind" ] || continue
      [ "$kind" = f ] && [[ "$name" =~ ^corelab-[a-z0-9][a-z0-9-]{0,47}\.ign$ ]] \
        || cl_die 3 "$p/snippets holds an entry that is not a regular corelab-*.ign file; refusing to give it to corelab-snip"
    done <<<"$entries"
  fi
}

# --- 0. parameters (no read of the host yet) -------------------------------------------
la_id CL_POOL "$CL_POOL"
la_id CL_LAB_STORAGE "$CL_LAB_STORAGE"
la_id CL_VM_STORAGE "$CL_VM_STORAGE"
la_id CL_BRIDGE "$CL_BRIDGE"
[[ "$CL_USER" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*@[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || cl_die 3 "CL_USER must look like name@realm"
[[ "$CL_TOKEN" =~ ^[A-Za-z][A-Za-z0-9._-]*$ ]] || cl_die 3 "CL_TOKEN must be a plain token id"
# One IP address, nothing else: it is written into a from="" restriction of authorized_keys.
[[ "$CL_WORKSTATION_ADDR" =~ ^([0-9]{1,3}(\.[0-9]{1,3}){3}|[0-9A-Fa-f:]{2,39})$ ]] \
  || cl_die 3 "CL_WORKSTATION_ADDR must be one IPv4 or IPv6 address"
# One public key on one line: it is written into authorized_keys.
[[ "$CL_SNIP_PUBKEY" =~ ^(ssh-ed25519|sk-ssh-ed25519@openssh\.com|ecdsa-sha2-nistp(256|384|521))\ [A-Za-z0-9+/]+={0,3}$ ]] \
  || cl_die 3 "CL_SNIP_PUBKEY is not one ed25519/ecdsa public key"
la_check_storage_path "$CL_LAB_STORAGE_PATH"
p=$CL_LAB_STORAGE_PATH

# --- 1. read the host's state (no change yet) -------------------------------------------
pools=$(pvesh get /pools --output-format json) || cl_die 4 "cannot list pools"
have_pool=$(la_list_has "$pools" poolid "$CL_POOL") || cl_die 4 "the pool list is not an array of records with a poolid"
[ "$have_pool" = 0 ] || [ "$have_pool" = 1 ] || cl_die 4 "unexpected answer while looking for pool $CL_POOL"

storage_list=$(pvesh get /storage --output-format json) || cl_die 4 "cannot list storages"
rows=$(printf '%s' "$storage_list" | cl_shape_ok list && printf '%s' "$storage_list" | cl_json_get '
  my (%seen, %pathful, %pathless);
  @pathful{qw(dir nfs cifs cephfs glusterfs btrfs)} = ();
  @pathless{qw(lvm lvmthin zfspool zfs rbd iscsi iscsidirect pbs)} = ();
  join("\n", map {
    die "storage entry is not an object\n" unless ref $_ eq "HASH";
    for my $f (qw(storage type)) { die "storage entry without $f\n" unless defined $_->{$f} && !ref $_->{$f} && length $_->{$f} }
    die "duplicate storage id\n" if $seen{$_->{storage}}++;
    my $t = $_->{type}; my $path = "";
    if (exists $pathful{$t}) {
      $path = $_->{path};
      die "storage without a usable path\n" unless defined $path && !ref $path && $path =~ m{\A/};
    } elsif (!exists $pathless{$t}) { die "storage of an unknown type\n" }
    my $c = $_->{content} // ""; die "content is not text\n" if ref $c;
    join("\x1f", $_->{storage}, $t, $path, $c) } @$d)') \
  || cl_die 4 "the storage list is unusable: not an array of records with id, type and (where required) path, or an unknown storage type"

# Provenance: the host, and the record of an earlier run in a root-owned location.
host_id=$(la_host_id)
la_record="$la_cfgdir/storage-$CL_LAB_STORAGE.record"
rec_state=none
[ ! -L "$la_cfgdir" ] || cl_die 3 "$la_cfgdir is a symbolic link"
if [ -e "$la_cfgdir" ]; then
  la_root_chain "$la_cfgdir"
  la_root_dir "$la_cfgdir"
  [ ! -L "$la_record" ] || cl_die 3 "$la_record is a symbolic link"
  if [ -e "$la_record" ]; then
    la_read_record "$la_record" storage path host state token dev ino fsid
    [ "${rec[storage]:-}" = "$CL_LAB_STORAGE" ] && [ "${rec[path]:-}" = "$p" ] \
      || cl_die 3 "$la_record names another storage or path than this run; not touching either"
    [ "${rec[host]:-}" = "$host_id" ] || cl_die 3 "$la_record was written on another host; not trusting it"
    [[ "${rec[token]:-}" =~ ^[0-9a-f]{32}$ ]] || cl_die 3 "$la_record has no usable token"
    case "${rec[state]:-}" in
      pending) ;;
      complete)
        [[ "${rec[dev]:-}" =~ ^[0-9]+$ && "${rec[ino]:-}" =~ ^[0-9]+$ && "${rec[fsid]:-}" =~ ^[0-9a-f]+$ ]] \
          || cl_die 3 "$la_record is complete but has no usable directory identity" ;;
      *) cl_die 3 "$la_record has an unknown state" ;;
    esac
    rec_state=${rec[state]}
  fi
fi

mine=""
cand_x=$p
[ -e "$p" ] || cand_x=${p%/*}
cand_mount=$(la_mount_of "$cand_x") || cl_die 3 "cannot place $cand_x in the mount table $la_mountinfo; refusing a layout I cannot verify"
while IFS=$'\037' read -r sid stype spath scontent; do
  [ -n "$sid" ] || continue
  if [ "$sid" = "$CL_LAB_STORAGE" ]; then mine="$stype|$spath|$scontent"; continue; fi
  [ -n "$spath" ] || continue
  rp=$(realpath -m -- "$spath") || cl_die 4 "cannot resolve the path of storage $sid"
  if [ "$rp" = / ] || [ "$rp" = "$p" ] || [[ "$p" == "$rp"/* ]] || [[ "$rp" == "$p"/* ]]; then
    cl_die 3 "CL_LAB_STORAGE_PATH overlaps the path of storage $sid; refusing"
  fi
  [ -e "$rp" ] || cl_die 3 "the path of storage $sid does not exist on this host, so I cannot verify the layout; refusing"
  other_mount=$(la_mount_of "$rp") || cl_die 3 "cannot place the path of storage $sid in the mount table; refusing"
  IFS=$'\037' read -r cid cdev csrc _ _ <<<"$cand_mount"
  IFS=$'\037' read -r oid odev osrc _ _ <<<"$other_mount"
  if [ "$cid" != "$oid" ]; then
    [ "$cdev" != "$odev" ] \
      || cl_die 3 "CL_LAB_STORAGE_PATH and storage $sid are on different mounts of the same device (bind mount or alias); refusing"
    case "$csrc" in
      tmpfs|none|proc|sysfs|devtmpfs|devpts|overlay|cgroup*) ;;
      *) [ "$csrc" != "$osrc" ] || cl_die 3 "CL_LAB_STORAGE_PATH and storage $sid come from the same mount source through different mounts; refusing" ;;
    esac
  fi
  want_id=$(stat -c %d:%i -- "$p" 2>/dev/null || true)
  if [ -n "$want_id" ] && [ "$(stat -c %d:%i -- "$rp")" = "$want_id" ]; then
    cl_die 3 "CL_LAB_STORAGE_PATH is the same directory as storage $sid; refusing"
  fi
done <<<"$rows"

if [ -e "$p" ]; then
  [ "$rec_state" != none ] || cl_die 3 "$p already exists and no root-owned record of an earlier run names it for storage $CL_LAB_STORAGE; refusing to adopt it, even if it looks empty. Remove it if you made it for this, or choose a path that does not exist"
  la_check_marker "${rec[token]}"
  under=$(la_mounts_under "$p") || cl_die 3 "cannot read the mount table $la_mountinfo; refusing a layout I cannot verify"
  [ -z "$under" ] || cl_die 3 "a mount lies at or beneath $p ($(printf '%s' "$under" | head -n 1)); this script makes none, so I will not adopt it"
  if [ "$rec_state" = complete ]; then
    [ "$(la_dir_ids "$p")" = "${rec[dev]} ${rec[ino]} ${rec[fsid]}" ] \
      || cl_die 3 "$p is not the directory instance recorded for it (device, inode or filesystem id differ); it was replaced or something was mounted there. Check by hand"
  fi
  la_inspect_storage_dir "$p"
else
  [ "$rec_state" != complete ] || cl_die 3 "the record says $p was created, but it is gone; not recreating it. Check by hand what happened"
  [ -z "$mine" ] || cl_die 3 "storage $CL_LAB_STORAGE is registered but $p does not exist and this script has no record of creating it; not changing it. Check the storage by hand"
fi

# The places root writes to, and the home of corelab-snip: validated before any change.
la_root_chain "$la_sbin"; la_root_dir "$la_sbin"
la_root_chain "$la_cfgdir"
la_hint=" The older layout, in which corelab-snip owns its home or .ssh, is refused: set both to root:root mode 0755 and remove anything but authorized_keys from .ssh, then run again."
la_root_chain "$la_home"
[ ! -L "$la_home" ] || cl_die 3 "$la_home is a symbolic link"
if [ -e "$la_home" ]; then
  la_root_dir "$la_home"
  [ ! -L "$la_home/.ssh" ] || cl_die 3 "$la_home/.ssh is a symbolic link"
  if [ -e "$la_home/.ssh" ]; then
    la_root_dir "$la_home/.ssh"
    ssh_entries=$(la_entries "$la_home/.ssh" '%f\n')
    while IFS= read -r comp; do
      [ -z "$comp" ] || [ "$comp" = authorized_keys ] || cl_die 3 "$la_home/.ssh holds '$comp'; remove it by hand (nothing is deleted here)"
    done <<<"$ssh_entries"
  fi
fi
la_hint=""
if id corelab-snip >/dev/null 2>&1; then
  [ "$(getent passwd corelab-snip | cut -d: -f6)" = "$la_home" ] \
    || cl_die 3 "user corelab-snip exists with a home other than $la_home; not changing it"
fi

# --- 2. changes ----------------------------------------------------------------------
if [ "$have_pool" = 1 ]; then
  cl_log "pool $CL_POOL exists"
else
  pveum pool add "$CL_POOL" --comment "CoreOS Platform Lab project guests" || cl_die 4 "pool add failed"
  cl_log "pool $CL_POOL created"
fi

want_content="snippets,import,iso,backup"
if [ ! -e "$p" ]; then
  # Pending record first, then the directory, then the marker, then the completed record: an
  # interrupted run leaves a record the next run can recognise, never an unrecorded directory.
  la_ensure_root_dir "$la_cfgdir"
  token=$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n') || cl_die 4 "cannot make a token"
  [[ "$token" =~ ^[0-9a-f]{32}$ ]] || cl_die 4 "unexpected token form"
  rec=([storage]="$CL_LAB_STORAGE" [path]="$p" [host]="$host_id" [state]=pending [token]="$token")
  la_write_record "$la_record" storage path host state token dev ino fsid
  install -d -m 0755 -o root -g root "$p"
  la_root_dir "$p"
  tmp=$(mktemp "$p/.marker.XXXXXXXX")
  la_tmps+=("$tmp")
  printf 'storage=%s\ntoken=%s\n' "$CL_LAB_STORAGE" "$token" > "$tmp"
  chmod 0644 "$tmp"
  mv -fT -- "$tmp" "$p/.corelab-project"
  rec_state=pending
fi
if [ "$rec_state" = pending ]; then
  dir_ids=$(la_dir_ids "$p")
  read -r id_dev id_ino id_fsid <<<"$dir_ids"
  rec[dev]=$id_dev; rec[ino]=$id_ino; rec[fsid]=$id_fsid
  rec[state]=complete
  la_write_record "$la_record" storage path host state token dev ino fsid
fi
if [ -z "$mine" ]; then
  pvesm add dir "$CL_LAB_STORAGE" --path "$p" --content "$want_content" || cl_die 4 "storage add failed"
  cl_log "storage $CL_LAB_STORAGE created at $p"
else
  IFS='|' read -r s_type s_path s_content <<<"$mine"
  [ "$s_type" = dir ] && [ "$(realpath -m -- "$s_path")" = "$p" ] \
    || cl_die 3 "storage $CL_LAB_STORAGE exists with type/path $s_type $s_path; not changing it"
  for c in snippets import iso backup; do
    case ",$s_content," in *",$c,"*) ;; *) cl_die 3 "storage $CL_LAB_STORAGE lacks content $c; fix by hand" ;; esac
  done
  cl_log "storage $CL_LAB_STORAGE exists as recorded"
fi
pvesm status --storage "$CL_LAB_STORAGE" >/dev/null || cl_die 4 "storage $CL_LAB_STORAGE not active"
la_root_dir "$p"
snip_dir="$p/snippets"
[ ! -L "$snip_dir" ] || cl_die 3 "$snip_dir is a symbolic link"
if [ ! -e "$snip_dir" ]; then install -d -m 0755 -o root -g root "$snip_dir"; fi
[ -d "$snip_dir" ] && [ "$(realpath -e -- "$snip_dir")" = "$snip_dir" ] || cl_die 3 "$snip_dir is not a real directory"
la_inspect_storage_dir "$p"

# snippet writer: the user, a root-owned home, the writer, its config, its key
if ! id corelab-snip >/dev/null 2>&1; then
  # /bin/sh, not nologin: sshd runs the forced command through the login shell.
  # No home is created by useradd: the home is made below, owned by root.
  useradd --system --no-create-home --home-dir "$la_home" --shell /bin/sh \
    --comment "corelab snippet writer" corelab-snip || cl_die 4 "useradd failed"
  passwd -l corelab-snip >/dev/null
  cl_log "user corelab-snip created (password locked)"
fi
chown -h root:corelab-snip -- "$snip_dir"
chmod 2770 "$snip_dir"

la_ensure_root_dir "$la_home"
ssh_dir="$la_home/.ssh"
la_ensure_root_dir "$ssh_dir"
la_ensure_root_dir "$la_cfgdir"
la_root_dir "$la_sbin"

tmp=$(mktemp "$la_sbin/.corelab-snippet-put.XXXXXXXX")
la_tmps+=("$tmp")
cl_file_snippet_writer > "$tmp"
chmod 0755 "$tmp"
perl -c "$tmp" >/dev/null 2>&1 || cl_die 4 "snippet writer does not compile"
mv -fT -- "$tmp" "$la_sbin/corelab-snippet-put"

tmp=$(mktemp "$la_cfgdir/.snippet-writer.conf.XXXXXXXX")
la_tmps+=("$tmp")
cl_file_snippet_writer_conf | sed "s#@SNIPPET_DIR@#$snip_dir#" > "$tmp"
chmod 0644 "$tmp"
mv -fT -- "$tmp" "$la_cfgdir/snippet-writer.conf"

# root:root 0644 is what sshd's StrictModes would have to accept (not checked here).
tmp=$(mktemp "$ssh_dir/.authorized_keys.XXXXXXXX")
la_tmps+=("$tmp")
printf 'restrict,from="%s",command="/usr/local/sbin/corelab-snippet-put" %s\n' \
  "$CL_WORKSTATION_ADDR" "$CL_SNIP_PUBKEY" > "$tmp"
chmod 0644 "$tmp"
mv -fT -- "$tmp" "$ssh_dir/authorized_keys"
cl_log "snippet writer installed for $snip_dir"

# 4. routine ACLs (same on user and token; token rights are the intersection)
cl_acl PVEVMAdmin "/pool/$CL_POOL"
cl_acl PVEDatastoreUser "/storage/$CL_LAB_STORAGE"
cl_acl PVEDatastoreUser "/storage/$CL_VM_STORAGE"
cl_acl PVESDNUser "/sdn/zones/localnetwork/$CL_BRIDGE"
cl_log "routine ACLs set"

echo "--- effective ACLs for $CL_USER"
acls=$(pveum acl list --output-format json) || cl_die 4 "cannot list ACLs"
printf '%s' "$acls" | cl_shape_ok list || cl_die 4 "the ACL list is not an array"
printf '%s' "$acls" | CL_U="$CL_USER" cl_json_get '
  join("\n", map { ($_->{path} // "") . " " . ($_->{ugid} // "") . " " . ($_->{roleid} // "") }
              grep { ref $_ eq "HASH" && index($_->{ugid} // "", $ENV{CL_U}) == 0 } @$d)' \
  || cl_die 4 "cannot read the ACL list"
echo
cl_log "prepare done"
