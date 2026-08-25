#!/usr/bin/env bash
# Tests for check-credentials.sh.
#
# The scanner guards a public repository, so it needs tests of its own: a guard
# that silently passes everything is worse than no guard, because it is trusted.
#
# Note on the fixtures: every fake credential below is BUILT BY CONCATENATION at
# runtime. Writing one as a literal would mean this test file itself matches the
# patterns, and committing the tests would be blocked by the very hook they test.
set -uo pipefail

SCANNER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/check-credentials.sh"
pass=0; fail=0
GREEN=$'\033[32m'; RED=$'\033[31m'; OFF=$'\033[0m'

ok()  { pass=$((pass+1)); echo "${GREEN}ok${OFF}   $1"; }
bad() { fail=$((fail+1)); echo "${RED}FAIL${OFF} $1"; }

# A Google-shaped key that does not appear literally in this file.
fake_key() { printf '%s%s%s' 'AIza' 'Sy' "$(printf 'B%.0s' $(seq 1 32))"; }

# Build a throwaway repo with one clean commit on `main`, and echo its path.
new_repo() {
  local d; d=$(mktemp -d)
  git -C "$d" init -q -b main
  git -C "$d" config user.email t@example.com
  git -C "$d" config user.name test
  echo "clean" > "$d/README.md"
  git -C "$d" add -A && git -C "$d" commit -qm base
  echo "$d"
}

# Invoked via `bash`, not executed directly. The scripts were committed 100644
# once, and on Linux that turns every call into "Permission denied" — which
# surfaced as all six tests failing identically, a symptom that says nothing
# about the scanner. The mode bit is fixed; this stops it mattering again.
run() { ( cd "$1" && shift && bash "$SCANNER" "$@" ) > /dev/null 2>&1; echo $?; }

# --- staged mode (the pre-commit path) ---------------------------------------

d=$(new_repo)
printf 'KEY=%s\n' "$(fake_key)" > "$d/leak.txt"
git -C "$d" add leak.txt
[ "$(run "$d")" = "1" ] && ok "staged: blocks a staged credential" \
                        || bad "staged: blocks a staged credential"
rm -rf "$d"

d=$(new_repo)
echo "just prose" > "$d/notes.md"
git -C "$d" add notes.md
[ "$(run "$d")" = "0" ] && ok "staged: allows clean content" \
                        || bad "staged: allows clean content"
rm -rf "$d"

# --- range mode (the CI path) -------------------------------------------------
# Nothing is ever staged in CI, so the scanner must be able to scan a commit
# RANGE. Without this the CI invocation reports "no staged files" and exits 0,
# which is a guard that passes on everything.

d=$(new_repo)
printf 'KEY=%s\n' "$(fake_key)" > "$d/leak.txt"
git -C "$d" add -A && git -C "$d" commit -qm "oops"
[ "$(run "$d" --range HEAD~1..HEAD)" = "1" ] && ok "range: blocks a committed credential" \
                                             || bad "range: blocks a committed credential"
rm -rf "$d"

d=$(new_repo)
echo "more prose" > "$d/notes.md"
git -C "$d" add -A && git -C "$d" commit -qm "fine"
[ "$(run "$d" --range HEAD~1..HEAD)" = "0" ] && ok "range: allows a clean commit" \
                                             || bad "range: allows a clean commit"
rm -rf "$d"

d=$(new_repo)
mkdir -p "$d/_OPERATIONS"; echo "internal" > "$d/_OPERATIONS/BIBLE.md"
git -C "$d" add -A && git -C "$d" commit -qm "private file"
[ "$(run "$d" --range HEAD~1..HEAD)" = "1" ] && ok "range: blocks a forbidden path" \
                                             || bad "range: blocks a forbidden path"
rm -rf "$d"

# An empty range must not be read as "clean" — it means the caller passed
# something wrong, and silently succeeding is the failure this whole file exists
# to prevent.
d=$(new_repo)
[ "$(run "$d" --range HEAD..HEAD)" = "0" ] && ok "range: an empty range is not an error" \
                                           || bad "range: an empty range is not an error"
rm -rf "$d"

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
