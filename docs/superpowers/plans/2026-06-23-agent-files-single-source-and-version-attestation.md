# Agent 慣例檔單一真檔 + 版本 attestation gate 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把四份 agent 慣例檔收斂為「canonical `CLAUDE.md` + symlink」單一真檔，並補上「repo 實際 pin 的引擎版本 ⟷ `policy_version`」的 attestation gate。

**Architecture:** R-14 由 config gate（`agent_files.mode`，預設 `copy`）決定行為——`copy` 維持四檔版本相等比對、`symlink` 強制鏡像檔為 symlink→canonical；新增 R-23 掃 workflow `uses:` 對齊引擎版本與 `policy_version`；R-08 擴充驗兩個新設定區塊。規則一律讀 `ctx.config`（由 `cli.build_context` 灌入）。

**Tech Stack:** Python 3.12、pytest、規則 plugin（`policy_check/rules/rNN_*.py` 經 `@register` 自動載入）。

**Branch:** `feature/agent-files-single-source-attestation`（已開）。對應 openspec change `agent-files-single-source-attestation`。

---

## File Structure

- `policy_check/rules/r08_policy_config_schema.py` — 修改：加 `agent_files` / `conventions_engine` 驗證。
- `policy_check/config.py` — 修改：`load()` 對 `agent_files.mode` 預設 `copy`。
- `policy_check/rules/r14_agent_files_version.py` — 修改：config-gated copy/symlink 兩路徑。
- `policy_check/rules/r23_engine_pin_attestation.py` — 新建：R-23 規則。
- `tests/test_rule_r08_policy_config_schema.py` — 修改：新區塊測試。
- `tests/test_config.py` — 修改：mode 預設測試。
- `tests/test_rule_r13_r14_agent_files.py` — 修改：symlink 模式測試（程式化建 symlink，不用 fixture，因 `copytree` 會 deref）。
- `tests/test_rule_r23_engine_pin_attestation.py` — 新建。
- `tests/test_rules_presence.py` — 修改：R-23 註冊存在性。
- 慣例檔／設定／文件：`.paul-project.yml`、`AGENTS.md`/`GEMINI.md`/`.github/copilot-instructions.md`（轉 symlink）、`CLAUDE.md`、`README.md`、`CHANGELOG.md`。

---

## Task 1: R-08 驗證 agent_files 與 conventions_engine

**Files:**
- Modify: `policy_check/rules/r08_policy_config_schema.py`
- Test: `tests/test_rule_r08_policy_config_schema.py`

- [ ] **Step 1: 寫失敗測試**

加到 `tests/test_rule_r08_policy_config_schema.py`（沿用該檔既有的 fixture/ctx 風格；此處用 tmp_path 直接寫 `.paul-project.yml`）：

```python
def _write_config(tmp_path, body: str):
    (tmp_path / ".paul-project.yml").write_text(body, encoding="utf-8")
    return tmp_path


def _r08():
    from policy_check.rules import registry
    return {r.rule_id: r for r in registry.load_all()}["R-08"]


def _ctx(repo_root):
    from policy_check.rules.base import RuleContext
    return RuleContext(repo_root=repo_root, profile="flat", policy_version="1.0.0")


def test_r08_fail_on_invalid_agent_files_mode(tmp_path):
    from policy_check.rules.base import Status
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nagent_files:\n  mode: link\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "agent_files.mode" in result.message


def test_r08_pass_on_valid_agent_files_mode(tmp_path):
    from policy_check.rules.base import Status
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nagent_files:\n  mode: symlink\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_fail_on_non_string_engine_repo(tmp_path):
    from policy_check.rules.base import Status
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nconventions_engine:\n  repo: [a, b]\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "conventions_engine.repo" in result.message


def test_r08_pass_on_string_engine_repo(tmp_path):
    from policy_check.rules.base import Status
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nconventions_engine:\n  repo: hamanpaul/paulsha-conventions\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_rule_r08_policy_config_schema.py -q -k "agent_files or engine_repo"`
Expected: FAIL（新驗證尚未實作，invalid 案例會被誤判 PASS）。

