# shellcheck shell=bash
# Action: bootstrap
# Creates the routine user and its privilege-separated token with READ-ONLY rights
# (PVEAuditor on /). Wider rights are granted later by `prepare`, after discovery.
#
# Parameters: CL_USER, CL_TOKEN, CL_EXPIRE_DAYS
#             Each is validated here before any use: host-run quotes the values for the
#             shell, but a quoted value still reaches Bash arithmetic and pveum arguments.
# Output:     one line CORELAB_TOKEN_SECRET=<secret>; host-run writes it to the token
#             file and never prints or logs it.
# Re-run:     the user is reused. An existing token of the same name is NOT replaced and
#             stops the run with exit 3 (rotate by choosing a new CL_TOKEN, then remove the
#             old one by hand). Every listing is read and parsed before it is trusted: a
#             failed or unparsable listing stops the run, it is never read as "absent".
# Not atomic: if a step after `token add` fails, the token exists on the host and its
#             secret was not stored. The message names the token; nothing is deleted here.

: "${CL_USER:?}" "${CL_TOKEN:?}" "${CL_EXPIRE_DAYS:?}"
export LC_ALL=C

# la_uint LABEL VALUE MIN MAX — canonical positive decimal: no sign, no leading zero, at most
# nine digits, inside MIN..MAX. After this passes, VALUE is safe in test and arithmetic.
la_uint() {
  [[ "$2" =~ ^[1-9][0-9]{0,8}$ ]] || cl_die 3 "$1 must be a positive decimal integer (no sign, no leading zero)"
  [ "$2" -ge "$3" ] && [ "$2" -le "$4" ] || cl_die 3 "$1=$2 is outside $3..$4"
}

# la_records JSON KEY — an array of objects, each with KEY as a non-empty scalar, KEY unique.
# Anything else fails, so an empty reply, [{}] or a non-array never reads as "not present".
la_records() {
  printf '%s' "$1" | cl_shape_ok list || return 1
  printf '%s' "$1" | CL_K="$2" cl_json_get '
    my %seen;
    for my $r (@$d) {
      die "element is not an object\n" unless ref $r eq "HASH";
      my $v = $r->{$ENV{CL_K}};
      die "record without a usable $ENV{CL_K}\n" unless defined $v && !ref $v && length $v;
      die "duplicate record\n" if $seen{$v}++;
    }
    scalar @$d'
}
# la_list_has JSON FIELD VALUE — 1 or 0, after la_records accepted the listing.
la_list_has() {
  la_records "$1" "$2" >/dev/null || return 1
  printf '%s' "$1" | CL_F="$2" CL_V="$3" cl_json_get 'scalar grep { $_->{$ENV{CL_F}} eq $ENV{CL_V} } @$d'
}

la_uint CL_EXPIRE_DAYS "$CL_EXPIRE_DAYS" 1 365
[[ "$CL_USER" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*@pve$ ]] || cl_die 3 "CL_USER must look like name@pve"
[[ "$CL_TOKEN" =~ ^[A-Za-z][A-Za-z0-9._-]*$ ]] || cl_die 3 "CL_TOKEN must be a plain token id"

users=$(pveum user list --output-format json) || cl_die 4 "cannot list users"
have_user=$(la_list_has "$users" userid "$CL_USER") || cl_die 4 "user list is not a JSON array of objects"
if [ "$have_user" = 1 ]; then
  cl_log "user $CL_USER exists"
elif [ "$have_user" = 0 ]; then
  pveum user add "$CL_USER" --comment "CoreOS Platform Lab agent (routine)" || cl_die 4 "user add failed"
  cl_log "user $CL_USER created"
else
  cl_die 4 "unexpected answer while looking for user $CL_USER"
fi

tokens=$(pveum user token list "$CL_USER" --output-format json) || cl_die 4 "cannot list tokens of $CL_USER"
have_token=$(la_list_has "$tokens" tokenid "$CL_TOKEN") || cl_die 4 "token list is not a JSON array of objects"
case "$have_token" in
  0) ;;
  1) cl_die 3 "token $CL_USER!$CL_TOKEN already exists; choose a new token name to rotate" ;;
  *) cl_die 4 "unexpected answer while looking for token $CL_TOKEN" ;;
esac

now=$(date +%s)
[[ "$now" =~ ^[1-9][0-9]{8,10}$ ]] || cl_die 4 "the host clock did not return epoch seconds"
expire=$(( now + CL_EXPIRE_DAYS * 86400 ))
# The response must be one object whose value is a single-line token of the expected
# characters. A rejected response is never echoed (stderr of the parser is discarded too,
# because a parse error can quote part of what it read).
secret=$(pveum user token add "$CL_USER" "$CL_TOKEN" --privsep 1 --expire "$expire" \
           --comment "corelab routine token" --output-format json \
         | cl_json_get '
             die "unexpected token response\n" unless ref $d eq "HASH";
             my $v = $d->{value};
             die "unexpected token response\n" unless defined $v && !ref $v && $v =~ /\A[A-Za-z0-9_.-]{8,128}\z/;
             $v' 2>/dev/null) \
  || cl_die 4 "token add failed or returned an unusable response; check 'pveum user token list $CL_USER' for $CL_TOKEN (nothing was removed)"
[[ "$secret" =~ ^[A-Za-z0-9_.-]{8,128}$ ]] \
  || cl_die 4 "token add returned an unusable secret; $CL_USER!$CL_TOKEN may exist without a stored secret: remove it by hand before retrying"

( cl_acl PVEAuditor / ) \
  || cl_die 4 "ACL step failed; $CL_USER!$CL_TOKEN exists, its secret was not stored: remove the token by hand before retrying"
printf 'CORELAB_TOKEN_SECRET=%s\n' "$secret"
unset secret
cl_log "token $CL_USER!$CL_TOKEN created, read-only, expires $(date -u -d "@$expire" +%F)"
