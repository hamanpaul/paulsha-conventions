#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." && pwd)"
WORKSPACE="${GITHUB_WORKSPACE:-$REPO_ROOT}"

PROFILE_INPUT="${1:-}"
VERSION_INPUT="${2:-}"
REPO_INPUT="${3:-.}"
ONLY_INPUT="${4:-}"
PR_TITLE_INPUT="${5:-}"
PR_BODY_INPUT="${6:-}"
PR_LABELS_INPUT="${7:-}"
PR_BASE_REF_INPUT="${8:-}"
PR_HEAD_REF_INPUT="${9:-}"

cd "$WORKSPACE"

# Validate profile and version against .paul-project.yml (fail-close)
CONFIG_PATH="${WORKSPACE}/${REPO_INPUT}/.paul-project.yml"
if [[ -f "$CONFIG_PATH" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi

  VALIDATION_RESULT=$("$PYTHON_BIN" - "$CONFIG_PATH" "$PROFILE_INPUT" "$VERSION_INPUT" <<'PYEOF'
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

  if [[ "$VALIDATION_RESULT" != "OK" ]]; then
    echo "Profile/version validation failed. See error above." >&2
    exit 1
  fi
fi

if [[ -x "${WORKSPACE}/.venv/bin/python" ]]; then
  PYTHON_BIN="${WORKSPACE}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

ARGS=(-m policy_check --repo "$REPO_INPUT")

if [[ -n "$ONLY_INPUT" ]]; then
  ARGS+=(--only "$ONLY_INPUT")
fi
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
