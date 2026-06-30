# Doc Rule Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 補強現有 doc-related rules 的 scope，並新增 deterministic 的 omission / generated-fact gates，讓 issue #26 的盲區可被 engine 穩定偵測。

**Architecture:** 這批變更分成三層。先抽出 shared canonical doc scope（`doc_paths`）供 `R-18` / `R-22` 共用，再新增 `R-25`（doc coverage）與 `R-26`（generated fact sync）兩條 opt-in 規則。共享邏輯只抽兩個小 helper：`_doc_scope.py` 管 docs 範圍，`_marker_sync.py` 管 marker/command 執行；coverage extractor 留在 `r25_doc_coverage.py` 內，避免過早抽象。

**Tech Stack:** Python 3.12、`fnmatch`、`re`、`subprocess`、git-based temp repo tests、pytest、YAML config parsing。

---

## File Structure

- Create: `policy_check/rules/_doc_scope.py` — shared canonical doc scope defaults + glob matching helper
- Create: `policy_check/rules/_marker_sync.py` — shared marker block extraction / command execution helper
- Create: `policy_check/rules/r25_doc_coverage.py` — deterministic coverage gate
- Create: `policy_check/rules/r26_generated_fact_sync.py` — generic generated-fact sync gate
- Create: `tests/test_rule_r25_doc_coverage.py` — temp-git-repo tests for `R-25`
- Create: `tests/test_rule_r26_generated_fact_sync.py` — temp-repo tests for `R-26`
- Create: `tests/test_self_dogfood_doc_rules.py` — self-dogfood assertions for this repo’s config/docs
- Modify: `policy_check/config.py:6-49` — add `doc_paths` default
- Modify: `policy_check/rules/r08_policy_config_schema.py:80-180` — validate `doc_paths`, `doc_coverage`, `generated_facts`
- Modify: `policy_check/rules/r18_docs_sync.py:9-54` — replace hard-coded docs scope with shared helper
- Modify: `policy_check/rules/r22_doc_reference.py:18-139` — derive candidate docs from shared helper while preserving built-in exclusions
- Modify: `policy_check/rules/r16_cli_help_sync.py:12-132` — reuse shared marker/command helper without changing `cli-help` behavior
- Modify: `tests/test_rule_r08_policy_config_schema.py:74-201` — config schema regressions for new surfaces
- Modify: `tests/test_rule_r18_docs_sync.py:9-65` — custom `doc_paths` regressions
- Modify: `tests/test_rule_r22_doc_reference.py:35-207` — custom-scope `R-22` regressions
- Modify: `.paul-project.yml:1-31` — dogfood `doc_paths` for this repo
- Modify: `README.md:44-61,129` — update rule table / governance text / config docs
- Modify: `CHANGELOG.md:8-40` — add `[Unreleased]` entry for #26

## Task 1: Shared canonical doc scope foundation (`doc_paths`, `R-08`, `R-18`)

**Files:**
- Create: `policy_check/rules/_doc_scope.py`
- Modify: `policy_check/config.py:6-49`
- Modify: `policy_check/rules/r08_policy_config_schema.py:80-180`
- Modify: `policy_check/rules/r18_docs_sync.py:9-54`
- Modify: `tests/test_rule_r08_policy_config_schema.py:74-201`
- Modify: `tests/test_rule_r18_docs_sync.py:9-65`

- [ ] **Step 1: Write the failing tests for `doc_paths` schema and `R-18` custom scope**

Add these tests to `tests/test_rule_r08_policy_config_schema.py`:

```python
def test_r08_fail_when_doc_paths_is_not_list(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\ndoc_paths: CLAUDE.md\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "doc_paths" in result.message


def test_r08_pass_when_doc_paths_is_string_list(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\n"
        "doc_paths: [\"README.md\", \"docs/**\", \"CLAUDE.md\"]\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS
```

Change `tests/test_rule_r18_docs_sync.py` so `make_ctx()` can accept config overrides, then add:

```python
def make_ctx(
    repo_root: Path,
    changed_files: list[str] | None = None,
    labels: list[str] | None = None,
    *,
    config: dict | None = None,
) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.1",
        config=config or {"code_paths": ["**/*.py", "**/*.sh", "scripts/**"]},
        changed_files=changed_files or [],
        pr_labels=labels or [],
    )


def test_r18_pass_when_code_change_with_custom_doc_path(tmp_path):
    result = get_rule("R-18").check(
        make_ctx(
            tmp_path,
            changed_files=["policy_check/foo.py", "CLAUDE.md"],
            config={
                "code_paths": ["**/*.py", "**/*.sh", "scripts/**"],
                "doc_paths": ["README.md", "docs/**", "CLAUDE.md"],
            },
        )
    )
    assert result.status == Status.PASS


def test_r18_warn_when_custom_doc_path_not_touched(tmp_path):
    result = get_rule("R-18").check(
        make_ctx(
            tmp_path,
            changed_files=["policy_check/foo.py"],
            config={
                "code_paths": ["**/*.py", "**/*.sh", "scripts/**"],
                "doc_paths": ["README.md", "docs/**", "CLAUDE.md"],
            },
        )
    )
    assert result.status == Status.WARN
```

