from __future__ import annotations

import yaml

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register


@register
class R08PolicyConfigSchema:
    rule_id = "R-08"
    exempt_label = None

    _required_keys = ("policy_profile", "policy_version")
    _valid_profiles = {"stage-driven", "flat"}

    def check(self, ctx: RuleContext) -> RuleResult:
        config_path = ctx.repo_root / ".paul-project.yml"
        if not config_path.is_file():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="Missing .paul-project.yml at repository root.",
            )

        try:
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f".paul-project.yml is not valid YAML: {exc}",
            )

        data = loaded or {}
        if not isinstance(data, dict):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=".paul-project.yml top-level must be a mapping/object.",
            )

        missing = [key for key in self._required_keys if key not in data]
        if missing:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f".paul-project.yml missing required keys: {missing}",
            )

        profile = data["policy_profile"]
        if profile not in self._valid_profiles:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=(
                    "policy_profile must be one of "
                    f"{sorted(self._valid_profiles)}, got {profile!r}"
                ),
            )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=".paul-project.yml schema is valid for R-08.",
        )
