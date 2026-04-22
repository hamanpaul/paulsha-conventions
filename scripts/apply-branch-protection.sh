#!/usr/bin/env bash
# Apply (or preview) branch protection for a repository branch via gh CLI.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/apply-branch-protection.sh [--repo OWNER/NAME] [--branch BRANCH] [--apply] [--dry-run] [--help]

Description:
  Previews or applies baseline branch protection settings using GitHub CLI.
  Default mode is dry-run.

Options:
  --repo OWNER/NAME  Target repository. Default: current gh repo.
  --branch BRANCH    Target branch. Default: main.
  --apply            Execute gh api call.
  --dry-run          Print the command only (default).
  --help             Show this help.
EOF
}

REPO=""
BRANCH="main"
APPLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      [[ $# -ge 2 ]] || {
        echo "ERROR: --repo requires a value" >&2
        exit 1
      }
      REPO="$2"
      shift 2
      ;;
    --branch)
      [[ $# -ge 2 ]] || {
        echo "ERROR: --branch requires a value" >&2
        exit 1
      }
      BRANCH="$2"
      shift 2
      ;;
    --apply)
      APPLY=1
      shift
      ;;
    --dry-run)
      APPLY=0
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh CLI is required" >&2
  exit 1
fi

if [[ -z "$REPO" ]]; then
  set +e
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)"
  GH_REPO_RC=$?
  set -e
  [[ $GH_REPO_RC -eq 0 && -n "$REPO" ]] || {
    echo "ERROR: unable to resolve repo automatically; pass --repo OWNER/NAME" >&2
    exit 1
  }
fi

[[ "$REPO" == */* ]] || {
  echo "ERROR: invalid repo format: $REPO (expected OWNER/NAME)" >&2
  exit 1
}

GH_ARGS=(
  api -X PUT "repos/${REPO}/branches/${BRANCH}/protection"
  -H "Accept: application/vnd.github+json"
  -f required_status_checks[strict]=true
  -f required_status_checks[contexts][]=policy-check
  -F enforce_admins=false
  -f required_pull_request_reviews[required_approving_review_count]=0
  -F required_conversation_resolution=true
  -F allow_force_pushes=false
  -F allow_deletions=false
  -F required_linear_history=false
)

echo "Target: ${REPO}:${BRANCH}"
printf 'gh'
for arg in "${GH_ARGS[@]}"; do
  printf ' %q' "$arg"
done
printf '\n'

if [[ $APPLY -eq 0 ]]; then
  echo "Dry-run only. Use --apply to execute."
  exit 0
fi

gh "${GH_ARGS[@]}" >/dev/null
echo "Branch protection applied."