- [ ] **Step 2: Run the targeted tests to prove RED**

Run:

```bash
python3 -m pytest tests/test_rule_r08_policy_config_schema.py -k doc_paths -q
python3 -m pytest tests/test_rule_r18_docs_sync.py -k custom_doc_path -q
```

Expected:
- the R-08 test fails because `doc_paths` is not validated yet
- the R-18 custom-scope test fails because `R-18` still ignores `CLAUDE.md`

- [ ] **Step 3: Implement the shared doc scope helper and wire it into config / `R-08` / `R-18`**

Create `policy_check/rules/_doc_scope.py`:

```python
from __future__ import annotations

from fnmatch import fnmatch

DEFAULT_DOC_PATHS = ("README.md", "docs/**")


def configured_doc_paths(config: dict | None) -> list[str]:
    raw = (config or {}).get("doc_paths") or list(DEFAULT_DOC_PATHS)
    return [str(item) for item in raw]


def matches_doc_path(rel: str, doc_paths: list[str]) -> bool:
    return any(fnmatch(rel, pattern) for pattern in doc_paths)


def is_canonical_doc(rel: str, config: dict | None) -> bool:
    return matches_doc_path(rel, configured_doc_paths(config))
```

Update `policy_check/config.py`:

```python
from pathlib import Path
import yaml

REQUIRED_KEYS = {"policy_profile", "policy_version"}
VALID_PROFILES = {"stage-driven", "flat"}
CONFIG_NAMES = (".project-policy.yml", ".paul-project.yml")
CONFIG_NAMES_DISPLAY = " or ".join(CONFIG_NAMES)
DEFAULT_CODE_PATHS = {
    "stage-driven": ["**/*.py", "**/*.sh", "scripts/**"],
    "flat": ["**/*.py", "**/*.sh", "scripts/**"],
}
DEFAULT_DOC_PATHS = ["README.md", "docs/**"]


def load(repo_root: Path) -> dict:
    path = config_path(repo_root)
    if not path.exists():
        raise ConfigError(f"{CONFIG_NAMES_DISPLAY} not found at repository root.")
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} is not valid YAML: {exc}") from exc
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise ConfigError(f"{path.name} missing keys: {sorted(missing)}")
    if data["policy_profile"] not in VALID_PROFILES:
        raise ConfigError(
            f"policy_profile must be one of {VALID_PROFILES}, got {data['policy_profile']}"
        )
    data.setdefault("code_paths", DEFAULT_CODE_PATHS[data["policy_profile"]])
    data.setdefault("doc_paths", list(DEFAULT_DOC_PATHS))
    data.setdefault("cli", [])
    agent_files = data.get("agent_files")
    if not isinstance(agent_files, dict):
        agent_files = {}
    agent_files.setdefault("mode", "copy")
    data["agent_files"] = agent_files
    return data
```

Update `policy_check/rules/r08_policy_config_schema.py`:

```python
        doc_paths = data.get("doc_paths")
        if doc_paths is not None and (
            not isinstance(doc_paths, list) or not all(isinstance(x, str) for x in doc_paths)
        ):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="doc_paths must be a list of strings",
            )
```

Update `policy_check/rules/r18_docs_sync.py`:

```python
from fnmatch import fnmatch

from policy_check.rules._doc_scope import is_canonical_doc
from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R18DocsSync:
    rule_id = "R-18"
    exempt_label = "policy-exempt:docs-sync"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"R-18 exempted by label: {self.exempt_label}",
                exempt_label=self.exempt_label,
            )
        code_paths = ctx.config.get("code_paths") or []
        has_code_change = any(
            any(fnmatch(changed_file, pattern) for pattern in code_paths)
            for changed_file in ctx.changed_files
        )
        if not has_code_change:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No code path files changed.",
            )
        if any(is_canonical_doc(changed_file, ctx.config) for changed_file in ctx.changed_files):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="Code change detected and canonical docs were updated.",
            )
        return RuleResult(
            rule_id=self.rule_id,
            status=Status.WARN,
            message=(
                "Code changed but no canonical docs update detected (advisory). "
                "Update docs if behavior changed, or apply the policy-exempt:docs-sync label."
            ),
        )
```

- [ ] **Step 4: Re-run the targeted tests until they pass**

Run:

```bash
python3 -m pytest tests/test_rule_r08_policy_config_schema.py -k doc_paths -q
python3 -m pytest tests/test_rule_r18_docs_sync.py -k custom_doc_path -q
```

Expected: all selected tests PASS.

