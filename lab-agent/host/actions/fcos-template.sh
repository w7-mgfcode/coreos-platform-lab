# shellcheck shell=bash
# Action: fcos-template (re-runnable only in the sense below)
# Builds the Fedora CoreOS template inside the pool, following the Fedora CoreOS
# documentation page "Provisioning Fedora CoreOS on Proxmox VE": import the proxmoxve
# qcow2, add a cloud-init drive and a serial console, then convert to a template. Routine work clones it; it never needs root again.
#
# Re-run behaviour:
#   * the template exists and matches (pool, node, flags, disk, cloud-init drive, serial
#     console, NIC bridge, boot order): nothing is changed, exit 0;
#   * a guest with that VMID exists and is anything else, including a half-built guest of
#     an earlier run: the script prints exactly what exists and stops with exit 3. It does
#     not resume and does not delete; the owner decides;
#   * a step fails after the guest was created: the script prints what exists and stops
#     with the exit code of the step; nothing is deleted.
# Image integrity: the downloaded artifact is kept under its published sha256 and is
# verified again on EVERY run before use. The decompressed copy is made fresh each run
# in a temporary file, imported and removed; a cached decompressed image is never trusted.
#
# Parameters: CL_TEMPLATE_VMID CL_POOL CL_VM_STORAGE CL_LAB_STORAGE_PATH CL_BRIDGE
#             CL_FCOS_IMAGE_URL CL_FCOS_IMAGE_SHA256
#             CL_VMID_RANGE (lo-hi) CL_SENTINEL_VMID  (project VMID range and sentinel;
#             the template VMID must lie inside the range and differ from the sentinel)

: "${CL_TEMPLATE_VMID:?}" "${CL_POOL:?}" "${CL_VM_STORAGE:?}" "${CL_LAB_STORAGE_PATH:?}" "${CL_BRIDGE:?}"
: "${CL_FCOS_IMAGE_URL:?}" "${CL_FCOS_IMAGE_SHA256:?}"
: "${CL_VMID_RANGE:?}" "${CL_SENTINEL_VMID:?}"
export LC_ALL=C

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
# la_records JSON KEY [FIELD[#]...] — an array of objects, each with KEY and every FIELD as a
# non-empty scalar (# = a canonical VMID: 100..999999999, no sign, no leading zero, so that
# "9100" and "09100" cannot be two identities), KEY unique. Prints the count; anything else fails, so an
# empty reply or [{}] never reads as "not present".
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
la_tmps=()
trap 'rm -f -- "${la_tmps[@]}"' EXIT

