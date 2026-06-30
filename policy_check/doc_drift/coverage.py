# policy_check/doc_drift/coverage.py
from __future__ import annotations

from collections.abc import Iterable

# 預設受治理前綴：與 R-24 重構前的 _GOVERNED_PREFIXES 等價（沿用現值，不偷偷收窄）。
# `docs/superpowers/` 廣義涵蓋其下 plans/specs 等所有 .md；openspec change 的孤兒判定
# 由呼叫端以「目錄下任一連結即算」另計（見 r24_moc_alignment）。
DEFAULT_GOVERNED_PREFIXES = (
    "openspec/changes/",
    "docs/superpowers/",
)


def orphans(
    head_files: Iterable[str],
    linked: set[str],
    *,
    prefixes: tuple[str, ...] = DEFAULT_GOVERNED_PREFIXES,
) -> list[str]:
    """回在受治理前綴下、為 .md 精確檔、且未被 linked 涵蓋者。"""
    out = []
    for rel in sorted(head_files):
        if not rel.endswith(".md"):
            continue
        if not rel.startswith(tuple(prefixes)):
            continue
        if rel not in linked:
            out.append(rel)
    return out
