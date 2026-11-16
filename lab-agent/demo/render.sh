#!/usr/bin/env bash
# Render the demo Butane to Ignition with a pinned Butane container.
# Usage: demo/render.sh <ssh-public-key-file> <output.ign>
# The output is a build artifact (*.ign is git-ignored); upload it with
#   ssh pve-snip put <slug> < <output.ign>
set -euo pipefail

BUTANE_IMAGE="quay.io/coreos/butane:v0.23.0"
here=$(cd "$(dirname "$0")" && pwd)
pubkey_file=${1:?usage: render.sh <ssh-public-key-file> <output.ign>}
out=${2:?usage: render.sh <ssh-public-key-file> <output.ign>}

pubkey=$(head -n 1 "$pubkey_file")
case "$pubkey" in
  ssh-ed25519\ *|ecdsa-sha2-nistp*\ *) ;;
  *) echo "render.sh: $pubkey_file is not an ed25519/ecdsa public key" >&2; exit 2 ;;
esac
pubkey=$(printf '%s' "$pubkey" | awk '{print $1" "$2}')

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
sed "s#@DEMO_SSH_PUBKEY@#$pubkey#" "$here/fcos-demo.bu" > "$tmp"
docker run --rm -i --network none "$BUTANE_IMAGE" --strict < "$tmp" > "$out"
echo "rendered $out ($(wc -c < "$out") bytes)"
