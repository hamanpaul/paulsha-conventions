#!/usr/bin/env bash
# Clean merged wt/* worktrees/branches conservatively (dry-run by default).
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/worktree-cleanup.sh [--repo PATH] [--base-ref REF] [--apply] [--dry-run] [--help]

Description:
  Finds merged worktree branches under wt/* and removes them with their
  corresponding worktree paths. Default mode is dry-run.

Safety:
  - Never removes main or feature/* branches.
  - Only considers wt/* branches.

Options:
  --repo PATH     Repository root. Default: current directory.
  --base-ref REF  Merge target reference. Default: origin/main (fallback: main).
  --apply         Perform removals.
  --dry-run       Print planned removals only (default).
  --help          Show this help.
EOF
}

REPO_ROOT="."
BASE_REF="origin/main"
APPLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      [[ $# -ge 2 ]] || {
        echo "ERROR: --repo requires a value" >&2
        exit 1
      }
      REPO_ROOT="$2"
      shift 2
      ;;
    --base-ref)
      [[ $# -ge 2 ]] || {
        echo "ERROR: --base-ref requires a value" >&2
        exit 1
      }
      BASE_REF="$2"
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

REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"
cd "$REPO_ROOT"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "ERROR: not a git repository: $REPO_ROOT" >&2
  exit 1
}

if ! git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
  if git rev-parse --verify main >/dev/null 2>&1; then
    BASE_REF="main"
  else
    echo "ERROR: unable to resolve base ref (tried origin/main and main)" >&2
    exit 1
  fi
fi

echo "Repository: $REPO_ROOT"
echo "Base ref:   $BASE_REF"
echo "Mode:       $([[ $APPLY -eq 1 ]] && echo apply || echo dry-run)"

CURRENT_WT="$(pwd)"
REMOVED=0
CANDIDATES=0

while IFS=$'\t' read -r wt branch_ref; do
  [[ -n "${wt:-}" && -n "${branch_ref:-}" ]] || continue
  [[ "$branch_ref" == refs/heads/wt/* ]] || continue
  CANDIDATES=$((CANDIDATES + 1))

  branch="${branch_ref#refs/heads/}"
  if [[ "$branch" == "main" || "$branch" == feature/* ]]; then
    echo "[skip] protected branch: $branch"
    continue
  fi

  if ! git merge-base --is-ancestor "$branch_ref" "$BASE_REF" 2>/dev/null; then
    echo "[keep] not merged into $BASE_REF: $branch"
    continue
  fi

  if [[ "$wt" == "$CURRENT_WT" ]]; then
    echo "[skip] current worktree: $wt ($branch)"
    continue
  fi

  if [[ $APPLY -eq 1 ]]; then
    echo "[apply] removing worktree: $wt ($branch)"
    git worktree remove --force "$wt"
    git branch -D "$branch"
    REMOVED=$((REMOVED + 1))
  else
    echo "[dry-run] would remove: $wt ($branch)"
  fi
done < <(git worktree list --porcelain | awk '/^worktree /{wt=$2} /^branch /{print wt "\t" $2}')

echo "Candidates: $CANDIDATES"
if [[ $APPLY -eq 1 ]]; then
  echo "Removed:    $REMOVED"
else
  echo "No changes made. Re-run with --apply to execute."
fi
