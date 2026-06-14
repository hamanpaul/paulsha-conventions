# R-21 機密掃描 + tier 欄位 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL：用 superpowers:subagent-driven-development（建議）或 superpowers:executing-plans 逐 task 實作。步驟用 checkbox（`- [ ]`）追蹤。

**Goal：** 在 `paulsha-conventions` 加入 R-21 機密掃描規則與 `.paul-project.yml` 的 `tier` 欄位，讓「宣告 tier=shareable 的 repo 不得含雇主機敏標記」成為可被 CI 強制的政策。

**Architecture：** 沿用既有 rule 框架（`@register` 類別 + `Rule` protocol + `RuleContext`/`RuleResult`/`Status`）。R-21 從 `ctx.config["tier"]` 讀分類；只對 `tier=shareable` 強制（命中 FAIL），其餘 tier 視為 not-applicable PASS。R-08 schema 規則新增 `tier` 合法值驗證。

**Tech Stack：** Python 3、pytest、PyYAML、既有 `policy_check` 引擎。

**範圍：** 本計畫只涵蓋 conventions 的程式變更（openspec tasks 1–3）。帳號 ops（轉 private / scrub / archive / 路 B，openspec tasks 4–6）是不可逆操作，走獨立 runbook、逐項人工確認，不在本計畫。

**前置：** 工作 clone `~/prj_pri/paulsha-conventions`，分支 `wt/account-visibility-secret-scan/openspec-propose`（已含 openspec-propose commit）。所有 commit 留在本分支、暫不 push。

---

## File Structure

- Create: `policy_check/rules/r21_secret_scan.py` — R-21 規則本體（掃描 + tier 感知 + 自我豁免）
- Modify: `policy_check/rules/r08_policy_config_schema.py` — 新增 optional `tier` 合法值驗證
- Create: `tests/test_rule_r21_secret_scan.py` — R-21 單元測試
- Create: `tests/fixtures/secret-scan/shareable-clean/**` — 乾淨 shareable repo fixture
- Create: `tests/fixtures/secret-scan/shareable-leak/**` — 含 `BGW720` 的 shareable repo
- Create: `tests/fixtures/secret-scan/work-leak/**` — 含 `BGW720` 的 work repo（不應 fail）
- Create: `tests/fixtures/policy-config/tier-invalid/**` — `tier` 非法值（R-08 應 fail）
- Modify: `.paul-project.yml` — dogfood：加 `tier: shareable` + `secret_scan.allow`
- Modify: `VERSION` / `CHANGELOG.md` / `.github/workflows/*` / 四份 agent 慣例檔 — 升版 1.0.2→1.0.3

---

## Task 1：R-08 schema 接受 optional `tier`

**Files:**
- Modify: `policy_check/rules/r08_policy_config_schema.py`
- Create: `tests/fixtures/policy-config/tier-valid/.paul-project.yml`
- Create: `tests/fixtures/policy-config/tier-invalid/.paul-project.yml`
- Modify: `tests/test_rule_r08_policy_config_schema.py`

- [ ] **Step 1：建立 fixtures**

`tests/fixtures/policy-config/tier-valid/.paul-project.yml`：
```yaml
policy_profile: flat
policy_version: 1.0.3
tier: shareable
```
`tests/fixtures/policy-config/tier-invalid/.paul-project.yml`：
```yaml
policy_profile: flat
policy_version: 1.0.3
tier: public
```

- [ ] **Step 2：寫失敗測試**（append 到 `tests/test_rule_r08_policy_config_schema.py`）

```python
def test_r08_accepts_valid_tier(fixture_repo):
    repo = fixture_repo("policy-config/tier-valid")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.PASS


def test_r08_rejects_invalid_tier(fixture_repo):
    repo = fixture_repo("policy-config/tier-invalid")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.FAIL
    assert "tier" in result.message
```
> 若該測試檔沒有 `get_rule`/`make_ctx` helper，比照 `tests/test_rule_r19_ci_tests.py` 的寫法補上（`get_rule()` 回傳 `loaded["R-08"]`）。

- [ ] **Step 3：跑測試確認失敗**

Run：`python3 -m pytest tests/test_rule_r08_policy_config_schema.py -q`
Expected：`test_r08_rejects_invalid_tier` FAIL（目前 R-08 不檢查 tier，非法值卻 PASS）。

- [ ] **Step 4：實作**（在 `r08_policy_config_schema.py` 的 profile 檢查後、回傳 PASS 前插入）

```python
        valid_tiers = {"shareable", "work", "personal"}
        tier = data.get("tier")
        if tier is not None and tier not in valid_tiers:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=(
                    "tier must be one of "
                    f"{sorted(valid_tiers)}, got {tier!r}"
                ),
            )
```