- [ ] **Step 5: Commit the foundation changes**

```bash
git add policy_check/config.py \
        policy_check/rules/_doc_scope.py \
        policy_check/rules/r08_policy_config_schema.py \
        policy_check/rules/r18_docs_sync.py \
        tests/test_rule_r08_policy_config_schema.py \
        tests/test_rule_r18_docs_sync.py
git commit -m "feat: add canonical doc scope support"
```

## Task 2: Extend `R-22` to use shared canonical doc scope without regressing exclusions

**Files:**
- Modify: `policy_check/rules/r22_doc_reference.py:18-139`
- Modify: `tests/test_rule_r22_doc_reference.py:35-207`
- Reuse: `policy_check/rules/_doc_scope.py`

- [ ] **Step 1: Write the failing `R-22` custom-scope regressions**

Add these tests to `tests/test_rule_r22_doc_reference.py`:

```python
def test_r22_scans_custom_doc_path(tmp_path):
    _init_repo(tmp_path)
    _write(
        tmp_path,
        ".paul-project.yml",
        _cfg_text('doc_paths: ["README.md", "docs/**", "CLAUDE.md"]\n'),
    )
    _write(tmp_path, "CLAUDE.md", "see `policy_check/rules/missing_rule.py`\n")
    _commit(tmp_path)
    res = get_rule().check(make_ctx(tmp_path))
    assert res.status == Status.WARN
    assert "CLAUDE.md" in res.detail


def test_r22_doc_paths_does_not_override_builtin_exclusions(tmp_path):
    _init_repo(tmp_path)
    _write(
        tmp_path,
        ".paul-project.yml",
        _cfg_text('doc_paths: ["README.md", "docs/**", "docs/superpowers/**"]\n'),
    )
    _write(tmp_path, "docs/superpowers/specs/x.md", "see `ghost_rule.py`\n")
    _commit(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS
```

- [ ] **Step 2: Run the targeted `R-22` regressions to prove RED**

Run:

```bash
python3 -m pytest tests/test_rule_r22_doc_reference.py -k "custom_doc_path or builtin_exclusions" -q
```

Expected: the custom-scope test fails because `_in_scope()` is still hard-coded to `README.md` / `docs/**`.

- [ ] **Step 3: Replace the hard-coded scope logic in `R-22`**

Update `policy_check/rules/r22_doc_reference.py`:

```python
from policy_check.rules._doc_links import (
    LINK_RE as _LINK_RE,
    git_tracked as _git_tracked,
    looks_like_path as _looks_like_path,
    path_candidates as _path_candidates,
    resolve_base as _resolve_base,
)
from policy_check.rules._doc_scope import configured_doc_paths, matches_doc_path

def _in_scope(rel: str, doc_paths: list[str]) -> bool:
    if rel.startswith(_EXCLUDE_PREFIXES):
        return False
    return matches_doc_path(rel, doc_paths)


@register
class R22DocReference:
    rule_id = "R-22"
    exempt_label = "policy-exempt:doc-reference"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                self.rule_id,
                Status.SKIP,
                f"Skipped by exemption label: {self.exempt_label}.",
                exempt_label=self.exempt_label,
            )
        root = ctx.repo_root
        config = ctx.config or {}
        doc_paths = configured_doc_paths(config)
        allow = (config.get("doc_reference") or {}).get("allow", [])
        head_files = _git_tracked(root)
        base = _resolve_base(root, ctx.pr_base_ref)
        base_files = _git_tracked(root, base) if base else set()
        removed_syms = _removed_symbols(root, base) if base else set()
        fails: list[str] = []
        warns: list[str] = []
        for rel in sorted(head_files):
            if not _in_scope(rel, doc_paths) or _is_exempt(rel, allow):
                continue
            try:
                text = (root / rel).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for kind, token, payload in _extract_refs(rel, text):
                if kind == "path" and not any(c in head_files for c in payload):
                    if base and any(c in base_files for c in payload):
                        fails.append(f"{rel} -> {token} (removed this change)")
                    else:
                        warns.append(f"{rel} -> {token}")
                elif kind == "symbol" and payload in removed_syms:
                    fails.append(f"{rel} -> `{payload}` (def/class removed this change)")
        if fails:
            return RuleResult(
                self.rule_id,
                Status.FAIL,
                f"docs contain {len(fails)} dangling reference(s) introduced by this change.",
                detail="\n".join(fails[:20]),
            )
        if warns:
            return RuleResult(
                self.rule_id,
                Status.WARN,
                f"docs contain {len(warns)} pre-existing dangling reference(s) (advisory).",
                detail="\n".join(warns[:20]),
            )
        return RuleResult(self.rule_id, Status.PASS, "No dangling doc references detected.")
```

Do **not** change `_EXCLUDE_PREFIXES`, `_SELF_EXEMPT`, diff-aware severity, or symbol logic in this task.

