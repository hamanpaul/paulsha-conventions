from __future__ import annotations

import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([\"']?)([^\"'#\s]+)\1\s*(?:#.*)?$")
TAG_RE = re.compile(r"^v?\d+(?:\.\d+){0,2}(?:[-+][0-9A-Za-z.-]+)?$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
BANNED_REFS = {"main", "master", "develop", "trunk"}


@register
class R15WorkflowPinning:
    rule_id = "R-15"
    exempt_label = None

    @staticmethod
    def _is_allowed_ref(ref: str) -> bool:
        if SHA_RE.fullmatch(ref):
            return True
        if TAG_RE.fullmatch(ref):
            return True
        return False

    def check(self, ctx: RuleContext) -> RuleResult:
        workflow_dir = ctx.repo_root / ".github" / "workflows"
        if not workflow_dir.is_dir():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No workflow files found.",
            )

        offenders: list[str] = []
        for workflow in sorted(workflow_dir.glob("*.yml")):
            for line_no, line in enumerate(
                workflow.read_text(encoding="utf-8", errors="replace").splitlines(),
                start=1,
            ):
                match = USES_RE.match(line)
                if not match:
                    continue

                uses_spec = match.group(2)
                if uses_spec.startswith("./"):
                    continue
                if "@" not in uses_spec:
                    continue

                uses_target, ref = uses_spec.rsplit("@", 1)
                if uses_target.startswith("./"):
                    continue

                if self._is_allowed_ref(ref):
                    continue

                reason = "branch ref not allowed"
                if ref in BANNED_REFS:
                    reason = f"branch ref '{ref}' not allowed"
                offenders.append(
                    f"{workflow.relative_to(ctx.repo_root)}:{line_no} uses {uses_target}@{ref} ({reason})"
                )

        if offenders:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="Workflow uses branch ref; pin with tag or 40-char SHA.",
                detail="\n".join(offenders),
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message="All workflow uses refs are pinned with tag or SHA.",
        )
