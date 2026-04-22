# policy_check/report.py
import os
from typing import Iterable

from policy_check.rules.base import RuleResult, Status


def emit(results: Iterable[RuleResult]) -> int:
    results = list(results)
    lines = ["# Policy Check Report\n"]
    fails = [r for r in results if r.status == Status.FAIL]
    skips = [r for r in results if r.status == Status.SKIP]
    passes = [r for r in results if r.status == Status.PASS]
    warns = [r for r in results if r.status == Status.WARN]

    lines.append(f"- pass: {len(passes)}")
    lines.append(f"- fail: {len(fails)}")
    lines.append(f"- warn: {len(warns)}")
    lines.append(f"- skip (exempt): {len(skips)}\n")

    for r in sorted(results, key=lambda x: x.rule_id):
        icon = {"pass": ":white_check_mark:", "fail": ":x:", "skip": ":warning:", "warn": ":warning:"}[r.status.value]
        lines.append(f"## {icon} {r.rule_id} — {r.status.value}")
        lines.append(r.message)
        if r.exempt_label:
            lines.append(f"exempt via: `{r.exempt_label}`")
        if r.detail:
            lines.append(f"\n<details><summary>detail</summary>\n\n```\n{r.detail}\n```\n\n</details>")
        lines.append("")

    report = "\n".join(lines)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(report)
    else:
        print(report)

    return 1 if fails else 0
