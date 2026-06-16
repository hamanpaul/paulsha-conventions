# R-21 機密標記 config 化 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL：用 superpowers:subagent-driven-development（建議）或 superpowers:executing-plans 逐 task 實作。步驟用 checkbox（`- [ ]`）追蹤。

**Goal：** 把 R-21 的雇主標記從寫死 regex 改為 config-driven（引擎 baseline 資料檔 + per-repo extend-only 疊加），並把個人路徑/憑證拆成 always-on 結構偵測器；vendor/OS 名減敏。

**Architecture：** R-21 偵測拆兩層——結構偵測器（`/home/<user>/`、private key，留 code）＋ marker tokens（字面、來自 `policy_check/data/secret_scan_defaults.yml` baseline 與 repo `.paul-project.yml secret_scan` 疊加）。`effective_markers = (baseline.markers ∪ repo.markers) − public_names`。

**Tech Stack：** Python 3.11、pytest、`importlib.resources`、PyYAML、既有 `policy_check` 規則框架。

**本地指令：** `python3 -m pytest -q`、`python3 -m policy_check --repo .`。文件一律 zh-tw。

---

## Task 1：baseline 資料檔 + loader

**Files:**
- Create: `policy_check/data/__init__.py`（空）、`policy_check/data/secret_scan_defaults.yml`
- Create: `policy_check/rules/_secret_scan_config.py`（loader + merge helper）
- Test: `tests/test_secret_scan_config.py`

- [ ] **1.1 寫 baseline 資料檔** `policy_check/data/secret_scan_defaults.yml`：
```yaml
# R-21 機密標記 baseline；減敏＝改此檔（移出 markers / 加入 public_names）後發版。
markers:
  - bgw720
  - build20
public_names:
  - brcm
  - broadcom
  - airoha
  - mtk
  - mediatek
  - prplos
  - prplog
  - marvell
```

- [ ] **1.2 寫失敗測試** `tests/test_secret_scan_config.py`：
```python
from policy_check.rules._secret_scan_config import load_baseline, resolve_markers

def test_baseline_loads_from_package_data():
    base = load_baseline()
    assert "bgw720" in base["markers"]
    assert "broadcom" in base["public_names"]

def test_resolve_extends_and_subtracts_public_names():
    repo_cfg = {"secret_scan": {"markers": ["foo123"], "public_names": ["bgw720"]}}
    eff = resolve_markers(repo_cfg)
    # repo marker 疊加進來
    assert "foo123" in eff
    # baseline marker 被 repo public_names 壓制
    assert "bgw720" not in eff
    # baseline public_name 仍不在 effective markers
    assert "broadcom" not in eff

def test_resolve_with_no_repo_config_uses_baseline():
    eff = resolve_markers({})
    assert "bgw720" in eff and "build20" in eff
    assert "broadcom" not in eff
```

- [ ] **1.3 跑測試** → FAIL（module 不存在）：`python3 -m pytest tests/test_secret_scan_config.py -q`

- [ ] **1.4 實作 loader** `policy_check/rules/_secret_scan_config.py`：
```python
"""R-21 機密標記設定：載入 baseline 資料檔並與 repo config 疊加（extend-only）。"""
from __future__ import annotations

from importlib.resources import files
from typing import Any

import yaml


def load_baseline() -> dict[str, list[str]]:
    """從套件資料檔載入 baseline markers / public_names。"""
    raw = files("policy_check.data").joinpath("secret_scan_defaults.yml").read_text(
        encoding="utf-8"
    )
    data = yaml.safe_load(raw) or {}
    return {
        "markers": [str(t).lower() for t in (data.get("markers") or [])],
        "public_names": [str(t).lower() for t in (data.get("public_names") or [])],
    }


def _repo_list(config: dict[str, Any], key: str) -> list[str]:
    sec = (config or {}).get("secret_scan") or {}
    raw = sec.get(key) or []
    return [str(t).lower() for t in raw if str(t).strip()]


def resolve_markers(config: dict[str, Any]) -> set[str]:
    """effective markers = (baseline.markers ∪ repo.markers) − public_names。extend-only。"""
    base = load_baseline()
    markers = set(base["markers"]) | set(_repo_list(config, "markers"))
    public = set(base["public_names"]) | set(_repo_list(config, "public_names"))
    return markers - public
```

- [ ] **1.5 跑測試** → PASS：`python3 -m pytest tests/test_secret_scan_config.py -q`

- [ ] **1.6 Commit**：`git add policy_check/data policy_check/rules/_secret_scan_config.py tests/test_secret_scan_config.py && git commit -m "feat(r21): 機密標記 baseline 資料檔 + config 疊加 loader"`

---

## Task 2：R-21 偵測改 config-driven（結構層 always-on + marker 層）

**Files:**
- Modify: `policy_check/rules/r21_secret_scan.py`（拆 `_EMPLOYER_MARKERS`；check 改用 `resolve_markers`）
- Test: `tests/test_rule_r21_secret_scan.py`（新增結構 always-on 案例）

