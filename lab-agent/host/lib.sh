# shellcheck shell=bash
# Helper functions prepended to every script host-run sends to the Proxmox host.
# Runs as root on the host. Depends only on what a stock Proxmox VE host has:
# bash, perl with JSON::PP, pvesh, qm, pct, pvesm, vzdump.
#
# Exit codes: 3 = state differs from what was approved (nothing changed for this item),
#             4 = a command failed, 5 = verification after a change failed,
#             6 = a live safety check refused (apply-manifest runs them for every item
#                 before any change, and again before each destructive step). A listing
#                 that is empty, malformed or unreadable where a safety decision needs it
#                 also gives 6; the same after a change gives 5 (verification could not be done).
#             7 = destructive execution is disabled in this version (see cl_destructive_gate):
#                 nothing was read or changed.
#
# What these checks are, and are not: every check reads the host's state and decides. None of
# them holds a lock across the decision and the command that follows it (see cl_prestate), so a
# concurrent administrator, scheduled job or API client can still change the host between the last
# check and the command. OPEN RISK (owner decision pending): this is neither fixed nor accepted.
# The window is reduced (each destructive command re-checks immediately before it), not closed.

cl_log() { printf '[corelab] %s\n' "$*" >&2; }
cl_die() { local code=$1; shift; printf '[corelab] ERROR: %s\n' "$*" >&2; exit "$code"; }

# DESTRUCTIVE EXECUTION IS DISABLED IN THIS VERSION (owner decision of 2026-11-16).
# The cleanup-manifest path can stop a guest, back it up in stop mode, destroy it and free a volume.
# Its safety rests on guarantees that are NOT established: the window between the last check and the
# command is open (see cl_prestate); that the guest and volume listings are complete, and that no
# other volume depends on a removed one (linked clones, backing chains, storage-level origins), is
# unproven; an inactive storage hides its volumes. None of this was ever run on a real host.
# Until those guarantees are established and independently reviewed, two things hold in this text:
#   1. Every function of that class, and the manifest script as a whole, calls this gate first and
#      stops before it reads or changes anything: exit 7. The function has no other branch.
#   2. THE DESTRUCTIVE COMMANDS THEMSELVES ARE NOT IN THIS FILE. Where one stood there is a comment
#      line that starts with "# DISABLED-COMMAND:", followed by a second call of the gate. This is
#      what holds when the gate does not: a shell in which `exit` (or `cl_die`) has been replaced by
#      an exported function or a start-up file can run past every refusal in this file, and then it
#      finds no stop, backup, destroy or free command to run. Nothing in the environment, the
#      arguments or the settings can put those commands back; only an edit of this file can.
# The guards further down are kept and are exercised offline, against stub tools only, through a
# test-only copy of this text in which the gate is a no-op and the comment lines are commands again
# (tests/fixtures.py). A stub pass is not evidence that execution is safe.
cl_destructive_gate() { cl_die 7 "destructive execution is disabled in this version of the tooling ($1); nothing was read or changed"; }

# cl_json_get PERL_EXPR  — read JSON on stdin, print the expression's value.
# The expression sees the decoded document as $d.
cl_json_get() {
  CL_EXPR="$1" perl -MJSON::PP -e '
    my $d = JSON::PP->new->utf8->decode(do { local $/; <STDIN> });
    my $v = eval $ENV{CL_EXPR}; die $@ if $@;
    print defined $v ? $v : "";'
}

