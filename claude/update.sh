#!/bin/sh
# Copies apple-ci's shared Claude instructions into this repository, where its CLAUDE.md imports
# them (README.md, "Claude"). Run it from the repository's root:
#   curl -fsSL https://raw.githubusercontent.com/j23n/apple-ci/main/claude/update.sh | sh
#   … | sh -s -- apps        in an app, which also gets apps.md (make update-apple-ci runs this)
#   … | sh -s -- --check     says which copies differ from apple-ci's, and exits 1 if any do
# APPLE_CI_RAW changes where the files come from (the self-test uses a file:// URL).
set -eu

raw="${APPLE_CI_RAW:-https://raw.githubusercontent.com/j23n/apple-ci/main}"
check=false
apps=false
for arg in "$@"; do
  case "$arg" in
    --check) check=true ;;
    apps) apps=true ;;
    *) echo "usage: update.sh [--check] [apps]" >&2; exit 2 ;;
  esac
done

# Each line: the file in apple-ci, then where the repository keeps its copy.
files="claude/j23n.md .apple-ci/claude/j23n.md
claude/link-pr.sh .apple-ci/claude/link-pr.sh
claude/pull_request_template.md .github/pull_request_template.md"
if $apps || { $check && [ -f .apple-ci/claude/apps.md ]; }; then
  files="$files
claude/apps.md .apple-ci/claude/apps.md"
fi

stale=0
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
while read -r source copy; do
  curl -fsSL "$raw/$source" -o "$tmp"
  if $check; then
    if ! cmp -s "$tmp" "$copy"; then
      echo "$copy differs from j23n/apple-ci's $source"
      stale=1
    fi
  else
    mkdir -p "$(dirname "$copy")"
    cat "$tmp" > "$copy"
  fi
done <<LIST
$files
LIST

if $check; then
  [ "$stale" -eq 0 ] || { echo "Refresh them with make update-apple-ci (or claude/update.sh)."; exit 1; }
  echo "The shared Claude instructions are current."
else
  chmod +x .apple-ci/claude/link-pr.sh
  echo "Updated: $(printf '%s\n' "$files" | awk '{print $2}' | tr '\n' ' ')"
fi
