import os
from typing import Iterable

from policy_check.rules.base import RuleResult, Status
from policy_check.rules.families import OTHER, ordered_families

_ICON = {
    "pass": ":white_check_mark:",
    "fail": ":x:",
    "skip": ":warning:",
    "warn": ":warning:",
}


def _render_rule(r: RuleResult) -> list[str]:
    block = [f"## {_ICON[r.status.value]} {r.rule_id} — {r.status.value}", r.message]
    if r.exempt_label:
        block.append(f"exempt via: `{r.exempt_label}`")
    if r.detail:
        block.append(f"\n<details><summary>detail</summary>\n\n```\n{r.detail}\n```\n\n</details>")
    block.append("")
    return block


def emit(
    results: Iterable[RuleResult],
    family_map: dict | None = None,
    *,
    engine_version_line: str | None = None,
) -> int:
    # 參數刻意命名 family_map（非 families）以免遮蔽 policy_check.rules.families 模組。
    results = list(results)
    lines = ["# Policy Check Report\n"]
    if engine_version_line:
        lines.append(engine_version_line)
        lines.append("")
    fails = [r for r in results if r.status == Status.FAIL]
    skips = [r for r in results if r.status == Status.SKIP]
    passes = [r for r in results if r.status == Status.PASS]
    warns = [r for r in results if r.status == Status.WARN]

    lines.append(f"- pass: {len(passes)}")
    lines.append(f"- fail: {len(fails)}")
    lines.append(f"- warn: {len(warns)}")
    lines.append(f"- skip (exempt): {len(skips)}\n")

    if family_map is None:
        # 向後相容：無 family map 時依 rule_id 平鋪
        for r in sorted(results, key=lambda x: x.rule_id):
            lines += _render_rule(r)
    else:
        by_family: dict[str, list[RuleResult]] = {}
        for r in results:
            by_family.setdefault(family_map.get(r.rule_id, OTHER), []).append(r)
        # 用 id(r) 追蹤已輸出者：RuleResult 是可變 dataclass、不可 hash，且 results=list(...)
        # 已把所有物件釘活整個 emit()，故 id 唯一且不會被回收重用。
        emitted: set[int] = set()
        for fam in ordered_families():
            group = by_family.get(fam)
            if not group:
                continue
            lines.append(f"### {fam}")
            lines.append("")
            for r in sorted(group, key=lambda x: x.rule_id):
                lines += _render_rule(r)
                emitted.add(id(r))
        # OTHER catch-all：family 不在 ordered_families()（含未分類）者，確保不被漏印
        leftovers = [r for r in results if id(r) not in emitted]
        if leftovers:
            lines.append(f"### {OTHER}")
            lines.append("")
            for r in sorted(leftovers, key=lambda x: x.rule_id):
                lines += _render_rule(r)

    report = "\n".join(lines)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(report)
    else:
        print(report)

    return 1 if fails else 0