# cl_shape_ok KIND — read JSON on stdin; succeed only when it has the expected shape.
# `null`, an empty string, text that is not JSON, and the wrong shape all fail. This is the
# shape control for every listing a safety decision rests on (it does NOT prove completeness): a listing that came back
# empty, malformed or unreadable with exit status 0 must not read as "nothing found" (R3-2).
#   array, list, object     an array that is non-empty / possibly empty, a non-empty object
#   guests, anyguests       /cluster/resources --type vm: every record is a qemu or lxc guest with
#                           a numeric vmid and a node name ([{}] is not a guest listing)
#   content, anycontent     a storage content listing: every record has a volume id
#   snapshots               a snapshot listing: every record has a path-safe name
#   config                  a guest or snapshot config: a non-empty object whose values are all
#                           plain scalars (a nested value, say {"data":{...}}, is refused)
#   pending                 a pending listing: every record has a key and at least one of value,
#                           pending, delete (a record without a payload says nothing: refused)
#   tasks                   a task listing (possibly empty): every record has a UPID
#   nodestorages            /nodes/N/storage: every record has a storage name and an active flag 0/1
# "any..." and tasks accept an empty array; every other kind needs at least one record.
cl_shape_ok() {
  CL_SHAPE="$1" perl -MJSON::PP -e '
    my $text = do { local $/; <STDIN> };
    my $d = eval { JSON::PP->new->utf8->decode($text // "") };
    exit 1 unless defined $d;
    my $plain = sub { my $v = shift; defined $v && (!ref $v || ref $v eq "JSON::PP::Boolean") };
    my $text_ok = sub { my ($v, $re) = @_; defined $v && !ref $v && "$v" =~ $re };
    my %rec = (
      guests => sub { my $r = shift; ref $r eq "HASH"
        && $text_ok->($r->{type}, qr/\A(?:qemu|lxc)\z/) && $text_ok->($r->{vmid}, qr/\A[1-9][0-9]{2,8}\z/)
        && $text_ok->($r->{node}, qr/\A[A-Za-z0-9][A-Za-z0-9-]{0,62}\z/)
        && (!defined $r->{pool} || $text_ok->($r->{pool}, qr/\A[A-Za-z0-9_.-]*\z/)) },
      content => sub { my $r = shift; ref $r eq "HASH"
        && $text_ok->($r->{volid}, qr/\A[A-Za-z0-9][A-Za-z0-9_.-]*:\S+\z/)
        && (!defined $r->{vmid} || $text_ok->($r->{vmid}, qr/\A[0-9]+\z/)) },
      snapshots => sub { my $r = shift; ref $r eq "HASH" && $text_ok->($r->{name}, qr/\A[A-Za-z][A-Za-z0-9_-]*\z/) },
      pending => sub { my $r = shift; ref $r eq "HASH" && $text_ok->($r->{key}, qr/\A[A-Za-z][A-Za-z0-9_]*\z/)
        && (defined $r->{value} || defined $r->{pending} || defined $r->{delete})  # a record with no payload says nothing
        && (!defined $r->{value} || $plain->($r->{value})) && (!defined $r->{pending} || $plain->($r->{pending}))
        && (!defined $r->{delete} || $plain->($r->{delete})) },
      tasks => sub { my $r = shift; ref $r eq "HASH" && $text_ok->($r->{upid}, qr/\A\S+\z/) },
      nodestorages => sub { my $r = shift; ref $r eq "HASH" && $text_ok->($r->{storage}, qr/\A[A-Za-z][A-Za-z0-9_.-]*\z/)
        && $text_ok->($r->{active}, qr/\A[01]\z/) },  # the activity flag decides what may be enumerated: it must be there
    );
    my %kind = (array => [undef, 0], list => [undef, 1], guests => ["guests", 0], anyguests => ["guests", 1],
                content => ["content", 0], anycontent => ["content", 1], snapshots => ["snapshots", 0],
                pending => ["pending", 0], tasks => ["tasks", 1], nodestorages => ["nodestorages", 0]);
    my $k = $ENV{CL_SHAPE};
    if ($k eq "object") { exit(ref $d eq "HASH" && %$d ? 0 : 1) }
    if ($k eq "config") {
      exit 1 unless ref $d eq "HASH" && %$d;
      $plain->($_) or exit 1 for values %$d;
      exit 0;
    }
    my $spec = $kind{$k} or exit 1;  # an unknown kind never passes
    exit 1 unless ref $d eq "ARRAY";
    exit 1 if !$spec->[1] && !@$d;
    if (defined $spec->[0]) { $rec{$spec->[0]}->($_) or exit 1 for @$d }
    exit 0;'
}

# cl_guest_state TYPE VMID  -> "node|name|status|template" or "absent"
cl_guest_state() {
  local type=$1 vmid=$2 json
  json=$(pvesh get /cluster/resources --type vm --output-format json) || cl_die 4 "cannot list guests"
  printf '%s' "$json" | CL_TYPE="$type" CL_VMID="$vmid" cl_json_get '
    my $out = "absent";
    for my $r (@$d) {
      next unless ($r->{type} // "") eq $ENV{CL_TYPE} && ($r->{vmid} // -1) == $ENV{CL_VMID};
      $out = join("|", $r->{node} // "", $r->{name} // "", $r->{status} // "", $r->{template} ? 1 : 0);
      last;
    }
    $out'
}

# cl_guest_digest TYPE VMID NODE  -> the config digest
cl_guest_digest() {
  local type=$1 vmid=$2 node=$3
  pvesh get "/nodes/$node/$type/$vmid/config" --output-format json \
    | cl_json_get '$d->{digest} // ""' || cl_die 4 "cannot read config of $type/$vmid"
}

# cl_expect_guest TYPE VMID NODE NAME STATUS DIGEST TEMPLATE
# Stops the whole run (exit 3) when the guest is not exactly as approved.
cl_expect_guest() {
  local type=$1 vmid=$2 node=$3 name=$4 status=$5 digest=$6 template=$7 state actual_digest
  state=$(cl_guest_state "$type" "$vmid") || cl_die 4 "cannot read the guest listing"
  [ "$state" != "absent" ] || cl_die 3 "$type/$vmid no longer exists"
  [ "$state" = "$node|$name|$status|$template" ] \
    || cl_die 3 "$type/$vmid changed: expected '$node|$name|$status|$template', found '$state'"
  actual_digest=$(cl_guest_digest "$type" "$vmid" "$node")
  [ "$actual_digest" = "$digest" ] || cl_die 3 "$type/$vmid config digest changed"
  cl_log "$type/$vmid matches the approved state"
}

# cl_backup_guest TYPE VMID NODE NAME STATUS DIGEST TEMPLATE STORAGE — `vzdump --mode stop` stops and
# restarts a running guest, so it is a destructive-class command too: the approved state, lock and task
# checks (cl_prestate) run right before it, like before stop and destroy.
cl_backup_guest() {
  cl_destructive_gate cl_backup_guest
  [ "$#" -eq 8 ] || cl_die 6 "internal error: cl_backup_guest takes 8 arguments"
  [[ "$8" =~ ^[A-Za-z][A-Za-z0-9_.-]*$ ]] || cl_die 6 "'$8' is not a storage name"
  cl_prestate "${@:1:7}"
  # DISABLED-COMMAND: vzdump "$2" --storage "$8" --mode stop --compress zstd || cl_die 4 "backup of $2 failed"
  cl_destructive_gate cl_backup_guest
}

cl_dump_config() {
  local type=$1 vmid=$2
  printf '[corelab] config of %s/%s follows\n' "$type" "$vmid"
  pvesh get "/nodes/$CL_NODE/$type/$vmid/config" --output-format json || cl_die 4 "cannot dump config"
  printf '\n'
}

cl_guest_cmd() { if [ "$1" = lxc ]; then printf 'pct'; else printf 'qm'; fi; }

# --- live safety checks (exit 6) -------------------------------------------------------
# They read the host's own state and compare it with CL_SENTINEL_VMID and CL_POOL, which
# the owner-side runner exports from the owner's settings. The manifest and the inventory
# are not trusted for these facts; only the pool a guest was inventoried in is compared.

cl_need_guard_config() {
  # The same form the agent side accepts: 100 .. 999999999, no sign, no leading zero. 0 protects nothing.
  [[ "${CL_SENTINEL_VMID:-}" =~ ^[1-9][0-9]{2,8}$ ]] \
    || cl_die 6 "CL_SENTINEL_VMID is not set to a valid VMID (100 to 999999999, no leading zero)"
  [ -n "${CL_POOL:-}" ] || cl_die 6 "CL_POOL is not set"
}

# cl_need_node — the node name every pvesh path below is built from, validated before use.
cl_need_node() {
  [[ "${CL_NODE:-}" =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,62}$ ]] || cl_die 6 "CL_NODE is not a valid node name"
}

# cl_expect_sentinel VMID — the VMID the manifest was built for must be the one in the settings.
cl_expect_sentinel() {
  cl_need_guard_config
  [ "$1" = "$CL_SENTINEL_VMID" ] \
    || cl_die 6 "the manifest was built for sentinel VMID $1, but the settings say $CL_SENTINEL_VMID; refusing"
  cl_log "sentinel VMID $CL_SENTINEL_VMID matches the manifest"
}

# cl_is_sentinel VMID — true when VMID is the sentinel (numeric, so 09050 is 9050).
cl_is_sentinel() { [[ "$1" =~ ^[0-9]{1,9}$ ]] && (( 10#$1 == 10#$CL_SENTINEL_VMID )); }

# cl_fetch_guests — read the live guest listing into CL_GUESTS_JSON. Refused (exit 6) unless every
# record is a well-formed guest AND the listing contains the sentinel guest. That last test is a
# control that DETECTS SOME truncated listings (one that lost the sentinel). It is NOT evidence that
# the listing is complete: a listing missing any other guest passes it. Completeness of the guest
# and volume enumeration is UNPROVEN (see the report, "Unproven guarantees").
cl_fetch_guests() {
  local json has
  cl_need_guard_config
  json=$(pvesh get /cluster/resources --type vm --output-format json) || cl_die 4 "cannot list guests"
  printf '%s' "$json" | cl_shape_ok guests \
    || cl_die 6 "the guest listing is empty, malformed or unreadable; refusing"
  has=$(printf '%s' "$json" | CL_VMID="$CL_SENTINEL_VMID" cl_json_get \
    'scalar grep { $_->{type} eq "qemu" && $_->{vmid} == $ENV{CL_VMID} } @$d') \
    || cl_die 6 "the guest listing is unreadable; refusing"
  [ "$has" = "1" ] \
    || cl_die 6 "the guest listing does not contain the sentinel guest $CL_SENTINEL_VMID; it may be incomplete; refusing"
  CL_GUESTS_JSON=$json
}

# cl_require_listed "TYPE/VMID ..." "STORAGE ..." — every guest and every storage the manifest
# names must be found by the listings the guards rely on (exit 6), the storages must be active, and
# the guest listing must contain the sentinel (cl_fetch_guests). Nothing is changed; this is the first
# live check. These are controls that DETECT SOME truncated listings; they do not establish that a
# listing is complete (UNPROVEN, see the report).
cl_require_listed() {
  local -a guests storages
  local g st found json
  cl_need_guard_config
  cl_need_node
  cl_fetch_guests
  read -ra guests <<<"$1"
  read -ra storages <<<"$2"
  for g in ${guests[@]+"${guests[@]}"}; do
    [[ "$g" =~ ^(qemu|lxc)/[1-9][0-9]{2,8}$ ]] || cl_die 6 "'$g' is not a guest reference"
    found=$(printf '%s' "$CL_GUESTS_JSON" | CL_TYPE="${g%/*}" CL_VMID="${g#*/}" cl_json_get \
      'scalar grep { $_->{type} eq $ENV{CL_TYPE} && $_->{vmid} == $ENV{CL_VMID} } @$d') \
      || cl_die 6 "the guest listing is unreadable"
    [ "$found" = "1" ] || cl_die 6 "guest $g is not in the live guest listing; refusing"
  done
  json=$(pvesh get "/nodes/$CL_NODE/storage" --output-format json) || cl_die 4 "cannot list the storages"
  printf '%s' "$json" | cl_shape_ok nodestorages || cl_die 6 "the storage listing is empty, malformed or unreadable"
  for st in ${storages[@]+"${storages[@]}"}; do
    [[ "$st" =~ ^[A-Za-z][A-Za-z0-9_.-]*$ ]] || cl_die 6 "'$st' is not a storage name"
    found=$(printf '%s' "$json" | CL_ST="$st" cl_json_get 'scalar grep { $_->{storage} eq $ENV{CL_ST} && $_->{active} } @$d') \
      || cl_die 6 "the storage listing is unreadable"
    [ "$found" = "1" ] || cl_die 6 "storage $st is not in the live storage listing, or is not active; refusing"
  done
  cl_log "the live listings contain the sentinel and everything the manifest names"
}

# cl_guard_guest TYPE VMID POOL — refuse the sentinel; refuse unless the guest exists live
# and its live pool is exactly POOL (the pool it was inventoried in, "" for none).
cl_guard_guest() {
  local type=$1 vmid=$2 pool=$3 live
  cl_need_guard_config
  [[ "$vmid" =~ ^[0-9]{1,9}$ ]] || cl_die 6 "$type/$vmid: not a VMID"
  ! cl_is_sentinel "$vmid" || cl_die 6 "$type/$vmid is the sentinel guest; refusing"
  cl_fetch_guests
  live=$(printf '%s' "$CL_GUESTS_JSON" | CL_TYPE="$type" CL_VMID="$vmid" cl_json_get '
    my $out = "absent";
    for my $r (@$d) {
      next unless ($r->{type} // "") eq $ENV{CL_TYPE} && ($r->{vmid} // -1) == $ENV{CL_VMID};
      $out = "pool=" . ($r->{pool} // "");
      last;
    }
    $out') || cl_die 6 "the guest listing is unreadable; refusing"
  [ "$live" != "absent" ] || cl_die 6 "$type/$vmid does not exist on the host"
  [ "$live" = "pool=$pool" ] \
    || cl_die 6 "$type/$vmid is in pool '${live#pool=}' on the host, but was inventoried in '$pool'; refusing"
  if [ "$pool" = "$CL_POOL" ]; then cl_log "$type/$vmid is a live member of pool $CL_POOL"; fi
  cl_log "$type/$vmid passed the live safety checks"
}

# cl_name_vmids VOLID — every VMID the volume name carries, one per line (all of them count).
cl_name_vmids() {
  CL_VOLID="$1" perl -e '
    my @ids = ($ENV{CL_VOLID} =~ /(?:^|[\/:])(?:vm|base|subvol|basevol)-(\d+)-|vzdump-(?:qemu|lxc)-(\d+)-/g);
    print "$_\n" for grep { defined && /^\d+$/ } @ids;'
}

# cl_need_volid VOLID — a volume id in the form every list uses (no whitespace, no quoting needed).
cl_need_volid() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*:[^[:space:]]+$ ]] || cl_die 6 "'$1' is not a volume id"
}

# cl_refuse_sentinel_name VOLID — exit 6 when any VMID in the name is the sentinel's.
cl_refuse_sentinel_name() {
  local ids id
  ids=$(cl_name_vmids "$1") || cl_die 4 "cannot parse $1"
  while IFS= read -r id; do
    [ -z "$id" ] || ! cl_is_sentinel "$id" || cl_die 6 "$1 belongs to the sentinel guest $id; refusing"
  done <<<"$ids"
}

# cl_scan_targets EXCLUDE_VMID — set CL_SCAN to the guests whose references matter: every guest
# outside CL_POOL AND the sentinel, whatever pool it is in (a sentinel placed in the pool must not
# stop being scanned), except the guest being destroyed. Every element is validated before use.
declare -a CL_SCAN=()
cl_scan_targets() {
  local out g
  out=$(printf '%s' "$CL_GUESTS_JSON" | CL_POOL="$CL_POOL" CL_SENTINEL_VMID="$CL_SENTINEL_VMID" CL_EXCL="${1:-}" \
    cl_json_get '
      join(" ", map { "$_->{node}/$_->{type}/$_->{vmid}" }
        grep { ($_->{pool} // "") ne $ENV{CL_POOL} || $_->{vmid} == $ENV{CL_SENTINEL_VMID} }
        grep { $ENV{CL_EXCL} eq "" || $_->{vmid} != $ENV{CL_EXCL} } @$d)') \
    || cl_die 6 "the guest listing is unreadable"
  read -ra CL_SCAN <<<"$out"
  for g in ${CL_SCAN[@]+"${CL_SCAN[@]}"}; do
    [[ "$g" =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,62}/(qemu|lxc)/[1-9][0-9]{2,8}$ ]] \
      || cl_die 6 "'$g' is not a guest reference; refusing"
  done
}

# cl_config_items — stdin: a guest or snapshot config (an object) or a pending listing (an array);
# CL_TARGET and CL_VIEW in the environment. Prints one line per config item:
#   TARGET <tab> VIEW <tab> KEY <tab> ITEM
# A config value is a list of comma-separated items, each a bare volume id or key=value; the key
# is dropped, so disk keys (scsi0: <volid>,size=…), file=<volid>, import-from=<volid>, every
# cicustom key (user=, meta=, network=, vendor=) and a snapshot's vmstate volume all come out as
# plain items. Tabs and newlines inside an item become spaces (a volume id has none).
cl_config_items() {
  cl_json_get '
    my @rows;
    my $emit = sub {
      my ($key, $val) = @_;
      return unless defined $val && !ref $val;
      for my $item (split /,/, "$val") {
        $item =~ s/^\s+//; $item =~ s/^[A-Za-z][A-Za-z0-9_-]*=//; $item =~ s/[\t\r\n]/ /g;
        next if $item eq "";
        push @rows, join("\t", $ENV{CL_TARGET}, $ENV{CL_VIEW}, $key, $item);
      }
    };
    if (ref $d eq "HASH") { $emit->($_, $d->{$_}) for sort keys %$d }
    elsif (ref $d eq "ARRAY") { for my $r (@$d) { $emit->($r->{key}, $r->{value}); $emit->($r->{key}, $r->{pending}) } }
    else { die "not a config\n" }
    join("", map { "$_\n" } @rows)'
}

# cl_views_of NODE/TYPE/VMID — every item the guest refers to, in every view the host offers:
#   default   GET .../config (the values with pending changes applied)
#   current   GET .../config?current=1 (the values in effect now)
#   pending   GET .../pending (each key's current value and its pending value)
#   snapshot:NAME   GET .../snapshot/NAME/config for every snapshot
# Each response must pass its shape check; one that does not stops the run (exit 6). The exact
# representation of these views on a real host has not been observed (NEEDS-LIVE).
cl_views_of() {
  local g=$1 cfg snaps s view
  [[ "$g" =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,62}/(qemu|lxc)/[1-9][0-9]{2,8}$ ]] || cl_die 6 "'$g' is not a guest reference"
  for view in default current; do
    if [ "$view" = current ]; then
      cfg=$(pvesh get "/nodes/$g/config" --current 1 --output-format json) || cl_die 4 "cannot read the current config of $g"
    else
      cfg=$(pvesh get "/nodes/$g/config" --output-format json) || cl_die 4 "cannot read config of $g"
    fi
    printf '%s' "$cfg" | cl_shape_ok config \
      || cl_die 6 "config of $g ($view view) is empty, malformed or unreadable; cannot show a volume unused"
    printf '%s' "$cfg" | CL_TARGET="$g" CL_VIEW="$view" cl_config_items || cl_die 6 "config of $g is unreadable"
  done
  cfg=$(pvesh get "/nodes/$g/pending" --output-format json) || cl_die 4 "cannot read the pending config of $g"
  printf '%s' "$cfg" | cl_shape_ok pending \
    || cl_die 6 "pending config of $g is empty, malformed or unreadable; cannot show a volume unused"
  printf '%s' "$cfg" | CL_TARGET="$g" CL_VIEW="pending" cl_config_items || cl_die 6 "pending config of $g is unreadable"
  snaps=$(pvesh get "/nodes/$g/snapshot" --output-format json) || cl_die 4 "cannot list snapshots of $g"
  printf '%s' "$snaps" | cl_shape_ok snapshots \
    || cl_die 6 "snapshot listing of $g is empty, malformed (or has a name that is not path-safe) or unreadable"
  snaps=$(printf '%s' "$snaps" | cl_json_get 'join(" ", grep { $_ ne "current" } map { $_->{name} } @$d)') \
    || cl_die 6 "snapshot names of $g are unreadable"
  local -a names
  read -ra names <<<"$snaps"
  for s in ${names[@]+"${names[@]}"}; do
    [[ "$s" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] || cl_die 6 "snapshot name '$s' of $g is not path-safe; refusing"
    cfg=$(pvesh get "/nodes/$g/snapshot/$s/config" --output-format json) || cl_die 4 "cannot read snapshot $s of $g"
    printf '%s' "$cfg" | cl_shape_ok config \
      || cl_die 6 "snapshot $s of $g is empty, malformed or unreadable; cannot show a volume unused"
    printf '%s' "$cfg" | CL_TARGET="$g" CL_VIEW="snapshot:$s" cl_config_items \
      || cl_die 6 "snapshot $s of $g is unreadable"
  done
}

# cl_collect_refs EXCLUDE_VMID — print the items of every scanned guest (cl_scan_targets) in every
# view. Needs CL_GUESTS_JSON (cl_fetch_guests) first, so that a failure here stops the caller.
cl_collect_refs() {
  local g rows
  cl_scan_targets "${1:-}"
  for g in ${CL_SCAN[@]+"${CL_SCAN[@]}"}; do
    rows=$(cl_views_of "$g") || exit $?
    printf '%s\n' "$rows"  # command substitution drops the last newline: keep targets apart
  done
}

# cl_refs_hit VOLID — stdin: cl_collect_refs output. Prints "TARGET<tab>VIEW<tab>KEY" of the first
# item that is the volume, or a longer id that starts with "<volid>/" (a linked clone's path).
cl_refs_hit() {
  CL_VOLID="$1" perl -e '
    my $want = $ENV{CL_VOLID};
    while (my $line = <STDIN>) {
      chomp $line;
      my ($t, $view, $key, $item) = split /\t/, $line, 4;
      next unless defined $item;
      if ($item eq $want || index($item, "$want/") == 0) { print "$t\t$view\t$key"; last }
    }'
}

# cl_refuse_if_referenced VOLID REFS — exit 6 with the first reference found.
cl_refuse_if_referenced() {
  local hit t view key what
  hit=$(printf '%s' "$2" | cl_refs_hit "$1") || cl_die 6 "the reference list is unreadable"
  [ -z "$hit" ] && return 0
  IFS=$'\t' read -r t view key <<<"$hit"
  case $view in
    snapshot:*) what="snapshot ${view#snapshot:} of guest $t outside pool $CL_POOL" ;;
    *) what="guest $t outside pool $CL_POOL ($view view, $key)" ;;
  esac
  [[ "$t" == */"$CL_SENTINEL_VMID" ]] && what="the sentinel guest $t ($view view, $key)"
  cl_die 6 "$1 is used by $what; refusing"
}

# cl_fetch_storages [STORAGE] — read /nodes/N/storage into CL_STORAGES_JSON; every record needs a
# storage name and an activity flag (0 or 1). With STORAGE, that storage must be listed and active.
# Without, EVERY storage must be active: an inactive storage cannot be listed, so what lives on it
# cannot be enumerated, and a removal cannot be shown safe while that is so (exit 6, never skipped).
cl_fetch_storages() {
  local json bad
  cl_need_node
  json=$(pvesh get "/nodes/$CL_NODE/storage" --output-format json) || cl_die 4 "cannot list the storages"
  printf '%s' "$json" | cl_shape_ok nodestorages \
    || cl_die 6 "the storage listing is empty, malformed (or a record has no valid active flag) or unreadable; refusing"
  if [ -n "${1:-}" ]; then
    bad=$(printf '%s' "$json" | CL_ST="$1" cl_json_get 'scalar grep { $_->{storage} eq $ENV{CL_ST} && $_->{active} } @$d') \
      || cl_die 6 "the storage listing is unreadable"
    [ "$bad" = "1" ] || cl_die 6 "storage $1 is not in the live storage listing, or is not active; refusing"
  else
    bad=$(printf '%s' "$json" | cl_json_get 'join(" ", map { $_->{storage} } grep { !$_->{active} } @$d)') \
      || cl_die 6 "the storage listing is unreadable"
    [ -z "$bad" ] || cl_die 6 "storage(s) $bad are not active: what lives on them cannot be enumerated, so the removal cannot be shown safe; refusing"
  fi
  CL_STORAGES_JSON=$json
}

# cl_check_listed_owner STORAGE VOLID — the host's own listing of the storage must show the volume,
# and the owner it reports must not be the sentinel (the name was checked before: this is the
# metadata). Used for a volume freed on its own and for every volume a destroy would delete.
cl_check_listed_owner() {
  local storage=$1 volid=$2 listing owners id
  local -a ids
  [[ "$storage" =~ ^[A-Za-z][A-Za-z0-9_.-]*$ ]] || cl_die 6 "'$storage' is not a storage name"
  [ "${volid%%:*}" = "$storage" ] || cl_die 6 "$volid is not on storage $storage; refusing"
  cl_fetch_storages "$storage"
  listing=$(pvesh get "/nodes/$CL_NODE/storage/$storage/content" --output-format json) \
    || cl_die 4 "cannot list $storage"
  printf '%s' "$listing" | cl_shape_ok content \
    || cl_die 6 "the listing of $storage is empty, malformed or unreadable; cannot tell whose volume $volid is"
  owners=$(printf '%s' "$listing" | CL_VOLID="$volid" cl_json_get '
    my ($v) = grep { $_->{volid} eq $ENV{CL_VOLID} } @$d;
    $v ? "found " . ($v->{vmid} // "") : "absent"') || cl_die 6 "the listing of $storage is unreadable"
  [ "$owners" != "absent" ] || cl_die 6 "$volid is not in the live listing of $storage; refusing"
  read -ra ids <<<"${owners#found}"
  for id in ${ids[@]+"${ids[@]}"}; do
    [[ "$id" =~ ^[0-9]{1,9}$ ]] || cl_die 6 "'$id' is not a VMID; refusing"
    ! cl_is_sentinel "$id" || cl_die 6 "$volid belongs to the sentinel guest $id; refusing"
  done
}

# cl_guard_volume STORAGE VOLID — refuse a volume the sentinel owns (by the host's listing or by
# any VMID in its name) and one that the sentinel or a guest outside CL_POOL references in its
# default, current, pending or any snapshot configuration. The storage listing must contain the
# volume, and every listing must have the shape of its endpoint; otherwise exit 6.
cl_guard_volume() {
  local storage=$1 volid=$2 refs
  cl_need_guard_config
  cl_need_node
  [[ "$storage" =~ ^[A-Za-z][A-Za-z0-9_.-]*$ ]] || cl_die 6 "'$storage' is not a storage name"
  cl_need_volid "$volid"
  # The name is checked before any listing is trusted, so a bad listing cannot hide the sentinel.
  cl_refuse_sentinel_name "$volid"
  cl_check_listed_owner "$storage" "$volid"
  cl_fetch_guests
  refs=$(cl_collect_refs "") || exit $?
  cl_refuse_if_referenced "$volid" "$refs"
  cl_log "$volid passed the live safety checks"
}

# cl_extract_config_volumes — stdin: cl_views_of output. Prints, one per line, every item in a disk
# key (scsi, virtio, ide, sata, efidisk, tpmstate, unused, mp, rootfs, vmstate) that looks like a
# volume id, except files in iso/vztmpl/snippets/import/backup paths (never deleted with a guest).
cl_extract_config_volumes() {
  perl -e '
    my %seen;
    while (my $line = <STDIN>) {
      chomp $line;
      my ($t, $view, $key, $item) = split /\t/, $line, 4;
      next unless defined $item;
      next unless $key =~ /\A(?:(?:scsi|virtio|ide|sata|efidisk|tpmstate|unused|mp)[0-9]*|rootfs|vmstate)\z/;
      next unless $item =~ /\A[A-Za-z0-9][A-Za-z0-9_.-]*:[^\s,]+\z/;
      next if $item =~ /\A[^:]+:(?:iso|vztmpl|snippets|import|backup)\//;
      print "$item\n" unless $seen{$item}++;
    }'
}

# cl_owned_volumes VMID — every volume in any storage (all are active: cl_fetch_storages ran) that
# is owned by the VMID, by the host's listing or by its name. Needs CL_STORAGES_JSON.
cl_owned_volumes() {
  local vmid=$1 names st listing
  local -a stores
  names=$(printf '%s' "$CL_STORAGES_JSON" | cl_json_get 'join(" ", map { $_->{storage} } @$d)') \
    || cl_die 6 "the storage listing is unreadable"
  read -ra stores <<<"$names"
  for st in ${stores[@]+"${stores[@]}"}; do
    [[ "$st" =~ ^[A-Za-z][A-Za-z0-9_.-]*$ ]] || cl_die 6 "'$st' is not a storage name"
    listing=$(pvesh get "/nodes/$CL_NODE/storage/$st/content" --output-format json) || cl_die 4 "cannot list $st"
    printf '%s' "$listing" | cl_shape_ok anycontent \
      || cl_die 6 "the listing of $st is malformed or unreadable; cannot tell what destroying $vmid would delete"
    printf '%s' "$listing" | CL_VMID="$vmid" cl_json_get '
      my $v = $ENV{CL_VMID};
      join("", map { "$_->{volid}\n" } grep {
        my $r = $_;
        my @named = ($r->{volid} =~ /(?:^|[\/:])(?:vm|base|subvol|basevol)-(\d+)-|vzdump-(?:qemu|lxc)-(\d+)-/g);
        $r->{volid} !~ /\A[^:]+:(?:iso|vztmpl|snippets|import|backup)\// &&
          ((defined $r->{vmid} && $r->{vmid} == $v) || scalar(grep { defined $_ && $_ == $v } @named))
      } @$d)' || cl_die 6 "the listing of $st is unreadable"
  done
}

# cl_destroy_set TYPE VMID — print, one per line, every volume that destroying the guest could
# delete, so each can be given the same guards as a volume freed on its own:
#   * every configured disk of the guest in every view, and every snapshot's disks and vmstate;
#   * every volume in any storage that is owned by its VMID (by the listing or by name), because
#     destroy can remove unreferenced disks of the guest too.
# Every step is checked on its own: the call sites run in an `||` context, where errexit does not
# rescue a failed step inside a function. Needs CL_GUESTS_JSON and CL_STORAGES_JSON.
cl_destroy_set() {
  local type=$1 vmid=$2 self rows configured owned
  [ -n "${CL_STORAGES_JSON:-}" ] || cl_die 6 "internal error: cl_fetch_storages must run before cl_destroy_set"
  self=$(printf '%s' "$CL_GUESTS_JSON" | CL_TYPE="$type" CL_VMID="$vmid" cl_json_get '
    my ($r) = grep { $_->{type} eq $ENV{CL_TYPE} && $_->{vmid} == $ENV{CL_VMID} } @$d;
    $r ? "$r->{node}/$r->{type}/$r->{vmid}" : ""') || cl_die 6 "the guest listing is unreadable"
  [ -n "$self" ] || cl_die 6 "$type/$vmid is not in the live guest listing; refusing"
  rows=$(cl_views_of "$self") || exit $?
  configured=$(printf '%s' "$rows" | cl_extract_config_volumes) \
    || cl_die 6 "the configured volumes of $self could not be extracted; refusing"
  owned=$(cl_owned_volumes "$vmid") || exit $?
  printf '%s\n%s\n' "$configured" "$owned" | sort -u
}

# cl_guard_destroy_set TYPE VMID — destroying a guest deletes volumes: each volume in its
# destruction set must pass the same checks as a volume freed on its own: no VMID of the sentinel in
# the name, the host's listing shows it and does not report the sentinel as its owner, and it is not
# referenced by the sentinel or a guest outside the pool other than this one. Every storage must be
# active (cl_fetch_storages), so that the set can be enumerated.
cl_guard_destroy_set() {
  local type=$1 vmid=$2 refs set v count=0
  cl_need_guard_config
  cl_need_node
  [[ "$vmid" =~ ^[1-9][0-9]{2,8}$ ]] || cl_die 6 "$type/$vmid: not a VMID"
  ! cl_is_sentinel "$vmid" || cl_die 6 "$type/$vmid is the sentinel guest; refusing"
  cl_fetch_guests
  cl_fetch_storages
  refs=$(cl_collect_refs "$vmid") || exit $?
  set=$(cl_destroy_set "$type" "$vmid") || exit $?
  while IFS= read -r v; do
    [ -n "$v" ] || continue
    cl_need_volid "$v"
    cl_refuse_sentinel_name "$v"
    cl_check_listed_owner "${v%%:*}" "$v"
    cl_refuse_if_referenced "$v" "$refs"
    count=$((count + 1))
  done <<<"$set"
  cl_log "$type/$vmid: the $count volume(s) its destruction would delete passed the live safety checks"
}

# cl_no_lock TYPE VMID NODE — exit 6 when the guest's config carries a lock (a backup, snapshot,
# migration or other task holds it). Taking the guest's own lock is NOT done: `qm/pct set --lock`
# rewrites the config (so the approved digest no longer matches) and destroying a locked guest then
# needs --skiplock, which would override every other holder's lock. Refusing on a lock is the
# alternative that exists; it does not exclude a task that starts a moment later (OPEN RISK).
cl_no_lock() {
  local type=$1 vmid=$2 node=$3 cfg lock
  cfg=$(pvesh get "/nodes/$node/$type/$vmid/config" --output-format json) || cl_die 4 "cannot read config of $type/$vmid"
  printf '%s' "$cfg" | cl_shape_ok config || cl_die 6 "config of $type/$vmid is empty, malformed or unreadable"
  lock=$(printf '%s' "$cfg" | cl_json_get '$d->{lock} // ""') || cl_die 6 "config of $type/$vmid is unreadable"
  [ -z "$lock" ] || cl_die 6 "$type/$vmid is locked ('$lock'); refusing"
}

# cl_no_active_tasks — exit 6 when any task is running on the node (a backup, a migration, another
# administrator's change). Any task counts, not only this guest's: the lab is single-owner.
cl_no_active_tasks() {
  local tasks n
  cl_need_node
  tasks=$(pvesh get "/nodes/$CL_NODE/tasks" --source active --output-format json) || cl_die 4 "cannot list the tasks"
  printf '%s' "$tasks" | cl_shape_ok tasks || cl_die 6 "the task listing is malformed or unreadable; refusing"
  n=$(printf '%s' "$tasks" | cl_json_get 'scalar @$d') || cl_die 6 "the task listing is unreadable"
  [ "$n" = "0" ] || cl_die 6 "$n task(s) active on node $CL_NODE; refusing to change anything while one runs"
}

# cl_prestate TYPE VMID NODE NAME STATUS DIGEST TEMPLATE — what must hold immediately before a
# destructive command on a guest: exactly the approved node, name, status, template and config
# digest (exit 3), no config lock and no active task on the node (exit 6).
#
# OPEN RISK (not fixed, not an accepted limitation; the owner decides): this is a check followed
# by a command, not a lock. The only guest lock the tools offer (`qm/pct set --lock`) rewrites the
# config that is being validated and makes destroy need --skiplock (see cl_no_lock), so it is not
# used. Whoever acts in the moments between the last check and the command is not excluded: a
# second administrator session, a scheduled job, an API client. The script can refuse on a lock
# and on an active task; it cannot see an actor that starts afterwards or that does not create a
# task. Run it only under the operational constraint stated in the report ("Residual concurrency
# risk"), which this code cannot enforce.
cl_prestate() {
  [ "$#" -eq 7 ] || cl_die 6 "internal error: cl_prestate takes 7 arguments"
  cl_expect_guest "$@"
  cl_no_lock "$1" "$2" "$3"
  cl_no_active_tasks
}

# cl_stop_guest / cl_destroy_guest TYPE VMID NODE NAME STATUS DIGEST TEMPLATE
cl_stop_guest() {
  cl_destructive_gate cl_stop_guest
  local cmd
  # shellcheck disable=SC2034  # cmd is read only by the disabled command below
  cmd=$(cl_guest_cmd "$1")
  cl_prestate "$@"
  # DISABLED-COMMAND: "$cmd" stop "$2" || cl_die 4 "stop of $1/$2 failed"
  cl_destructive_gate cl_stop_guest
}

# Destroying a guest deletes its volumes: guard each of them first (cl_guard_destroy_set), then
# re-check the approved state, then destroy. The same OPEN RISK applies (see cl_prestate): the
# volume guards and the approved-state check are not atomic with the destroy command.
cl_destroy_guest() {
  cl_destructive_gate cl_destroy_guest
  local cmd
  # shellcheck disable=SC2034  # cmd is read only by the disabled command below
  cmd=$(cl_guest_cmd "$1")
  [ "$#" -eq 7 ] || cl_die 6 "internal error: cl_destroy_guest takes 7 arguments"
  cl_guard_destroy_set "$1" "$2"
  cl_prestate "$@"
  # DISABLED-COMMAND: "$cmd" destroy "$2" --purge 1 || cl_die 4 "destroy of $1/$2 failed"
  cl_destructive_gate cl_destroy_guest
}

cl_verify_guest_absent() {
  local json present
  json=$(pvesh get /cluster/resources --type vm --output-format json) || cl_die 4 "cannot list guests"
  # An unreadable or null listing proves nothing: it must not read as "absent".
  printf '%s' "$json" | cl_shape_ok anyguests || cl_die 5 "guest listing is unreadable; cannot verify that $1 is gone"
  present=$(printf '%s' "$json" | CL_VMID="$1" cl_json_get \
    'scalar grep { ($_->{vmid} // -1) == $ENV{CL_VMID} } @$d') || cl_die 5 "cannot read the guest listing"
  [ "$present" = "0" ] || cl_die 5 "guest $1 still present"
}

# cl_expect_volume STORAGE VOLID SIZE
cl_expect_volume() {
  local storage=$1 volid=$2 size=$3 json actual
  json=$(pvesh get "/nodes/$CL_NODE/storage/$storage/content" --output-format json) || cl_die 4 "cannot list $storage"
  printf '%s' "$json" | cl_shape_ok anycontent || cl_die 6 "the listing of $storage is malformed or unreadable"
  actual=$(printf '%s' "$json" | CL_VOLID="$volid" cl_json_get '
      my ($v) = grep { ($_->{volid} // "") eq $ENV{CL_VOLID} } @$d;
      $v ? ($v->{size} // "") : "absent"') || cl_die 4 "cannot list $storage"
  [ "$actual" != "absent" ] || cl_die 3 "$volid no longer exists"
  [ "$actual" = "$size" ] || cl_die 3 "$volid changed size: expected $size, found $actual"
  cl_log "$volid matches the approved state"
}

# cl_free_volume STORAGE VOLID SIZE — guard the volume (references in every view, sentinel), check
# that it is still the approved one and that no task is active, then free it. The same OPEN RISK
# applies between these checks and the command (see cl_prestate): a volume can be attached, snapshotted
# or replaced after the last scan and before `pvesm free`; no storage lock is taken.
cl_free_volume() {
  cl_destructive_gate cl_free_volume
  [ "$#" -eq 3 ] || cl_die 6 "internal error: cl_free_volume takes 3 arguments"
  cl_guard_volume "$1" "$2"
  cl_expect_volume "$1" "$2" "$3"
  cl_no_active_tasks
  # DISABLED-COMMAND: pvesm free "$2" || cl_die 4 "free of $2 failed"
  cl_destructive_gate cl_free_volume
}

cl_verify_volume_absent() {
  local present json
  json=$(pvesh get "/nodes/$CL_NODE/storage/$1/content" --output-format json) || cl_die 4 "cannot list $1"
  # An unreadable or null listing proves nothing: it must not read as "absent".
  printf '%s' "$json" | cl_shape_ok anycontent || cl_die 5 "the listing of $1 is unreadable; cannot verify that $2 is gone"
  present=$(printf '%s' "$json" | CL_VOLID="$2" cl_json_get \
    'scalar grep { ($_->{volid} // "") eq $ENV{CL_VOLID} } @$d') || cl_die 5 "cannot read the listing of $1"
  [ "$present" = "0" ] || cl_die 5 "volume $2 still present"
}

# cl_acl ROLE PATH — grant ROLE on PATH to the agent user and its token (idempotent).
cl_acl() {
  pveum acl modify "$2" --users "$CL_USER" --roles "$1" || cl_die 4 "acl $1 on $2 (user) failed"
  pveum acl modify "$2" --tokens "$CL_USER!$CL_TOKEN" --roles "$1" || cl_die 4 "acl $1 on $2 (token) failed"
}
