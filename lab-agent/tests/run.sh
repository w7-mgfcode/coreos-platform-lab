#!/usr/bin/env bash
# Offline gate for the lab agent. Touches no host: unit tests use fixtures and stubs.
# Tools not installed locally run from pinned container images (network: none). The gate
# never pulls, builds or installs anything: a missing docker or image is a SKIP. A container
# exit status is never taken as proof that a tool read every input: ShellCheck must report one
# record per input file and Butane must emit an Ignition document made from its input.
#
# Prints PASS/FAIL/SKIP per check, names every failed and skipped check, then a final
# RESULT line. Exit status:
#   0  RESULT: PASS        every check ran and passed (no SKIP, no skipped unit test)
#   1  RESULT: FAIL        at least one check failed
#   2  RESULT: INCOMPLETE  nothing failed, but at least one check (or unit test) was skipped
set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1  # leave no bytecode in lab-agent/ or .claude/

here=$(cd "$(dirname "$0")/.." && pwd)
repo=$(cd "$here/.." && pwd)
SHELLCHECK_IMAGE="docker.io/koalaman/shellcheck:v0.10.0"
BUTANE_IMAGE="quay.io/coreos/butane:v0.23.0"
EXPECTED_CHECKS=7

# Required inventory (paths relative to lab-agent/). The checks below enumerate the host actions
# with a glob, which only finds what exists: without this list, deleting an action would shrink
# the set of inputs and still pass. Edit the list when an action is added or removed on purpose.
REQUIRED_FILES=(
  host/lib.sh
  host/actions/backup-config.sh
  host/actions/bootstrap.sh
  host/actions/discover-host.sh
  host/actions/fcos-template.sh
  host/actions/preflight.sh
  host/actions/prepare.sh
  host/actions/sentinel.sh
  host/snippet-writer/corelab-snippet-put
  demo/render.sh
  demo/fcos-demo.bu
  tests/run.sh
)
missing_required=()
for f in "${REQUIRED_FILES[@]}"; do
  [ -f "$here/$f" ] || missing_required+=("$f")
done
# The reverse direction: an entry in host/actions (hidden ones included) that the list does not
# name is an unreviewed input, so it fails the gate here instead of depending on a unit test.
unlisted=()
while IFS= read -r f; do
  listed=0
  for r in "${REQUIRED_FILES[@]}"; do [ "$r" = "host/actions/$f" ] && listed=1; done
  [ "$listed" -eq 1 ] || unlisted+=("host/actions/$f")
