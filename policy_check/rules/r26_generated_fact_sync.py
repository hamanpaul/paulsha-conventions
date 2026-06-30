"""R-26 — generic generated-fact marker sync.

Generalizes R-16's CLI-help marker-sync to any structured generated fact.
Opt-in: when ``.paul-project.yml`` does not declare ``generated_facts`` the rule
is not-applicable and PASSes. When declared, each entry's command is executed
deterministically and its normalized stdout MUST match the ``generated-fact``
marker block in the entry's ``reflected_in`` document.

Coexists with R-16: this rule reads only ``generated-fact`` markers, so existing
``cli-help`` markers and the ``cli`` config keep working unchanged.
"""
from __future__ import annotations

import subprocess

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register
from policy_check.rules._marker_sync import marker_block, normalize, run_command


@register
class R26GeneratedFactSync:
    rule_id = "R-26"
    exempt_label = None  # opt-in via config; unconfigured repos are not-applicable

    def check(self, ctx: RuleContext) -> RuleResult:
        config = ctx.config or {}
        entries = config.get("generated_facts")
        if not entries:
            return RuleResult(self.rule_id, Status.PASS,
                              "No generated_facts declared (not applicable).")
        if not isinstance(entries, list):
            return RuleResult(self.rule_id, Status.FAIL,
                              "generated_facts must be a list of mappings.")

        failures: list[str] = []
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                failures.append(f"entry[{index}] is not a mapping/object")
                continue

            command = entry.get("command")
            reflected_in = entry.get("reflected_in")
            marker = entry.get("marker")
            if not command or not reflected_in or not marker:
                failures.append(
                    f"entry[{index}] missing required keys: command/reflected_in/marker"
                )
                continue

            try:
                result = run_command(str(command), ctx.repo_root)
            except (OSError, subprocess.SubprocessError) as exc:
                failures.append(f"entry[{index}] command failed to run: {exc}")
                continue

            if result.returncode != 0:
                failures.append(
                    f"entry[{index}] command exit={result.returncode} for {command!r}"
                )
                continue

            # Generic generated facts compare normalized stdout only (stderr ignored).
            actual = normalize(result.stdout)

            target_path = ctx.repo_root / str(reflected_in)
            if not target_path.is_file():
                failures.append(f"entry[{index}] reflected_in not found: {reflected_in}")
                continue

            text = target_path.read_text(encoding="utf-8", errors="replace")
            found, block = marker_block(text, str(marker), tag="generated-fact")
            if not found:
                failures.append(
                    f"entry[{index}] marker missing/invalid: marker={marker!r} in {reflected_in}"
                )
                continue

            if normalize(block) != actual:
                failures.append(
                    f"entry[{index}] output mismatch for marker={marker!r} in {reflected_in}"
                )

        if failures:
            return RuleResult(
                self.rule_id, Status.FAIL,
                "generated-fact markers are out of sync or misconfigured.",
                detail="\n".join(failures))

        return RuleResult(
            self.rule_id, Status.PASS,
            f"All {len(entries)} generated-fact marker(s) are in sync.")
