# policy_check/doc_drift/engine.py
from __future__ import annotations

from pathlib import Path

from policy_check.doc_drift import refs as dd_refs
from policy_check.doc_drift import symbols as dd_symbols
from policy_check.doc_drift import drift as dd_drift
from policy_check.doc_drift import provision as dd_provision
from policy_check.doc_drift.paths import git_tracked, resolve_base

_DOC_SCOPE = ("README.md",)  # 簡化：doc-drift mode 掃 README + docs/**


def _in_scope(rel: str) -> bool:
    return rel == "README.md" or rel.startswith("docs/")


def run_doc_drift(repo_root: Path, base_ref: str, head_ref: str = "HEAD"):
    """回 (fails: list[str], warns: list[str])。"""
    root = Path(repo_root)
    base = resolve_base(root, base_ref)
    fails: list[str] = []
    warns: list[str] = []
    removed_ids: set = set()
    head_ids: set = set()
    if base and dd_provision.ensure_object(root, base) and dd_provision.ensure_object(root, head_ref):
        base_ids = dd_symbols.symbols_at(root, base)
        head_ids = dd_symbols.symbols_at(root, head_ref)
        removed_ids = dd_drift.removed_identities(base_ids, head_ids)
    head_files = git_tracked(root)
    for rel in sorted(f for f in head_files if _in_scope(f)):
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for kind, token, payload in dd_refs.extract_refs(rel, text):
            if kind == "symbol":
                v = dd_drift.classify_symbol_token(token, removed_ids, head_ids)
                if v == "FAIL":
                    fails.append(f"{rel} -> `{token}` (symbol removed this change)")
                elif v == "WARN":
                    warns.append(f"{rel} -> `{token}` (ambiguous)")
            elif kind == "path" and not any(c in head_files for c in payload):
                warns.append(f"{rel} -> {token}")
    return fails, warns
