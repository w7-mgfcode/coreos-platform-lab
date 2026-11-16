#!/usr/bin/env bash
# Read-only export of a repository's issue tree and its Projects v2 board for check.py.
# Usage: inventory.sh OWNER/REPO PROJECT_OWNER PROJECT_NUMBER OUT_DIR
# Only GET requests and one GraphQL *query*. Never writes to GitHub. OUT_DIR must be outside the
# tracked tree (it holds issue text, which is data and may be private until reviewed).
# A failed or truncated fetch (including ANY truncated nested GraphQL connection) is recorded in meta.json
# (complete=false); check.py then refuses to conclude. Exit: 0 complete, 1 incomplete or a local write failed, 2 usage.
set -uo pipefail
repo=${1:?OWNER/REPO}; powner=${2:?project owner}; pnum=${3:?project number}; out=${4:?out dir}
if ! command -v gh >/dev/null || ! command -v jq >/dev/null; then echo "gh and jq are required" >&2; exit 2; fi
mkdir -p "$out"
if [ -n "$(ls -A "$out")" ]; then echo "OUT_DIR must be new or empty" >&2; exit 2; fi
if git -C "$out" rev-parse --is-inside-work-tree >/dev/null 2>&1 && ! git -C "$out" check-ignore -q "$out/x" 2>/dev/null; then
  echo "OUT_DIR is inside a git work tree and not ignored: refusing" >&2; exit 2
fi
errors=()
fail() { errors+=("$1"); }
# Paginated REST list -> one JSON array. gh 2.46 has no --slurp, so merge the pages with jq.
rest_list() { # path outfile
  gh api --paginate "$1" 2>"$out/.err" | jq -s 'add // []' >"$2" || { fail "$1: $(head -c 200 "$out/.err")"; echo '[]' >"$2"; }
  jq -e 'type=="array"' "$2" >/dev/null 2>&1 || { fail "$1: not an array"; echo '[]' >"$2"; }
}
rest_list "repos/$repo/issues?state=all&per_page=100" "$out/issues.json"
rest_list "repos/$repo/pulls?state=all&per_page=100" "$out/pulls.json"
rest_list "repos/$repo/milestones?state=all&per_page=100" "$out/milestones.json"
rest_list "repos/$repo/labels?per_page=100" "$out/labels.json"

# Per-issue native edges. A failed call is an error, never an empty result.
: >"$out/.sub"; : >"$out/.blk"
for n in $(jq -r '.[] | select(has("pull_request")|not) | .number' "$out/issues.json"); do
  if c=$(gh api --paginate "repos/$repo/issues/$n/sub_issues?per_page=100" 2>/dev/null | jq -s -c --argjson p "$n" '{parent:$p, children:(add//[]|map(.number))}'); then
    echo "$c" >>"$out/.sub" || fail "append to sub_issues intermediate for #$n"; else fail "sub_issues of #$n"; fi
  if b=$(gh api --paginate "repos/$repo/issues/$n/dependencies/blocked_by?per_page=100" 2>/dev/null | jq -s -c --argjson i "$n" '{issue:$i, blocked_by:(add//[]|map(.number))}'); then
    echo "$b" >>"$out/.blk" || fail "append to blocked_by intermediate for #$n"; else fail "blocked_by of #$n"; fi
done
# Every local intermediate must hold exactly one line per issue before it is trusted.
nissues=$(jq '[.[] | select(has("pull_request")|not)] | length' "$out/issues.json" 2>/dev/null || echo -1)
for f in .sub .blk; do
  have=$(wc -l <"$out/$f" 2>/dev/null || echo -2)
  [ "$have" -eq "$nissues" ] || fail "intermediate $f has $have lines for $nissues issues"
done
jq -s '.' "$out/.sub" >"$out/sub_issues.json" || fail "write sub_issues.json"
jq -s '.' "$out/.blk" >"$out/blocked_by.json" || fail "write blocked_by.json"

# Any nested connection that reports hasNextPage=true was truncated: refuse (no need to paginate it).
# $2 is a jq path to ignore (the cursor-paged project items).
truncated() { # file label [ignore-path]
  jq -e "${3:+del($3) |} [.. | objects | select(has(\"pageInfo\")) | .pageInfo.hasNextPage] | any | not" "$1" >/dev/null 2>&1 || fail "$2: a connection is truncated or unreadable"
}

# GraphQL (query only): totals for completeness, PR closing references, and the whole board.
owner=${repo%%/*}; name=${repo##*/}
# shellcheck disable=SC2016  # GraphQL variables are literal text, not shell expansions
gh api graphql -f owner="$owner" -f name="$name" -f query='
query($owner:String!,$name:String!){repository(owner:$owner,name:$name){
  issues{totalCount} pullRequests(first:100){totalCount pageInfo{hasNextPage}
    nodes{number closingIssuesReferences(first:50){pageInfo{hasNextPage} nodes{number}}}}
  labels{totalCount} milestones{totalCount}}}' >"$out/totals.json" 2>"$out/.err" || fail "totals: $(head -c 200 "$out/.err")"
jq -c '[.data.repository.pullRequests.nodes[] | {pr:.number, closes:[.closingIssuesReferences.nodes[].number]}]' "$out/totals.json" >"$out/closing.json" 2>/dev/null || { fail "closing references unreadable"; echo '[]' >"$out/closing.json"; }
truncated "$out/totals.json" "totals/closing references"

