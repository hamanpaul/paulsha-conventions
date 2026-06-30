# CHANGELOG per-PR fragment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 CHANGELOG 從共用 `[Unreleased]` 區段改為 `changelog.d/<issue>-<slug>.md` 每 PR 一碎片，消除並行 agent 的 merge conflict；release 時用 `policy_check.changelog collate` 收斂成 Keep-a-Changelog dated 段。

**Architecture:** 新增 `policy_check/changelog.py`（純邏輯 frontmatter 解析 + type→KaC 段映射 + 產段；I/O 邊緣讀/寫/刪；CLI `collate` 子命令，比照 `policy_check/drift.py`）。改寫 `R-09`（驗 `changed_files` 含 `changelog.d/*.md`）與 `R-04`（移除 `[Unreleased]` 必備）。本 repo dogfood + 文件。

**Tech Stack:** Python 3.11+、`yaml`（PyYAML，已用於 config）、`argparse`、`pytest`。

---

## File Structure

- Create `policy_check/changelog.py` — fragment 解析、type 映射、產段（純邏輯）+ collate I/O + CLI `main()`。
- Create `tests/test_changelog.py` — changelog.py 單元測試。
- Modify `policy_check/rules/r09_code_changelog_sync.py` — 改驗 fragment。
- Modify `tests/test_rule_r09_code_changelog_sync.py` — 改寫測試。
- Modify `policy_check/rules/r04_changelog_format.py` — 移除 `[Unreleased]` 必備。
- Modify `tests/test_rule_r04_changelog_format.py` — 改寫測試。
- Create `changelog.d/.gitkeep` + `changelog.d/24-changelog-fragments.md` — dogfood。
- Modify `CHANGELOG.md` — 移除 `## [Unreleased]` 標頭（保留歷史 dated 段）。
- Modify `CLAUDE.md`、`README.md` — 文件。

---

## Task 1: changelog.py 純邏輯 — fragment 解析

**Files:**
- Create: `policy_check/changelog.py`
- Test: `tests/test_changelog.py`

- [ ] **Step 1: 寫 failing test（frontmatter 解析）**

```python
# tests/test_changelog.py
from __future__ import annotations
import pytest
from policy_check import changelog as cl


def test_parse_fragment_extracts_type_and_body():
    text = "---\ntype: feat\nscope: changelog\nissue: 24\n---\n並行安全的碎片模型。\n"
    frag = cl.parse_fragment(text)
    assert frag.type == "feat"
    assert frag.scope == "changelog"
    assert frag.issue == 24
    assert frag.body == "並行安全的碎片模型。"


def test_parse_fragment_missing_type_raises():
    with pytest.raises(cl.FragmentError):
        cl.parse_fragment("---\nscope: x\n---\n沒有 type。\n")


def test_parse_fragment_optional_fields_default_none():
    frag = cl.parse_fragment("---\ntype: fix\n---\n只修一個 bug。\n")
    assert frag.type == "fix" and frag.scope is None and frag.issue is None
    assert frag.body == "只修一個 bug。"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest -q tests/test_changelog.py -k parse_fragment`
Expected: FAIL — `ImportError: cannot import name 'changelog'`（模組不存在）

- [ ] **Step 3: 實作 parse_fragment（最小）**