- [ ] **Step 4: Re-run the `R-22` regressions**

Run:

```bash
python3 -m pytest tests/test_rule_r22_doc_reference.py -k "custom_doc_path or builtin_exclusions" -q
python3 -m pytest tests/test_rule_r22_doc_reference.py -q
```

Expected: the new regressions PASS, then the full `R-22` test file PASSes.

- [ ] **Step 5: Commit the `R-22` scope change**

```bash
git add policy_check/rules/r22_doc_reference.py \
        tests/test_rule_r22_doc_reference.py
git commit -m "feat: let r22 use canonical doc scope"
```

## Task 3: Implement `R-25` deterministic doc coverage

**Files:**
- Create: `policy_check/rules/r25_doc_coverage.py`
- Modify: `policy_check/rules/r08_policy_config_schema.py:100-180`
- Create: `tests/test_rule_r25_doc_coverage.py`
- Reuse: `policy_check/rules/_doc_scope.py`, `policy_check/rules/_doc_links.py`

- [ ] **Step 1: Write the failing `R-25` tests and schema regressions**

Create `tests/test_rule_r25_doc_coverage.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from policy_check import config as cfg
from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")


def _commit(repo: Path, msg: str = "c") -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _cfg_text(extra: str = "") -> str:
    return "policy_profile: flat\npolicy_version: 1.0.7\ndoc_paths: [\"README.md\"]\n" + extra


def get_rule():
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert "R-25" in loaded, "R-25 is not registered"
    return loaded["R-25"]


def make_ctx(repo: Path, *, base: str | None = None) -> RuleContext:
    return RuleContext(
        repo_root=repo,
        profile="flat",
        policy_version="1.0.7",
        config=cfg.load(repo),
        pr_base_ref=base,
    )


def test_r25_pass_when_not_configured(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", "policy_profile: flat\npolicy_version: 1.0.7\n")
    _commit(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS


def test_r25_fail_when_new_module_is_unmentioned(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(
        "doc_coverage:\n"
        "  mode: changed\n"
        "  targets: [\"README.md\"]\n"
        "  sources:\n"
        "    - kind: modules\n"
        "      include: [\"pkg/**/*.py\"]\n"
    ))
    _write(tmp_path, "README.md", "existing docs only\n")
    base = _commit(tmp_path, "base")
    _write(tmp_path, "pkg/new_feature.py", "VALUE = 1\n")
    _commit(tmp_path, "head")
    res = get_rule().check(make_ctx(tmp_path, base=base))
    assert res.status == Status.FAIL
    assert "pkg/new_feature.py" in (res.detail or "")


def test_r25_pass_when_new_module_is_mentioned(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(
        "doc_coverage:\n"
        "  mode: changed\n"
        "  targets: [\"README.md\"]\n"
        "  sources:\n"
        "    - kind: modules\n"
        "      include: [\"pkg/**/*.py\"]\n"
    ))
    _write(tmp_path, "README.md", "documents `pkg/new_feature.py`\n")
    base = _commit(tmp_path, "base")
    _write(tmp_path, "pkg/new_feature.py", "VALUE = 1\n")
    _commit(tmp_path, "head")
    assert get_rule().check(make_ctx(tmp_path, base=base)).status == Status.PASS


def test_r25_warn_when_changed_mode_has_no_base(tmp_path):
    _init_repo(tmp_path)
    _write(tmp_path, ".paul-project.yml", _cfg_text(
        "doc_coverage:\n"
        "  mode: changed\n"
        "  targets: [\"README.md\"]\n"
        "  sources:\n"
        "    - kind: modules\n"
        "      include: [\"pkg/**/*.py\"]\n"
    ))
    _write(tmp_path, "README.md", "existing docs only\n")
    _write(tmp_path, "pkg/new_feature.py", "VALUE = 1\n")
    _commit(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.WARN
```

Add these schema tests to `tests/test_rule_r08_policy_config_schema.py`:

```python
def test_r08_fail_when_doc_coverage_mode_is_invalid(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\n"
        "doc_coverage:\n  mode: someday\n  targets: [\"README.md\"]\n  sources: []\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "doc_coverage.mode" in result.message


def test_r08_pass_when_doc_coverage_mode_is_changed(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\n"
        "doc_coverage:\n  mode: changed\n  targets: [\"README.md\"]\n  sources: []\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS
```

- [ ] **Step 2: Run the new tests to prove RED**

Run:

```bash
python3 -m pytest tests/test_rule_r25_doc_coverage.py -q
python3 -m pytest tests/test_rule_r08_policy_config_schema.py -k doc_coverage -q
```

Expected:
- `tests/test_rule_r25_doc_coverage.py` fails with `AssertionError: R-25 is not registered`
- the `doc_coverage` schema test fails because `R-08` does not validate this section yet

- [ ] **Step 3: Implement `R-25` and the `doc_coverage` schema**