- [ ] **Step 5：跑測試確認通過**

Run：`python3 -m pytest tests/test_rule_r08_policy_config_schema.py -q`
Expected：PASS。

- [ ] **Step 6：commit**

```bash
git add policy_check/rules/r08_policy_config_schema.py tests/test_rule_r08_policy_config_schema.py tests/fixtures/policy-config
git commit -m "feat(policy): R-08 接受 optional tier 欄位"
```

---

## Task 2：R-21 核心掃描（shareable 乾淨 PASS / 命中 FAIL）

**Files:**
- Create: `policy_check/rules/r21_secret_scan.py`
- Create: `tests/test_rule_r21_secret_scan.py`
- Create: `tests/fixtures/secret-scan/shareable-clean/**`、`tests/fixtures/secret-scan/shareable-leak/**`

- [ ] **Step 1：建立 fixtures**

`tests/fixtures/secret-scan/shareable-clean/.paul-project.yml`：
```yaml
policy_profile: flat
policy_version: 1.0.3
tier: shareable
```
`tests/fixtures/secret-scan/shareable-clean/README.md`：
```markdown
# clean tool

A generic tool with no employer content.
```
`tests/fixtures/secret-scan/shareable-leak/.paul-project.yml`：
```yaml
policy_profile: flat
policy_version: 1.0.3
tier: shareable
```
`tests/fixtures/secret-scan/shareable-leak/src/platform.py`：
```python
# platform descriptor for BGW720
DEVICE = "BGW720"
```

- [ ] **Step 2：寫失敗測試** `tests/test_rule_r21_secret_scan.py`

```python
from __future__ import annotations

from pathlib import Path

from policy_check import config as cfg
from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(repo_root: Path, labels: list[str] | None = None) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.3",
        config=cfg.load(repo_root),
        pr_labels=labels or [],
    )


def get_rule():
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert "R-21" in loaded, "R-21 is not registered"
    return loaded["R-21"]


def test_r21_pass_when_shareable_clean(fixture_repo):
    repo = fixture_repo("secret-scan/shareable-clean")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.PASS


def test_r21_fail_when_shareable_has_marker(fixture_repo):
    repo = fixture_repo("secret-scan/shareable-leak")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.FAIL
    assert "BGW720" in result.detail or "platform.py" in result.detail
```

- [ ] **Step 3：跑測試確認失敗**

Run：`python3 -m pytest tests/test_rule_r21_secret_scan.py -q`
Expected：FAIL with `AssertionError: R-21 is not registered`（規則尚不存在）。

- [ ] **Step 4：實作 R-21（最小版，先不含豁免/非 shareable 分支）** `policy_check/rules/r21_secret_scan.py`

```python
from __future__ import annotations

import re
from pathlib import Path

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

_EMPLOYER_MARKERS = re.compile(
    r"\b(brcm|broadcom|airoha|prplos|prplog|bgw720|build20)\b"
    r"|/home/[a-z_][a-z0-9_-]*/",
    re.IGNORECASE,
)
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
_BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip",
               ".gz", ".bin", ".ico", ".woff", ".woff2"}


def _iter_text_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if any(part in _SKIP_DIRS for part in rel_parts):
            continue
        if p.suffix.lower() in _BINARY_EXT:
            continue
        yield p


@register
class R21SecretScan:
    rule_id = "R-21"
    exempt_label = "policy-exempt:secret-scan"

    def check(self, ctx: RuleContext) -> RuleResult:
        hits: list[str] = []
        for path in _iter_text_files(ctx.repo_root):
            rel = path.relative_to(ctx.repo_root).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for ln, line in enumerate(text.splitlines(), 1):
                if _EMPLOYER_MARKERS.search(line) or _PRIVATE_KEY.search(line):
                    hits.append(f"{rel}:{ln}")
                    break
        if hits:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"shareable repo contains confidential markers in {len(hits)} file(s).",
                detail="\n".join(hits[:20]),
            )
        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message="No confidential markers detected.",
        )
```

- [ ] **Step 5：跑測試確認通過**

Run：`python3 -m pytest tests/test_rule_r21_secret_scan.py -q`
Expected：兩個測試 PASS。

- [ ] **Step 6：commit**

```bash
git add policy_check/rules/r21_secret_scan.py tests/test_rule_r21_secret_scan.py tests/fixtures/secret-scan
git commit -m "feat(policy): R-21 機密掃描核心（命中雇主標記 FAIL）"
```

---

## Task 3：tier 感知（work/personal → not-applicable PASS）+ 豁免 label

**Files:**
- Modify: `policy_check/rules/r21_secret_scan.py`
- Modify: `tests/test_rule_r21_secret_scan.py`
- Create: `tests/fixtures/secret-scan/work-leak/**`