- [ ] **Step 3: 實作驗證**

在 `policy_check/rules/r08_policy_config_schema.py` 的 `check()` 內、`doc_reference` 區塊之後、`return ... PASS` 之前插入：

```python
        # 驗證 agent_files 區塊：須為 mapping；mode（若存在）須 ∈ {symlink, copy}
        agent_files = data.get("agent_files")
        if agent_files is not None:
            if not isinstance(agent_files, dict):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="agent_files must be a mapping",
                )
            mode = agent_files.get("mode")
            if mode is not None and mode not in ("symlink", "copy"):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="agent_files.mode must be one of ['copy', 'symlink']",
                )

        # 驗證 conventions_engine 區塊：須為 mapping；repo（若存在）須為 str
        conventions_engine = data.get("conventions_engine")
        if conventions_engine is not None:
            if not isinstance(conventions_engine, dict):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="conventions_engine must be a mapping",
                )
            repo = conventions_engine.get("repo")
            if repo is not None and not isinstance(repo, str):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="conventions_engine.repo must be a string",
                )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_rule_r08_policy_config_schema.py -q`
Expected: PASS（全部）。

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r08_policy_config_schema.py tests/test_rule_r08_policy_config_schema.py
git commit -m "feat(r08): 驗證 agent_files.mode 與 conventions_engine.repo"
```

---

## Task 2: config.load 對 agent_files.mode 預設 copy

**Files:**
- Modify: `policy_check/config.py:42-44`
- Test: `tests/test_config.py`

- [ ] **Step 1: 寫失敗測試**

加到 `tests/test_config.py`：

```python
def test_load_defaults_agent_files_mode_to_copy(tmp_path):
    from policy_check import config as cfg
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.0\n", encoding="utf-8"
    )
    data = cfg.load(tmp_path)
    assert data["agent_files"]["mode"] == "copy"


def test_load_preserves_explicit_symlink_mode(tmp_path):
    from policy_check import config as cfg
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.0\nagent_files:\n  mode: symlink\n",
        encoding="utf-8",
    )
    data = cfg.load(tmp_path)
    assert data["agent_files"]["mode"] == "symlink"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_config.py -q -k agent_files`
Expected: FAIL with `KeyError: 'agent_files'`。

- [ ] **Step 3: 實作預設**

在 `policy_check/config.py` 的 `load()` 中，`data.setdefault("cli", [])` 之後、`return data` 之前插入：

```python
    agent_files = data.get("agent_files")
    if not isinstance(agent_files, dict):
        agent_files = {}
    agent_files.setdefault("mode", "copy")
    data["agent_files"] = agent_files
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_config.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add policy_check/config.py tests/test_config.py
git commit -m "feat(config): agent_files.mode 預設 copy"
```

---

## Task 3: R-14 config-gated（symlink 模式）

**Files:**
- Modify: `policy_check/rules/r14_agent_files_version.py`
- Test: `tests/test_rule_r13_r14_agent_files.py`

- [ ] **Step 1: 寫失敗測試**

加到 `tests/test_rule_r13_r14_agent_files.py`（程式化建 symlink；`make_ctx` 已支援 `labels`，這裡額外用 `config` 參數，故另寫 helper）：

```python
import os


def _symlink_ctx(repo_root, policy_version="1.0.0"):
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version=policy_version,
        config={"agent_files": {"mode": "symlink"}},
    )


def _build_symlink_repo(tmp_path, *, canonical_symlink=False, mirror_as_copy=False, wrong_target=False):
    repo = tmp_path / "repo"
    (repo / ".github").mkdir(parents=True)
    if canonical_symlink:
        (repo / "OTHER.md").write_text("policy_version: 1.0.0\n", encoding="utf-8")
        os.symlink("OTHER.md", repo / "CLAUDE.md")
    else:
        (repo / "CLAUDE.md").write_text("policy_version: 1.0.0\n", encoding="utf-8")
    # mirrors
    for name in ("AGENTS.md", "GEMINI.md"):
        if mirror_as_copy and name == "AGENTS.md":
            (repo / name).write_text("policy_version: 1.0.0\n", encoding="utf-8")
        elif wrong_target and name == "AGENTS.md":
            (repo / "DECOY.md").write_text("policy_version: 1.0.0\n", encoding="utf-8")
            os.symlink("DECOY.md", repo / name)
        else:
            os.symlink("CLAUDE.md", repo / name)
    os.symlink("../CLAUDE.md", repo / ".github" / "copilot-instructions.md")
    return repo