```python
# policy_check/changelog.py
"""CHANGELOG per-PR fragment model + release collation (ops tool, NOT an R-xx rule)."""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


class FragmentError(Exception):
    """Raised when a changelog fragment is malformed."""


@dataclass
class Fragment:
    type: str
    body: str
    scope: str | None = None
    issue: int | None = None


def parse_fragment(text: str) -> Fragment:
    if not text.startswith("---"):
        raise FragmentError("fragment must start with a YAML frontmatter block")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise FragmentError("fragment frontmatter block is not closed")
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise FragmentError(f"invalid frontmatter YAML: {exc}") from exc
    if not isinstance(meta, dict):
        raise FragmentError("frontmatter must be a mapping")
    ftype = meta.get("type")
    if not ftype or not isinstance(ftype, str):
        raise FragmentError("fragment frontmatter requires a string 'type'")
    body = parts[2].strip()
    if not body:
        raise FragmentError("fragment body must not be empty")
    issue = meta.get("issue")
    return Fragment(
        type=ftype,
        body=body,
        scope=meta.get("scope"),
        issue=int(issue) if issue is not None else None,
    )
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest -q tests/test_changelog.py -k parse_fragment`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add policy_check/changelog.py tests/test_changelog.py
git commit -m "feat: #24 changelog fragment 解析（frontmatter → Fragment）"
```

---

## Task 2: changelog.py 純邏輯 — type 映射與產段

**Files:**
- Modify: `policy_check/changelog.py`
- Test: `tests/test_changelog.py`

- [ ] **Step 1: 寫 failing test（映射 + 產段 + 未知 type）**

```python
def test_render_section_groups_by_type_in_fixed_order():
    frags = [
        cl.Fragment(type="fix", body="修 A。"),
        cl.Fragment(type="feat", body="加 B。"),
        cl.Fragment(type="refactor", body="重構 C。"),
    ]
    out = cl.render_section("1.0.9", "2026-06-30", frags)
    assert out.startswith("## [1.0.9] - 2026-06-30\n")
    # Added 在 Changed 之前、Changed 在 Fixed 之前
    assert out.index("### Added") < out.index("### Changed") < out.index("### Fixed")
    assert "- 加 B。" in out and "- 重構 C。" in out and "- 修 A。" in out


def test_render_section_unknown_type_raises():
    with pytest.raises(cl.FragmentError):
        cl.render_section("1.0.9", "2026-06-30", [cl.Fragment(type="wat", body="x")])


def test_render_section_preserves_within_group_order():
    frags = [cl.Fragment(type="feat", body="第一"), cl.Fragment(type="feat", body="第二")]
    out = cl.render_section("1.0.9", "2026-06-30", frags)
    assert out.index("- 第一") < out.index("- 第二")
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest -q tests/test_changelog.py -k render_section`
Expected: FAIL — `AttributeError: module 'policy_check.changelog' has no attribute 'render_section'`

- [ ] **Step 3: 實作映射與 render_section**

```python
# 加到 policy_check/changelog.py（FragmentError/Fragment 之後）
TYPE_TO_SECTION = {
    "feat": "Added",
    "fix": "Fixed",
    "refactor": "Changed",
    "perf": "Changed",
    "change": "Changed",
    "remove": "Removed",
    "deprecate": "Deprecated",
    "security": "Security",
}
SECTION_ORDER = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]


def render_section(version: str, date: str, fragments: list[Fragment]) -> str:
    grouped: dict[str, list[str]] = {}
    for frag in fragments:
        section = TYPE_TO_SECTION.get(frag.type)
        if section is None:
            raise FragmentError(
                f"unknown fragment type {frag.type!r}; "
                f"allowed: {sorted(TYPE_TO_SECTION)}"
            )
        grouped.setdefault(section, []).append(frag.body)
    lines = [f"## [{version}] - {date}", ""]
    for section in SECTION_ORDER:
        if section not in grouped:
            continue
        lines.append(f"### {section}")
        lines.extend(f"- {body}" for body in grouped[section])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest -q tests/test_changelog.py -k render_section`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add policy_check/changelog.py tests/test_changelog.py
git commit -m "feat: #24 changelog type→KaC 段映射與產段"
```

---

## Task 3: changelog.py — collate I/O + CLI

**Files:**
- Modify: `policy_check/changelog.py`
- Test: `tests/test_changelog.py`

- [ ] **Step 1: 寫 failing test（collate 端到端）**

```python
def _write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_collate_inserts_section_and_clears_fragments(tmp_path):
    _write(tmp_path / "CHANGELOG.md",
           "# Changelog\n\n本專案變更記錄。\n\n## [1.0.8] - 2026-06-30\n\n### Added\n- 舊東西。\n")
    _write(tmp_path / "changelog.d" / ".gitkeep", "")
    _write(tmp_path / "changelog.d" / "24-frag.md", "---\ntype: feat\n---\n加新東西。\n")
    _write(tmp_path / "changelog.d" / "30-fix.md", "---\ntype: fix\n---\n修個 bug。\n")

    cl.collate(tmp_path, "1.0.9", "2026-07-01")

    text = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    # 新段在 # Changelog 之後、舊 [1.0.8] 之前
    assert text.index("## [1.0.9] - 2026-07-01") < text.index("## [1.0.8]")
    assert "- 加新東西。" in text and "- 修個 bug。" in text
    # fragment 檔被刪、.gitkeep 保留
    assert not (tmp_path / "changelog.d" / "24-frag.md").exists()
    assert not (tmp_path / "changelog.d" / "30-fix.md").exists()
    assert (tmp_path / "changelog.d" / ".gitkeep").exists()


def test_collate_cli_main(tmp_path):
    _write(tmp_path / "CHANGELOG.md", "# Changelog\n\n## [1.0.8] - 2026-06-30\n\n### Added\n- x。\n")
    _write(tmp_path / "changelog.d" / "24-frag.md", "---\ntype: feat\n---\nCLI 路徑。\n")
    rc = cl.main(["collate", "--repo", str(tmp_path), "--version", "1.0.9", "--date", "2026-07-01"])
    assert rc == 0
    assert "CLI 路徑。" in (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest -q tests/test_changelog.py -k collate`