# --- validate everything before the first read of the host's state or any write ---------
[[ "$CL_VMID_RANGE" =~ ^([1-9][0-9]{2,8})-([1-9][0-9]{2,8})$ ]] || cl_die 3 "CL_VMID_RANGE must look like 9100-9199"
CL_VMID_MIN=${BASH_REMATCH[1]}
CL_VMID_MAX=${BASH_REMATCH[2]}
[ "$CL_VMID_MIN" -le "$CL_VMID_MAX" ] || cl_die 3 "the start of CL_VMID_RANGE is above its end"
la_uint CL_SENTINEL_VMID "$CL_SENTINEL_VMID" 100 999999999
la_uint CL_TEMPLATE_VMID "$CL_TEMPLATE_VMID" "$CL_VMID_MIN" "$CL_VMID_MAX"
[ "$CL_TEMPLATE_VMID" -ne "$CL_SENTINEL_VMID" ] || cl_die 3 "the template VMID is the sentinel VMID"
la_id CL_POOL "$CL_POOL"
la_id CL_VM_STORAGE "$CL_VM_STORAGE"
la_id CL_BRIDGE "$CL_BRIDGE"
[[ "$CL_FCOS_IMAGE_URL" =~ ^https://[A-Za-z0-9][A-Za-z0-9._~%/:@+=\&?,\;-]{0,1000}$ ]] \
  || cl_die 3 "image URL must be https and use only plain URL characters"
[[ "$CL_FCOS_IMAGE_SHA256" =~ ^[0-9a-f]{64}$ ]] || cl_die 3 "bad sha256"

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
vmid=$CL_TEMPLATE_VMID

# --- read the host's state (each listing must succeed and parse) ------------------------
storage_list=$(pvesh get /storage --output-format json) || cl_die 4 "cannot list storages"
la_records "$storage_list" storage type >/dev/null || cl_die 4 "the storage list is not an array of records with unique ids and types"
registered=$(printf '%s' "$storage_list" | CL_P="$p" cl_json_get '
  die "not a JSON array\n" unless ref $d eq "ARRAY";
  my ($s) = grep { ref $_ eq "HASH" && ($_->{type} // "") eq "dir" && ($_->{path} // "") eq $ENV{CL_P} } @$d;
  $s ? ($s->{content} // "") : "absent"') || cl_die 4 "the storage list is not a JSON array"
[ "$registered" != absent ] || cl_die 3 "no directory storage is registered at $p; run prepare first"
case ",$registered," in *,import,*) ;; *) cl_die 3 "the storage at $p lacks the import content type; run prepare" ;; esac

pools=$(pvesh get /pools --output-format json) || cl_die 4 "cannot list pools"
la_records "$pools" poolid >/dev/null || cl_die 4 "the pool list is not an array of records with unique ids"
have_pool=$(printf '%s' "$pools" | CL_P="$CL_POOL" cl_json_get '
  die "not a JSON array\n" unless ref $d eq "ARRAY";
  scalar grep { ref $_ eq "HASH" && ($_->{poolid} // "") eq $ENV{CL_P} } @$d') || cl_die 4 "the pool list is not a JSON array"
[ "$have_pool" = 1 ] || cl_die 3 "pool $CL_POOL does not exist; run prepare first"

# la_guest_row — "type|node|status|template|pool" of the guest with the template VMID, or absent.
la_guest_row() {
  local resources
  resources=$(pvesh get /cluster/resources --type vm --output-format json) || cl_die 4 "cannot list guests"
  la_records "$resources" vmid# type >/dev/null || cl_die 4 "the guest list is not an array of records with unique numeric VMIDs"
  printf '%s' "$resources" | CL_V="$vmid" cl_json_get '
    die "not a JSON array\n" unless ref $d eq "ARRAY";
    my @hits;
    for my $r (@$d) {
      die "element is not an object\n" unless ref $r eq "HASH";
      next unless defined $r->{vmid} && $r->{vmid} == $ENV{CL_V};
      push @hits, join("|", $r->{type} // "", $r->{node} // "", $r->{status} // "", $r->{template} ? 1 : 0, $r->{pool} // "");
    }
    die "more than one guest entry for the VMID\n" if @hits > 1;
    @hits ? $hits[0] : "absent"' || cl_die 4 "the guest list is not usable"
}

# la_describe — print exactly what exists for the template VMID (key names; volume ids only).
la_describe() {
  local row cfg vols
  row=$(la_guest_row) || return 0
  cl_log "guest list entry (type|node|status|template|pool): $row"
  if cfg=$(pvesh get "/nodes/$node/qemu/$vmid/config" --output-format json 2>/dev/null); then
    printf '%s' "$cfg" | cl_json_get '
      die "not an object\n" unless ref $d eq "HASH";
      join("\n", map { my $v = (/\A(?:scsi|ide|sata|virtio|efidisk|tpmstate|unused)[0-9]*\z/) ? " = $d->{$_}" : ""; "[corelab]   config key: $_$v" } sort keys %$d)' >&2 || true
    echo >&2
  else
    cl_log "its config could not be read"
  fi
  if vols=$(pvesh get "/nodes/$node/storage/$CL_VM_STORAGE/content" --vmid "$vmid" --output-format json 2>/dev/null); then
    printf '%s' "$vols" | cl_json_get '
      die "not an array\n" unless ref $d eq "ARRAY";
      join("\n", map { "[corelab]   volume on the VM storage: " . ($_->{volid} // "?") } @$d)' >&2 || true
    echo >&2
  fi
}

# la_verify_template CODE — exit CODE unless the guest is the finished, matching template.
la_verify_template() {
  local code=$1 row cfg problems
  row=$(la_guest_row)
  [ "$row" != absent ] || cl_die "$code" "guest $vmid is not there"
  [ "$row" = "qemu|$node|stopped|1|$CL_POOL" ] \
    || cl_die "$code" "guest $vmid is not the template: (type|node|status|template|pool) is '$row', expected 'qemu|$node|stopped|1|$CL_POOL'"
  cfg=$(pvesh get "/nodes/$node/qemu/$vmid/config" --output-format json) \
    || cl_die 4 "cannot read the config of guest $vmid"
  problems=$(printf '%s' "$cfg" | CL_V="$vmid" CL_S="$CL_VM_STORAGE" CL_B="$CL_BRIDGE" cl_json_get '
    die "config is not an object\n" unless ref $d eq "HASH";
    my @p;
    push @p, "name" unless ($d->{name} // "") eq "corelab-fcos-template";
    push @p, "template flag" unless ($d->{template} // "") eq "1";
    push @p, "scsi0" unless ($d->{scsi0} // "") =~ /\A\Q$ENV{CL_S}\E:(?:base|vm)-\Q$ENV{CL_V}\E-disk-[0-9]+(?:,|\z)/;
    push @p, "ide2 cloud-init drive" unless ($d->{ide2} // "") =~ /\A\Q$ENV{CL_S}\E:(?:base|vm)-\Q$ENV{CL_V}\E-cloudinit(?:,|\z)/;
    push @p, "serial0" unless ($d->{serial0} // "") eq "socket";
    push @p, "vga" unless ($d->{vga} // "") eq "serial0";
    push @p, "net0 bridge" unless ($d->{net0} // "") =~ /\Avirtio(?:=[0-9A-Fa-f:]+)?(?:,[^,]*)*,bridge=\Q$ENV{CL_B}\E(?:,|\z)/;
    push @p, "boot order" unless ($d->{boot} // "") =~ /(?:\A|;)order=scsi0(?:;|\z)/;
    join("; ", @p)') || cl_die 4 "the guest config is not a JSON object"
  [ -z "$problems" ] || cl_die "$code" "guest $vmid does not match the template this script builds: $problems"
}

row=$(la_guest_row)
if [ "$row" != absent ]; then
  la_describe
  if [ "$row" = "qemu|$node|stopped|1|$CL_POOL" ]; then
    la_verify_template 3
    cl_log "template $vmid exists and matches"
    exit 0
  fi
  cl_die 3 "guest $vmid already exists and is not a finished, matching template (see above); not resuming, not deleting: the owner decides"
fi

vols=$(pvesh get "/nodes/$node/storage/$CL_VM_STORAGE/content" --vmid "$vmid" --output-format json) \
  || cl_die 4 "cannot list volumes on $CL_VM_STORAGE"
la_records "$vols" volid >/dev/null || cl_die 4 "the volume list is not an array of records with unique volids"
leftover=$(printf '%s' "$vols" | cl_json_get '
  die "not a JSON array\n" unless ref $d eq "ARRAY";
  for my $r (@$d) { die "element is not an object\n" unless ref $r eq "HASH" }
  scalar @$d') || cl_die 4 "the volume list is not a JSON array of objects"
[ "$leftover" = 0 ] || cl_die 3 "$CL_VM_STORAGE holds $leftover volume(s) of VMID $vmid but no guest uses them; not creating over them"

# --- the image: verified on every use -----------------------------------------------------
import_dir="$p/import"
if [ ! -e "$import_dir" ]; then install -d -m 0755 -o root -g root "$import_dir"; fi
la_root_dir "$import_dir"
artifact="$import_dir/corelab-fcos-$CL_FCOS_IMAGE_SHA256.artifact"

la_sha256() { # FILE — print the sha256 of a regular file
  local out
  out=$(sha256sum -- "$1") || cl_die 4 "cannot hash $1"
  out=${out%% *}
  [[ "$out" =~ ^[0-9a-f]{64}$ ]] || cl_die 4 "unexpected sha256sum output"
  printf '%s' "$out"
}

if [ -L "$artifact" ]; then
  cl_die 3 "$artifact is a symbolic link"
elif [ -e "$artifact" ]; then
  [ -f "$artifact" ] || cl_die 3 "$artifact is not a regular file"
  [ "$(la_sha256 "$artifact")" = "$CL_FCOS_IMAGE_SHA256" ] \
    || cl_die 3 "the cached image $artifact does not match the pinned sha256; remove it by hand and run again"
  cl_log "cached image verified against the pinned sha256"
else
  dl=$(mktemp "$import_dir/.download.XXXXXXXX")
  la_tmps+=("$dl")
  curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 -o "$dl" -- "$CL_FCOS_IMAGE_URL" \
    || cl_die 4 "download failed"
  [ "$(la_sha256 "$dl")" = "$CL_FCOS_IMAGE_SHA256" ] || cl_die 3 "checksum mismatch; the download was discarded"
  mv -T -- "$dl" "$artifact" || cl_die 4 "cannot store the verified image"
  cl_log "image downloaded and verified against the pinned sha256"
fi

# A fresh decompressed copy for this run only (the sha256 above covers the artifact as published).
img=$(mktemp --suffix=.qcow2 "$import_dir/.import.XXXXXXXX")
la_tmps+=("$img")
case "$CL_FCOS_IMAGE_URL" in
  *.xz)
    if ! xz -dc -- "$artifact" > "$img"; then cl_die 4 "decompression failed; no guest was created"; fi ;;
  *)
    cp -- "$artifact" "$img" || cl_die 4 "cannot copy the image; no guest was created" ;;
esac
[ -s "$img" ] || cl_die 4 "the decompressed image is empty; no guest was created"

# --- build; any failure from here on leaves a guest that is reported, never deleted ------
la_partial() { # CODE MESSAGE...
  local code=$1; shift
  cl_log "PARTIAL: guest $vmid was created by this run and is NOT a finished template. Nothing was deleted."
  la_describe
  cl_die "$code" "$* — stopping; inspect the guest and decide by hand whether to remove it"
}

qm create "$vmid" --name corelab-fcos-template --pool "$CL_POOL" \
  --memory 2048 --cores 2 --cpu host --net0 "virtio,bridge=$CL_BRIDGE" \
  --scsihw virtio-scsi-pci --serial0 socket --vga serial0 --ostype l26 \
  || cl_die 4 "template create failed; check whether guest $vmid exists before running again"
qm disk import "$vmid" "$img" "$CL_VM_STORAGE" --target-disk scsi0 || la_partial 4 "disk import failed"
qm set "$vmid" --ide2 "$CL_VM_STORAGE:cloudinit" --boot order=scsi0 || la_partial 4 "template config failed"
qm template "$vmid" || la_partial 4 "template conversion failed"
la_verify_template 5
cl_log "template $vmid ready in pool $CL_POOL"
