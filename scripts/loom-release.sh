#!/bin/sh
# Loom release: publish the pack at LOOM_RELEASE_SHA as a GitHub release of this repo.
#
# The pack ships the way its README installs it: a zip of the repository (data/, fonts and
# the MSE executables). This script checks the pack, then creates the tag v<version>-<sha7>
# at exactly that commit with a GitHub release whose notes list the merged changes and link the
# tag's zip. The tag is derived from the commit, so a retry finds the release it already
# published and exits 0 without shipping twice.
#
# Modes (LOOM_RELEASE_MODE): plan/check describe what would ship and change nothing;
# run/resume publish. Needs gh logged in (or RELEASE_GH_TOKEN) with contents:write on the repo.
set -eu

MODE="${LOOM_RELEASE_MODE:-run}"
cd "$(dirname "$0")/.."

SHA=$(git rev-parse --verify "${LOOM_RELEASE_SHA:-HEAD}^{commit}")
SHORT=$(printf %s "$SHA" | cut -c1-7)
if [ -z "${RELEASE_REPO:-}" ]; then
  RELEASE_REPO=$(git remote get-url origin | sed -E 's#^.*github\.com[:/]##; s#\.git$##')
fi
REPO="$RELEASE_REPO"

HEADLINE=$(git show "$SHA:changelog.txt" | head -n1 | tr -d '\r' | sed 's/^\xEF\xBB\xBF//')
VERSION=$(printf %s "$HEADLINE" | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n1)
[ -n "$VERSION" ] || { echo "No version found in the first line of changelog.txt at $SHA" >&2; exit 1; }
TAG="v$VERSION-$SHORT"
PRERELEASE=""
case "$HEADLINE" in *PRERELEASE*|*prerelease*) PRERELEASE="--prerelease" ;; esac

echo "Checking the pack at $SHA"
git diff --quiet "$SHA" -- data scripts || echo "warning: working tree differs from $SHA; checking the working tree" >&2
python3 -B scripts/check-pack.py

if [ -n "${RELEASE_GH_TOKEN:-}" ]; then GH_TOKEN="$RELEASE_GH_TOKEN"; export GH_TOKEN; fi
command -v gh >/dev/null || { echo "gh CLI not found" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "gh is not logged in on this device (or set RELEASE_GH_TOKEN)" >&2; exit 1; }
gh api "repos/$REPO/commits/$SHA" --jq .sha >/dev/null || { echo "$SHA is not on github.com/$REPO" >&2; exit 1; }

# gh api prints the error body on stdout for a 404, so discard output on failure.
PUBLISHED=$(gh api "repos/$REPO/releases/tags/$TAG" --jq '.html_url' 2>/dev/null) || PUBLISHED=""
TAG_SHA=$(gh api "repos/$REPO/git/ref/tags/$TAG" --jq '.object.sha' 2>/dev/null) || TAG_SHA=""
if [ -n "$TAG_SHA" ] && [ "$TAG_SHA" != "$SHA" ]; then
  # Annotated tags point at a tag object; resolve it to its commit.
  TAG_SHA=$(gh api "repos/$REPO/git/tags/$TAG_SHA" --jq '.object.sha' 2>/dev/null) || true
  [ "$TAG_SHA" = "$SHA" ] || { echo "Tag $TAG already exists on $REPO at $TAG_SHA, not $SHA" >&2; exit 1; }
fi

ZIP="https://github.com/$REPO/archive/refs/tags/$TAG.zip"
NOTES=$(mktemp)
trap 'rm -f "$NOTES"' EXIT
{
  echo "$HEADLINE"
  echo
  echo "Download the pack: $ZIP"
  echo "Extract it and follow the README's installation steps (copy into your MSE folder, or run it standalone)."
  if [ -n "${LOOM_RELEASE_DIR:-}" ] && [ -s "$LOOM_RELEASE_DIR/merged.json" ]; then
    echo
    echo "## Changes"
    python3 -c 'import json,sys
for pr in json.load(open(sys.argv[1])): print("- %s (#%s)" % (pr.get("title", "").strip(), pr.get("number", "")))' "$LOOM_RELEASE_DIR/merged.json"
  fi
  echo
  echo "Commit: $SHA"
} > "$NOTES"

if [ -n "$PUBLISHED" ]; then
  MSG="Already published: $PUBLISHED ($TAG at $SHA). Nothing to do."
else
  MSG="Would publish GitHub release $TAG${PRERELEASE:+ (prerelease)} on $REPO at $SHA; the pack downloads from $ZIP"
fi

if [ "$MODE" = "plan" ] || [ "$MODE" = "check" ]; then
  echo "$MSG"
  if [ -n "${LOOM_RELEASE_DIR:-}" ]; then
    { printf '# Release plan\n\n%s\n\n## Release notes\n\n' "$MSG"; cat "$NOTES"; } > "$LOOM_RELEASE_DIR/plan.md"
  fi
  exit 0
fi

if [ -n "$PUBLISHED" ]; then
  echo "$MSG"
  exit 0
fi

if [ -n "$TAG_SHA" ]; then
  gh release create "$TAG" -R "$REPO" --verify-tag --title "Full Magic Pack $VERSION ($SHORT)" --notes-file "$NOTES" $PRERELEASE
else
  gh release create "$TAG" -R "$REPO" --target "$SHA" --title "Full Magic Pack $VERSION ($SHORT)" --notes-file "$NOTES" $PRERELEASE
fi
URL=$(gh api "repos/$REPO/releases/tags/$TAG" --jq '.html_url')
echo "Published $URL"
echo "Pack download: $ZIP"