Create `policy_check/rules/r25_doc_coverage.py`:

```python
from __future__ import annotations

import os
import re
import shlex
import subprocess
from fnmatch import fnmatch
from pathlib import Path

from policy_check.rules._doc_links import git_tracked, resolve_base
from policy_check.rules._doc_scope import configured_doc_paths, matches_doc_path
from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


def _fact_mentioned(text: str, fact: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_./-]){re.escape(fact)}(?![A-Za-z0-9_./-])"
    return re.search(pattern, text) is not None


def _read_targets(root: Path, targets: list[str]) -> dict[str, str]:
    return {
        target: (root / target).read_text(encoding="utf-8")
        for target in targets
    }


def _extract_modules(files: set[str], source: dict) -> set[str]:
    include = source.get("include") or []
    exclude = source.get("exclude") or []
    selected = {path for path in files if any(fnmatch(path, pat) for pat in include)}
    return {
        path for path in selected
        if not any(fnmatch(path, pat) for pat in exclude)
    }


def _extract_rpc_methods(root: Path, source: dict) -> set[str]:
    pattern = re.compile(str(source["pattern"]))
    facts: set[str] = set()
    for rel in source["include"]:
        text = (root / rel).read_text(encoding="utf-8")
        facts.update(pattern.findall(text))
    return facts


def _extract_env_vars(root: Path, files: set[str], source: dict) -> set[str]:
    token_re = re.compile(rf"\\b{re.escape(str(source['prefix']))}[A-Z0-9_]+\\b")
    facts: set[str] = set()
    for rel in files:
        if any(fnmatch(rel, pat) for pat in source["include"]):
            facts.update(token_re.findall((root / rel).read_text(encoding="utf-8")))
    return facts


def _extract_cli_tree(root: Path, source: dict) -> set[str]:
    proc = subprocess.run(
        shlex.split(str(source["command"])),
        cwd=root,
        env={**os.environ, "LC_ALL": "C"},
        capture_output=True,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cli_tree command failed: {source['command']}")
    return {line.strip() for line in proc.stdout.decode("utf-8", "replace").splitlines() if line.strip()}


@register
class R25DocCoverage:
    rule_id = "R-25"
    exempt_label = None

    def check(self, ctx: RuleContext) -> RuleResult:
        section = (ctx.config or {}).get("doc_coverage")
        if not section:
            return RuleResult(self.rule_id, Status.PASS, "doc_coverage not configured; R-25 not applicable.")
        mode = str(section.get("mode", "changed"))
        if mode not in {"changed", "all"}:
            return RuleResult(self.rule_id, Status.FAIL, "doc_coverage.mode must be 'changed' or 'all'")
        targets = [str(item) for item in (section.get("targets") or [])]
        if not targets:
            return RuleResult(self.rule_id, Status.FAIL, "doc_coverage.targets must not be empty")
        doc_paths = configured_doc_paths(ctx.config)
        for target in targets:
            if not matches_doc_path(target, doc_paths):
                return RuleResult(self.rule_id, Status.FAIL, f"doc_coverage target outside canonical scope: {target}")
            if not (ctx.repo_root / target).is_file():
                return RuleResult(self.rule_id, Status.FAIL, f"doc_coverage target not found: {target}")

        base = resolve_base(ctx.repo_root, ctx.pr_base_ref)
        if mode == "changed" and not base:
            return RuleResult(
                self.rule_id,
                Status.WARN,
                "doc_coverage.mode=changed requires diff context; falling back to advisory WARN.",
            )

        head_files = git_tracked(ctx.repo_root)
        base_files = git_tracked(ctx.repo_root, base) if base else set()
        target_texts = _read_targets(ctx.repo_root, targets)
        sources = section.get("sources") or []

        def _extract_source_facts(root: Path, files: set[str], source: dict) -> set[str]:
            kind = str(source["kind"])
            if kind == "modules":
                return _extract_modules(files, source)
            if kind == "rpc_methods":
                return _extract_rpc_methods(root, source)
            if kind == "env_vars":
                return _extract_env_vars(root, files, source)
            if kind == "cli_tree":
                return _extract_cli_tree(root, source)
            raise ValueError(f"unsupported doc_coverage source kind: {kind}")

        head_facts: set[str] = set()
        base_facts: set[str] = set()
        for source in sources:
            if not isinstance(source, dict) or "kind" not in source:
                return RuleResult(self.rule_id, Status.FAIL, "doc_coverage source entries must be mappings with kind")
            head_facts |= _extract_source_facts(ctx.repo_root, head_files, source)
            if mode == "changed" and base:
                base_facts |= _extract_source_facts(ctx.repo_root, base_files, source)

        required_facts = head_facts - base_facts if mode == "changed" else head_facts
        missing = sorted(
            fact for fact in required_facts
            if not any(_fact_mentioned(text, fact) for text in target_texts.values())
        )
        if missing:
            return RuleResult(
                self.rule_id,
                Status.FAIL,
                f"canonical docs are missing {len(missing)} required fact mention(s).",
                detail="\n".join(missing[:20]),
            )
        return RuleResult(self.rule_id, Status.PASS, "All required facts are mentioned in canonical docs.")
```

