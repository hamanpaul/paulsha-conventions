from __future__ import annotations

import re

import yaml

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.config import CONFIG_NAMES_DISPLAY, config_path
from policy_check.rules.registry import register

# conventions_engine.repo 須為 'owner/repo'（空字串 = 未設/NA sentinel，放行）
_ENGINE_REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


@register
class R08PolicyConfigSchema:
    rule_id = "R-08"
    exempt_label = None

    _required_keys = ("policy_profile", "policy_version")
    _valid_profiles = {"stage-driven", "flat"}
    _valid_tiers = {"shareable", "work", "personal"}

    def check(self, ctx: RuleContext) -> RuleResult:
        path = config_path(ctx.repo_root)
        if not path.is_file():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"Missing {CONFIG_NAMES_DISPLAY} at repository root.",
            )

        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"{path.name} is not valid YAML: {exc}",
            )

        data = loaded or {}
        if not isinstance(data, dict):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"{path.name} top-level must be a mapping/object.",
            )

        missing = [key for key in self._required_keys if key not in data]
        if missing:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=f"{path.name} missing required keys: {missing}",
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

        tier = data.get("tier")
        if tier is not None and tier not in self._valid_tiers:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=(
                    "tier must be one of "
                    f"{sorted(self._valid_tiers)}, got {tier!r}"
                ),
            )

        # 驗證 secret_scan 區塊：allow/markers/public_names 須為 list[str]
        secret_scan = data.get("secret_scan")
        if secret_scan is not None:
            if not isinstance(secret_scan, dict):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="secret_scan must be a mapping",
                )
            for key in ("allow", "markers", "public_names"):
                val = secret_scan.get(key)
                if val is None:
                    continue
                if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                    return RuleResult(
                        rule_id=self.rule_id,
                        status=Status.FAIL,
                        message=f"secret_scan.{key} must be a list of strings",
                    )

        # 驗證 doc_reference 區塊：allow 須為 list[str]
        doc_reference = data.get("doc_reference")
        if doc_reference is not None:
            if not isinstance(doc_reference, dict):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="doc_reference must be a mapping",
                )
            allow = doc_reference.get("allow")
            if allow is not None and (
                not isinstance(allow, list) or not all(isinstance(x, str) for x in allow)
            ):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="doc_reference.allow must be a list of strings",
                )

        # 驗證 agent_files 區塊：須為 mapping；mode（若存在）須 ∈ {symlink, copy}
        agent_files = data.get("agent_files")
        if agent_files is not None:
            if not isinstance(agent_files, dict):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="agent_files must be a mapping",
                )
            mode = agent_files.get("mode")
            if mode is not None and mode not in ("symlink", "copy"):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="agent_files.mode must be one of ['copy', 'symlink']",
                )

        # 驗證 conventions_engine 區塊：須為 mapping；repo（若存在）須為 str
        conventions_engine = data.get("conventions_engine")
        if conventions_engine is not None:
            if not isinstance(conventions_engine, dict):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="conventions_engine must be a mapping",
                )
            repo = conventions_engine.get("repo")
            if repo is not None and not isinstance(repo, str):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="conventions_engine.repo must be a string",
                )
            if isinstance(repo, str) and repo != "" and not _ENGINE_REPO_RE.match(repo):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="conventions_engine.repo must be 'owner/repo' form (no trailing slash or extra path segment)",
                )

        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=f"{path.name} schema is valid for R-08.",
        )