- [ ] **2.1 寫失敗測試**（加到 `tests/test_rule_r21_secret_scan.py`）：結構偵測器在 markers 為空時仍咬，且 vendor 名不再咬。用既有 `make_ctx`/fixture 風格，於 tmp repo 寫入：
```python
def test_structural_detectors_always_on(tmp_path):
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n"
        "secret_scan:\n  public_names: [bgw720, build20]\n", encoding="utf-8")
    (tmp_path / "f.txt").write_text("home path /home/paul_chen/secret\n", encoding="utf-8")
    _git_init(tmp_path)  # helper：git init + add（沿用本檔既有 pattern；若無則 subprocess git init/add）
    assert get_rule().check(make_ctx(tmp_path)).status == Status.FAIL

def test_public_vendor_name_not_flagged(tmp_path):
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n", encoding="utf-8")
    (tmp_path / "doc.md").write_text("supports broadcom brcm prplOS marvell\n", encoding="utf-8")
    _git_init(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS
```
（若本檔已有 git-init helper 就重用；否則加一個 `_git_init`。）

- [ ] **2.2 跑** → FAIL（broadcom 仍被舊 regex 咬）：`python3 -m pytest tests/test_rule_r21_secret_scan.py -q`

- [ ] **2.3 改 `r21_secret_scan.py`**：移除 `_EMPLOYER_MARKERS`，改：
```python
from policy_check.rules._secret_scan_config import resolve_markers

_STRUCTURAL = re.compile(r"/home/[a-z_][a-z0-9_-]*/")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")


def _build_marker_re(tokens: set[str]) -> "re.Pattern[str] | None":
    if not tokens:
        return None
    alt = "|".join(re.escape(t) for t in sorted(tokens))
    return re.compile(rf"\b({alt})\b", re.IGNORECASE)
```
check 內（取代 line 94、104-107）：
```python
        config = ctx.config or {}
        allow = (config.get("secret_scan") or {}).get("allow", [])
        marker_re = _build_marker_re(resolve_markers(config))
        hits: list[str] = []
        for path in _iter_text_files(ctx.repo_root):
            rel = path.relative_to(ctx.repo_root).as_posix()
            if _is_exempt(rel, allow):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for ln, line in enumerate(text.splitlines(), 1):
                if _STRUCTURAL.search(line) or _PRIVATE_KEY.search(line) or (
                    marker_re is not None and marker_re.search(line)
                ):
                    hits.append(f"{rel}:{ln}")
                    break
```
（`_SELF_EXEMPT` 內把 `_secret_scan_config.py`、`data/secret_scan_defaults.yml` 也加入豁免，避免規則掃到自身的 token 清單。）

- [ ] **2.4 跑** → 新測試 PASS：`python3 -m pytest tests/test_rule_r21_secret_scan.py -q`

- [ ] **2.5 Commit**：`git commit -am "feat(r21): 偵測改 config-driven markers + always-on 結構偵測器"`

---

## Task 3：R-08 schema 驗證 secret_scan.markers / public_names

**Files:**
- Modify: `policy_check/rules/r08_policy_config_schema.py`
- Test: `tests/test_rule_r08_policy_config_schema.py`

- [ ] **3.1 寫失敗測試**（加到 R-08 測試檔；沿用其建 ctx 風格）：
```python
def test_r08_accepts_secret_scan_marker_lists(tmp_path):
    cfg = ("policy_profile: flat\npolicy_version: \"1.0.4\"\ntier: shareable\n"
           "secret_scan:\n  markers: [\"FOO123\"]\n  public_names: [\"broadcom\"]\n")
    assert _run_r08(tmp_path, cfg).status == Status.PASS

def test_r08_rejects_non_str_list_markers(tmp_path):
    cfg = ("policy_profile: flat\npolicy_version: \"1.0.4\"\ntier: shareable\n"
           "secret_scan:\n  markers: \"not-a-list\"\n")
    assert _run_r08(tmp_path, cfg).status == Status.FAIL
```
（`_run_r08` 為該檔既有 helper；若無則依現有測試模式建立。）

- [ ] **3.2 跑** → FAIL：`python3 -m pytest tests/test_rule_r08_policy_config_schema.py -q`

- [ ] **3.3 在 R-08 `check()` 的 tier 驗證後、回 PASS 前插入**：
```python
        secret_scan = data.get("secret_scan")
        if secret_scan is not None:
            if not isinstance(secret_scan, dict):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="secret_scan must be a mapping")
            for key in ("allow", "markers", "public_names"):
                val = secret_scan.get(key)
                if val is None:
                    continue
                if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                    return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                      message=f"secret_scan.{key} must be a list of strings")
```

- [ ] **3.4 跑** → PASS：`python3 -m pytest tests/test_rule_r08_policy_config_schema.py -q`

- [ ] **3.5 Commit**：`git commit -am "feat(r08): 驗證 secret_scan.markers/public_names 為 list[str]"`

---

## Task 4：更新 R-21 fixtures + 行為測試（extend / 抑制）