- [ ] **Step 1：建立 fixture** `tests/fixtures/secret-scan/work-leak/.paul-project.yml`：
```yaml
policy_profile: flat
policy_version: 1.0.3
tier: work
```
`tests/fixtures/secret-scan/work-leak/src/platform.py`：
```python
DEVICE = "BGW720"
```

- [ ] **Step 2：寫失敗測試**（append）

```python
def test_r21_pass_when_work_tier_has_marker(fixture_repo):
    repo = fixture_repo("secret-scan/work-leak")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.PASS
    assert "work" in result.message


def test_r21_skip_with_exemption_label(fixture_repo):
    repo = fixture_repo("secret-scan/shareable-leak")
    result = get_rule().check(
        make_ctx(repo, labels=["policy-exempt:secret-scan"])
    )
    assert result.status == Status.SKIP
    assert result.exempt_label == "policy-exempt:secret-scan"
```

- [ ] **Step 3：跑測試確認失敗**

Run：`python3 -m pytest tests/test_rule_r21_secret_scan.py -q`
Expected：兩個新測試 FAIL（work-leak 目前回 FAIL；label 目前未處理）。

- [ ] **Step 4：實作**（把 `check` 開頭改成下列，掃描迴圈不動）

```python
    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"Skipped by exemption label: {self.exempt_label}.",
                exempt_label=self.exempt_label,
            )

        tier = (ctx.config or {}).get("tier")
        if tier != "shareable":
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message=(
                    f"tier={tier!r}; R-21 enforces only tier=shareable. "
                    "Not applicable."
                ),
            )

        hits: list[str] = []
        # ...（以下掃描迴圈與 Task 2 相同）
```

- [ ] **Step 5：跑測試確認通過**

Run：`python3 -m pytest tests/test_rule_r21_secret_scan.py -q`
Expected：全 PASS。

- [ ] **Step 6：commit**

```bash
git add policy_check/rules/r21_secret_scan.py tests/test_rule_r21_secret_scan.py tests/fixtures/secret-scan/work-leak
git commit -m "feat(policy): R-21 tier 感知（非 shareable 視為 not-applicable）+ 豁免 label"
```

---

## Task 4：自我參照豁免（self-exempt + config allowlist）

**Files:**
- Modify: `policy_check/rules/r21_secret_scan.py`
- Modify: `tests/test_rule_r21_secret_scan.py`
- Create: `tests/fixtures/secret-scan/shareable-allowlisted/**`

- [ ] **Step 1：建立 fixture**（標記只出現在被 allowlist 的路徑）

`tests/fixtures/secret-scan/shareable-allowlisted/.paul-project.yml`：
```yaml
policy_profile: flat
policy_version: 1.0.3
tier: shareable
secret_scan:
  allow:
    - "docs/**"
```
`tests/fixtures/secret-scan/shareable-allowlisted/docs/markers.md`：
```markdown
This documentation legitimately mentions BGW720 and brcm as examples.
```

- [ ] **Step 2：寫失敗測試**（append）

```python
def test_r21_respects_config_allowlist(fixture_repo):
    repo = fixture_repo("secret-scan/shareable-allowlisted")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.PASS


def test_r21_exempts_own_rule_file(tmp_path):
    # 模擬 repo 內含本規則檔（其 denylist 字串不應觸發）
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n",
        encoding="utf-8",
    )
    rules_dir = tmp_path / "policy_check" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "r21_secret_scan.py").write_text(
        'MARKERS = "brcm broadcom BGW720"\n', encoding="utf-8"
    )
    from policy_check import config as cfg
    ctx = RuleContext(
        repo_root=tmp_path, profile="flat", policy_version="1.0.3",
        config=cfg.load(tmp_path),
    )
    assert get_rule().check(ctx).status == Status.PASS
```

- [ ] **Step 3：跑測試確認失敗**

Run：`python3 -m pytest tests/test_rule_r21_secret_scan.py -q`
Expected：兩個新測試 FAIL（目前無豁免邏輯）。

- [ ] **Step 4：實作**（檔案頂部加常數 + helper；掃描迴圈內加豁免判斷）

頂部加：
```python
from fnmatch import fnmatch

_SELF_EXEMPT = (
    "policy_check/rules/r21_secret_scan.py",
    "tests/test_rule_r21_secret_scan.py",
    "tests/fixtures/secret-scan/**",
)


def _is_exempt(rel: str, allow: list[str]) -> bool:
    for pat in (*_SELF_EXEMPT, *allow):
        if fnmatch(rel, pat):
            return True
        base = pat[:-2] if pat.endswith("/**") else pat
        if rel == base or rel.startswith(base.rstrip("/") + "/"):
            return True
    return False
```
`check` 內取得 allow 並在迴圈中跳過：
```python
        allow = ((ctx.config or {}).get("secret_scan") or {}).get("allow", [])
        hits: list[str] = []
        for path in _iter_text_files(ctx.repo_root):
            rel = path.relative_to(ctx.repo_root).as_posix()
            if _is_exempt(rel, allow):
                continue
            # ...（read_text + 掃描，與前同）
```

