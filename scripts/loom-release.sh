#!/bin/sh
# Loom release: offer this fork's main to the upstream pack as a pull request.
# Idempotent: if the PR is already open it just follows main, so nothing is opened twice.
set -eu
UPSTREAM="${RELEASE_UPSTREAM:-MagicSetEditorPacks/Full-Magic-Pack}"
FORK="${RELEASE_FORK:-lawlordev/Full-Magic-Pack}"
BRANCH="${RELEASE_BRANCH:-main}"
MODE="${LOOM_RELEASE_MODE:-run}"
OWNER="${FORK%%/*}"

command -v gh >/dev/null || { echo "gh CLI not found" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "gh is not logged in on this device" >&2; exit 1; }

AHEAD=$(gh api "repos/$UPSTREAM/compare/$BRANCH...$OWNER:${FORK#*/}:$BRANCH" --jq .ahead_by)
EXISTING=$(gh pr list -R "$UPSTREAM" --state open --limit 100 --json url,headRefName,headRepositoryOwner \
  --jq ".[] | select(.headRefName==\"$BRANCH\" and .headRepositoryOwner.login==\"$OWNER\") | .url" | head -n1)

TITLE="Template updates from $FORK"
BODY="Changes merged into $FORK@$BRANCH${LOOM_RELEASE_SHA:+ (up to $LOOM_RELEASE_SHA)}."
if [ -n "${LOOM_RELEASE_DIR:-}" ] && [ -f "$LOOM_RELEASE_DIR/merged.json" ] && command -v jq >/dev/null; then
  LIST=$(jq -r '.[] | "- \(.title) (#\(.number))"' "$LOOM_RELEASE_DIR/merged.json" || true)
  [ -n "$LIST" ] && BODY="$BODY

$LIST"
fi

if [ "$AHEAD" = "0" ]; then
  MSG="$FORK@$BRANCH has nothing upstream lacks; nothing to release."
elif [ -n "$EXISTING" ]; then
  MSG="Upstream PR already open and tracking $BRANCH ($AHEAD commits): $EXISTING"
else
  MSG="Would open a PR to $UPSTREAM from $OWNER:$BRANCH with $AHEAD commits."
fi

if [ "$MODE" = "plan" ] || [ "$MODE" = "check" ]; then
  echo "$MSG"
  [ -n "${LOOM_RELEASE_DIR:-}" ] && printf '# Release plan\n\n%s\n\n%s\n' "$MSG" "$BODY" > "$LOOM_RELEASE_DIR/plan.md"
  exit 0
fi

if [ "$AHEAD" = "0" ] || [ -n "$EXISTING" ]; then
  echo "$MSG"
  exit 0
fi
gh pr create -R "$UPSTREAM" --base "$BRANCH" --head "$OWNER:$BRANCH" --title "$TITLE" --body "$BODY"
