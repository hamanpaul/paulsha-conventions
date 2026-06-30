# .github/actions/doc-drift/run.sh
#!/usr/bin/env bash
set -euo pipefail

ACTION_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# 引擎位置：action 自帶 policy_check（checkout 於 caller workspace 時需自取）
ENGINE_ROOT="${ACTION_DIR}/../../.."   # 自家 repo dogfood；外部用 uses: 取得本 action 所在 repo
export PYTHONPATH="${ENGINE_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

BASE_SHA="${DOC_DRIFT_BASE_SHA:-${GH_BASE_SHA:-}}"
HEAD_SHA="${GH_HEAD_SHA:-HEAD}"

if [[ -z "$BASE_SHA" ]]; then
  echo "ERROR: 無法決定 base SHA（非 PR 事件或未提供 base-sha）。" >&2
  exit 2
fi

MODE="${DOC_DRIFT_MODE:-doc-drift}"
ARGS=(--mode "$MODE" --repo "${GITHUB_WORKSPACE:-.}" --base "$BASE_SHA" --head "$HEAD_SHA")
if [[ "$MODE" == "moc" ]]; then
  ARGS+=(--map "${DOC_DRIFT_MAP:-docs/MOC.md}")
  if [[ -n "${DOC_DRIFT_GOVERNED_PREFIX:-}" ]]; then
    # 空白或逗號分隔 → 多個 --governed-prefix
    IFS=', ' read -r -a _prefs <<< "${DOC_DRIFT_GOVERNED_PREFIX}"
    for p in "${_prefs[@]}"; do
      [[ -n "$p" ]] && ARGS+=(--governed-prefix "$p")
    done
  fi
fi

PY=python3; command -v python3 >/dev/null || PY=python
exec "$PY" -m policy_check.doc_drift "${ARGS[@]}"