Extend `policy_check/rules/r08_policy_config_schema.py` so `doc_coverage` obeys:

```python
        doc_coverage = data.get("doc_coverage")
        if doc_coverage is not None:
            if not isinstance(doc_coverage, dict):
                return RuleResult(self.rule_id, Status.FAIL, "doc_coverage must be a mapping")
            mode = doc_coverage.get("mode")
            if mode is not None and mode not in ("changed", "all"):
                return RuleResult(self.rule_id, Status.FAIL, "doc_coverage.mode must be one of ['changed', 'all']")
            targets = doc_coverage.get("targets")
            if targets is not None and (
                not isinstance(targets, list) or not all(isinstance(x, str) for x in targets)
            ):
                return RuleResult(self.rule_id, Status.FAIL, "doc_coverage.targets must be a list of strings")
            sources = doc_coverage.get("sources")
            if sources is not None and (
                not isinstance(sources, list) or not all(isinstance(x, dict) for x in sources)
            ):
                return RuleResult(self.rule_id, Status.FAIL, "doc_coverage.sources must be a list of mappings")
```

- [ ] **Step 4: Re-run the coverage tests until they pass**

Run:

```bash
python3 -m pytest tests/test_rule_r25_doc_coverage.py -q
python3 -m pytest tests/test_rule_r08_policy_config_schema.py -k doc_coverage -q
```

Expected: both commands PASS.

- [ ] **Step 5: Commit `R-25`**

```bash
git add policy_check/rules/r25_doc_coverage.py \
        policy_check/rules/r08_policy_config_schema.py \
        tests/test_rule_r25_doc_coverage.py \
        tests/test_rule_r08_policy_config_schema.py
git commit -m "feat: add deterministic doc coverage rule"
```

## Task 4: Implement generic marker sync (`R-26`) without breaking `R-16`

**Files:**
- Create: `policy_check/rules/_marker_sync.py`
- Create: `policy_check/rules/r26_generated_fact_sync.py`
- Modify: `policy_check/rules/r16_cli_help_sync.py:12-132`
- Modify: `policy_check/rules/r08_policy_config_schema.py:100-180`
- Create: `tests/test_rule_r26_generated_fact_sync.py`
- Modify: `tests/test_rule_r16_cli_help_sync.py:31-52`

- [ ] **Step 1: Write the failing `R-26` tests**

Create `tests/test_rule_r26_generated_fact_sync.py`:

```python
from __future__ import annotations

from pathlib import Path

from policy_check import config as cfg
from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_repo(tmp_path: Path, extra_config: str = "", readme: str = "") -> Path:
    _write(
        tmp_path,
        ".paul-project.yml",
        "policy_profile: flat\npolicy_version: 1.0.7\n" + extra_config,
    )
    _write(tmp_path, "README.md", readme)
    return tmp_path


def get_rule():
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert "R-26" in loaded, "R-26 is not registered"
    return loaded["R-26"]


def make_ctx(repo: Path) -> RuleContext:
    return RuleContext(
        repo_root=repo,
        profile="flat",
        policy_version="1.0.7",
        config=cfg.load(repo),
    )


def test_r26_pass_when_not_configured(tmp_path):
    repo = _make_repo(tmp_path)
    assert get_rule().check(make_ctx(repo)).status == Status.PASS


def test_r26_pass_when_marker_matches_stdout(tmp_path):
    repo = _make_repo(
        tmp_path,
        extra_config=(
            "generated_facts:\n"
            "  - kind: fact_list\n"
            "    command: \"python3 scripts/print_facts.py\"\n"
            "    reflected_in: \"README.md\"\n"
            "    marker: \"rpc-methods\"\n"
        ),
        readme=(
            "<!-- BEGIN: generated-fact marker=\"rpc-methods\" -->\n"
            "session.open\n"
            "session.renumber\n"
            "<!-- END: generated-fact marker=\"rpc-methods\" -->\n"
        ),
    )
    _write(repo, "scripts/print_facts.py", "print('session.open\\nsession.renumber')\n")
    assert get_rule().check(make_ctx(repo)).status == Status.PASS


def test_r26_fail_when_marker_missing(tmp_path):
    repo = _make_repo(
        tmp_path,
        extra_config=(
            "generated_facts:\n"
            "  - kind: fact_list\n"
            "    command: \"python3 scripts/print_facts.py\"\n"
            "    reflected_in: \"README.md\"\n"
            "    marker: \"rpc-methods\"\n"
        ),
        readme="no marker here\n",
    )
    _write(repo, "scripts/print_facts.py", "print('session.open')\n")
    assert get_rule().check(make_ctx(repo)).status == Status.FAIL
```