def test_r14_symlink_pass_on_valid_topology(tmp_path):
    repo = _build_symlink_repo(tmp_path)
    result = get_rule("R-14").check(_symlink_ctx(repo))
    assert result.status == Status.PASS


def test_r14_symlink_fail_when_mirror_is_copy(tmp_path):
    repo = _build_symlink_repo(tmp_path, mirror_as_copy=True)
    result = get_rule("R-14").check(_symlink_ctx(repo))
    assert result.status == Status.FAIL
    assert "expected symlink" in result.detail


def test_r14_symlink_fail_when_target_wrong(tmp_path):
    repo = _build_symlink_repo(tmp_path, wrong_target=True)
    result = get_rule("R-14").check(_symlink_ctx(repo))
    assert result.status == Status.FAIL
    assert "target mismatch" in result.detail


def test_r14_symlink_fail_when_canonical_is_symlink(tmp_path):
    repo = _build_symlink_repo(tmp_path, canonical_symlink=True)
    result = get_rule("R-14").check(_symlink_ctx(repo))
    assert result.status == Status.FAIL
    assert "canonical must be a regular file" in result.detail
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_rule_r13_r14_agent_files.py -q -k symlink`
Expected: FAIL（R-14 尚未認得 symlink 模式，copy 路徑會把 symlink 當一般檔讀版本而誤判 PASS）。

- [ ] **Step 3: 改寫 R-14**

將 `policy_check/rules/r14_agent_files_version.py` 全檔改為：

```python
from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.r13_agent_files_exist import AGENT_FILES
from policy_check.rules.registry import register

VER_RE = re.compile(r"^policy_version:\s*([0-9]+\.[0-9]+\.[0-9]+(?:-fix\.\d+)?)\s*$", re.MULTILINE)

CANONICAL = "CLAUDE.md"


@register
class R14AgentFilesVersion:
    rule_id = "R-14"
    exempt_label = None

    def check(self, ctx: RuleContext) -> RuleResult:
        agent_files_cfg = ctx.config.get("agent_files") or {}
        mode = agent_files_cfg.get("mode", "copy") if isinstance(agent_files_cfg, dict) else "copy"
        if mode == "symlink":
            return self._check_symlink(ctx)
        return self._check_copy(ctx)

    def _check_copy(self, ctx: RuleContext) -> RuleResult:
        declared = ctx.policy_version
        mismatches: list[str] = []
        for name in AGENT_FILES:
            path = ctx.repo_root / name
            if not path.is_file():
                continue  # R-13 handles missing required agent files.
            text = path.read_text(encoding="utf-8", errors="replace")
            match = VER_RE.search(text)
            if not match:
                mismatches.append(f"{name}: policy_version not declared")
                continue
            found = match.group(1)
            if found != declared:
                mismatches.append(f"{name}: policy_version {found} != declared {declared}")
        if mismatches:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="agent file version drift",
                detail="\n".join(mismatches),
            )
        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=f"agent files aligned to policy_version {declared}",
        )

    def _check_symlink(self, ctx: RuleContext) -> RuleResult:
        declared = ctx.policy_version
        problems: list[str] = []
        canonical_path = ctx.repo_root / CANONICAL

        if canonical_path.is_symlink():
            problems.append(f"{CANONICAL}: canonical must be a regular file, found symlink")
        elif canonical_path.is_file():
            text = canonical_path.read_text(encoding="utf-8", errors="replace")
            match = VER_RE.search(text)
            if not match:
                problems.append(f"{CANONICAL}: policy_version not declared")
            elif match.group(1) != declared:
                problems.append(f"{CANONICAL}: policy_version {match.group(1)} != declared {declared}")
        # 缺 canonical 交由 R-13

        canonical_resolved = canonical_path.resolve()
        for name in AGENT_FILES:
            if name == CANONICAL:
                continue
            path = ctx.repo_root / name
            if not path.exists():
                continue  # 缺檔／斷鏈交由 R-13
            if not path.is_symlink():
                problems.append(f"{name}: expected symlink → {CANONICAL}, found regular file")
                continue
            if path.resolve() != canonical_resolved:
                problems.append(f"{name}: symlink target mismatch (expected {CANONICAL})")

        if problems:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="agent file single-source integrity violation",
                detail="\n".join(problems),
            )
        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=f"agent files single-source (symlink → {CANONICAL}) aligned to {declared}",
        )