- [ ] **Step 5：跑測試確認通過**

Run：`python3 -m pytest tests/test_rule_r21_secret_scan.py -q`
Expected：全 PASS。

- [ ] **Step 6：commit**

```bash
git add policy_check/rules/r21_secret_scan.py tests/test_rule_r21_secret_scan.py tests/fixtures/secret-scan/shareable-allowlisted
git commit -m "feat(policy): R-21 自我參照豁免 + config allowlist"
```

---

## Task 5：dogfood conventions 自身 config + 全測試綠

**Files:**
- Modify: `.paul-project.yml`

- [ ] **Step 1：設定 conventions 自身 tier 與 allowlist**（避免 R-21 掃到自身規則/測試/openspec/docs 的 denylist 字串）

在 `.paul-project.yml` 末尾加：
```yaml
tier: shareable
secret_scan:
  allow:
    - "policy_check/rules/r21_secret_scan.py"
    - "tests/test_rule_r21_secret_scan.py"
    - "tests/fixtures/secret-scan/**"
    - "openspec/**"
    - "docs/**"
```

- [ ] **Step 2：對 conventions 自身跑 R-21 + 全測試**

Run：`python3 -m pytest -q`
Expected：全 PASS（含新 R-21 測試）。

- [ ] **Step 3：對自身跑 policy_check（R-21 應 PASS）**

Run：`python3 -m policy_check --repo . 2>&1 | grep -E "R-21|R-08|FAIL|FAILURE" || true`
Expected：R-21 PASS、無 FAILURE。

- [ ] **Step 4：commit**

```bash
git add .paul-project.yml
git commit -m "chore(policy): dogfood R-21（conventions 自身 tier=shareable + allowlist）"
```

---

## Task 6：升版 1.0.2 → 1.0.3 + 傳播

**Files:**
- Modify: `VERSION`、`CHANGELOG.md`、`.github/workflows/*.yml`（policy_version）、四份 agent 慣例檔（CLAUDE.md / AGENTS.md / GEMINI.md / copilot-instructions）

- [ ] **Step 1：更新 VERSION**

`VERSION` 內容改為：
```
1.0.3
```

- [ ] **Step 2：更新 CHANGELOG `[Unreleased]`**

在 `CHANGELOG.md` 的 `[Unreleased]` 段加：
```markdown
### Added
- R-21：機密掃描規則（tier=shareable 命中雇主標記/憑證模式則 FAIL；自我參照與 allowlist 豁免）。
- `.paul-project.yml` 新增 optional `tier`（shareable | work | personal）與 `secret_scan.allow`。
```

- [ ] **Step 3：同步 policy_version 字串（R-20）**

把 `.github/workflows/` 各 caller 的 `policy_version: "1.0.2"` 改為 `policy_version: "1.0.3"`；四份 agent 慣例檔開頭的 `policy_version: 1.0.2` 改為 `1.0.3`（R-13/R-14 要求四份一致）。

Run：`grep -rl "1.0.2" .github/ CLAUDE.md AGENTS.md GEMINI.md .github/copilot-instructions.md 2>/dev/null`
逐一改為 `1.0.3`。

- [ ] **Step 4：跑完整 policy_check + 全測試**

Run：`python3 -m pytest -q && python3 -m policy_check --repo .`
Expected：pytest 全 PASS；policy_check 無 FAILURE（R-19/R-20/R-21 皆綠）。

- [ ] **Step 5：commit**

```bash
git add VERSION CHANGELOG.md .github CLAUDE.md AGENTS.md GEMINI.md .github/copilot-instructions.md
git commit -m "chore(release): policy 1.0.3（R-21 + tier）"
```

---

## Self-Review

- **Spec coverage：** openspec `secret-scan` 三條 requirement → Task 1（tier schema）、Task 2–3（shareable FAIL / work PASS）、Task 4（自我豁免）全覆蓋。tasks.md 1.x→Task 2–4、2.x→Task 1+5、3.x→Task 6。✓
- **帳號 ops（tasks 4–6）** 不在本計畫，屬 runbook，已於範圍註明。
- **型別一致：** `RuleContext.config`/`Status`/`RuleResult` 全沿用 `base.py` 既有定義；`_is_exempt`/`_iter_text_files` 在 Task 2/4 定義後於同檔使用，無前向參照。
- **Placeholder 掃描：** 各 code step 均含完整程式碼，無 TBD/TODO。
