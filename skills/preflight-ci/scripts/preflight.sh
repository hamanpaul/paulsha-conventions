#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE_ROOT="$(git -C "$SKILL_DIR" rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: preflight-ci is not inside a paulsha-conventions checkout" >&2
  exit 2
}
TARGET_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: run preflight-ci from a target git repository" >&2
  exit 2
}

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
