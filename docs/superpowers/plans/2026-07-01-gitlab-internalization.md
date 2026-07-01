# GitLab 內部化 / 離線 pip 套件 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓引擎能以離線 pip 套件在 GitLab merge_request pipeline 當 gate：GitLab MR context provider、R-23 pip-mode attestation、離線可安裝 wheel。

**Architecture:** `pr_context.py` 加 GitLab provider（`load_pr_meta()` 分派）與 `changed_files` SHA/branch 拆路徑；`RuleContext` 加 `provider`；R-12 在 GitLab 標 NA；R-23 依 `conventions_engine.mode` 分岔（pip 態比對已安裝版本、PEP 440 正規化、fail-closed）；R-08 驗 `mode` 列舉；pyproject 版本 lockstep 測試；wheel 真離線 smoke。GitHub 路徑零回歸。

**Tech Stack:** Python 3.11+（stdlib `importlib.metadata`；不引入 `packaging`）、pytest、setuptools build、universal-ctags（系統前置）。

**對應 spec：** `docs/superpowers/specs/2026-07-01-gitlab-internalization-design.md`（v2）、`openspec/changes/gitlab-internalization/`。

**慣例：** worktree `feature/20-gitlab-pip`；每 code task TDD-first；commit zh-tw + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`；測試 `python3 -m pytest -q`。

---

## Task 1: RuleContext.provider + pr_context GitLab provider

**Files:** Modify `policy_check/rules/base.py`、`policy_check/pr_context.py`；Test `tests/test_pr_context_gitlab.py`

- [ ] **Step 1: 失敗測試**

```python
# tests/test_pr_context_gitlab.py
import os
from policy_check import pr_context as prc


def _clear(mp):
    for k in list(os.environ):
        if k.startswith("CI_MERGE_REQUEST_") or k in ("GITHUB_EVENT_PATH",):
            mp.delenv(k, raising=False)


def test_gitlab_pr_meta_maps_and_strips_labels(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "7")
    monkeypatch.setenv("CI_MERGE_REQUEST_TITLE", "feat: x")
    monkeypatch.setenv("CI_MERGE_REQUEST_DESCRIPTION", "body")
    monkeypatch.setenv("CI_MERGE_REQUEST_LABELS", "wip, policy-exempt:docs-sync ,")
    monkeypatch.setenv("CI_MERGE_REQUEST_SOURCE_BRANCH_NAME", "fix-x")
    monkeypatch.setenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "main")
    m = prc.gitlab_pr_meta()
    assert m["pr_title"] == "feat: x"
    assert m["pr_labels"] == ["wip", "policy-exempt:docs-sync"]
    assert m["pr_head_ref"] == "fix-x" and m["pr_base_ref"] == "main"
    assert m["provider"] == "gitlab"


def test_gitlab_labels_unset_is_empty_list(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "7")
    assert prc.gitlab_pr_meta()["pr_labels"] == []


def test_load_pr_meta_dispatch(monkeypatch):
    _clear(monkeypatch)
    # 無 GitLab、無 GitHub event → {}
    assert prc.load_pr_meta() == {}
    # GitLab 優先
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "7")
    assert prc.load_pr_meta().get("provider") == "gitlab"
```

- [ ] **Step 2: 跑 → FAIL**（`gitlab_pr_meta`/`load_pr_meta` 不存在）

Run: `python3 -m pytest tests/test_pr_context_gitlab.py -q`

- [ ] **Step 3: 實作**

`policy_check/rules/base.py` 的 `RuleContext` 加欄位（在 `latest_tag` 後）：
```python
    provider: Optional[str] = None                 # "github" | "gitlab" | None
```

`policy_check/pr_context.py`：`pr_meta_from_event` 回傳 dict 加兩鍵：
```python
        "provider": "github" if has_pr else None,
        "pr_base_sha": None,
