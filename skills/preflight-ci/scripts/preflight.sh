#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: run preflight-ci from a target git repository" >&2
  exit 2
}

ENGINE_ROOT="$(git -C "$SKILL_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$ENGINE_ROOT" || ! -f "$ENGINE_ROOT/policy_check/preflight.py" ]]; then
  if [[ -n "${PSC_CONVENTIONS_ROOT:-}" ]]; then
    RUNTIME_ROOT="$PSC_CONVENTIONS_ROOT"
  elif [[ -n "${XDG_DATA_HOME:-}" ]]; then
    RUNTIME_ROOT="$XDG_DATA_HOME/paulsha-conventions"
  else
    RUNTIME_ROOT="$HOME/.local/share/paulsha-conventions"
  fi
  LAUNCHER="$RUNTIME_ROOT/bin/policy-preflight"
  [[ -x "$LAUNCHER" ]] || {
    echo "ERROR: deployed policy-preflight launcher not found: $LAUNCHER" >&2
    exit 2
  }
  exec "$LAUNCHER" --repo "$TARGET_ROOT" "$@"
fi

PYTHON_BIN="${PSC_PREFLIGHT_PYTHON:-python3}"
case "$PYTHON_BIN" in
  /*)
    ;;
  */*)
    PYTHON_BIN="$TARGET_ROOT/$PYTHON_BIN"
    ;;
  *)
    PYTHON_BIN="$(command -v "$PYTHON_BIN" 2>/dev/null)" || {
      echo "ERROR: Python interpreter not found: ${PSC_PREFLIGHT_PYTHON:-python3}" >&2
      exit 2
    }
    ;;
esac

[[ -x "$PYTHON_BIN" ]] || {
  echo "ERROR: Python interpreter is not executable: $PYTHON_BIN" >&2
  exit 2
}

exec env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$ENGINE_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  "$PYTHON_BIN" -P -m policy_check.preflight \
  "$@" \
  --repo "$TARGET_ROOT" \
  --engine-source "$ENGINE_ROOT"
