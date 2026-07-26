#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: scripts/install-preflight-skill.sh [--target-root PATH] [--replace] [--replace-managed-runtime]"
}

TARGET_ROOT="${HOME}/.agents/skills"
REPLACE=0
REPLACE_MANAGED_RUNTIME=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-root)
      [[ $# -ge 2 ]] || {
        echo "ERROR: --target-root requires a path" >&2
        exit 2
      }
      TARGET_ROOT="$2"
      shift 2
      ;;
    --replace)
      REPLACE=1
      shift
      ;;
    --replace-managed-runtime)
      REPLACE=1
      REPLACE_MANAGED_RUNTIME=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$REPO_ROOT/skills/preflight-ci"
TARGET="$TARGET_ROOT/preflight-ci"

[[ -f "$SOURCE/SKILL.md" ]] || {
  echo "ERROR: canonical skill is missing: $SOURCE" >&2
  exit 1
}

mkdir -p "$TARGET_ROOT"
if [[ -L "$TARGET" ]]; then
  if [[ "$(readlink -f "$TARGET")" == "$(readlink -f "$SOURCE")" ]]; then
    echo "preflight-ci already points to $SOURCE"
    exit 0
  fi
  LINK_TARGET="$(readlink "$TARGET")"
  RESOLVED_TARGET="$(readlink -f "$TARGET")"
  case "$LINK_TARGET:$RESOLVED_TARGET" in
    */current/artifact/skills/preflight-ci:*|*:*/releases/*/artifact/skills/preflight-ci)
      [[ $REPLACE_MANAGED_RUNTIME -eq 1 ]] || {
        echo "ERROR: $TARGET is managed by a runtime bundle; follow the runtime bundle runbook or pass --replace-managed-runtime for an explicit source-checkout migration" >&2
        exit 1
      }
      ;;
  esac
  [[ $REPLACE -eq 1 ]] || {
    echo "ERROR: $TARGET points elsewhere; pass --replace to migrate the symlink" >&2
    exit 1
  }
  unlink "$TARGET"
elif [[ -e "$TARGET" ]]; then
  echo "ERROR: refusing to replace non-symlink target: $TARGET" >&2
  exit 1
fi

ln -s "$SOURCE" "$TARGET"
echo "installed preflight-ci -> $SOURCE"
