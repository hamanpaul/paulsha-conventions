from __future__ import annotations

import os
import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

_IN_SCOPE_PREFIXES = ("docs/",)           # 加上 README.md（見 _in_scope）
_EXCLUDE_PREFIXES = ("openspec/", "docs/superpowers/", "tests/fixtures/doc-reference/")
_SELF_EXEMPT = (
    "policy_check/rules/r22_doc_reference.py",
    "tests/test_rule_r22_doc_reference.py",
    "tests/fixtures/doc-reference/**",
)
_CODE_EXTS = (".py", ".sh", ".yml", ".yaml", ".toml", ".js", ".ts",
              ".json", ".cfg", ".ini", ".md")

_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
_CAMEL_RE = re.compile(r"^[A-Za-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*$")
_DEFCLASS_RE = re.compile(r"^([+-])\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)")


def _in_scope(rel: str) -> bool:
    if rel.startswith(_EXCLUDE_PREFIXES):
        return False
    return rel == "README.md" or rel.startswith(_IN_SCOPE_PREFIXES)


def _is_exempt(rel: str, allow: list[str]) -> bool:
    for pat in (*_SELF_EXEMPT, *allow):
        if fnmatch(rel, pat):
            return True
        base = pat[:-3] if pat.endswith("/**") else pat
        if rel == base or rel.startswith(base.rstrip("/") + "/"):
            return True
    return False


def _is_symbol(tok: str) -> bool:
    return len(tok) >= 3 and bool(_SNAKE_RE.match(tok) or _CAMEL_RE.match(tok))


def _looks_like_path(tok: str) -> bool:
    tok = tok.strip()
    if not tok or " " in tok or any(c in tok for c in "<>{}*$"):
        return False  # 排除 placeholder/glob（如 feature/<slug>、${{ inputs.x }}）
    if tok.startswith(("./", "../")):
        return True
    # 需有 code 副檔名才視為本地路徑候選——避免把目錄（tests/）與
    # GitHub org/repo slug（hamanpaul/paulsha-conventions）誤判為本地檔
    return tok.endswith(_CODE_EXTS)


def _git_tracked(root: Path, rev: str | None = None) -> set[str]:
    cmd = ["git", "-C", str(root)]
    cmd += (["ls-tree", "-r", "--name-only", rev] if rev else ["ls-files"])
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return set()
    return {l.strip() for l in out.splitlines() if l.strip()}


def _resolve_base(root: Path, base_ref: str | None) -> str | None:
    if not base_ref:
        return None
    for cand in (base_ref, f"origin/{base_ref}"):
        try:
            sha = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "--verify", "-q", f"{cand}^{{commit}}"],
                text=True, stderr=subprocess.DEVNULL).strip()
        except subprocess.CalledProcessError:
            continue
        if not sha:
            continue
        # 回傳 merge-base：讓 path prong（base_files）與 symbol prong（base...HEAD）
        # 用同一歸責基準，避免上游分歧（base 落後分支）造成的偽 FAIL
        try:
            mb = subprocess.check_output(
                ["git", "-C", str(root), "merge-base", sha, "HEAD"],
                text=True, stderr=subprocess.DEVNULL).strip()
        except subprocess.CalledProcessError:
            mb = ""
        return mb or sha
    return None


def _defined_in_head(root: Path, name: str) -> bool:
    try:
        subprocess.check_output(
            ["git", "-C", str(root), "grep", "-qE",
             rf"(def|class)[[:space:]]+{re.escape(name)}\b", "HEAD"],
            stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def _removed_symbols(root: Path, base: str) -> set[str]:
    try:
        diff = subprocess.check_output(
            ["git", "-C", str(root), "diff", f"{base}...HEAD", "--", "*.py"],
            text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return set()
    candidates: set[str] = set()
    for line in diff.splitlines():
        m = _DEFCLASS_RE.match(line)
        if m and m.group(1) == "-":
            candidates.add(m.group(2))
    return {name for name in candidates if not _defined_in_head(root, name)}


def _path_candidates(doc_rel: str, target: str) -> list[str]:
    """正規化成 repo-relative posix 候選（doc-relative 與 root-relative 各一）。"""
    target = target.split("#", 1)[0].strip()
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return []
    doc_dir = Path(doc_rel).parent
    cands: list[str] = []
    for base in (doc_dir / target, Path(target)):
        norm = os.path.normpath(base.as_posix())
        if norm == "." or norm.startswith("..") or norm.startswith("/"):
            continue
        posix = Path(norm).as_posix()
        if posix not in cands:
            cands.append(posix)
    return cands


def _extract_refs(doc_rel: str, text: str):
    """yield (kind, token, payload)。kind=='path' → payload=list[str] 候選；'symbol' → payload=name。"""
    for m in _LINK_RE.finditer(text):
        cands = _path_candidates(doc_rel, m.group(1))
        if cands:
            yield ("path", m.group(1), cands)
    for m in _CODE_SPAN_RE.finditer(text):
        tok = m.group(1).strip()
        if _looks_like_path(tok):
            cands = _path_candidates(doc_rel, tok)
            if cands:
                yield ("path", tok, cands)
        elif _is_symbol(tok):
            yield ("symbol", tok, tok)


@register
class R22DocReference:
    rule_id = "R-22"
    exempt_label = "policy-exempt:doc-reference"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(self.rule_id, Status.SKIP,
                              f"Skipped by exemption label: {self.exempt_label}.",
                              exempt_label=self.exempt_label)

        root = ctx.repo_root
        config = ctx.config or {}
        allow = (config.get("doc_reference") or {}).get("allow", [])
        head_files = _git_tracked(root)
        base = _resolve_base(root, ctx.pr_base_ref)
        base_files = _git_tracked(root, base) if base else set()
        removed_syms = _removed_symbols(root, base) if base else set()

        fails: list[str] = []
        warns: list[str] = []
        for rel in sorted(head_files):
            if not _in_scope(rel) or _is_exempt(rel, allow):
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
            return RuleResult(self.rule_id, Status.FAIL,
                              f"docs contain {len(fails)} dangling reference(s) introduced by this change.",
                              detail="\n".join(fails[:20]))
        if warns:
            return RuleResult(self.rule_id, Status.WARN,
                              f"docs contain {len(warns)} pre-existing dangling reference(s) (advisory).",
                              detail="\n".join(warns[:20]))
        return RuleResult(self.rule_id, Status.PASS, "No dangling doc references detected.")
