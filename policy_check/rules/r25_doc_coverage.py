"""R-25 — deterministic doc coverage (omission) gate.

Opt-in: when the project policy does not declare ``doc_coverage`` the rule is
not-applicable and PASSes. When declared, it checks that the repo's declared
public facts are each mentioned at least once in the configured target docs.

``mode: changed`` only requires facts newly introduced in ``base...HEAD``;
``mode: all`` requires every extracted fact. Command-based ``cli_tree`` sources
cannot be snapshotted at base, so in ``changed`` mode they are only checked when
the gate also has full evidence (i.e. they are gated in ``all`` mode only) —
consistent with the design principle of never FAILing without evidence.
"""
from __future__ import annotations

import subprocess

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register
from policy_check.rules._doc_scope import configured_doc_paths, matches_doc_path
from policy_check.rules._doc_links import git_tracked, resolve_base
from policy_check.rules import _fact_extract as fe


def _git_show(root, rev: str, rel: str):
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "show", f"{rev}:{rel}"],
            text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None


@register
class R25DocCoverage:
    rule_id = "R-25"
    exempt_label = None  # opt-in via config; unconfigured repos are not-applicable

    def check(self, ctx: RuleContext) -> RuleResult:
        config = ctx.config or {}
        dc = config.get("doc_coverage")
        if dc is None:
            return RuleResult(self.rule_id, Status.PASS,
                              "No doc_coverage declared (not applicable).")
        if not isinstance(dc, dict):
            return RuleResult(self.rule_id, Status.FAIL,
                              "doc_coverage must be a mapping.")

        root = ctx.repo_root
        mode = dc.get("mode", "changed")
        if mode not in ("changed", "all"):
            return RuleResult(self.rule_id, Status.FAIL,
                              f"doc_coverage.mode must be 'changed' or 'all', got {mode!r}.")

        targets = dc.get("targets") or []
        sources = dc.get("sources") or []
        doc_paths = configured_doc_paths(config)

        if not targets:
            return RuleResult(self.rule_id, Status.FAIL,
                              "doc_coverage.targets must list at least one target doc.")
        for target in targets:
            if not matches_doc_path(target, doc_paths):
                return RuleResult(self.rule_id, Status.FAIL,
                                  f"doc_coverage target out of canonical doc scope (doc_paths): {target}")
            if not (root / target).is_file():
                return RuleResult(self.rule_id, Status.FAIL,
                                  f"doc_coverage target doc not found: {target}")

        if not sources:
            return RuleResult(self.rule_id, Status.FAIL,
                              "doc_coverage.sources must declare at least one extractor.")
        for index, source in enumerate(sources, start=1):
            err = fe.validate_source(source)
            if err:
                return RuleResult(self.rule_id, Status.FAIL,
                                  f"doc_coverage.sources[{index}] invalid: {err}")

        target_text = "\n".join(
            (root / t).read_text(encoding="utf-8", errors="replace") for t in targets
        )

        file_sources = [s for s in sources if s["kind"] in fe.FILE_KINDS]
        cli_sources = [s for s in sources if s["kind"] in fe.COMMAND_KINDS]

        head_files = git_tracked(root)

        def _read_head(rel: str):
            try:
                return (root / rel).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return None

        try:
            head_file_facts: set[str] = set()
            for source in file_sources:
                head_file_facts |= fe.extract_file_facts(source, head_files, _read_head)
        except fe.ExtractorError as exc:
            return RuleResult(self.rule_id, Status.FAIL,
                              f"doc_coverage extractor failed: {exc}")

        note = ""
        if mode == "all":
            # cli_tree is only executed/gated in mode=all (cannot be snapshotted at base).
            try:
                cli_facts: set[str] = set()
                for source in cli_sources:
                    cli_facts |= fe.extract_cli_facts(source, root)
            except fe.ExtractorError as exc:
                return RuleResult(self.rule_id, Status.FAIL,
                                  f"doc_coverage extractor failed: {exc}")
            facts_to_check = head_file_facts | cli_facts
        else:  # changed
            base = resolve_base(root, ctx.pr_base_ref)
            if not base:
                return RuleResult(
                    self.rule_id, Status.WARN,
                    "doc_coverage mode=changed but no base ref is resolvable; "
                    "omission gate skipped (no diff context).")
            base_files = git_tracked(root, base)
            base_file_facts: set[str] = set()
            for source in file_sources:
                base_file_facts |= fe.extract_file_facts(
                    source, base_files, lambda rel: _git_show(root, base, rel))
            facts_to_check = head_file_facts - base_file_facts
            if cli_sources:
                # cli_tree cannot be diffed at base; not executed nor gated in changed mode.
                note = " (cli_tree sources are only gated in mode=all; skipped in changed)"

        missing = sorted(f for f in facts_to_check if not fe.is_mentioned(f, target_text))
        if missing:
            return RuleResult(
                self.rule_id, Status.FAIL,
                f"{len(missing)} declared fact(s) not mentioned in target docs.{note}",
                detail="\n".join(missing[:20]))

        return RuleResult(
            self.rule_id, Status.PASS,
            f"All {len(facts_to_check)} checked fact(s) are documented.{note}")