```
並在檔尾新增：
```python
def gitlab_pr_meta() -> dict:
    """從 GitLab merge_request pipeline 的 CI_MERGE_REQUEST_* 組與 GitHub 等效的 meta。"""
    def _env(k):
        v = os.environ.get(k)
        return v if v not in (None, "") else None

    labels_raw = os.environ.get("CI_MERGE_REQUEST_LABELS")
    labels = (
        [t.strip() for t in labels_raw.split(",") if t.strip()]
        if labels_raw is not None else []
    )
    return {
        "pr_title": _env("CI_MERGE_REQUEST_TITLE"),
        "pr_body": _env("CI_MERGE_REQUEST_DESCRIPTION"),
        "pr_labels": labels,
        "pr_base_ref": _env("CI_MERGE_REQUEST_TARGET_BRANCH_NAME"),
        "pr_head_ref": _env("CI_MERGE_REQUEST_SOURCE_BRANCH_NAME"),
        "pr_base_sha": _env("CI_MERGE_REQUEST_DIFF_BASE_SHA"),
        "provider": "gitlab",
    }


def load_pr_meta() -> dict:
    """provider 分派：GitLab MR > GitHub event > 空 {}（恆為 dict）。"""
    if os.environ.get("CI_MERGE_REQUEST_IID"):
        return gitlab_pr_meta()
    event = load_event_payload()
    if event:
        return pr_meta_from_event(event)
    return {}
```

- [ ] **Step 4: 跑 → PASS**

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/base.py policy_check/pr_context.py tests/test_pr_context_gitlab.py
git commit -m "feat(pr-context): GitLab MR provider + load_pr_meta 分派 + RuleContext.provider

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: changed_files 拆 SHA / branch 路徑

**Files:** Modify `policy_check/pr_context.py`；Test `tests/test_pr_context_changed_files.py`

- [ ] **Step 1: 失敗測試**

```python
# tests/test_pr_context_changed_files.py
import subprocess
from pathlib import Path
from policy_check import pr_context as prc


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)


