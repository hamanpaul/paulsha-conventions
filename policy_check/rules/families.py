"""規則 → family 的中央有序分類（純呈現層）。

不觸及 rule_id / exempt_label / 規則行為。新增規則須在此登記其 id；
tests/test_families.py 的完整性測試保證每個註冊規則恰好被分類一次。
"""
from __future__ import annotations

# 順序即報告輸出順序。每個 rule_id 恰好屬一個 family。
FAMILIES: list[tuple[str, tuple[str, ...]]] = [
    ("README", ("R-01", "R-02")),
    ("CHANGELOG", ("R-03", "R-04", "R-09")),
    ("VERSION", ("R-05", "R-06", "R-07")),
    ("CONFIG", ("R-08",)),
    ("PR", ("R-10", "R-11", "R-12", "R-17")),
    ("AGENT", ("R-13", "R-14")),
    ("WORKFLOW", ("R-15", "R-20", "R-23")),
    ("MARKER-SYNC", ("R-16", "R-26")),
    ("CI", ("R-19",)),
    ("SECRET", ("R-21",)),
    ("DOC-ALIGN", ("R-18", "R-22", "R-24", "R-25")),
]

OTHER = "OTHER"

_RULE_TO_FAMILY = {rid: fam for fam, rids in FAMILIES for rid in rids}


def family_of(rule_id: str) -> str:
    """回 rule_id 所屬 family；未分類回 OTHER。"""
    return _RULE_TO_FAMILY.get(rule_id, OTHER)


def ordered_families() -> list[str]:
    """family 名的輸出順序（不含 OTHER；OTHER 由 report 尾端 catch-all 處理）。"""
    return [fam for fam, _ in FAMILIES]