```

- [ ] **Step 4: 跑測試確認通過（含既有 copy 測試回歸）**

Run: `python3 -m pytest tests/test_rule_r13_r14_agent_files.py -q`
Expected: PASS（symlink 新測試 + 既有 copy 測試全綠）。

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r14_agent_files_version.py tests/test_rule_r13_r14_agent_files.py
git commit -m "feat(r14): config-gated 單一真檔完整性（symlink 模式）"
```

---

## Task 4: R-23 engine pin attestation（新 rule）

**Files:**
- Create: `policy_check/rules/r23_engine_pin_attestation.py`
- Test: `tests/test_rule_r23_engine_pin_attestation.py`

- [ ] **Step 1: 寫失敗測試**

建立 `tests/test_rule_r23_engine_pin_attestation.py`：

```python
from __future__ import annotations

from pathlib import Path

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status

REPO = "hamanpaul/paulsha-conventions"
ENGINE = f"{REPO}/.github/workflows/reusable-policy-check.yml"


def _rule():
    return {r.rule_id: r for r in registry.load_all()}["R-23"]


def _ctx(repo_root: Path, *, policy_version="1.0.5", configured=True, labels=None):
    config = {"conventions_engine": {"repo": REPO}} if configured else {}
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version=policy_version,
        config=config,
        pr_labels=labels or [],
    )


def _wf(tmp_path: Path, uses_line: str):
    d = tmp_path / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / "policy-check.yml").write_text(f"jobs:\n  check:\n    {uses_line}\n", encoding="utf-8")
    return tmp_path


def test_r23_pass_on_tag_match(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.5")
    assert _rule().check(_ctx(repo)).status == Status.PASS


def test_r23_fail_on_tag_mismatch(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.2")
    result = _rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "1.0.2" in result.detail and "1.0.5" in result.detail


def test_r23_pass_on_sha_with_matching_comment(tmp_path):
    sha = "a" * 40
    repo = _wf(tmp_path, f"uses: {ENGINE}@{sha}  # v1.0.5")
    assert _rule().check(_ctx(repo)).status == Status.PASS


def test_r23_fail_on_sha_with_mismatching_comment(tmp_path):
    sha = "a" * 40
    repo = _wf(tmp_path, f"uses: {ENGINE}@{sha}  # v1.0.2")
    assert _rule().check(_ctx(repo)).status == Status.FAIL


def test_r23_warn_on_bare_sha(tmp_path):
    sha = "b" * 40
    repo = _wf(tmp_path, f"uses: {ENGINE}@{sha}")
    assert _rule().check(_ctx(repo)).status == Status.WARN


def test_r23_na_on_local_uses(tmp_path):
    repo = _wf(tmp_path, "uses: ./.github/workflows/reusable-policy-check.yml")
    assert _rule().check(_ctx(repo)).status == Status.PASS


def test_r23_na_when_engine_not_configured(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.2")
    assert _rule().check(_ctx(repo, configured=False)).status == Status.PASS


def test_r23_skip_on_exempt_label(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.2")
    result = _rule().check(_ctx(repo, labels=["policy-exempt:engine-pin"]))
    assert result.status == Status.SKIP
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest tests/test_rule_r23_engine_pin_attestation.py -q`
Expected: FAIL with `AssertionError: R-23 is not registered`（rule 尚未建立）。