def _repo(tmp_path: Path) -> tuple[Path, str]:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    base = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    (tmp_path / "b.py").write_text("y = 2\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "next")
    return tmp_path, base


def test_changed_files_by_sha_no_origin_prefix(tmp_path):
    repo, base = _repo(tmp_path)
    # base 為 SHA → git diff <sha>...HEAD（不加 origin/，否則無效 ref 回 []）
    got = prc.changed_files(None, repo, base_sha=base)
    assert "b.py" in got


def test_changed_files_by_branch_uses_origin(tmp_path, monkeypatch):
    repo, _ = _repo(tmp_path)
    # 無 origin remote → origin/<b> 解析失敗 → []（不崩潰）
    assert prc.changed_files("main", repo) == []
```

- [ ] **Step 2: 跑 → FAIL**（`changed_files` 尚無 `base_sha`）

- [ ] **Step 3: 實作** — `changed_files` 改：

```python
def changed_files(base_ref: str | None, repo_root: Path, base_sha: str | None = None) -> list[str]:
    if base_sha:
        rng = f"{base_sha}...HEAD"          # SHA 直接用，不加 origin/
    elif base_ref:
        rng = f"origin/{base_ref}...HEAD"
    else:
        return []
    cmd = ["git", "-C", str(repo_root), "diff", "--name-only", rng]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return []
    return [l.strip() for l in out.splitlines() if l.strip()]
```

- [ ] **Step 4: 跑 → PASS**

- [ ] **Step 5: Commit**

```bash
git add policy_check/pr_context.py tests/test_pr_context_changed_files.py
git commit -m "fix(pr-context): changed_files 拆 SHA/branch 兩路徑（SHA 不加 origin/ 前綴）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: cli.build_context 接 load_pr_meta

**Files:** Modify `policy_check/cli.py`

- [ ] **Step 1: 改 `build_context`** — 把：

```python
    event = prc.load_event_payload()
    pr_meta = prc.pr_meta_from_event(event)
    return RuleContext(
        ...
        changed_files=prc.changed_files(pr_meta.get("pr_base_ref") or args.pr_base_ref, repo_root),
        latest_tag=prc.latest_tag(repo_root),
    )
```

換成：

```python
    pr_meta = prc.load_pr_meta()
    base_ref = pr_meta.get("pr_base_ref") or args.pr_base_ref
    return RuleContext(
        repo_root=repo_root,
        profile=conf["policy_profile"],
        policy_version=conf["policy_version"],
        config=conf,
        pr_title=pr_meta.get("pr_title") or args.pr_title,
        pr_body=pr_meta.get("pr_body") or args.pr_body,
        pr_labels=(
            pr_meta["pr_labels"]
            if pr_meta.get("pr_labels") is not None
            else (args.pr_labels.split(",") if args.pr_labels else [])
        ),
        pr_base_ref=base_ref,
        pr_head_ref=pr_meta.get("pr_head_ref") or args.pr_head_ref,
        changed_files=prc.changed_files(base_ref, repo_root, pr_meta.get("pr_base_sha")),
        latest_tag=prc.latest_tag(repo_root),
        provider=pr_meta.get("provider"),
    )
```

- [ ] **Step 2: 驗證**

Run: `python3 -m pytest -q` → 全綠
Run: `python3 -m policy_check --repo .` → 行為與改前一致（本地/GitHub）

- [ ] **Step 3: Commit**

```bash
git add policy_check/cli.py
git commit -m "feat(cli): build_context 改用 load_pr_meta（provider 分派 + base_sha）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: R-12 在 GitLab 標 NA

**Files:** Modify `policy_check/rules/r12_branch_source.py`；Test `tests/test_rule_r12_gitlab_na.py`

- [ ] **Step 1: 失敗測試**

```python
# tests/test_rule_r12_gitlab_na.py
from pathlib import Path
from policy_check.rules.r12_branch_source import R12BranchSource
from policy_check.rules.base import RuleContext, Status


def _ctx(**kw):
    return RuleContext(repo_root=Path("."), profile="flat", policy_version="1.0.10", **kw)


def test_r12_na_on_gitlab():
    res = R12BranchSource().check(_ctx(provider="gitlab", pr_base_ref="master", pr_head_ref="fix-x"))
    assert res.status == Status.PASS
    assert "GitLab" in res.message or "not applicable" in res.message.lower()


def test_r12_github_unchanged_fail():
    # GitHub：base=main、head 非 feature/ → 仍 FAIL（既有行為）
    res = R12BranchSource().check(_ctx(provider="github", pr_base_ref="main", pr_head_ref="random"))
    assert res.status == Status.FAIL
```

- [ ] **Step 2: 跑 → FAIL**（GitLab case 目前會誤 FAIL）

- [ ] **Step 3: 實作** — 在 `r12` 的 `check()` 內、exempt label 判定之後，加：

```python
        if ctx.provider == "gitlab":
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="GitLab provider: branch-source convention (hamanpaul-specific) not applicable.",
            )
```

- [ ] **Step 4: 跑 → PASS** + 既有 R-12 測試續綠（`python3 -m pytest tests/test_rule_r12_branch_source.py -q`）

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r12_branch_source.py tests/test_rule_r12_gitlab_na.py
git commit -m "feat(R-12): GitLab provider 下標 NA（分支慣例 hamanpaul 專屬，不硬套）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: R-23 pip-mode + R-08 mode 列舉

**Files:** Modify `policy_check/rules/r23_engine_pin_attestation.py`、`policy_check/rules/r08_policy_config_schema.py`；Test `tests/test_rule_r23_pip_mode.py`

- [ ] **Step 1: 失敗測試**

```python
# tests/test_rule_r23_pip_mode.py
from pathlib import Path
import policy_check.rules.r23_engine_pin_attestation as r23m
from policy_check.rules.r23_engine_pin_attestation import R23EnginePinAttestation
from policy_check.rules.base import RuleContext, Status


def _ctx(policy_version, mode=None, repo=None):
    ce = {}
    if mode is not None:
        ce["mode"] = mode
    if repo is not None:
        ce["repo"] = repo
    return RuleContext(repo_root=Path("."), profile="flat",
                       policy_version=policy_version, config={"conventions_engine": ce})


def test_pip_mode_match_pass(monkeypatch):
    monkeypatch.setattr(r23m, "_installed_version", lambda: "1.0.11")
    assert R23EnginePinAttestation().check(_ctx("1.0.11", mode="pip")).status == Status.PASS