# Board: owner may be a user or an organization; items are paged by cursor until hasNextPage is false.
# shellcheck disable=SC2016
q='query($login:String!,$num:Int!,$after:String){__K__(login:$login){projectV2(number:$num){
  id title public closed shortDescription readme
  fields(first:50){pageInfo{hasNextPage} nodes{__typename ... on ProjectV2FieldCommon{id name dataType}
    ... on ProjectV2SingleSelectField{options{id name}}}}
  views(first:30){totalCount pageInfo{hasNextPage} nodes{id name layout filter
    groupByFields(first:5){pageInfo{hasNextPage} nodes{... on ProjectV2FieldCommon{name}}}
    verticalGroupByFields(first:5){pageInfo{hasNextPage} nodes{... on ProjectV2FieldCommon{name}}}
    sortByFields(first:5){pageInfo{hasNextPage} nodes{field{... on ProjectV2FieldCommon{name}} direction}}
    fields(first:30){pageInfo{hasNextPage} nodes{... on ProjectV2FieldCommon{name}}}}}
  items(first:100,after:$after){totalCount pageInfo{hasNextPage endCursor} nodes{id isArchived type
    content{__typename ... on Issue{number state stateReason repository{nameWithOwner}}
      ... on PullRequest{number state repository{nameWithOwner}} ... on DraftIssue{title}}
    fieldValues(first:30){pageInfo{hasNextPage} nodes{__typename
      ... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{name}}}
      ... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2FieldCommon{name}}}
      ... on ProjectV2ItemFieldMilestoneValue{milestone{title} field{... on ProjectV2FieldCommon{name}}}}}}}}}}'
kind=user; gh api graphql -f query="${q//__K__/user}" -f login="$powner" -F num="$pnum" >/dev/null 2>&1 || kind=organization
after=""; : >"$out/.pages"
while :; do
  args=(-f query="${q//__K__/$kind}" -f login="$powner" -F num="$pnum"); if [ -n "$after" ]; then args+=(-f after="$after"); fi
  page=$(gh api graphql "${args[@]}" 2>"$out/.err") || { fail "project page: $(head -c 200 "$out/.err")"; break; }
  jq -c . <<<"$page" >>"$out/.pages" || fail "append project page"
  printf '%s' "$page" >"$out/.page" || fail "write project page"; truncated "$out/.page" "project (nested connection)" ".data[].projectV2.items.pageInfo"
  [ "$(jq -r ".data.$kind.projectV2.items.pageInfo.hasNextPage" <<<"$page")" = "true" ] || break
  after=$(jq -r ".data.$kind.projectV2.items.pageInfo.endCursor" <<<"$page")
done
# Merge pages into one document; pageInfo comes from the LAST page, so a broken loop leaves hasNextPage true.
python3 -I - "$out" "$kind" <<'PY' || fail "project merge"
import json, sys
out, kind = sys.argv[1], sys.argv[2]
pages = [json.loads(l) for l in open(out + "/.pages") if l.strip()]
doc = pages[0]
items = doc["data"][kind]["projectV2"]["items"]
items["nodes"] = [n for p in pages for n in p["data"][kind]["projectV2"]["items"]["nodes"]]
items["pageInfo"] = pages[-1]["data"][kind]["projectV2"]["items"]["pageInfo"]
with open(out + "/project.json", "w") as f:
    json.dump(doc, f)
PY
# The merged item list must equal the total the board reports.
got=$(jq ".data.$kind.projectV2.items.nodes | length" "$out/project.json" 2>/dev/null || echo -1)
want=$(jq ".data.$kind.projectV2.items.totalCount" "$out/project.json" 2>/dev/null || echo -2)
[ "$got" = "$want" ] || fail "merged project items: $got of $want"

# Expected counts come from GraphQL totals, never from what was just fetched.
exp=$(jq -c '{issues:(.data.repository.issues.totalCount), pulls:(.data.repository.pullRequests.totalCount),
              labels:(.data.repository.labels.totalCount), milestones:(.data.repository.milestones.totalCount)}' "$out/totals.json" 2>/dev/null || echo '{}')
pitems=$(jq -r ".data.$kind.projectV2.items.totalCount // empty" "$out/project.json" 2>/dev/null)
[ -n "$pitems" ] && exp=$(jq -c --argjson n "$pitems" '. + {project_items:$n}' <<<"$exp")
# GraphQL issues.totalCount counts issues only (not PRs); issues.json holds both, check.py counts non-PRs.
ids=$(jq -r '[.[]|.number]|sort|"\(.[0]//0)..\(.[-1]//0)"' "$out/issues.json")
printf '%s\n' "${errors[@]+"${errors[@]}"}" | jq -R . | jq -s --arg repo "$repo" --arg at "$(date -u +%FT%TZ)" --arg ids "$ids" --argjson exp "$exp" \
  '{repo:$repo, fetched_at:$at, number_range:$ids, expected:$exp, errors:(map(select(length>0))), complete:((map(select(length>0))|length)==0)}' >"$out/meta.json" \
  || { echo "cannot write meta.json" >&2; exit 1; }
rm -f "$out"/.sub "$out"/.blk "$out"/.pages "$out"/.page "$out"/.err
complete=$(jq -r .complete "$out/meta.json" 2>/dev/null) || complete=false
echo "export: $out (complete=$complete, errors=$(jq '.errors|length' "$out/meta.json" 2>/dev/null))"
[ "$complete" = "true" ] || { jq -r '.errors[]' "$out/meta.json" >&2 2>/dev/null; exit 1; }
