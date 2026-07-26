from __future__ import annotations

import re
from pathlib import PurePosixPath

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check import config as policy_config
from policy_check.rules.registry import register

# conventions_engine.repo 須為 'owner/repo'（空字串 = 未設/NA sentinel，放行）
_ENGINE_REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


def _is_repo_relative_path(value: object, *, allow_dot: bool = True) -> bool:
    if not isinstance(value, str) or not value.strip() or "\\" in value:
        return False
    path = PurePosixPath(value.strip())
    if path.is_absolute() or ".." in path.parts:
        return False
    return allow_dot or path.as_posix() != "."


@register
class R08PolicyConfigSchema:
    rule_id = "R-08"
    exempt_label = None

    _required_keys = ("policy_profile", "policy_version")
    _valid_profiles = {"stage-driven", "flat"}
    _valid_tiers = {"shareable", "work", "personal"}

    def check(self, ctx: RuleContext) -> RuleResult:
        try:
            resolution = policy_config.resolve(ctx.repo_root)
        except policy_config.ConfigError as exc:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message=str(exc),
            )

        path = resolution.path
        data = resolution.data

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
            mode = conventions_engine.get("mode")
            if mode is not None and mode not in ("workflow", "pip"):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="conventions_engine.mode must be one of ['workflow', 'pip']",
                )
            if isinstance(repo, str) and repo != "" and not _ENGINE_REPO_RE.match(repo):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="conventions_engine.repo must be 'owner/repo' form (no trailing slash or extra path segment)",
                )

        # 驗證 doc_paths：若存在，須為 list[str]
        doc_paths = data.get("doc_paths")
        if doc_paths is not None and (
            not isinstance(doc_paths, list) or not all(isinstance(x, str) for x in doc_paths)
        ):
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="doc_paths must be a list of strings",
            )

        # 驗證 doc_coverage 區塊：mapping；mode ∈ {changed, all}；targets list[str]；sources list[mapping]
        doc_coverage = data.get("doc_coverage")
        if doc_coverage is not None:
            if not isinstance(doc_coverage, dict):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="doc_coverage must be a mapping")
            mode = doc_coverage.get("mode")
            if mode is not None and mode not in ("changed", "all"):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="doc_coverage.mode must be one of ['all', 'changed']")
            targets = doc_coverage.get("targets")
            if targets is not None and (
                not isinstance(targets, list) or not all(isinstance(x, str) for x in targets)
            ):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="doc_coverage.targets must be a list of strings")
            sources = doc_coverage.get("sources")
            if sources is not None and (
                not isinstance(sources, list) or not all(isinstance(x, dict) for x in sources)
            ):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="doc_coverage.sources must be a list of mappings")

        # 驗證 generated_facts 區塊：list[mapping]
        generated_facts = data.get("generated_facts")
        if generated_facts is not None and (
            not isinstance(generated_facts, list)
            or not all(isinstance(x, dict) for x in generated_facts)
        ):
            return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                              message="generated_facts must be a list of mappings")

        # 驗證 preflight：typed argv、repo-relative paths、bounded timeout。
        # 未知 subkey 保持 lenient；只驗已知契約欄位。
        preflight = data.get("preflight")
        if preflight is not None:
            if not isinstance(preflight, dict):
                return RuleResult(
                    rule_id=self.rule_id,
                    status=Status.FAIL,
                    message="preflight must be a mapping",
                )
            steps = preflight.get("steps")
            if steps is not None:
                if not isinstance(steps, list) or not all(
                    isinstance(step, dict) for step in steps
                ):
                    return RuleResult(
                        rule_id=self.rule_id,
                        status=Status.FAIL,
                        message="preflight.steps must be a list of mappings",
                    )
                names: set[str] = set()
                for index, step in enumerate(steps):
                    prefix = f"preflight.steps[{index}]"
                    name = step.get("name")
                    if not isinstance(name, str) or not name.strip():
                        return RuleResult(
                            rule_id=self.rule_id,
                            status=Status.FAIL,
                            message=f"{prefix}.name must be a non-empty string",
                        )
                    if name.strip() in names:
                        return RuleResult(
                            rule_id=self.rule_id,
                            status=Status.FAIL,
                            message=f"{prefix}.name must be unique",
                        )
                    names.add(name.strip())
                    if step.get("kind") not in ("validation", "tests"):
                        return RuleResult(
                            rule_id=self.rule_id,
                            status=Status.FAIL,
                            message=f"{prefix}.kind must be one of ['tests', 'validation']",
                        )
                    argv = step.get("argv")
                    if (
                        not isinstance(argv, list)
                        or not argv
                        or not all(isinstance(item, str) and item for item in argv)
                    ):
                        return RuleResult(
                            rule_id=self.rule_id,
                            status=Status.FAIL,
                            message=f"{prefix}.argv must be a non-empty list of strings",
                        )
                    cwd = step.get("cwd")
                    if cwd is not None and not _is_repo_relative_path(cwd):
                        return RuleResult(
                            rule_id=self.rule_id,
                            status=Status.FAIL,
                            message=f"{prefix}.cwd must be a repo-relative path",
                        )
                    when = step.get("when_path_exists")
                    if when is not None and not _is_repo_relative_path(
                        when,
                        allow_dot=False,
                    ):
                        return RuleResult(
                            rule_id=self.rule_id,
                            status=Status.FAIL,
                            message=(
                                f"{prefix}.when_path_exists must be a repo-relative path"
                            ),
                        )
                    timeout = step.get("timeout_seconds")
                    if timeout is not None and (
                        not isinstance(timeout, int)
                        or isinstance(timeout, bool)
                        or timeout <= 0
                    ):
                        return RuleResult(
                            rule_id=self.rule_id,
                            status=Status.FAIL,
                            message=f"{prefix}.timeout_seconds must be a positive integer",
                        )

        # 驗證 moc 區塊：mapping；static/map 為 str；triggers 為 list[str]
        moc = data.get("moc")
        if moc is not None:
            if not isinstance(moc, dict):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="moc must be a mapping")
            for key in ("static", "map"):
                val = moc.get(key)
                if val is not None and not isinstance(val, str):
                    return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                      message=f"moc.{key} must be a string")
            triggers = moc.get("triggers")
            if triggers is not None and (
                not isinstance(triggers, list) or not all(isinstance(x, str) for x in triggers)
            ):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="moc.triggers must be a list of strings")

        # 驗證 auto_build 區塊（#30）：LLM auto build 慣例欄位。
        # 只驗形狀、永不執行其中命令；未知 subkey 一律放行（欄位演進不綁 engine release）。
        auto_build = data.get("auto_build")
        if auto_build is not None:
            if not isinstance(auto_build, dict):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="auto_build must be a mapping")
            description = auto_build.get("description")
            if description is not None and not isinstance(description, str):
                return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                  message="auto_build.description must be a string")
            for key in ("setup", "steps", "artifacts", "verify"):
                val = auto_build.get(key)
                if val is None:
                    continue
                if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                    return RuleResult(rule_id=self.rule_id, status=Status.FAIL,
                                      message=f"auto_build.{key} must be a list of strings")

        warning = resolution.warning
        return RuleResult(
            rule_id=self.rule_id,
            status=Status.WARN if warning else Status.PASS,
            message=warning or f"{path.name} schema is valid for R-08.",
        )
