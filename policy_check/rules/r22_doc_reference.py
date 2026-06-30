from __future__ import annotations

import re
from fnmatch import fnmatch

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register
from policy_check.rules._doc_scope import configured_doc_paths, matches_doc_path
from policy_check.rules._doc_links import (
    LINK_RE as _LINK_RE,
    looks_like_path as _looks_like_path,
    path_candidates as _path_candidates,
    git_tracked as _git_tracked,
    resolve_base as _resolve_base,
)
from policy_check.doc_drift import symbols as dd_symbols
from policy_check.doc_drift import drift as dd_drift
from policy_check.doc_drift import provision as dd_provision

_EXCLUDE_PREFIXES = ("openspec/", "docs/superpowers/", "tests/fixtures/doc-reference/")
_SELF_EXEMPT = (
    "policy_check/rules/r22_doc_reference.py",
    "tests/test_rule_r22_doc_reference.py",
    "tests/fixtures/doc-reference/**",
)

_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
_CAMEL_RE = re.compile(r"^[A-Za-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*$")
# 限定式：A.b（含點，末段為 snake/Camel/簡單識別字）
_QUALIFIED_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")
# 裸名識別字（含裸 member 名，如 `close`），交由 scoped 核心判定歧義/移除
_BARE_RE = re.compile(r"^[a-z][a-z0-9]*$")


def _in_scope(rel: str, doc_paths: list[str]) -> bool:
    # repo-declared canonical scope (doc_paths) minus rule-level built-in noise.
    if rel.startswith(_EXCLUDE_PREFIXES):
        return False
    return matches_doc_path(rel, doc_paths)


def _is_exempt(rel: str, allow: list[str]) -> bool:
    for pat in (*_SELF_EXEMPT, *allow):
        if fnmatch(rel, pat):
            return True
        base = pat[:-3] if pat.endswith("/**") else pat
        if rel == base or rel.startswith(base.rstrip("/") + "/"):
            return True
    return False


def _is_symbol(tok: str) -> bool:
    if len(tok) < 3:
        return False
    return bool(
        _SNAKE_RE.match(tok)
        or _CAMEL_RE.match(tok)
        or _QUALIFIED_RE.match(tok)
        or _BARE_RE.match(tok)
    )


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
        doc_paths = configured_doc_paths(config)
        allow = (config.get("doc_reference") or {}).get("allow", [])
        head_files = _git_tracked(root)
        base = _resolve_base(root, ctx.pr_base_ref)
        base_files = _git_tracked(root, base) if base else set()

        removed_ids: set = set()
        head_ids: set = set()
        if base:
            head_sha = "HEAD"
            if dd_provision.ensure_object(root, base) and dd_provision.ensure_object(root, head_sha):
                base_ids = dd_symbols.symbols_at(root, base)
                head_ids = dd_symbols.symbols_at(root, head_sha)
                removed_ids = dd_drift.removed_identities(base_ids, head_ids)

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
                elif kind == "symbol":
                    verdict = dd_drift.classify_symbol_token(token, removed_ids, head_ids)
                    if verdict == "FAIL":
                        fails.append(f"{rel} -> `{token}` (symbol removed this change)")
                    elif verdict == "WARN":
                        warns.append(f"{rel} -> `{token}` (ambiguous: same-named symbol remains)")

        if fails:
            return RuleResult(self.rule_id, Status.FAIL,
                              f"docs contain {len(fails)} dangling reference(s) introduced by this change.",
                              detail="\n".join(fails[:20]))
        if warns:
            return RuleResult(self.rule_id, Status.WARN,
                              f"docs contain {len(warns)} pre-existing dangling reference(s) (advisory).",
                              detail="\n".join(warns[:20]))
        return RuleResult(self.rule_id, Status.PASS, "No dangling doc references detected.")
