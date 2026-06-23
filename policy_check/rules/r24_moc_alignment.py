from __future__ import annotations

from fnmatch import fnmatch

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register
from policy_check.rules._doc_links import (
    LINK_RE, path_candidates, git_tracked, resolve_base,
)

_GOVERNED_PREFIXES = ("openspec/changes/", "docs/superpowers/")


@register
class R24MocAlignment:
    rule_id = "R-24"
    exempt_label = "policy-exempt:moc-alignment"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(self.rule_id, Status.SKIP,
                              f"Skipped by exemption label: {self.exempt_label}.",
                              exempt_label=self.exempt_label)

        moc = (ctx.config or {}).get("moc") or {}
        if not isinstance(moc, dict) or not moc:
            return RuleResult(self.rule_id, Status.PASS, "No moc declared; R-24 not applicable.")

        fails: list[str] = []
        warns: list[str] = []

        changed = set(ctx.changed_files or [])
        static = moc.get("static")
        triggers = moc.get("triggers") or []
        if static and triggers and changed:
            hit = sorted(f for f in changed if any(fnmatch(f, g) for g in triggers))
            if hit and static not in changed:
                warns.append(
                    f"static MOC '{static}' 未隨 trigger 變更同步；命中：{', '.join(hit[:5])}"
                )

        return self._verdict(fails, warns)

    def _verdict(self, fails, warns) -> RuleResult:
        if fails:
            return RuleResult(self.rule_id, Status.FAIL,
                              f"MOC map has {len(fails)} dangling reference(s) introduced by this change.",
                              detail="\n".join(fails[:20]))
        if warns:
            return RuleResult(self.rule_id, Status.WARN,
                              f"MOC alignment: {len(warns)} advisory item(s).",
                              detail="\n".join(warns[:20]))
        return RuleResult(self.rule_id, Status.PASS, "MOC aligned with this change.")