Add one compatibility assertion to `tests/test_rule_r16_cli_help_sync.py`:

```python
def test_r16_existing_cli_help_fixture_still_passes_after_helper_extraction(fixture_repo):
    repo = fixture_repo("cli-help-synced")
    result = get_rule("R-16").check(make_ctx(repo))
    assert result.status == Status.PASS
```

- [ ] **Step 2: Run the new marker-sync tests to prove RED**

Run:

```bash
python3 -m pytest tests/test_rule_r26_generated_fact_sync.py -q
python3 -m pytest tests/test_rule_r16_cli_help_sync.py -q
```

Expected:
- the `R-26` test file fails with `AssertionError: R-26 is not registered`
- the existing `R-16` tests still pass before refactoring

- [ ] **Step 3: Extract the shared marker helper, refactor `R-16`, and add `R-26`**

Create `policy_check/rules/_marker_sync.py`:

```python
from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path


def normalize(text: str) -> str:
    return text.strip()


def extract_marker_block(text: str, marker_kind: str, marker: str) -> tuple[bool, str]:
    pattern = (
        rf"<!--\s*BEGIN:\s*{re.escape(marker_kind)}\s+marker=\"{re.escape(marker)}\"\s*-->"
        rf"(.*?)"
        rf"<!--\s*END:\s*{re.escape(marker_kind)}\s+marker=\"{re.escape(marker)}\"\s*-->"
    )
    match = re.search(pattern, text, flags=re.DOTALL)
    if not match:
        return False, ""
    return True, match.group(1)


def run_command(command: str, *, cwd: Path, timeout: int = 30, extra_args: list[str] | None = None, include_stderr: bool = False) -> tuple[int, str]:
    proc = subprocess.run(
        [*shlex.split(str(command)), *(extra_args or [])],
        cwd=cwd,
        env={**os.environ, "LC_ALL": "C"},
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    output = proc.stdout.decode("utf-8", "replace")
    if include_stderr:
        output += proc.stderr.decode("utf-8", "replace")
    return proc.returncode, normalize(output)
```

Refactor `policy_check/rules/r16_cli_help_sync.py` to call:

```python
exit_code, actual = run_command(
    str(command),
    cwd=ctx.repo_root,
    extra_args=help_args,
    include_stderr=True,
)
found, block = extract_marker_block(text, "cli-help", str(marker))
```

Create `policy_check/rules/r26_generated_fact_sync.py`:

```python
from __future__ import annotations

from policy_check.rules._marker_sync import extract_marker_block, normalize, run_command
from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R26GeneratedFactSync:
    rule_id = "R-26"
    exempt_label = None

    def check(self, ctx: RuleContext) -> RuleResult:
        entries = (ctx.config or {}).get("generated_facts") or []
        if not entries:
            return RuleResult(self.rule_id, Status.PASS, "generated_facts not configured; R-26 not applicable.")

        failures: list[str] = []
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                failures.append(f"entry[{index}] is not a mapping/object")
                continue
            command = entry.get("command")
            reflected_in = entry.get("reflected_in")
            marker = entry.get("marker")
            if not command or not reflected_in or not marker:
                failures.append(f"entry[{index}] missing required keys: command/reflected_in/marker")
                continue
            exit_code, actual = run_command(str(command), cwd=ctx.repo_root, include_stderr=False)
            if exit_code != 0:
                failures.append(f"entry[{index}] command exit={exit_code} for {command!r}")
                continue
            text = (ctx.repo_root / str(reflected_in)).read_text(encoding="utf-8", errors="replace")
            found, block = extract_marker_block(text, "generated-fact", str(marker))
            if not found:
                failures.append(f"entry[{index}] marker missing/invalid: marker={marker!r} in {reflected_in}")
                continue
            if normalize(block) != actual:
                failures.append(f"entry[{index}] output mismatch for marker={marker!r}")
        if failures:
            return RuleResult(self.rule_id, Status.FAIL, "Generated fact markers are out of sync.", detail="\\n".join(failures))
        return RuleResult(self.rule_id, Status.PASS, f"All {len(entries)} generated fact markers are in sync.")
```

Extend `policy_check/rules/r08_policy_config_schema.py`:

```python
        generated_facts = data.get("generated_facts")
        if generated_facts is not None:
            if not isinstance(generated_facts, list):
                return RuleResult(self.rule_id, Status.FAIL, "generated_facts must be a list")
            for index, entry in enumerate(generated_facts, start=1):
                if not isinstance(entry, dict):
                    return RuleResult(self.rule_id, Status.FAIL, f"generated_facts[{index}] must be a mapping")
```

- [ ] **Step 4: Re-run the marker-sync tests until they pass**

Run:

```bash
python3 -m pytest tests/test_rule_r26_generated_fact_sync.py -q
python3 -m pytest tests/test_rule_r16_cli_help_sync.py -q
```

Expected: both commands PASS, proving generic marker sync works without regressing `R-16`.

- [ ] **Step 5: Commit `R-26` and the helper extraction**

```bash
git add policy_check/rules/_marker_sync.py \
        policy_check/rules/r16_cli_help_sync.py \
        policy_check/rules/r26_generated_fact_sync.py \
        policy_check/rules/r08_policy_config_schema.py \
        tests/test_rule_r26_generated_fact_sync.py \
        tests/test_rule_r16_cli_help_sync.py
git commit -m "feat: add generated fact sync rule"
```

## Task 5: Dogfood the config/docs and run the real verification gates

**Files:**
- Create: `tests/test_self_dogfood_doc_rules.py`
- Modify: `.paul-project.yml:1-31`
- Modify: `README.md:44-61,129`
- Modify: `CHANGELOG.md:8-40`

- [ ] **Step 1: Write the failing self-dogfood assertions**

Create `tests/test_self_dogfood_doc_rules.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).parent.parent


def test_paul_project_yml_declares_doc_paths():
    config = yaml.safe_load((ROOT / ".paul-project.yml").read_text(encoding="utf-8"))
    assert config.get("doc_paths") == ["README.md", "docs/**", "CLAUDE.md"]


def test_readme_mentions_r25_r26_and_doc_paths():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "R-25" in text
    assert "R-26" in text
    assert "doc_paths" in text


def test_changelog_mentions_issue_26_rule_hardening():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "#26" in text
    assert "R-25" in text
    assert "R-26" in text
```

- [ ] **Step 2: Run the self-dogfood tests to prove RED**

Run:

```bash
python3 -m pytest tests/test_self_dogfood_doc_rules.py -q
```

Expected: FAIL because `.paul-project.yml`, `README.md`, and `CHANGELOG.md` have not been updated yet.

- [ ] **Step 3: Update this repo’s config and docs**

Update `.paul-project.yml` to add:

```yaml
doc_paths:
  - "README.md"
  - "docs/**"
  - "CLAUDE.md"
```

Update `README.md`:

```md
| R-18 | docs/README 對齊 code 變動 | code_paths 有變動但 canonical docs（由 `doc_paths` 決定，預設 `README.md` / `docs/**`）未同步（**WARN**，不擋 merge） | `policy-exempt:docs-sync` |
| R-22 | docs 對 code 產物引用無懸空 | canonical docs（由 `doc_paths` 決定）引用的路徑／內部連結／反引號 symbol 在 repo 不存在；本次變更新破壞 **FAIL**、陳年懸空 **WARN**、無 diff context（本地）降 WARN | `policy-exempt:doc-reference` |
| R-25 | canonical docs 覆蓋新增 public facts | `doc_coverage` 宣告的新增（或全量）facts 未在 canonical docs 被 mention | — |
| R-26 | generated fact marker 與實際輸出同步 | `generated_facts` 宣告的 marker 區塊與 command stdout 不一致 | — |
```

Also add one short config example paragraph near the existing CLI help section explaining that:

```md
- `doc_paths` 定義 canonical docs 範圍（預設 `README.md` / `docs/**`）
- `doc_coverage` 與 `generated_facts` 為 opt-in surfaces；未宣告時對應規則為 not-applicable
```

Update `CHANGELOG.md` under `[Unreleased]`:

```md
### Added
- **#26 文件規則補強**：新增 shared `doc_paths` canonical doc scope，`R-18` / `R-22` 改讀該範圍；新增 `R-25`（deterministic doc coverage，支援 `changed` / `all`）與 `R-26`（generic generated fact sync，與既有 `R-16` backward-compatible）。
```

- [ ] **Step 4: Re-run the self-dogfood tests and then the targeted rule tests**

Run:

```bash
python3 -m pytest tests/test_self_dogfood_doc_rules.py -q
python3 -m pytest \
  tests/test_rule_r08_policy_config_schema.py \
  tests/test_rule_r18_docs_sync.py \
  tests/test_rule_r22_doc_reference.py \
  tests/test_rule_r25_doc_coverage.py \
  tests/test_rule_r16_cli_help_sync.py \
  tests/test_rule_r26_generated_fact_sync.py -q
```

Expected: all listed tests PASS.

- [ ] **Step 5: Run the real repo gates and commit the documentation / dogfood batch**

Run:

```bash
python3 -m pytest -q
python3 -m policy_check --repo .
```

Expected:
- full pytest suite PASSes
- `python3 -m policy_check --repo .` exits 0 with no FAIL results

Then commit:

```bash
git add .paul-project.yml README.md CHANGELOG.md tests/test_self_dogfood_doc_rules.py
git commit -m "docs: dogfood doc rule hardening"
```