- [ ] **Step 3: 實作 R-23**

建立 `policy_check/rules/r23_engine_pin_attestation.py`：

```python
from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

_USES_RE = re.compile(
    r'^\s*(?:-\s*)?uses:\s*["\']?(?P<target>[^"\'@#\s]+)@(?P<ref>[^"\'#\s]+)["\']?'
    r'\s*(?:#\s*(?P<comment>.*?))?\s*$'
)
_TAG_VER_RE = re.compile(r'^v?(\d+\.\d+\.\d+(?:-fix\.\d+)?)$')
_COMMENT_VER_RE = re.compile(r'v?(\d+\.\d+\.\d+(?:-fix\.\d+)?)')
_SHA_RE = re.compile(r'^[0-9a-fA-F]{40}$')


@register
class R23EnginePinAttestation:
    rule_id = "R-23"
    exempt_label = "policy-exempt:engine-pin"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"R-23 exempted by label: {self.exempt_label}",
                exempt_label=self.exempt_label,
            )

        engine_cfg = ctx.config.get("conventions_engine") or {}
        repo = engine_cfg.get("repo") if isinstance(engine_cfg, dict) else None
        if not repo:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No conventions_engine.repo configured; R-23 not applicable.",
            )

        workflows_dir = ctx.repo_root / ".github" / "workflows"
        if not workflows_dir.is_dir():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No .github/workflows directory; R-23 not applicable.",
            )

        declared = ctx.policy_version
        fails: list[str] = []
        warns: list[str] = []
        matched = 0

        for workflow in sorted(workflows_dir.iterdir()):
            if workflow.suffix not in (".yml", ".yaml") or not workflow.is_file():
                continue
            for line_no, line in enumerate(
                workflow.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
            ):
                m = _USES_RE.match(line)
                if not m:
                    continue
                target = m.group("target")
                if target.startswith("./"):
                    continue
                if not (target == repo or target.startswith(repo + "/")):
                    continue
                matched += 1
                ref = m.group("ref")
                comment = m.group("comment") or ""
                loc = f"{workflow.name}:{line_no}"

                tag_match = _TAG_VER_RE.match(ref)
                if tag_match:
                    version = tag_match.group(1)
                elif _SHA_RE.match(ref):
                    cm = _COMMENT_VER_RE.search(comment)
                    if not cm:
                        warns.append(
                            f"{loc}: engine pinned by SHA without '# vX.Y.Z' annotation; "
                            f"version not verifiable offline"
                        )
                        continue
                    version = cm.group(1)
                else:
                    warns.append(
                        f"{loc}: engine ref '{ref}' is neither semver tag nor 40-char SHA; "
                        f"version not verifiable"
                    )
                    continue

                if version != declared:
                    fails.append(
                        f"{loc}: engine pinned at v{version} but policy_version declares {declared}"
                    )

        if matched == 0:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message=f"No external pin of {repo}; R-23 not applicable.",
            )
        if fails:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="engine pin out of sync with policy_version",
                detail="\n".join(fails + warns),
            )
        if warns:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.WARN,
                message="engine pin version not verifiable offline",
                detail="\n".join(warns),
            )
        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=f"engine pin aligned to policy_version {declared}",
        )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest tests/test_rule_r23_engine_pin_attestation.py -q`
Expected: PASS（全部）。

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r23_engine_pin_attestation.py tests/test_rule_r23_engine_pin_attestation.py
git commit -m "feat(r23): engine pin ⟷ policy_version attestation"
```

---

## Task 5: R-23 註冊存在性測試

**Files:**
- Modify: `tests/test_rules_presence.py`

- [ ] **Step 1: 寫測試**

加到 `tests/test_rules_presence.py`（沿用該檔既有 `get_rule` helper）：

```python
def test_r23_is_registered():
    rule = get_rule("R-23")
    assert rule.rule_id == "R-23"
    assert rule.exempt_label == "policy-exempt:engine-pin"