def test_pip_mode_fix_maps_to_post(monkeypatch):
    # policy -fix.N ↔ 安裝版 PEP440 .postN
    monkeypatch.setattr(r23m, "_installed_version", lambda: "1.0.11.post1")
    assert R23EnginePinAttestation().check(_ctx("1.0.11-fix.1", mode="pip")).status == Status.PASS


def test_pip_mode_mismatch_fail(monkeypatch):
    monkeypatch.setattr(r23m, "_installed_version", lambda: "1.0.10")
    assert R23EnginePinAttestation().check(_ctx("1.0.11", mode="pip")).status == Status.FAIL


def test_pip_mode_not_installed_fail_closed(monkeypatch):
    def _boom():
        from importlib.metadata import PackageNotFoundError
        raise PackageNotFoundError("policy-check")
    monkeypatch.setattr(r23m, "_installed_version", _boom)
    assert R23EnginePinAttestation().check(_ctx("1.0.11", mode="pip")).status == Status.FAIL


def test_pip_mode_independent_of_repo(monkeypatch):
    # mode:pip + repo 未設 + 版本不符 → FAIL（非 NA 早退）
    monkeypatch.setattr(r23m, "_installed_version", lambda: "9.9.9")
    assert R23EnginePinAttestation().check(_ctx("1.0.11", mode="pip")).status == Status.FAIL
```

- [ ] **Step 2: 跑 → FAIL**（尚無 pip 分支 / `_installed_version`）

- [ ] **Step 3: 實作 r23** — import 區加：

```python
import importlib.metadata
```

在類別外（module 層）加可 monkeypatch 的 helper 與正規化：

```python
def _installed_version() -> str:
    return importlib.metadata.version("policy-check")


def _canon_version(v: str) -> str:
    """policy 語法 X.Y.Z[-fix.N] ↔ PEP 440 X.Y.Z[.postN] 的共同正規化。"""
    v = v.strip().lower()
    v = re.sub(r"-fix\.(\d+)$", r".post\1", v)
    return v
```

在 `check()` 內、exempt label 判定之後、`engine_cfg`/`repo` 早退之前，插入 mode 分岔：

```python
        engine_cfg = ctx.config.get("conventions_engine") or {}
        mode = (engine_cfg.get("mode") if isinstance(engine_cfg, dict) else None) or "workflow"
        if mode == "pip":
            declared = ctx.policy_version
            try:
                installed = _installed_version()
            except importlib.metadata.PackageNotFoundError:
                return RuleResult(
                    rule_id=self.rule_id, status=Status.FAIL,
                    message="conventions_engine.mode=pip but 'policy-check' is not installed; version not attestable.",
                )
            if _canon_version(installed) == _canon_version(declared):
                return RuleResult(
                    rule_id=self.rule_id, status=Status.PASS,
                    message=f"installed policy-check {installed} matches policy_version {declared}",
                )
            return RuleResult(
                rule_id=self.rule_id, status=Status.FAIL,
                message=f"installed policy-check {installed} but policy_version declares {declared}",
            )
        # 以下為 workflow 路徑（現行行為，完全不變）——沿用既有 repo 早退 + workflow 掃描。
```

> 注意：workflow 路徑原本第一行就是 `engine_cfg = ctx.config.get(...)`；重構後 engine_cfg 已在上面取得，勿重複宣告，直接接 `repo = engine_cfg.get("repo") ...`。

- [ ] **Step 4: 實作 r08 mode 列舉** — 在 `r08` 的 conventions_engine 驗證區塊（`repo` 為 str 檢查旁）加：

```python
            mode = conventions_engine.get("mode")
            if mode is not None and mode not in ("workflow", "pip"):
                return RuleResult(
                    rule_id=self.rule_id, status=Status.FAIL,
                    message="conventions_engine.mode must be one of ['workflow', 'pip']",
                )
