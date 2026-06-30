# policy_check/doc_drift/coverage.py
from __future__ import annotations

from collections.abc import Iterable

# 預設受治理前綴（沿用 R-24 現值）。openspec change 以「目錄下任一連結即算」處理，
# 故這裡的 plans/specs 為精確檔案；openspec changes 的孤兒判定由呼叫端傳對應集合。
DEFAULT_GOVERNED_PREFIXES = (
    "openspec/changes/",
    "docs/superpowers/plans/",
    "docs/superpowers/specs/",
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
