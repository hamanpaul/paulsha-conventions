from __future__ import annotations

import subprocess

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register
from policy_check.rules._marker_sync import marker_block, normalize, run_command


@register
class R16CliHelpSync:
    rule_id = "R-16"
    exempt_label = "policy-exempt:cli-help"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message="R-16 skipped by exemption label.",
                exempt_label=self.exempt_label,
            )

        entries = ctx.config.get("cli") or []
        if not entries:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No CLI entries declared in .paul-project.yml.",
            )

        failures: list[str] = []

        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                failures.append(f"entry[{index}] is not a mapping/object")
                continue

            command = entry.get("command")
            reflected_in = entry.get("reflected_in")
            marker = entry.get("marker")
            help_args_raw = entry.get("help_args", ["--help"])

            if not command or not reflected_in or not marker:
                failures.append(
                    f"entry[{index}] missing required keys: command/reflected_in/marker"
                )
                continue

            if isinstance(help_args_raw, str):
                help_args = [help_args_raw]
            elif isinstance(help_args_raw, list):
                help_args = [str(arg) for arg in help_args_raw]
            else:
                failures.append(f"entry[{index}] help_args must be a string or list")
                continue

            try:
                result = run_command(str(command), ctx.repo_root, extra_args=help_args)
            except (OSError, subprocess.SubprocessError) as exc:
                failures.append(f"entry[{index}] command failed to run: {exc}")
                continue

            if result.returncode != 0:
                failures.append(
                    f"entry[{index}] command exit={result.returncode} for {command!r}"
                )
                continue

            # R-16 historically compares combined stdout+stderr.
            actual = normalize(result.stdout + result.stderr)

            target_path = ctx.repo_root / str(reflected_in)
            if not target_path.is_file():
                failures.append(
                    f"entry[{index}] reflected_in not found: {reflected_in}"
                )
                continue

            text = target_path.read_text(encoding="utf-8", errors="replace")
            found, block = marker_block(text, str(marker), tag="cli-help")
            if not found:
                failures.append(
                    f"entry[{index}] marker missing/invalid: marker={marker!r} in {reflected_in}"
                )
                continue

            documented = normalize(block)
            if documented != actual:
                failures.append(
                    f"entry[{index}] output mismatch for marker={marker!r}: "
                    f"doc={documented!r} actual={actual!r}"
                )

        if failures:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="CLI help output is out of sync with documented markers.",
                detail="\n".join(failures),
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=f"All {len(entries)} CLI help markers are in sync.",
        )