```

- [ ] **Step 2: 跑測試確認通過**

Run: `python3 -m pytest tests/test_rules_presence.py -q -k r23`
Expected: PASS（R-23 已於 Task 4 註冊）。

- [ ] **Step 3: Commit**

```bash
git add tests/test_rules_presence.py
git commit -m "test(r23): 註冊存在性"
```

---

## Task 6: 將本 repo 轉為 symlink 模式並 dogfood

**Files:**
- Modify: `.paul-project.yml`
- Replace（轉 symlink）: `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`

- [ ] **Step 1: `.paul-project.yml` 新增設定**

在 `.paul-project.yml` 加（`conventions_engine` 因本 repo 以 `./` 在地引用引擎而 R-23 NA，附說明性註解；可不設 `repo`）：

```yaml
agent_files:
  mode: symlink
conventions_engine:
  # 本 repo 即引擎本體，workflow 以 ./ 在地引用 → R-23 NA。
  # 下游 repo 在此填 hamanpaul/paulsha-conventions 以啟用 attestation。
  repo: ""
```

注意：`repo: ""` 為空字串，R-23 視為未設（`if not repo`）→ NA。R-08 接受空字串（`isinstance(repo, str)` 為真）。

- [ ] **Step 2: 轉 symlink**

```bash
cd /home/paul_chen/prj_pri/paulsha-conventions
rm AGENTS.md GEMINI.md .github/copilot-instructions.md
ln -s CLAUDE.md AGENTS.md
ln -s CLAUDE.md GEMINI.md
ln -s ../CLAUDE.md .github/copilot-instructions.md
git add -A AGENTS.md GEMINI.md .github/copilot-instructions.md .paul-project.yml
```

- [ ] **Step 3: 驗證 git 以 symlink（mode 120000）記錄**

Run: `git ls-files -s AGENTS.md GEMINI.md .github/copilot-instructions.md`
Expected: 每行皆以 `120000` 開頭。

- [ ] **Step 4: dogfood 整體規則**

Run: `python3 -m policy_check --repo .`
Expected: 無 failure；R-13 PASS、R-14 PASS（symlink）、R-23 PASS（NA）。

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: 本 repo agent 慣例檔轉 symlink 單一真檔（mode: symlink）"
```

---

## Task 7: 慣例檔文字、白名單、文件、CHANGELOG

**Files:**
- Modify: `CLAUDE.md`（canonical；symlink 自動跟隨）
- Modify: `README.md` / 相關 `docs/**`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 更新 CLAUDE.md 文字**

在 `CLAUDE.md` 做下列替換：
1. 第 2 行 HTML 註記
   - 舊：`<!-- 若修改此檔，同步更新 CLAUDE.md / AGENTS.md / GEMINI.md / .github/copilot-instructions.md 四份 -->`
   - 新：`<!-- 此為 canonical 真檔；AGENTS.md / GEMINI.md / .github/copilot-instructions.md 為指向本檔的 symlink，只維護本檔 -->`
2. 「改版號時」區塊中「`四份 agent 檔`」→「`canonical CLAUDE.md`（其餘三檔為 symlink 自動跟隨）」。
3. 「禁止」區塊
   - 舊：`- 修改本檔而不同步其他三份 agent convention 檔`
   - 新：`- 把 agent symlink（AGENTS.md / GEMINI.md / .github/copilot-instructions.md）還原成獨立複本（mode: symlink 下 R-14 會 FAIL）`
4. 「Exemption Labels 白名單」新增一行：
   `- \`policy-exempt:engine-pin\` — R-23 引擎 pin 版本與 policy_version 對齊`
5. 在「完成任務（claim done）前」清單補一條：
   `- [ ] R-23：workflow 對引擎的 pin 版本與 \`policy_version\` 一致（tag 或 SHA+\`# vX.Y.Z\` 註解），或上 \`policy-exempt:engine-pin\``

