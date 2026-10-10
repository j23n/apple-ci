#!/bin/sh
# Tests link-pr.sh with a stand-in for gh, which keeps the issues a pull request closes in a file
# (the self-test runs it): sh claude/test-link-pr.sh
set -eu

here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir "$work/bin"
cat > "$work/bin/gh" <<'GH'
#!/bin/sh
# gh issue view N --json id -q .id, gh pr view M --json id|closingIssuesReferences -q …, gh api graphql …
state="$GH_STATE"
case "$1 $2" in
  "issue view") echo "ISSUE_$3" ;;
  "pr view")
    if [ "$5" = id ]; then echo "PR_$3"; else cat "$state" 2>/dev/null || true; fi ;;
  "api graphql")
    [ -n "${GH_IGNORES_MUTATIONS:-}" ] && exit 0
    query="$4"; issue="${6#issue=}"; issue="${issue#ISSUE_}"
    case "$query" in
      *addCloseIssueReferences*) echo "$issue" >> "$state" ;;
      *removeCloseIssueReferences*) grep -vx "$issue" "$state" > "$state.new" || true; mv "$state.new" "$state" ;;
    esac ;;
  *) echo "unexpected: gh $*" >&2; exit 3 ;;
esac
GH
chmod +x "$work/bin/gh"
PATH="$work/bin:$PATH"
GH_STATE="$work/closes"
export PATH GH_STATE
link="$here/link-pr.sh"

fail() { echo "FAIL: $1" >&2; exit 1; }

out=$(sh "$link" 12 34) || fail "linking failed"
[ "$out" = "#34 closes #12 when it's merged" ] || fail "linking said: $out"
grep -qx 12 "$GH_STATE" || fail "the link wasn't made"

out=$(sh "$link" --remove 12 34) || fail "removing failed"
[ "$out" = "#34 no longer closes #12" ] || fail "removing said: $out"
! grep -qx 12 "$GH_STATE" || fail "the link wasn't removed"

for args in "" "12" "12 34 56" "twelve 34" "12 #34" "--remove 12"; do
  # shellcheck disable=SC2086
  if sh "$link" $args 2>/dev/null; then fail "accepted: $args"; fi
done

if GH_IGNORES_MUTATIONS=1 sh "$link" 12 34 2>/dev/null; then fail "didn't notice that the link wasn't made"; fi

echo "link-pr.sh: all tests passed"
