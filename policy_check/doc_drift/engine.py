# policy_check/doc_drift/engine.py
from __future__ import annotations

from pathlib import Path

from policy_check.doc_drift import refs as dd_refs
from policy_check.doc_drift import symbols as dd_symbols
from policy_check.doc_drift import drift as dd_drift
from policy_check.doc_drift import provision as dd_provision
from policy_check.doc_drift import exempt as dd_exempt
from policy_check.doc_drift.paths import git_tracked, resolve_base

_DOC_SCOPE = ("README.md",)  # 簡化：doc-drift mode 掃 README + docs/**


def _in_scope(rel: str) -> bool:
    return rel == "README.md" or rel.startswith("docs/")


def _load_allowlist(root: Path) -> dd_exempt.Allowlist:
    p = root / ".doc-drift-allow"
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    return dd_exempt.parse_allowlist(lines)


class DriftProvisionError(Exception):
    """base/head git 物件無法供給時拋出；CLI 應 fail-fast（非零 exit），不得 fail-open。"""


def _require_base(root: Path, base_ref: str, head_ref: str) -> str:
    """解析並確保 base/head 物件存在；任一缺失即 raise（符合 doc-drift-core spec 的 fail-fast）。"""
    base = resolve_base(root, base_ref)
    if not base:
        raise DriftProvisionError(f"無法解析 base ref '{base_ref}'")
    if not (dd_provision.ensure_object(root, base) and dd_provision.ensure_object(root, head_ref)):
        raise DriftProvisionError(
            f"base/head 物件無法取得（shallow checkout？git fetch fallback 失敗）："
            f"base={base} head={head_ref}"
        )
    return base


def run_doc_drift(repo_root: Path, base_ref: str, head_ref: str = "HEAD"):
    """回 (fails, warns)；base/head 物件無法供給時 raise DriftProvisionError。"""
    root = Path(repo_root)
    base = _require_base(root, base_ref, head_ref)
    base_ids = dd_symbols.symbols_at(root, base)
    head_ids = dd_symbols.symbols_at(root, head_ref)
    removed_ids = dd_drift.removed_identities(base_ids, head_ids)
    head_files = git_tracked(root)
    base_files = git_tracked(root, base)
    allow = _load_allowlist(root)
    fails: list[str] = []
    warns: list[str] = []
    for rel in sorted(f for f in head_files if _in_scope(f)):
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.splitlines():
            if dd_exempt.line_is_ignored(line):
                continue
            for kind, token, payload in dd_refs.extract_refs(rel, line):
                if dd_exempt.is_allowed(rel, token, allow):
                    continue
                if kind == "symbol":
                    v = dd_drift.classify_symbol_token(token, removed_ids, head_ids)
                    if v == "FAIL":
                        fails.append(f"{rel} -> `{token}` (symbol removed this change)")
                    elif v == "WARN":
                        warns.append(f"{rel} -> `{token}` (ambiguous)")
                elif kind == "path" and not any(c in head_files for c in payload):
                    # 本次移除（base 有、head 無）→ FAIL；陳年懸空 → WARN（對齊 R-22）
                    if any(c in base_files for c in payload):
                        fails.append(f"{rel} -> {token} (path removed this change)")
                    else:
                        warns.append(f"{rel} -> {token}")
    return fails, warns


from policy_check.doc_drift import coverage as dd_coverage
from policy_check.doc_drift.paths import LINK_RE, looks_like_path, path_candidates
import re as _re

_CODE_SPAN = _re.compile(r"`([^`\n]+)`")


def _map_refs(map_rel, text, prefixes):
    tokens = [m.group(1) for m in LINK_RE.finditer(text)]
    tokens += [t for t in (m.group(1).strip() for m in _CODE_SPAN.finditer(text)) if looks_like_path(t)]
    for tok in tokens:
        cands = [c for c in path_candidates(map_rel, tok) if c.startswith(tuple(prefixes))]
        if cands:
            yield tok, cands


def run_moc(repo_root, base_ref, map_rel, prefixes, head_ref="HEAD"):
    root = Path(repo_root)
    base = _require_base(root, base_ref, head_ref)
    head_files = git_tracked(root)
    base_files = git_tracked(root, base)
    fails, warns = [], []
    try:
        text = (root / map_rel).read_text(encoding="utf-8")
    except OSError:
        return [f"moc.map '{map_rel}' 不存在"], []
    allow = _load_allowlist(root)
    # linked 以全文計算：被 inline-ignore 的行仍算「已連結」，否則僅出現在 ignore 行的
    # 受治理檔會被誤判 orphan。inline-ignore / allowlist 只影響 dangling 的 FAIL/WARN 判定。
    linked = set()
    for _tok, cands in _map_refs(map_rel, text, prefixes):
        linked.update(cands)
    for line in text.splitlines():
        if dd_exempt.line_is_ignored(line):
            continue
        for tok, cands in _map_refs(map_rel, line, prefixes):
            if dd_exempt.is_allowed(map_rel, tok, allow):
                continue
            if any(c in head_files for c in cands):
                continue
            if base and any(c in base_files for c in cands):
                fails.append(f"{map_rel} -> {tok} (removed this change)")
            else:
                warns.append(f"{map_rel} -> {tok}")
    file_prefixes = tuple(p for p in prefixes if not p.startswith("openspec/changes/"))
    for orphan in dd_coverage.orphans(head_files, linked, prefixes=file_prefixes):
        warns.append(f"orphan: {orphan} 未被 {map_rel} 連結")
    # openspec change：change dir 下任一連結即算（與 R-24 同一判定，避免標 tasks.md 偽 orphan）
    if any(p.startswith("openspec/changes/") for p in prefixes):
        for name in dd_coverage.openspec_change_orphans(head_files, linked):
            warns.append(f"orphan: openspec change '{name}' 未被 {map_rel} 連結")
    return fails, warns
