#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." && pwd)"
WORKSPACE="${GITHUB_WORKSPACE:-$REPO_ROOT}"

PROFILE_INPUT="${1:-}"
VERSION_INPUT="${2:-}"

# Repo path: always current workspace (action runs in checked-out repo)
REPO_INPUT="."

# PR context from GitHub environment variables
PR_TITLE_INPUT="${GITHUB_PR_TITLE:-}"
PR_BODY_INPUT="${GITHUB_PR_BODY:-}"
PR_LABELS_INPUT="${GITHUB_PR_LABELS:-}"
PR_BASE_REF_INPUT="${GITHUB_BASE_REF:-}"
PR_HEAD_REF_INPUT="${GITHUB_HEAD_REF:-}"

cd "$WORKSPACE"

# Validate profile and version against .paul-project.yml (fail-close)
# REPO_INPUT can be absolute or relative path; normalize it
if [[ "$REPO_INPUT" = /* ]]; then
  CONFIG_PATH="${REPO_INPUT}/.paul-project.yml"
else
  CONFIG_PATH="${WORKSPACE}/${REPO_INPUT}/.paul-project.yml"
fi

if [[ -f "$CONFIG_PATH" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi

  # Run validation script, preserving stderr
  VALIDATION_SCRIPT=$(cat <<'PYEOF'
import sys
import yaml
config_path = sys.argv[1]
expected_profile = sys.argv[2]
expected_version = sys.argv[3]

try:
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    actual_profile = config.get("policy_profile", "")
    actual_version = config.get("policy_version", "")
    
    if expected_profile and actual_profile != expected_profile:
        print(f"ERROR: profile mismatch: action expects '{expected_profile}' but .paul-project.yml has '{actual_profile}'", file=sys.stderr)
        sys.exit(1)
    if expected_version and actual_version != expected_version:
        print(f"ERROR: version mismatch: action expects '{expected_version}' but .paul-project.yml has '{actual_version}'", file=sys.stderr)
        sys.exit(1)
    print("OK")
except Exception as exc:
    print(f"ERROR: failed to validate config: {exc}", file=sys.stderr)
    sys.exit(1)
PYEOF
)

  if ! "$PYTHON_BIN" -c "$VALIDATION_SCRIPT" "$CONFIG_PATH" "$PROFILE_INPUT" "$VERSION_INPUT"; then
    echo "Profile/version validation failed. See error above." >&2
    exit 1
  fi
fi

# Policy check execution
if [[ -x "${WORKSPACE}/.venv/bin/python" ]]; then
  PYTHON_BIN="${WORKSPACE}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

ARGS=(-m policy_check --repo "$REPO_INPUT")

if [[ -n "$PR_TITLE_INPUT" ]]; then
  ARGS+=(--pr-title "$PR_TITLE_INPUT")
fi
if [[ -n "$PR_BODY_INPUT" ]]; then
  ARGS+=(--pr-body "$PR_BODY_INPUT")
fi
if [[ -n "$PR_LABELS_INPUT" ]]; then
  ARGS+=(--pr-labels "$PR_LABELS_INPUT")
fi
if [[ -n "$PR_BASE_REF_INPUT" ]]; then
  ARGS+=(--pr-base-ref "$PR_BASE_REF_INPUT")
fi
if [[ -n "$PR_HEAD_REF_INPUT" ]]; then
  ARGS+=(--pr-head-ref "$PR_HEAD_REF_INPUT")
fi

exec "$PYTHON_BIN" "${ARGS[@]}"
