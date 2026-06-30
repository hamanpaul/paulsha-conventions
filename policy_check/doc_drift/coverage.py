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


def openspec_change_orphans(head_files: Iterable[str], linked: set[str]) -> list[str]:
    """回 active openspec change 名稱中，change dir 下無「任一」linked 連結者。

    與 R-24 同一判定（目錄級，不要求逐檔連結），供 r24 規則與 standalone moc mode 共用，
    避免兩端對 openspec change 的孤兒判定 drift（例如 proposal.md 已連結卻誤標 tasks.md）。
    """
    names = sorted({
        rel.split("/")[2] for rel in head_files
        if rel.startswith("openspec/changes/")
        and not rel.startswith("openspec/changes/archive/")
        and len(rel.split("/")) >= 3
    })
    out = []
    for name in names:
        prefix = f"openspec/changes/{name}/"
        if not any(t.startswith(prefix) for t in linked):
            out.append(name)
    return out