- [ ] **Step 2: 更新 README / docs 的 rule 目錄與模型描述**

Run: `grep -rn "R-14\|R-22\|四份\|agent convention\|policy-exempt" README.md docs/ --include="*.md" -l`
對命中檔：(a) 把 agent 慣例檔模型由「四份」改述為「canonical CLAUDE.md + symlink」；(b) R-14 條目改述為「config-gated 單一真檔完整性」；(c) rule 目錄補 R-23 與 `policy-exempt:engine-pin`。

- [ ] **Step 3: CHANGELOG [Unreleased] 補 entry**

在 `CHANGELOG.md` 的 `[Unreleased]` 下新增：

```markdown
### Added
- R-23：engine pin ⟷ `policy_version` attestation；新增豁免 label `policy-exempt:engine-pin`。
- `.paul-project.yml` 支援 `agent_files.mode`（`copy`/`symlink`）與 `conventions_engine.repo`。

### Changed
- R-14 升級為 config-gated 單一真檔完整性；`symlink` 模式下三鏡像檔須為指向 `CLAUDE.md` 的 symlink。
- 本 repo agent 慣例檔改為 canonical `CLAUDE.md` + symlink（只維護一份）。
```

- [ ] **Step 4: 驗證 doc 無新懸空 + 全綠**

Run: `python3 -m pytest -q && python3 -m policy_check --repo .`
Expected: pytest 全綠；policy_check 無 failure（R-22 無「本次新破壞」、R-18/R-16/語言皆過）。

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs CHANGELOG.md
git commit -m "docs: 慣例檔/README/CHANGELOG 同步 symlink 模型與 R-23"
```

---

## Task 8: 最終驗證與 openspec 標記

**Files:**
- Verify only（+ openspec change 進度）

- [ ] **Step 1: 全套件測試**

Run: `python3 -m pytest -q`
Expected: 全綠（含 self-dogfood R-16、action/integration）。

- [ ] **Step 2: 完整 policy_check**

Run: `python3 -m policy_check --repo .`
Expected: 無任何 failure。

- [ ] **Step 3: 勾選 openspec tasks**

將 `openspec/changes/agent-files-single-source-attestation/tasks.md` 對應項打勾，並：
Run: `openspec validate "agent-files-single-source-attestation"`
Expected: `is valid`。

- [ ] **Step 4: Commit**

```bash
git add openspec/changes/agent-files-single-source-attestation/tasks.md
git commit -m "chore(openspec): 勾選 agent-files-single-source-attestation tasks"
```

---

## Release 待辦（merge 當下執行，不在本 plan 的 feature commit 內）

合併本 PR 當下立即補 release bump `1.0.5 → 1.0.6`：`VERSION`、`.paul-project.yml policy_version`、`CLAUDE.md` 的 `policy_version` 與 `managed-by@v1.0.6`、workflow `policy_version` 字面值、git tag、`RELEASES.md`。PR body 用 zh-tw；PR template checklist 全勾；若引用 issue 用 closing-keyword。
```

## Self-Review

**Spec coverage（對照 openspec specs）：**
- agent-files-single-source：canonical+symlink topology（Task 3）、copy 預設（Task 3 _check_copy 回歸）、agent_files schema（Task 1）— 全覆蓋。
- engine-version-attestation：tag/SHA-comment 對齊（Task 4）、純 SHA WARN（Task 4）、NA（Task 4）、豁免 SKIP（Task 4）、conventions_engine schema（Task 1）— 全覆蓋。

**Placeholder scan：** 無 TBD/TODO；每段 code step 皆含實際程式碼與預期輸出。

**Type consistency：** `CANONICAL`/`AGENT_FILES` 常數、`_USES_RE`/`_TAG_VER_RE`/`_COMMENT_VER_RE`/`_SHA_RE`、`exempt_label="policy-exempt:engine-pin"` 在 plan 與 spec 一致；`ctx.config` 讀法（`agent_files.mode`、`conventions_engine.repo`）與 `RuleContext.config` 欄位一致。