```

補測試 `tests/test_rule_r08_policy_config_schema.py`：`mode: pipp` → FAIL；`mode: pip`/`workflow`/未設 → PASS。

- [ ] **Step 5: 跑 → PASS** + 既有 R-23/R-08 測試續綠 + 全 suite

Run: `python3 -m pytest -q`

- [ ] **Step 6: Commit**

```bash
git add policy_check/rules/r23_engine_pin_attestation.py policy_check/rules/r08_policy_config_schema.py tests/test_rule_r23_pip_mode.py tests/test_rule_r08_policy_config_schema.py
git commit -m "feat(R-23): pip-mode attestation（顯式 mode、fail-closed、PEP440 正規化）+ R-08 驗 mode 列舉

- mode 先判、pip 分支獨立於 conventions_engine.repo（防 fail-open）
- 比對已安裝 policy-check 版本，-fix.N↔.postN 正規化；未安裝 FAIL
- workflow（預設）路徑零回歸

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 版本 lockstep 測試

**Files:** Test `tests/test_version_lockstep.py`

- [ ] **Step 1: 失敗測試**（先確認三者一致，測試即斷言）

```python
# tests/test_version_lockstep.py
import re
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', text)
    assert m, "pyproject [project].version 找不到"
    return m.group(1)


def test_version_lockstep():
    v_file = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    cfg = yaml.safe_load((REPO / ".paul-project.yml").read_text(encoding="utf-8"))
    assert _pyproject_version() == v_file == str(cfg["policy_version"]), (
        f"版本不一致：pyproject={_pyproject_version()} VERSION={v_file} "
        f"policy_version={cfg['policy_version']}"
    )
```

- [ ] **Step 2: 跑 → PASS**（現況三者皆 1.0.10；若不符則先修一致）

- [ ] **Step 3: Commit**

```bash
git add tests/test_version_lockstep.py
git commit -m "test(version): pyproject==VERSION==policy_version lockstep 守恆

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: wheel package-data 稽核 + 真離線 smoke

**Files:** 可能 Modify `pyproject.toml`；Test `tests/test_wheel_offline.py`

- [ ] **Step 1: 稽核 package-data** — 確認 wheel 含所有 runtime 非-.py 資產：

Run: `grep -rnE "data/|\.yml|read_text\(|open\(" policy_check --include=*.py | grep -viE "test|fixture"`
確認 `[tool.setuptools.package-data]` 已涵蓋（現有 `policy_check.data` = `*.yml`）；若有其他資產（如 baseline 檔）未涵蓋則補。`tests/fixtures` 不得打包（現有 pytest `--ignore` 與 packages.find `include=["policy_check*"]` 已排除）。

- [ ] **Step 2: 真離線 smoke 測試**（slow / packaging gate）

```python
# tests/test_wheel_offline.py
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("PACKAGING") != "1",
    reason="離線 wheel smoke 僅在 PACKAGING=1（有 build 工具）環境跑",
)


def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def test_wheel_builds_installs_offline_and_runs(tmp_path):
    dist = tmp_path / "dist"
    vendor = tmp_path / "vendor"
    # 1) build engine wheel
    _run([sys.executable, "-m", "build", "--wheel", "--outdir", str(dist)], cwd=str(REPO))
    wheel = next(dist.glob("policy_check-*.whl"))
    # 2) 下載相依閉包到 vendor（build 階段可連網）
    _run([sys.executable, "-m", "pip", "download", "--dest", str(vendor), str(wheel)])
    # 3) 乾淨 venv，離線安裝（--no-index + --find-links）
    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    vpy = venv_dir / ("Scripts" if os.name == "nt" else "bin") / "python"
    _run([str(vpy), "-m", "pip", "install", "--no-index", "--find-links", str(vendor), str(wheel)])
    # 4) 離線執行：對最小 fixture repo 跑 policy-check
    fixture = tmp_path / "repo"
    fixture.mkdir()
    (fixture / ".paul-project.yml").write_text("policy_profile: flat\npolicy_version: 1.0.10\n")
    proc = subprocess.run(
        [str(vpy), "-m", "policy_check", "--repo", str(fixture), "--only", "R-08"],
        capture_output=True, text=True,
    )
    # R-08 對缺欄位的最小 config 可能 FAIL，但「能離線執行並產報告」才是本測試重點
    assert "Policy Check Report" in proc.stdout, proc.stderr