done < <(cd "$here/host/actions" 2>/dev/null && shopt -s dotglob nullglob && printf '%s\n' *)
inventory_problems=$(( ${#missing_required[@]} + ${#unlisted[@]} ))

# Private scratch directory (mode 700, unpredictable name), removed on exit.
if ! scratch=$(mktemp -d "${TMPDIR:-/tmp}/corelab-gate.XXXXXXXX"); then
  echo "FAIL   cannot create a private temporary directory"; echo; echo "RESULT: FAIL"; exit 1
fi
trap 'rm -rf "$scratch"' EXIT

checks=0
failed=()
skipped=()
result() {
  printf '%-6s %s\n' "$1" "$2"
  checks=$((checks + 1))
  case "$1" in
    FAIL) failed+=("$2") ;;
    SKIP) skipped+=("$2") ;;
  esac
  return 0
}

# image_ready IMAGE: true only if docker is on PATH and IMAGE is already present locally.
# Never pulls. On false, $why says which prerequisite is missing.
why=""
image_ready() {
  if ! command -v docker >/dev/null 2>&1; then
    why="docker not found on PATH"; return 1
  fi
  if ! docker image inspect "$1" >/dev/null 2>&1; then
    why="image $1 not present locally or docker daemon unreachable (the gate does not pull)"; return 1
  fi
  return 0
}

# 1. Python unit tests. Verbose output goes to the private scratch directory; the summary
#    line (with any skipped count) is shown, and skipped tests are named.
ut_log="$scratch/unittest.log"
(cd "$here" && python3 -m unittest discover -v -s tests -t . >"$ut_log" 2>&1)
ut_rc=$?
ran=$(grep -Eo '^Ran [0-9]+ tests?' "$ut_log" | tail -n 1)
summary=$(grep -E '^(OK|FAILED)( \(.*\))?$' "$ut_log" | tail -n 1)
nran=$(printf '%s' "$ran" | grep -Eo '[0-9]+' || true)
nskip=$(printf '%s' "$summary" | grep -Eo 'skipped=[0-9]+' | cut -d= -f2 || true)
if [ "$ut_rc" -ne 0 ] || [ "${summary%% *}" != OK ] || [ -z "$nran" ] || [ "$nran" -eq 0 ]; then
  result FAIL "python unit tests (${ran:-no tests ran}; ${summary:-no summary line}; exit $ut_rc)"
  cat "$ut_log"
elif [ -n "$nskip" ] && [ "$nskip" -gt 0 ]; then
  result SKIP "python unit tests ($ran; $summary): $nskip unit test(s) skipped"
  grep -E '\.\.\. skipped' "$ut_log" | sed 's/^/  skipped test: /'
else
  result PASS "python unit tests ($ran; $summary)"
fi

# 2. Perl syntax of the snippet writer
if perl -c "$here/host/snippet-writer/corelab-snippet-put" >/dev/null 2>&1; then
  result PASS "perl -c corelab-snippet-put"
else
  result FAIL "perl -c corelab-snippet-put"
fi

# 3. bash -n on every shell file (an unmatched glob is a syntax failure, not a silent drop)
bad=0
for f in "$here"/host/lib.sh "$here"/host/actions/*.sh "$here"/demo/render.sh "$here"/tests/run.sh; do
  bash -n "$f" || { echo "  syntax error: $f"; bad=1; }
done
for f in "${missing_required[@]}"; do echo "  missing required file: $f"; bad=1; done
for f in "${unlisted[@]}"; do echo "  unlisted file (not in REQUIRED_FILES): $f"; bad=1; done
if [ "$bad" -eq 0 ]; then result PASS "bash -n on all shell files (${#REQUIRED_FILES[@]} required files present, none unlisted)"
else result FAIL "bash -n / required inventory"; fi

# 4. shellcheck: each action is checked together with lib.sh, as the owner-only runner sends them.
#    A container exit status is not proof that every file was read, so the run uses the
#    checkstyle format, which prints one <file name=...> record per input the tool processed
#    (clean files included). The gate fails unless the records match the inputs one to one.
if image_ready "$SHELLCHECK_IMAGE"; then
  work="$scratch/shellcheck"
  mkdir "$work"
  for a in "$here"/host/actions/*.sh; do
    { echo '#!/usr/bin/env bash'; echo 'set -euo pipefail'; cat "$here/host/lib.sh" "$a"; } > "$work/$(basename "$a")"
  done
  cp "$here/demo/render.sh" "$here/tests/run.sh" "$work/"
  chmod 0755 "$work"; chmod 0644 "$work"/*.sh
  files=()
  for f in "$work"/*.sh; do files+=("/mnt/$(basename "$f")"); done
  sc_out="$scratch/shellcheck.xml"
  # SC2154: CL_* parameters and embedded-file functions are exported by the runner's header.
  docker run --rm --network none -v "$work:/mnt:ro" "$SHELLCHECK_IMAGE" -S warning -e SC2154 -f checkstyle \
    "${files[@]}" >"$sc_out" 2>"$scratch/shellcheck.err"
  sc_rc=$?
  for f in "${missing_required[@]}"; do echo "  missing required file: $f"; done
  for f in "${unlisted[@]}"; do echo "  unlisted file (not in REQUIRED_FILES): $f"; done
  # The checkstyle formatter writes characters such as - _ . / as numeric character references.
  records=$(sed -n "s/^<file name='\([^']*\)'.*/\1/p" "$sc_out" \
            | sed -e 's/&#45;/-/g' -e 's/&#95;/_/g' -e 's/&#46;/./g' -e 's/&#47;/\//g' -e 's/&amp;/\&/g')
  nrec=0
  while IFS= read -r line; do [ -n "$line" ] && nrec=$((nrec + 1)); done <<<"$records"
  unprocessed=()
  for f in "${files[@]}"; do
    case $'\n'"$records"$'\n' in *$'\n'"$f"$'\n'*) ;; *) unprocessed+=("$f") ;; esac
  done
  if [ "$inventory_problems" -gt 0 ]; then
    result FAIL "shellcheck: required inventory differs from the tree (${#missing_required[@]} missing, ${#unlisted[@]} unlisted)"
  elif [ "$sc_rc" -ne 0 ]; then
    result FAIL "shellcheck (exit $sc_rc)"; cat "$sc_out" "$scratch/shellcheck.err"
  elif [ "${#unprocessed[@]}" -gt 0 ] || [ "$nrec" -ne "${#files[@]}" ]; then
    result FAIL "shellcheck processed $nrec of ${#files[@]} input files (exit 0 is not proof)"
    for f in "${unprocessed[@]}"; do echo "  no shellcheck record for: $f"; done
  else
    result PASS "shellcheck (actions+lib, render.sh, run.sh; $nrec of ${#files[@]} files processed)"
  fi
else
  result SKIP "shellcheck: $why"
fi