**Files:**
- Modify: `tests/fixtures/secret-scan/shareable-leak/src/platform.py`、`tests/fixtures/secret-scan/shareable-allowlisted/docs/markers.md`、`tests/fixtures/secret-scan/work-leak/src/platform.py`
- Test: `tests/test_rule_r21_secret_scan.py`

- [ ] **4.1 清 fixtures**：把含 `brcm broadcom BGW720` 的行改為僅 `BGW720`（vendor 名移除），確保 leak fixture 仍因 `BGW720` FAIL、但不是因 vendor 名。逐檔讀後改。

- [ ] **4.2 加 per-repo extend 測試**：
```python
def test_repo_can_extend_markers(tmp_path):
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n"
        "secret_scan:\n  markers: [\"acme9000\"]\n", encoding="utf-8")
    (tmp_path / "x.md").write_text("internal acme9000 board\n", encoding="utf-8")
    _git_init(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.FAIL

def test_repo_public_names_suppresses(tmp_path):
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n"
        "secret_scan:\n  public_names: [\"bgw720\"]\n", encoding="utf-8")
    (tmp_path / "x.md").write_text("legacy BGW720 note\n", encoding="utf-8")
    _git_init(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS
```

- [ ] **4.3 跑既有+新 R-21 測試全綠**：`python3 -m pytest tests/test_rule_r21_secret_scan.py -q`

- [ ] **4.4 Commit**：`git commit -am "test(r21): 更新 fixtures 並補 extend/抑制/結構 always-on 測試"`

---

## Task 5：套件打包資料檔 + 安裝後可載入

**Files:**
- Modify: `pyproject.toml`

- [ ] **5.1 在 `pyproject.toml` 加 package-data**（確保 `.yml` 隨安裝），於 `[tool.setuptools]` 區：
```toml
[tool.setuptools.package-data]
"policy_check.data" = ["*.yml"]
```
並確認 `[tool.setuptools.packages.find]` 的 `include = ["policy_check*"]` 已涵蓋 `policy_check.data`（有 `__init__.py` 即可）。

- [ ] **5.2 驗證 importlib.resources 載入**（從非 repo 根目錄跑，模擬安裝後）：
```bash
cd /tmp && python3 -c "import sys; sys.path.insert(0, '$OLDPWD'); from policy_check.rules._secret_scan_config import load_baseline; print(load_baseline()['markers'])"
```
Expected：印出 `['bgw720', 'build20']`。

- [ ] **5.3 Commit**：`git commit -am "build: 打包 policy_check/data/*.yml（R-21 baseline）"`

---

## Task 6：釋出 1.0.4（版本 + 文件 + 自掃）

**Files:**
- Modify: `VERSION`、`CHANGELOG.md`、`.paul-project.yml`、`CLAUDE.md`/`AGENTS.md`/`GEMINI.md`/`.github/copilot-instructions.md`、`.github/workflows/*`（依本 repo 既有 1.0.3→自身版本標記慣例）

- [ ] **6.1 `VERSION`** 1.0.3 → `1.0.4`。

- [ ] **6.2 `CHANGELOG.md [Unreleased]`** 加條目：R-21 機密標記 config 化（baseline 資料檔 + per-repo extend-only；結構偵測器 always-on；vendor/OS 名減敏）；R-08 驗證 secret_scan 標記欄位。

- [ ] **6.3 同步本 repo policy_version 標記** 1.0.3 → 1.0.4：`.paul-project.yml` + 四份 agent 檔的 `managed-by@vX`/`policy_version` 裸行（R-14）。本 repo 為 engine 本體，無下游 engine pin 需改。

- [ ] **6.4 自掃**：`python3 -m policy_check --repo .` → 0 fail（含 R-21 對 conventions 自身 tier=shareable：確認自身 `r21_secret_scan.py`/data/fixtures 已被 `_SELF_EXEMPT` 豁免、不誤報）。

- [ ] **6.5 全測試**：`python3 -m pytest -q` → 全綠。

- [ ] **6.6 Commit**：`git commit -am "chore(release): policy 1.0.4（R-21 config 化 + R-08 schema）"`

---

## Self-Review

- **Spec 覆蓋**：design 兩層架構→T2；baseline 資料檔→T1；extend-only/public_names 抑制→T1/T4；R-08 schema→T3；打包→T5；行為不變（path/key/bgw720/build20 保留、vendor 減敏）→T2/T4；釋出 1.0.4→T6。spec 各 Requirement/Scenario 皆有對應 task。✓
- **型別一致**：`load_baseline()→dict[str,list[str]]`、`resolve_markers(config)→set[str]`、`_build_marker_re(set)→Pattern|None` 跨 task 一致。
- **風險**：T2 改 check 主體須保留 `_iter_text_files`/`_is_exempt`/`allow`/tier-gate 原行為；唯一行為差異＝vendor 名不再 flag（刻意）。T6 自掃須確認 `_SELF_EXEMPT` 已含新檔（`_secret_scan_config.py`、`data/secret_scan_defaults.yml`），否則 conventions 自身 shareable 會誤報 bgw720（fixtures/data 內）。