```

- [ ] **Step 3: 於 packaging 環境驗證**

Run（需 `pip install build`）：`PACKAGING=1 python3 -m pytest tests/test_wheel_offline.py -q`
Expected: PASS（一般 `python3 -m pytest -q` 會 skip 此檔）

- [ ] **Step 4: Commit**

```bash
git add tests/test_wheel_offline.py pyproject.toml
git commit -m "test(packaging): 真 build+download+install(--no-index --find-links)+run 離線 smoke

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 文件（GitLab CI）+ changelog

**Files:** Modify `README.md`；Create `changelog.d/20-gitlab-pip.md`

- [ ] **Step 1: README 補「離線 pip 安裝 + GitLab CI gate」段**，含：
  - 離線安裝：build wheel → `pip download` 相依閉包 → `pip install --no-index --find-links <vendor> policy-check==X.Y.Z`（強調 `--no-index <wheel>` 單獨不足、需 vendored 相依）。
  - `.gitlab-ci.yml` 範例 job：`rules: - if: $CI_PIPELINE_SOURCE == "merge_request_event"`、`variables: GIT_DEPTH: "0"`、`before_script: apt-get update && apt-get install -y universal-ctags`、`.paul-project.yml` 設 `conventions_engine: { mode: pip }`、`script: policy-check --repo .`。
  - build-time 需網路（取相依閉包）vs gate-time 離線 的界線。
  - **發行管道選型**（Artifactory/內部 PyPI/GitLab Package Registry）明列為待公司決定的 follow-up。

- [ ] **Step 2: changelog fragment**

```markdown
---
type: feat
scope: gitlab
issue: 20
---
引擎可作為離線 pip 套件在 GitLab merge_request pipeline 當 gate：新增 GitLab MR context provider（R-12 於 GitLab 標 NA）、R-23 pip-mode attestation（顯式 conventions_engine.mode、fail-closed、PEP440 正規化）、wheel 離線安裝（vendored 相依）與版本 lockstep；GitHub 路徑零回歸。發行管道選型另行追蹤。
```

- [ ] **Step 3: Commit**

```bash
git add README.md changelog.d/20-gitlab-pip.md
git commit -m "docs(gitlab): 離線 pip 安裝 + GitLab CI gate 文件 + changelog fragment

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: docs/MOC + 收尾驗收

**Files:** Modify `docs/MOC.md`

- [ ] **Step 1: docs/MOC.md 連結本 spec + plan**（Plans／Specs 段各一行，避免 R-24 orphan WARN）。

- [ ] **Step 2: openspec validate**

Run: `openspec validate gitlab-internalization --strict` → valid

- [ ] **Step 3: 全 suite**

Run: `python3 -m pytest -q`（wheel smoke 由 PACKAGING gate 略過）→ 全綠

- [ ] **Step 4: 全 policy gate**

Run: `python3 -m policy_check --repo .`
Expected: 無 fail（本 repo `conventions_engine.mode` 未設 → workflow 路徑、repo="" → R-23 NA；R-24 orphan 已由 Step 1 消除）。

- [ ] **Step 5: Commit**

```bash
git add docs/MOC.md
git commit -m "docs: MOC 連結 #20 spec/plan

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review（plan 對 spec / openspec 覆蓋）

- chunk 2 provider + changed_files + R-12 NA → Task 1/2/3/4。✅（對抗式覆審 D1–D4）
- chunk 3 pip-mode + R-08 mode → Task 5。✅（D5–D7）
- chunk 1a 版本 lockstep + 真離線 smoke + package-data + ctags 文件 → Task 6/7/8。✅（D8–D11）
- 收尾 MOC/gate/validate → Task 9。✅

**型別一致：** `load_pr_meta`/`gitlab_pr_meta`/`changed_files(base_ref, root, base_sha)`/`RuleContext.provider`/`_installed_version`/`_canon_version` 於各 task 一致；版本 `1.0.10`（動工時）於 lockstep/測試一致。

**Non-goals 遵守：** 不選發行管道、不改規則判定語義（R-10/11/17 換來源、R-12 GitLab NA、R-23 多 pip 態）、GitHub 路徑零回歸、零 rule_id/label 變動。
