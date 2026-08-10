# arc-conventions portability（階段一）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「誰是 canonical authority」從原始碼常數下移為 distribution identity（安裝期決定、執行期唯讀），讓同一份 codebase 能以 `arc-conventions` 身分部署，且不放寬既有信任邊界。

**Architecture:** 新增 `policy_check/identity.py` 作為單一身分入口，讀取套件資料檔 `policy_check/data/distribution.yml`（安裝期可由 `install.sh` 覆寫）。`drift.py`、`preflight.py`、`runtime_bundle/*` 的硬編碼常數改為向 identity 取值。`.project-policy.yml` 的 `conventions_engine.repo` 語意不變 —— 只能宣告一致，不一致仍拋 `PreflightGateError`。

**Tech Stack:** Python 3.10+、PyYAML（`policy_check` 既有依賴）、pytest、`importlib.resources`

- Spec：`docs/superpowers/specs/2026-08-10-arc-conventions-portability-design.md`
- Issue：[#63](https://github.com/hamanpaul/paulsha-conventions/issues/63)
- 分支：`feature/63-arc-conventions-portability`（已建立，勿在 `main` 動工）

## Global Constraints

- **不得觸及版號語法**。以下 5 處在階段一完全不改：`rules/r06_version_format.py:14`、`drift.py:20-21`、`drift.py:25-28`、`preflight.py:424`、`rules/r23_engine_pin_attestation.py:14-16`。版號策略另案處理。
- **`provider` 階段一固定 `github`**。R-15 / R-20 行為不變，不得為了 GitLab 改動它們。
- **`policy_check/runtime_bundle/verification.py` 必須維持 stdlib-only**（檔頭註解已載明：source package 與 vendored bootstrap manager 共用這份實作）。**不得在該檔 import `yaml` 或 `policy_check.identity`**；身分一律由呼叫端以參數傳入。
- **Fail-closed，不得回退預設值**。identity 缺漏／不合法時拋錯，絕不悄悄改用硬編碼值。
- **既有行為零變更**。內建 `distribution.yml` 的值等於現行常數；完成後既有測試必須全綠。
- **不得從環境變數或被檢查 repo 的檔案讀取 identity**。身分屬於「這份被安裝的引擎」。
- 每個 task 結束時 `python3 -m pytest -q` 必須全綠，並 `python3 -m policy_check --repo .` 維持 `fail: 0`。
- 本分支為 code change，需要一個 changelog fragment（Task 1 建立，涵蓋整個 PR）。

---

### Task 1: distribution identity 模組

**Files:**
- Create: `policy_check/identity.py`
- Create: `policy_check/data/distribution.yml`
- Create: `tests/test_identity.py`
- Create: `changelog.d/63-arc-conventions-portability.md`

**Interfaces:**
- Consumes: 無（本 task 為基礎）
- Produces:
  - `policy_check.identity.identity() -> DistributionIdentity`（`functools.lru_cache` 包裝，測試可用 `identity.cache_clear()` 重置）
  - `DistributionIdentity` frozen dataclass，欄位 `canonical_org: str`、`engine_repo: str`、`remote_base: str`、`distribution_name: str`、`provider: str`
  - `DistributionIdentity.remote_urls() -> set[str]`（https / ssh:// / scp-like 三種形式）
  - `policy_check.identity.IdentityError`（`RuntimeError` 子類）

- [ ] **Step 1: 寫失敗測試**

建立 `tests/test_identity.py`：

```python
import pytest

from policy_check import identity as ident


@pytest.fixture(autouse=True)
def _clear_cache():
    ident.identity.cache_clear()
    yield
    ident.identity.cache_clear()


def test_builtin_identity_matches_current_constants():
    got = ident.identity()
    assert got.canonical_org == "hamanpaul"
    assert got.engine_repo == "hamanpaul/paulsha-conventions"
    assert got.remote_base == "https://github.com"
    assert got.distribution_name == "paulsha-conventions"
    assert got.provider == "github"


def test_remote_urls_covers_three_forms():
    assert ident.identity().remote_urls() == {
        "https://github.com/hamanpaul/paulsha-conventions",
        "ssh://git@github.com/hamanpaul/paulsha-conventions",
        "git@github.com:hamanpaul/paulsha-conventions",
    }


def test_alternative_distribution_swaps_urls(monkeypatch):
    monkeypatch.setattr(ident, "_load_raw", lambda: {
        "canonical_org": "hamanpaul",
        "engine_repo": "hamanpaul/arc-conventions",
        "remote_base": "https://github.com",
        "distribution_name": "arc-conventions",
        "provider": "github",
    })
    got = ident.identity()
    assert got.distribution_name == "arc-conventions"
    assert "https://github.com/hamanpaul/arc-conventions" in got.remote_urls()


def test_incomplete_identity_is_fail_closed(monkeypatch):
    monkeypatch.setattr(ident, "_load_raw", lambda: {"canonical_org": "hamanpaul"})
    with pytest.raises(ident.IdentityError) as exc:
        ident.identity()
    assert "engine_repo" in str(exc.value)


def test_invalid_provider_is_rejected(monkeypatch):
    monkeypatch.setattr(ident, "_load_raw", lambda: {
        "canonical_org": "hamanpaul",
        "engine_repo": "hamanpaul/arc-conventions",
        "remote_base": "https://github.com",
        "distribution_name": "arc-conventions",
        "provider": "bitbucket",
    })
    with pytest.raises(ident.IdentityError):
        ident.identity()


def test_distribution_build_is_optional_and_int(monkeypatch):
    base = {
        "canonical_org": "hamanpaul",
        "engine_repo": "hamanpaul/arc-conventions",
        "remote_base": "https://github.com",
        "distribution_name": "arc-conventions",
        "provider": "github",
    }
    monkeypatch.setattr(ident, "_load_raw", lambda: dict(base))
    assert ident.identity().distribution_build is None

    ident.identity.cache_clear()
    monkeypatch.setattr(ident, "_load_raw", lambda: {**base, "distribution_build": 3})
    assert ident.identity().distribution_build == 3

    ident.identity.cache_clear()
    monkeypatch.setattr(ident, "_load_raw", lambda: {**base, "distribution_build": "x"})
    with pytest.raises(ident.IdentityError):
        ident.identity()
```

`distribution_build` 是**選填**的發行編號（決策 A′）。內建的 upstream `distribution.yml` 不設此欄，因此 upstream 行為與 artifact 名稱完全不變。

- [ ] **Step 2: 執行測試確認失敗**

Run: `python3 -m pytest tests/test_identity.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'policy_check.identity'`

- [ ] **Step 3: 建立資料檔**

`policy_check/data/distribution.yml`：

```yaml
# 這份被安裝的引擎的發行身分。執行期唯讀。
# runtime bundle 的 install.sh 會在安裝期覆寫本檔以切換發行身分。
canonical_org: hamanpaul
engine_repo: hamanpaul/paulsha-conventions
remote_base: https://github.com
distribution_name: paulsha-conventions
provider: github
```

`pyproject.toml` 已宣告 `"policy_check.data" = ["*.yml"]`，不需改打包設定。

- [ ] **Step 4: 實作模組**

`policy_check/identity.py`：

```python
"""Distribution identity：這份被安裝的引擎的發行身分（執行期唯讀）。

身分屬於「被安裝的引擎」，不屬於「被檢查的 repo」，因此只從套件資料檔讀取，
不讀環境變數、不讀被檢查 repo 的任何檔案。缺漏或不合法一律 fail-closed，
不得回退到硬編碼預設值（回退等同悄悄放寬信任）。
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any

import yaml

REQUIRED_FIELDS = (
    "canonical_org",
    "engine_repo",
    "remote_base",
    "distribution_name",
    "provider",
)
VALID_PROVIDERS = {"github", "gitlab"}


class IdentityError(RuntimeError):
    """Distribution identity 缺漏或不合法。"""


@dataclass(frozen=True)
class DistributionIdentity:
    canonical_org: str
    engine_repo: str
    remote_base: str
    distribution_name: str
    provider: str
    # 選填：發行編號。只進 manifest 與報告，不進 artifact 檔名
    # （integrity.py:23 的目錄名正則內嵌版號語法，階段一不得更動）。
    distribution_build: int | None = None

    def remote_urls(self) -> set[str]:
        base = self.remote_base.rstrip("/")
        host = base.split("://", 1)[-1]
        return {
            f"{base}/{self.engine_repo}",
            f"ssh://git@{host}/{self.engine_repo}",
            f"git@{host}:{self.engine_repo}",
        }


def _load_raw() -> dict[str, Any]:
    raw = files("policy_check.data").joinpath("distribution.yml").read_text(
        encoding="utf-8"
    )
    return yaml.safe_load(raw) or {}


@lru_cache(maxsize=1)
def identity() -> DistributionIdentity:
    data = _load_raw()
    missing = [f for f in REQUIRED_FIELDS if not str(data.get(f) or "").strip()]
    if missing:
        raise IdentityError(
            f"distribution identity incomplete: {', '.join(missing)}"
        )
    provider = str(data["provider"]).strip()
    if provider not in VALID_PROVIDERS:
        raise IdentityError(
            "distribution identity provider must be one of "
            f"{sorted(VALID_PROVIDERS)}, got {provider!r}"
        )
    build = data.get("distribution_build")
    if build is not None:
        try:
            build = int(build)
        except (TypeError, ValueError):
            raise IdentityError(
                f"distribution_build must be an integer, got {build!r}"
            ) from None
    return DistributionIdentity(
        canonical_org=str(data["canonical_org"]).strip(),
        engine_repo=str(data["engine_repo"]).strip(),
        remote_base=str(data["remote_base"]).strip(),
        distribution_name=str(data["distribution_name"]).strip(),
        provider=provider,
        distribution_build=build,
    )
```

- [ ] **Step 5: 執行測試確認通過**

Run: `python3 -m pytest tests/test_identity.py -q`
Expected: PASS，6 passed

- [ ] **Step 6: 建立 changelog fragment**

`changelog.d/63-arc-conventions-portability.md`：

```markdown
---
type: feat
scope: portability
issue: 63
---
新增 distribution identity（`policy_check/identity.py` + `policy_check/data/distribution.yml`），把 canonical authority 從原始碼常數下移為安裝期決定、執行期唯讀的發行身分，讓同一份 codebase 能以不同發行身分部署；`.project-policy.yml` 只能宣告一致、不能改指向的既有信任邊界不變。
```

- [ ] **Step 7: 全套件迴歸與 commit**

Run: `python3 -m pytest -q`
Expected: 全綠（本 task 未動既有程式碼）

```bash
git add policy_check/identity.py policy_check/data/distribution.yml tests/test_identity.py changelog.d/63-arc-conventions-portability.md
git commit -m "feat(portability): 新增 distribution identity 模組（#63）"
```

---

### Task 2: drift.py 改用 identity

**Files:**
- Modify: `policy_check/drift.py:17-18`（`CANONICAL_ORG` / `CANONICAL_REPO`）
- Test: `tests/test_drift.py`（既有檔案，新增測試）

**Interfaces:**
- Consumes: `policy_check.identity.identity()`
- Produces: `policy_check.drift.canonical_org() -> str`、`policy_check.drift.canonical_repo() -> str`

**注意：** `drift.py:20-21` 的 `_VERSION_RE` / `_TAG_RE` 與 `parse_version()` 的排序 tuple 屬版號語法，**本 task 不得更動**。

- [ ] **Step 1: 找出所有引用點**

Run: `grep -n "CANONICAL_ORG\|CANONICAL_REPO" policy_check/ tests/ -r`
把輸出記下來 —— Step 4 必須全部改完，不能漏。

- [ ] **Step 2: 寫失敗測試**

在 `tests/test_drift.py` 末尾新增：

```python
def test_drift_canonical_values_follow_identity(monkeypatch):
    from policy_check import drift, identity as ident

    ident.identity.cache_clear()
    monkeypatch.setattr(ident, "_load_raw", lambda: {
        "canonical_org": "hamanpaul",
        "engine_repo": "hamanpaul/arc-conventions",
        "remote_base": "https://github.com",
        "distribution_name": "arc-conventions",
        "provider": "github",
    })
    try:
        assert drift.canonical_org() == "hamanpaul"
        assert drift.canonical_repo() == "arc-conventions"
    finally:
        ident.identity.cache_clear()
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `python3 -m pytest tests/test_drift.py::test_drift_canonical_values_follow_identity -q`
Expected: FAIL，`AttributeError: module 'policy_check.drift' has no attribute 'canonical_org'`

- [ ] **Step 4: 實作**

`policy_check/drift.py`：刪除第 17-18 行的兩個常數，改為（放在 import 區之後、`_VERSION_RE` 之前）：

```python
from policy_check.identity import identity


def canonical_org() -> str:
    return identity().canonical_org


def canonical_repo() -> str:
    return identity().engine_repo.split("/", 1)[1]
```

接著把 Step 1 grep 出的 `CANONICAL_ORG` 全部改為 `canonical_org()`、`CANONICAL_REPO` 全部改為 `canonical_repo()`。**採用函式而非模組層常數，是為了避免 import 期就觸發 identity 載入而讓錯誤出現在無關的 traceback。**

- [ ] **Step 5: 執行測試確認通過**

Run: `python3 -m pytest tests/test_drift.py -q`
Expected: PASS，既有 drift 測試亦全綠

- [ ] **Step 6: 全套件迴歸與 commit**

Run: `python3 -m pytest -q`
Expected: 全綠

```bash
git add policy_check/drift.py tests/test_drift.py
git commit -m "refactor(portability): drift 的 canonical org/repo 改用 identity（#63）"
```

---

### Task 3: preflight 去硬編碼與信任邊界

**Files:**
- Modify: `policy_check/preflight.py:39`（`CANONICAL_ENGINE_REPO`）
- Modify: `policy_check/preflight.py:451-453`（`_is_canonical_checkout` 的 canonical remote 集合）
- Modify: `policy_check/preflight.py:468-476`（`_source_engine` 的比對與錯誤訊息）
- Modify: `policy_check/preflight.py:657`（engine fetch 的 URL）
- Test: `tests/test_preflight_identity.py`（新建）

**Interfaces:**
- Consumes: `policy_check.identity.identity()`、`DistributionIdentity.remote_urls()`
- Produces: 無新公開介面；`CANONICAL_ENGINE_REPO` 常數移除，改由 `identity().engine_repo` 取得

- [ ] **Step 1: 寫失敗測試**

建立 `tests/test_preflight_identity.py`：

```python
import pytest

from policy_check import identity as ident
from policy_check import preflight


ARC = {
    "canonical_org": "hamanpaul",
    "engine_repo": "hamanpaul/arc-conventions",
    "remote_base": "https://github.com",
    "distribution_name": "arc-conventions",
    "provider": "github",
}


@pytest.fixture
def arc_identity(monkeypatch):
    ident.identity.cache_clear()
    monkeypatch.setattr(ident, "_load_raw", lambda: dict(ARC))
    yield
    ident.identity.cache_clear()


def test_canonical_remote_set_follows_identity(arc_identity):
    urls = ident.identity().remote_urls()
    assert "https://github.com/hamanpaul/arc-conventions" in urls
    assert "https://github.com/hamanpaul/paulsha-conventions" not in urls


def test_repo_config_cannot_redirect_engine(arc_identity, tmp_path):
    """核心不變式：被檢查的 repo 不能把 authority 指到別處。"""
    engine_root = tmp_path / "engine"
    (engine_root / "policy_check").mkdir(parents=True)
    (engine_root / "policy_check" / "preflight.py").write_text("", encoding="utf-8")
    config = {
        "policy_version": "1.0.15",
        "conventions_engine": {"repo": "attacker/evil-conventions"},
    }
    with pytest.raises(preflight.PreflightGateError) as exc:
        preflight._source_engine(engine_root, config, display_prefix="test")
    message = str(exc.value)
    assert "conventions_engine.repo" in message
    assert "hamanpaul/arc-conventions" in message
    assert "attacker/evil-conventions" in message
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `python3 -m pytest tests/test_preflight_identity.py -q`
Expected: FAIL —— 第一個測試因 `_load_raw` 尚未被 preflight 採用而失敗；第二個測試的錯誤訊息不含雙方值。

- [ ] **Step 3: 實作**

`policy_check/preflight.py`：

1. 刪除第 39 行 `CANONICAL_ENGINE_REPO = "hamanpaul/paulsha-conventions"`，於 import 區加入：

```python
from policy_check.identity import identity
```

2. `_is_canonical_checkout()`（原 451-453）改為：

```python
    normalized_remote = remote.stdout.strip().removesuffix(".git")
    return remote.returncode == 0 and normalized_remote in identity().remote_urls()
```

3. `_source_engine()` 的比對改為（原 468-476）：

```python
    engine_repo = identity().engine_repo
    if configured_repo and configured_repo != engine_repo:
        raise PreflightGateError(
            "source engine disagrees with conventions_engine.repo: "
            f"distribution={engine_repo!r}, repo declared={configured_repo!r}"
        )
    if not (engine_root / "policy_check" / "preflight.py").is_file():
        raise PreflightGateError("source engine is missing policy_check/preflight.py")
    if not _is_canonical_checkout(engine_root):
        raise PreflightGateError(
            f"source engine must be a checkout of {engine_repo}"
        )
```

4. engine fetch URL（原 657）改為：

```python
                f"{identity().remote_base.rstrip('/')}/{engine_repo}.git",
```

其中 `engine_repo` 取自該函式既有的參數；若該函式尚未持有 identity，於函式開頭加入 `remote_base = identity().remote_base` 並使用之。

- [ ] **Step 4: 執行測試確認通過**

Run: `python3 -m pytest tests/test_preflight_identity.py -q`
Expected: PASS，2 passed

- [ ] **Step 5: 補離線行為測試**

spec 要求「`remote_base` 指向不可達位址 + `--offline` 時不得嘗試網路」。於 `tests/test_preflight_identity.py` 末尾新增：

```python
def test_offline_does_not_touch_unreachable_remote(monkeypatch, tmp_path):
    """--offline 時走已安裝版本比對路徑，不得對 remote_base 發出網路請求。"""
    ident.identity.cache_clear()
    monkeypatch.setattr(ident, "_load_raw", lambda: {
        "canonical_org": "hamanpaul",
        "engine_repo": "hamanpaul/arc-conventions",
        "remote_base": "https://unreachable.invalid",
        "distribution_name": "arc-conventions",
        "provider": "github",
    })

    calls: list[list[str]] = []

    def _spy(cmd, *args, **kwargs):
        calls.append(list(cmd))
        raise AssertionError(f"offline path must not run: {cmd}")

    monkeypatch.setattr(preflight, "_run_or_error", _spy)
    try:
        assert preflight._version_matches("1.0.15", "1.0.15") is True
        assert calls == []
    finally:
        ident.identity.cache_clear()
```

若 `_version_matches` 的實際簽章與此不符，先 `grep -n "def _version_matches" policy_check/preflight.py` 核對後調整呼叫，斷言意圖不變：**offline 且版本相符時不得觸發任何外部命令**。

- [ ] **Step 6: 執行測試確認通過**

Run: `python3 -m pytest tests/test_preflight_identity.py -q`
Expected: PASS，3 passed

- [ ] **Step 7: 全套件迴歸與 commit**

Run: `python3 -m pytest -q`
Expected: 全綠（內建 identity 值等於原常數，既有 preflight 測試不受影響）

```bash
git add policy_check/preflight.py tests/test_preflight_identity.py
git commit -m "refactor(portability): preflight 的 engine 身分改用 identity（#63）"
```

---

### Task 4: runtime_bundle 的身分參數化

**Files:**
- Modify: `policy_check/runtime_bundle/verification.py:17`（移除模組常數）、`:114`（`_require_manifest_shape` 簽章）、`:122`（比對）、`:183`（`load_and_verify_bundle` 簽章）、`:215`、`:249`
- Modify: `policy_check/runtime_bundle/integrity.py:11`（import）、`:92`（呼叫）
- Modify: `policy_check/runtime_bundle/builder.py:20`（import）、`:140-142`（remote 集合）、`:491`（manifest repository）、`:528`（呼叫）
- Modify: `policy_check/runtime_bundle/cli.py:65`（呼叫）
- Modify: `policy_check/preflight.py:700`（呼叫）
- Test: `tests/test_runtime_bundle.py:47`（既有，改用參數）、新增測試

**Interfaces:**
- Consumes: `policy_check.identity.identity()`（僅在可 import yaml 的模組中）
- Produces:
  - `verification.load_and_verify_bundle(bundle_root: Path, *, expected_repository: str) -> dict[str, Any]`
  - `verification._require_manifest_shape(manifest: dict[str, Any], expected_repository: str) -> None`

**注意：** `verification.py` 必須維持 stdlib-only。**不得在該檔 import `policy_check.identity` 或 `yaml`**；身分只以參數傳入。

- [ ] **Step 1: 寫失敗測試**

在 `tests/test_runtime_bundle.py` 末尾新增：

```python
def test_verification_module_stays_stdlib_only():
    """verification.py 由 vendored bootstrap manager 共用，不得引入第三方或套件內依賴。"""
    from pathlib import Path

    source = Path("policy_check/runtime_bundle/verification.py").read_text(encoding="utf-8")
    assert "import yaml" not in source
    assert "policy_check.identity" not in source


def test_manifest_repository_is_checked_against_argument():
    from policy_check.runtime_bundle import verification

    manifest = {
        "schema_version": verification.SCHEMA_VERSION,
        "policy_version": "1.0.15",
        "skill_version": "1.0.15",
        "repository": "hamanpaul/arc-conventions",
        "release_tag": "v1.0.15",
        "release_commit": "0" * 40,
    }
    with pytest.raises(verification.BundleError):
        verification._require_manifest_shape(manifest, "hamanpaul/paulsha-conventions")
    verification._require_manifest_shape(manifest, "hamanpaul/arc-conventions")
```

若 `tests/test_runtime_bundle.py` 尚未 import pytest，於檔首加入 `import pytest`。

- [ ] **Step 2: 執行測試確認失敗**

Run: `python3 -m pytest tests/test_runtime_bundle.py -q -k "stdlib_only or repository_is_checked"`
Expected: FAIL，`TypeError: _require_manifest_shape() takes 1 positional argument but 2 were given`

- [ ] **Step 3: 實作 verification.py**

1. 刪除第 17 行 `CANONICAL_REPOSITORY = "hamanpaul/paulsha-conventions"`
2. `_require_manifest_shape` 簽章改為 `def _require_manifest_shape(manifest: dict[str, Any], expected_repository: str) -> None:`
3. 第 122 行比對改為：

```python
    if manifest.get("repository") != expected_repository:
        raise BundleError("manifest repository is not canonical")
```

4. `load_and_verify_bundle` 簽章改為 `def load_and_verify_bundle(bundle_root: Path, *, expected_repository: str) -> dict[str, Any]:`
5. 第 215 行改為 `_require_manifest_shape(manifest, expected_repository)`
6. 第 249 行的內部呼叫改為 `load_and_verify_bundle(bundle_root, expected_repository=expected_repository)`，並替該函式加上同名 keyword-only 參數往上傳遞

- [ ] **Step 4: 更新所有呼叫端**

- `policy_check/runtime_bundle/integrity.py`：從 import 清單移除 `CANONICAL_REPOSITORY`，於檔案加入 `from policy_check.identity import identity`；第 92 行改為 `load_and_verify_bundle(extracted, expected_repository=identity().engine_repo)`
- `policy_check/runtime_bundle/builder.py`：從第 20 行 import 移除 `CANONICAL_REPOSITORY`，加入 `from policy_check.identity import identity`；`_canonical_remote()` 改為 `return remote in identity().remote_urls()`；第 491 行改為 `"repository": identity().engine_repo,`；第 528 行改為 `load_and_verify_bundle(bundle, expected_repository=identity().engine_repo)`
- `policy_check/runtime_bundle/cli.py:65` 改為 `load_and_verify_bundle(Path(args.bundle), expected_repository=identity().engine_repo)`，並加入 import
- `policy_check/preflight.py:700` 改為 `load_and_verify_bundle(path.parent, expected_repository=identity().engine_repo)`
- `tests/test_runtime_bundle.py:47` 的 `integrity.CANONICAL_REPOSITORY` 改為 `"hamanpaul/paulsha-conventions"`（字面值，測試不應依賴已移除的常數）

- [ ] **Step 5: bundle artifact 命名與 manifest distribution 區塊**

發行名稱出現在 **3 處**，三處都要改；**版號語法部分一律逐字保留**（決策 A′：發行編號不進檔名）。

1. `policy_check/runtime_bundle/builder.py:393` 的封存檔名：

```python
    archive = destination / f"paulsha-conventions-v{version}.tar.gz"
```

改為：

```python
    archive = destination / f"{identity().distribution_name}-v{version}.tar.gz"
```

2. `policy_check/runtime_bundle/builder.py:455` 的 bundle 目錄名：

```python
        bundle = temp / f"paulsha-conventions-v{version}"
```

改為：

```python
        bundle = temp / f"{identity().distribution_name}-v{version}"
```

3. `policy_check/runtime_bundle/integrity.py:23` 有一條解析目錄名的正則：

```python
    r"^paulsha-conventions-v\d+\.\d+\.\d+(?:-fix\.\d+)?$"
```

**只把前綴參數化，`v\d+\.\d+\.\d+(?:-fix\.\d+)?` 的部分一字不動**（那是版號語法，屬 Global Constraints 禁區）。改為在使用處以 identity 組出：

```python
import re

from policy_check.identity import identity

def _bundle_dir_re() -> re.Pattern[str]:
    return re.compile(
        r"^" + re.escape(identity().distribution_name)
        + r"-v\d+\.\d+\.\d+(?:-fix\.\d+)?$"
    )
```

並把原本引用該模組層常數的地方改為呼叫 `_bundle_dir_re()`。用函式而非模組層常數，是為了讓 identity 在 import 期之後才被解析。

4. 在 `builder.py` 的 manifest 字典（`"repository"` 那一項附近）新增 distribution 區塊，供安裝期取用；`distribution_build` 僅在有設定時寫入：

```python
            "distribution": {
                "canonical_org": identity().canonical_org,
                "engine_repo": identity().engine_repo,
                "remote_base": identity().remote_base,
                "distribution_name": identity().distribution_name,
                "provider": identity().provider,
                **(
                    {"distribution_build": identity().distribution_build}
                    if identity().distribution_build is not None
                    else {}
                ),
            },
```

`_require_manifest_shape` 只檢查特定鍵，新增鍵不影響既有驗證。

- [ ] **Step 5b: 驗證 upstream artifact 名稱未改變**

Run: `python3 -m pytest tests/test_runtime_bundle.py -q`
Expected: PASS —— 內建 identity 的 `distribution_name` 就是 `paulsha-conventions`，且未設 `distribution_build`，故 upstream 的檔名、目錄名與正則行為與改動前完全相同。若有測試因名稱改變而失敗，表示某處誤用了 `distribution_build`。

- [ ] **Step 6: 執行測試確認通過**

Run: `python3 -m pytest tests/test_runtime_bundle.py -q`
Expected: PASS

- [ ] **Step 7: 全套件迴歸與 commit**

Run: `python3 -m pytest -q`
Expected: 全綠

```bash
git add policy_check/runtime_bundle/ policy_check/preflight.py tests/test_runtime_bundle.py
git commit -m "refactor(portability): runtime bundle 的 repository 身分改為參數傳入（#63）"
```

---

### Task 5: 安裝期寫入身分、swap 演練與文件同步

**Files:**
- Modify: runtime bundle 的 `install.sh`（路徑以 `grep -rn "install.sh" policy_check/runtime_bundle/ docs/` 確認；bundle 版型見 `docs/runtime-bundle-runbook.md`）
- Create: `tests/test_identity_swap.py`
- Modify: `README.md`（新增 distribution identity 段落）
- Modify: `docs/superpowers/specs/2026-08-10-arc-conventions-portability-design.md`（狀態改為「已實作」）

**Interfaces:**
- Consumes: Task 1-4 的全部產出
- Produces: 無新程式介面

- [ ] **Step 1: 寫 swap 演練測試**

建立 `tests/test_identity_swap.py`：

```python
"""swap 演練：驗證「日後切到 ARC GitLab 只需換設定」這項承諾。"""
import pytest

from policy_check import identity as ident


GITLAB_ARC = {
    "canonical_org": "mcu",
    "engine_repo": "mcu/ti/arc-conventions",
    "remote_base": "https://vcs-sw2.arcadyan.com.tw",
    "distribution_name": "arc-conventions",
    "provider": "github",
}


@pytest.fixture
def gitlab_identity(monkeypatch):
    ident.identity.cache_clear()
    monkeypatch.setattr(ident, "_load_raw", lambda: dict(GITLAB_ARC))
    yield
    ident.identity.cache_clear()


def test_remote_urls_follow_non_github_base(gitlab_identity):
    assert ident.identity().remote_urls() == {
        "https://vcs-sw2.arcadyan.com.tw/mcu/ti/arc-conventions",
        "ssh://git@vcs-sw2.arcadyan.com.tw/mcu/ti/arc-conventions",
        "git@vcs-sw2.arcadyan.com.tw:mcu/ti/arc-conventions",
    }


def test_bundle_verification_follows_swapped_identity(gitlab_identity):
    from policy_check.runtime_bundle import verification

    manifest = {
        "schema_version": verification.SCHEMA_VERSION,
        "policy_version": "1.0.15",
        "skill_version": "1.0.15",
        "repository": "mcu/ti/arc-conventions",
        "release_tag": "v1.0.15",
        "release_commit": "0" * 40,
    }
    verification._require_manifest_shape(manifest, ident.identity().engine_repo)
```

- [ ] **Step 2: 執行測試確認通過**

Run: `python3 -m pytest tests/test_identity_swap.py -q`
Expected: PASS，2 passed（Task 1-4 已提供全部能力；本測試是對承諾的驗收，不需新程式碼）

若 FAIL，表示前面 task 有遺漏的硬編碼，回頭修正後再繼續。

- [ ] **Step 3: 安裝期寫入身分**

`install.sh` **不是 repo 內的檔案**，而是由 `policy_check/runtime_bundle/builder.py:471` 以 `installer.write_text(INSTALLER, ...)` 產生。因此要改的是同檔的 `INSTALLER` 字串常數。

Run: `grep -n "^INSTALLER" policy_check/runtime_bundle/builder.py`

在 `INSTALLER` 的 wheel 安裝步驟之後，加入下列片段。它從 bundle 根目錄的 `manifest.json` 讀 `distribution` 區塊（Task 4 Step 5 已寫入），再寫進安裝出的套件：

```sh
python3 - "$(dirname "$0")/manifest.json" <<'PY'
import json, pathlib, sys, importlib.util

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
dist = manifest.get("distribution")
if not dist:
    raise SystemExit("manifest is missing distribution identity")
spec = importlib.util.find_spec("policy_check.data")
if spec is None or not spec.submodule_search_locations:
    raise SystemExit("installed policy_check.data not found")
target = pathlib.Path(spec.submodule_search_locations[0]) / "distribution.yml"
target.write_text(
    "".join(
        f"{key}: {dist[key]}\n"
        for key in (
            "canonical_org",
            "engine_repo",
            "remote_base",
            "distribution_name",
            "provider",
        )
    ),
    encoding="utf-8",
)
PY
```

缺 `distribution` 區塊即中止安裝（fail-closed），不得沿用 wheel 內的預設身分。

- [ ] **Step 4: 更新 README**

在 README 的 Usage 之後新增一段（中英雙語區塊各一份，比照既有結構）：

```markdown
### Distribution identity

引擎的發行身分（canonical org、engine repo、remote base、distribution name、provider）
記於 `policy_check/data/distribution.yml`，於**安裝期**決定、**執行期唯讀**。
它屬於「被安裝的這份引擎」，不屬於「被檢查的 repo」——`.project-policy.yml` 的
`conventions_engine.repo` 只能宣告與其一致，不能改指向；不一致一律
`PreflightGateError`。缺漏或不合法時 fail-closed，不回退預設值。
```

- [ ] **Step 5: 更新 spec 狀態**

把 spec 開頭的「狀態：設計待審」改為「狀態：已實作（見 `docs/superpowers/plans/2026-08-10-arc-conventions-portability.md`）」。

- [ ] **Step 6: 全套件迴歸、dogfood 與 commit**

Run: `python3 -m pytest -q`
Expected: 全綠

Run: `python3 -m policy_check --repo .`
Expected: `fail: 0`（R-22 的 3 筆既有 dangling reference warn 屬預期）

```bash
git add -A
git commit -m "feat(portability): 安裝期寫入 distribution identity 並補文件（#63）"
```

---

## 驗收對照（對應 issue #63）

| 驗收條件 | 由哪個 task 滿足 |
| --- | --- |
| 既有 `hamanpaul/*` repo 行為不變 | Task 1 內建值等於原常數；每個 task 的全套件迴歸 |
| 可用非 github.com 的 remote 完成 engine pin 驗證 | Task 3 + Task 5 Step 1-2 的 swap 演練 |
| runtime bundle 可用非 `paulsha-conventions` 身分產出並通過 verification | Task 4 + Task 5 Step 2 |
| R-15 / R-20 在 gitlab 下的行為 | **不在階段一**（Global Constraints 已排除） |
| R-23 信任模型變更有文件說明 | Task 5 Step 4（README）+ spec |
| `ot-ti-mirror` 能完成一次完整 policy-check | **不在本計畫**，屬 ot-ti-mirror 側落地工作 |