Expected: FAIL — `AttributeError: ... has no attribute 'collate'`

- [ ] **Step 3: 實作 collate + insert + main**

```python
# 加到 policy_check/changelog.py
import re

_FRAGMENT_GLOB = "*.md"
_DATED_SECTION_RE = re.compile(r"(?m)^##\s+\[")


def load_fragments(repo_root: Path) -> list[tuple[str, Fragment]]:
    """Return (filename, Fragment) for each changelog.d/*.md, sorted by filename."""
    d = repo_root / "changelog.d"
    if not d.is_dir():
        return []
    out = []
    for path in sorted(d.glob(_FRAGMENT_GLOB)):
        out.append((path.name, parse_fragment(path.read_text(encoding="utf-8"))))
    return out


def _insert_section(changelog_text: str, section: str) -> str:
    """Insert `section` before the first dated `## [` heading; else append."""
    m = _DATED_SECTION_RE.search(changelog_text)
    block = section.rstrip() + "\n\n"
    if m:
        return changelog_text[:m.start()] + block + changelog_text[m.start():]
    return changelog_text.rstrip() + "\n\n" + block


def collate(repo_root: Path, version: str, date: str) -> int:
    """Collate changelog.d/*.md into a dated CHANGELOG section; return fragment count."""
    loaded = load_fragments(repo_root)
    if not loaded:
        return 0
    fragments = [frag for _name, frag in loaded]
    section = render_section(version, date, fragments)  # raises on unknown type
    changelog_path = repo_root / "CHANGELOG.md"
    text = changelog_path.read_text(encoding="utf-8")
    changelog_path.write_text(_insert_section(text, section), encoding="utf-8")
    for name, _frag in loaded:
        (repo_root / "changelog.d" / name).unlink()
    return len(loaded)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="policy-check-changelog")
    sub = p.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("collate", help="Collate changelog.d/*.md into a dated CHANGELOG section")
    pc.add_argument("--repo", default=".")
    pc.add_argument("--version", required=True)
    pc.add_argument("--date", required=True)
    args = p.parse_args(argv)
    if args.cmd == "collate":
        n = collate(Path(args.repo), args.version, args.date)
        print(f"collated {n} fragment(s) into [{args.version}] - {args.date}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest -q tests/test_changelog.py`
Expected: PASS（全部）

- [ ] **Step 5: Commit**

```bash
git add policy_check/changelog.py tests/test_changelog.py
git commit -m "feat: #24 changelog collate（讀 changelog.d → 插段 → 清碎片）+ CLI"
```

---

## Task 4: R-09 改驗 fragment

**Files:**
- Modify: `policy_check/rules/r09_code_changelog_sync.py`
- Test: `tests/test_rule_r09_code_changelog_sync.py`

- [ ] **Step 1: 寫/改 failing test**

把既有「[Unreleased] 有 bullet」測試改為「有 changelog.d fragment」。新增/改寫：

```python
def test_r09_code_change_with_fragment_passes(tmp_path):
    repo = _repo_with_code_change(tmp_path, changed=["policy_check/x.py", "changelog.d/24-foo.md"])
    assert get_rule("R-09").check(_ctx(repo, changed_files=["policy_check/x.py", "changelog.d/24-foo.md"])).status == Status.PASS


def test_r09_code_change_without_fragment_fails(tmp_path):
    assert get_rule("R-09").check(_ctx(tmp_path, changed_files=["policy_check/x.py"])).status == Status.FAIL


def test_r09_skip_label(tmp_path):
    res = get_rule("R-09").check(_ctx(tmp_path, changed_files=["policy_check/x.py"], labels=["skip-changelog"]))
    assert res.status == Status.SKIP


def test_r09_no_code_change_passes(tmp_path):
    assert get_rule("R-09").check(_ctx(tmp_path, changed_files=["README.md"])).status == Status.PASS
```

（依現有測試檔的 helper 形態調整 `_ctx` / `get_rule`；R-09 用 `ctx.changed_files` 與 `code_paths`，預設 code_paths 含 `**/*.py`。）

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest -q tests/test_rule_r09_code_changelog_sync.py`
Expected: FAIL（現行 R-09 看 CHANGELOG `[Unreleased]`，不認 fragment）

- [ ] **Step 3: 改寫 R-09**

把 `r09_code_changelog_sync.py` 的 CHANGELOG 讀取/`_unreleased_has_bullet_entry` 換成 fragment 檢查：

```python
from __future__ import annotations

from fnmatch import fnmatch

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


def _pr_added_fragment(changed_files: list[str]) -> bool:
    for f in changed_files:
        if f and fnmatch(f, "changelog.d/*.md") and not f.endswith("/.gitkeep"):
            return True
    return False


@register
class R09CodeChangelogSync:
    rule_id = "R-09"
    exempt_label = "skip-changelog"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(self.rule_id, Status.SKIP,
                              f"Skipped by exemption label: {self.exempt_label}.",
                              exempt_label=self.exempt_label)

        code_paths = ctx.config.get("code_paths") or []
        has_code_change = any(
            any(cf and fnmatch(cf, pat) for pat in code_paths)
            for cf in ctx.changed_files
        )
        if not has_code_change:
            return RuleResult(self.rule_id, Status.PASS, "No code path files changed.")

        if _pr_added_fragment(ctx.changed_files):
            return RuleResult(self.rule_id, Status.PASS,
                              "Code change detected and a changelog.d fragment was added.")
        return RuleResult(self.rule_id, Status.FAIL,
                          "Code files changed but no changelog.d/*.md fragment was added "
                          "(add one, or apply the skip-changelog label).")
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest -q tests/test_rule_r09_code_changelog_sync.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r09_code_changelog_sync.py tests/test_rule_r09_code_changelog_sync.py
git commit -m "feat: #24 R-09 改驗本 PR 是否附 changelog.d fragment"
```

---

## Task 5: R-04 移除 [Unreleased] 必備

**Files:**
- Modify: `policy_check/rules/r04_changelog_format.py:14-17,53`
- Test: `tests/test_rule_r04_changelog_format.py`

- [ ] **Step 1: 寫/改 failing test**

```python
def test_r04_no_unreleased_but_dated_section_passes(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.0.9] - 2026-07-01\n\n### Added\n- x。\n", encoding="utf-8")
    assert get_rule("R-04").check(_ctx(tmp_path)).status == Status.PASS


def test_r04_missing_changelog_header_fails(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text("沒有標頭\n\n## [1.0.9] - 2026-07-01\n", encoding="utf-8")
    assert get_rule("R-04").check(_ctx(tmp_path)).status == Status.FAIL
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python3 -m pytest -q tests/test_rule_r04_changelog_format.py -k no_unreleased`
Expected: FAIL（現行 R-04 仍要求 `## [Unreleased]`）

- [ ] **Step 3: 改 R-04**

`policy_check/rules/r04_changelog_format.py`：從 `_required_patterns` 移除 `## [Unreleased]` 那項；PASS 訊息改掉。

```python
    _required_patterns = {
        "# Changelog": re.compile(r"(?m)^#\s+Changelog\s*$"),
    }
```
並把 line 53 PASS 訊息 `"... includes # Changelog and ## [Unreleased]."` 改為 `f"{changelog.name} includes # Changelog header."`。

- [ ] **Step 4: 跑測試確認通過**

Run: `python3 -m pytest -q tests/test_rule_r04_changelog_format.py`
Expected: PASS（既有 [Unreleased]-present 的測試若存在，需一併調整為不再依賴該段；present 仍應 PASS——因為只移除「必備」不移除「允許」）

- [ ] **Step 5: Commit**

```bash
git add policy_check/rules/r04_changelog_format.py tests/test_rule_r04_changelog_format.py
git commit -m "feat: #24 R-04 不再要求 [Unreleased]（保留 # Changelog + dated 段）"
```

---

## Task 6: 本 repo dogfood

**Files:**
- Create: `changelog.d/.gitkeep`, `changelog.d/24-changelog-fragments.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 建 changelog.d/ + 本案 fragment**

```bash
mkdir -p changelog.d && : > changelog.d/.gitkeep
```
`changelog.d/24-changelog-fragments.md`：
```markdown
---
type: feat
scope: changelog
issue: 24
---
CHANGELOG 改 per-PR fragment（`changelog.d/<issue>-<slug>.md`）消除並行 agent 的 `[Unreleased]` 衝突：R-09 改驗本 PR 有無 fragment、R-04 不再要求 `[Unreleased]`、新增 `python3 -m policy_check.changelog collate` 於 release 收斂碎片成 Keep-a-Changelog dated 段。
```

- [ ] **Step 2: 移除本 repo CHANGELOG 的 [Unreleased] 標頭**

把 `CHANGELOG.md` 的 `## [Unreleased]` 區段標頭移除（保留其下歷史內容並入緊接的處理：把現存 `[Unreleased]` 內未切段的 backlog 維持原位作為歷史，僅刪掉 `## [Unreleased]` 那一行與其空行，使後續 dated 段成為主體）。**不**回頭重切舊版段。

- [ ] **Step 3: 驗證 R-04/R-09 對本 repo 通過**

Run: `python3 -m policy_check --repo . --only R-04,R-09 --pr-base-ref main`
Expected: R-04 PASS（無 [Unreleased] 仍過）、R-09 PASS（本 PR 有 `changelog.d/24-*.md`，需 `--pr-base-ref` 讓 changed_files 含它）

- [ ] **Step 4: Commit**

```bash
git add changelog.d CHANGELOG.md
git commit -m "chore: #24 dogfood changelog.d + 移除本 repo [Unreleased] 標頭"
```

---

## Task 7: 文件（CLAUDE.md + README）

**Files:**
- Modify: `CLAUDE.md`（canonical；三 symlink 自動跟隨）
- Modify: `README.md`

- [ ] **Step 1: 改 CLAUDE.md checklist**

把「改 code 時」與「claim done 前」兩處的 `同步更新 CHANGELOG.md [Unreleased]` / `[Unreleased] 有對應 entry` 改為 `新增 changelog.d/<issue>-<slug>.md fragment（或 skip-changelog + 理由）`。

- [ ] **Step 2: 改 README**

- 規則表 R-04（移除 [Unreleased] 必備描述）、R-09（改驗 fragment）。
- 新增「CHANGELOG fragment 模型」小節：`changelog.d/<issue>-<slug>.md` 格式、type→段映射、`python3 -m policy_check.changelog collate --version X.Y.Z --date YYYY-MM-DD` 收斂指令。

- [ ] **Step 3: 本任務的 fragment（文件變動也記）**

文件變動屬 docs；若 README/CLAUDE 變動觸發 R-09（非 code_paths，不會），無需額外 fragment。Task 6 的 fragment 已涵蓋本案。

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: #24 CLAUDE/README 改述 changelog fragment 模型與 collate"
```

---

## Task 8: 全套驗證

- [ ] **Step 1: 全套件 + gate**

Run: `python3 -m pytest -q`
Expected: 全綠（含新 test_changelog + 改寫的 R-04/R-09）

Run: `python3 -m policy_check --repo .`
Expected: 0 fail（R-04/R-09 對本 repo 的 dogfood 狀態通過；R-22 pre-existing `./LICENSE` advisory WARN 不算 fail）

- [ ] **Step 2: 勾選 openspec tasks.md 並準備 review/archive**

---

## Self-Review

- **Spec coverage**：spec 的 4 個 requirement（fragment 模型 / R-09 / R-04 / collate）各對應 Task 1-6；並行不衝突由 Task 6 dogfood + spec scenario 驗證。✅
- **Placeholder scan**：無 TBD；每 step 有實際 code/command。✅
- **Type consistency**：`Fragment`、`parse_fragment`、`render_section`、`collate`、`load_fragments`、`main`、`_pr_added_fragment`、`TYPE_TO_SECTION`、`SECTION_ORDER` 全程一致。✅
