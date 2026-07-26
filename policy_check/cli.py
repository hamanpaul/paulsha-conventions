# policy_check/cli.py
import argparse
import sys
from pathlib import Path

from policy_check import config as cfg
from policy_check import pr_context as prc
from policy_check.rules import registry
from policy_check.rules import families
from policy_check.rules.base import RuleContext
from policy_check.report import emit


def build_context(args: argparse.Namespace) -> RuleContext:
    repo_root = Path(args.repo).resolve()
    conf = cfg.load(repo_root)
    pr_meta = prc.load_pr_meta()
    base_ref = pr_meta.get("pr_base_ref") or args.pr_base_ref
    repo_visibility = (
        pr_meta.get("repo_visibility")
        or args.repo_visibility
        or "unknown"
    )
    return RuleContext(
        repo_root=repo_root,
        profile=conf["policy_profile"],
        policy_version=conf["policy_version"],
        config=conf,
        pr_title=pr_meta.get("pr_title") or args.pr_title,
        pr_body=pr_meta.get("pr_body") or args.pr_body,
        pr_labels=(
            pr_meta["pr_labels"]
            if pr_meta.get("pr_labels") is not None
            else (args.pr_labels.split(",") if args.pr_labels else [])
        ),
        pr_base_ref=base_ref,
        pr_head_ref=pr_meta.get("pr_head_ref") or args.pr_head_ref,
        repo_visibility=repo_visibility,
        changed_files=prc.changed_files(base_ref, repo_root, pr_meta.get("pr_base_sha")),
        latest_tag=prc.latest_tag(repo_root),
        provider=pr_meta.get("provider"),
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="policy-check")
    p.add_argument("--repo", default=".", help="Repository root")
    p.add_argument("--pr-title", default=None)
    p.add_argument("--pr-body", default=None)
    p.add_argument("--pr-labels", default=None, help="Comma-separated")
    p.add_argument("--pr-base-ref", default=None)
    p.add_argument("--pr-head-ref", default=None)
    p.add_argument(
        "--repo-visibility",
        choices=["public", "private", "internal", "unknown"],
        default=None,
    )
    p.add_argument("--only", default=None, help="Comma-separated rule IDs (e.g. R-01,R-09)")
    args = p.parse_args(argv)

    try:
        ctx = build_context(args)
    except cfg.ConfigError as exc:
        print(f"policy-check: configuration error: {exc}", file=sys.stderr)
        return 2
    rules = registry.load_all()
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        rules = [r for r in rules if r.rule_id in wanted]
    results = [r.check(ctx) for r in rules]
    family_map = {r.rule_id: families.family_of(r.rule_id) for r in rules}
    return emit(results, family_map)


if __name__ == "__main__":
    sys.exit(main())