# 5. Butane --strict on the demo config (with a placeholder key). Exit status alone is not proof
#    that the tool translated this input: the output must be an Ignition document that carries
#    the placeholder key taken from the input.
BUTANE_KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPLACEHOLDERplaceholderPLACEHOLDERplace'
if image_ready "$BUTANE_IMAGE"; then
  bu_out="$scratch/butane.json"
  if sed "s#@DEMO_SSH_PUBKEY@#$BUTANE_KEY#" "$here/demo/fcos-demo.bu" \
       | docker run --rm -i --network none "$BUTANE_IMAGE" --strict >"$bu_out" 2>"$scratch/butane.err"; then
    if python3 -c 'import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
text = open(sys.argv[1], encoding="utf-8").read()
sys.exit(0 if isinstance(doc, dict) and doc.get("ignition", {}).get("version") and sys.argv[2] in text else 1)' \
         "$bu_out" "$BUTANE_KEY" 2>/dev/null; then
      result PASS "butane --strict demo/fcos-demo.bu (Ignition output carries the input's key)"
    else
      result FAIL "butane --strict demo/fcos-demo.bu produced no valid Ignition for this input (exit 0 is not proof)"
    fi
  else
    result FAIL "butane --strict demo/fcos-demo.bu"; cat "$scratch/butane.err"
  fi
else
  result SKIP "butane: $why"
fi

# local_state PATH: "absent" only if nothing is there at all (not even a dangling symlink),
# "file" for a regular file (or a symlink to one), "invalid" for everything else.
local_state() {
  if [ -e "$1" ] || [ -L "$1" ]; then
    if [ -f "$1" ]; then echo file; else echo invalid; fi
  else
    echo absent
  fi
}

# 6. JSON configuration. The in-tree files are always checked and a missing one is a FAIL.
#    A local-only file (.mcp.json) is checked if present; its absence is an info line, not a
#    SKIP and not a FAIL, so the gate can pass in a clean checkout. A present but invalid path
#    (dangling symlink, directory, other non-regular file) is a FAIL, never "absent".
bad=0
json_files=("$repo/.claude/settings.json" "$here/mcp.example.json")
case "$(local_state "$repo/.mcp.json")" in
  file) json_files+=("$repo/.mcp.json") ;;
  invalid) echo "  present but not a regular file: .mcp.json"; bad=1 ;;
  *) echo "info   .mcp.json not present (local-only file, not checked)" ;;
esac
json_names=""
for f in "${json_files[@]}"; do
  if [ ! -f "$f" ]; then echo "  missing in-tree file: ${f#"$repo"/}"; bad=1; continue; fi
  python3 -m json.tool "$f" >/dev/null || { echo "  invalid JSON: ${f#"$repo"/}"; bad=1; }
  json_names="${json_names:+$json_names, }${f#"$repo"/}"
done
if [ "$bad" -eq 0 ]; then result PASS "JSON syntax ($json_names)"; else result FAIL "JSON syntax"; fi

# 7. Hooks compile (in memory: no __pycache__ is written). The in-tree candidate is always
#    compiled and a missing one is a FAIL; the active local hook is compiled if it exists, and a
#    present but invalid path is a FAIL.
bad=0
hook_files=("$here/proposed/hooks/pve-guard.py")
case "$(local_state "$repo/.claude/hooks/pve-guard.py")" in
  file) hook_files+=("$repo/.claude/hooks/pve-guard.py") ;;
  invalid) echo "  present but not a regular file: .claude/hooks/pve-guard.py"; bad=1 ;;
  *) echo "info   .claude/hooks/pve-guard.py not present (local-only file, not checked)" ;;
esac
hook_names=""
for f in "${hook_files[@]}"; do
  if [ ! -f "$f" ]; then echo "  missing in-tree file: ${f#"$repo"/}"; bad=1; continue; fi
  python3 -c 'import sys; compile(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1], "exec")' "$f" \
    || { echo "  does not compile: ${f#"$repo"/}"; bad=1; }
  hook_names="${hook_names:+$hook_names, }${f#"$repo"/}"
done
if [ "$bad" -eq 0 ]; then result PASS "pve-guard.py compiles ($hook_names)"; else result FAIL "pve-guard.py compiles"; fi

if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  result FAIL "gate integrity: $checks check results recorded, $EXPECTED_CHECKS expected"
fi

echo
for c in "${failed[@]}"; do echo "failed:  $c"; done
for c in "${skipped[@]}"; do echo "skipped: $c"; done
if [ "${#failed[@]}" -gt 0 ]; then
  echo "RESULT: FAIL (${#failed[@]} failed, ${#skipped[@]} skipped)"
  exit 1
elif [ "${#skipped[@]}" -gt 0 ]; then
  echo "RESULT: INCOMPLETE (${#skipped[@]} skipped; not a pass)"
  exit 2
fi
echo "RESULT: PASS (all $EXPECTED_CHECKS checks ran)"
exit 0
