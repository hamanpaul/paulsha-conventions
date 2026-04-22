from __future__ import annotations

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R07VersionTagSync:
    rule_id = "R-07"
    exempt_label = None

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        tag = tag.strip()
        return tag[1:] if tag.startswith("v") else tag

    @staticmethod
    def _find_release_label(labels: list[str]) -> str | None:
        for label in labels:
            if label.startswith("release:"):
                return label
        return None

    def check(self, ctx: RuleContext) -> RuleResult:
        version_path = ctx.repo_root / "VERSION"
        if not version_path.is_file():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="Missing VERSION at repository root (see R-05).",
            )

        version = version_path.read_text(encoding="utf-8", errors="replace").strip()
        if not version:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="VERSION is empty.",
                detail="Expected plain semantic version without v prefix.",
            )

        if ctx.latest_tag is None:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No latest tag found; treat as first release.",
            )

        latest_tag_raw = ctx.latest_tag.strip()
        latest_tag = self._normalize_tag(latest_tag_raw)

        if version == latest_tag:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message=f"VERSION ({version}) matches latest tag ({latest_tag_raw}).",
            )

        release_label = self._find_release_label(ctx.pr_labels)
        if release_label:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=(
                    f"VERSION ({version}) mismatches latest tag ({latest_tag_raw}); "
                    f"skipped by release label {release_label}."
                ),
                detail=f"normalized_latest_tag={latest_tag}",
                exempt_label=release_label,
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.FAIL,
            message=f"VERSION ({version}) mismatches latest tag ({latest_tag_raw}).",
            detail=f"normalized_latest_tag={latest_tag}",
        )
