#!/usr/bin/env bash
# Apply the repository settings documented in docs/repository-governance.md.
# Dry-run by default. Pass --apply after maintainer approval to change GitHub state.
set -euo pipefail

repo="${GITHUB_REPOSITORY:-huntsyea/hermes-evenhub-bridge}"
mode="${1:---dry-run}"

if [ "$mode" != "--dry-run" ] && [ "$mode" != "--apply" ]; then
  echo "usage: $0 [--dry-run|--apply]" >&2
  exit 2
fi

run() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  if [ "$mode" = "--apply" ]; then
    "$@"
  fi
}

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

cat > "$tmpdir/branch-protection.json" <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "lint-and-test (3.11)",
      "lint-and-test (3.12)",
      "lint-and-test (3.13)",
      "Analyze (python)",
      "Analyze (actions)"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1,
    "require_last_push_approval": true,
    "bypass_pull_request_allowances": {
      "users": ["huntsyea"],
      "teams": [],
      "apps": []
    }
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": false
}
JSON

tag_ruleset() {
  local name="$1"
  local pattern="$2"
  local file="$tmpdir/${name// /-}.json"
  local existing_id=""

  cat > "$file" <<JSON
{
  "name": "$name",
  "target": "tag",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["$pattern"],
      "exclude": []
    }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" }
  ]
}
JSON

  if [ "$mode" = "--apply" ]; then
    existing_id="$(gh api "repos/$repo/rulesets?targets=tag" \
      --jq ".[] | select(.name == \"$name\") | .id" | head -n 1)"
  fi

  if [ -n "$existing_id" ]; then
    run gh api "repos/$repo/rulesets/$existing_id" \
      --method PUT \
      --input "$file"
  else
    run gh api "repos/$repo/rulesets" \
      --method POST \
      --input "$file"
  fi
}

run gh api "repos/$repo" \
  --method PATCH \
  --field "delete_branch_on_merge=true" \
  --field "has_wiki=false" \
  --field "has_projects=false"

run gh api "repos/$repo/vulnerability-alerts" \
  --method PUT \
  --silent

run gh api "repos/$repo/automated-security-fixes" \
  --method PUT \
  --silent

run gh api "repos/$repo/branches/main/protection" \
  --method PUT \
  --input "$tmpdir/branch-protection.json"

tag_ruleset "Protect plugin release tags" "refs/tags/v*"
tag_ruleset "Protect sidecar release tags" "refs/tags/sidecar-v*"

if [ "$mode" = "--dry-run" ]; then
  echo "dry-run only; rerun with --apply after explicit maintainer approval"
fi
