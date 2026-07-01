from __future__ import annotations

import importlib.metadata
import re

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register

_USES_RE = re.compile(
    r'^\s*(?:-\s*)?uses:\s*["\']?(?P<target>[^"\'@#\s]+)@(?P<ref>[^"\'#\s]+)["\']?'
    r'\s*(?:#\s*(?P<comment>.*?))?\s*$'
)
# 「偏 semver」tag（v1 / v1.2 也納入比對 → 與完整 policy_version 不齊即 FAIL，不放生 WARN）
_TAG_LOOSE_RE = re.compile(r'^v?(\d+(?:\.\d+){0,2}(?:-fix\.\d+)?)$')
# 尾註版本須以 vX.Y.Z 起首（錨定），避免誤取註解中任意 version token
_COMMENT_VER_RE = re.compile(r'^v?(\d+\.\d+\.\d+(?:-fix\.\d+)?)\b')
_SHA_RE = re.compile(r'^[0-9a-fA-F]{40}$')


def _installed_version() -> str:
    return importlib.metadata.version("policy-check")


def _canon_version(v: str) -> str:
    """policy 語法 X.Y.Z[-fix.N] ↔ PEP 440 X.Y.Z[.postN] 的共同正規化。"""
    v = v.strip().lower()
    v = re.sub(r"^v(?=\d)", "", v, count=1)
    v = re.sub(r"-fix\.(\d+)$", r".post\1", v)
    return v


@register
class R23EnginePinAttestation:
    rule_id = "R-23"
    exempt_label = "policy-exempt:engine-pin"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.SKIP,
                message=f"R-23 exempted by label: {self.exempt_label}",
                exempt_label=self.exempt_label,
            )

        engine_cfg = ctx.config.get("conventions_engine") or {}
        mode = (engine_cfg.get("mode") if isinstance(engine_cfg, dict) else None) or "workflow"
        if mode == "pip":
            declared = ctx.policy_version
            try:
                installed = _installed_version()
            except importlib.metadata.PackageNotFoundError:
                return RuleResult(
                    rule_id=self.rule_id, status=Status.FAIL,
                    message="conventions_engine.mode=pip but 'policy-check' is not installed; version not attestable.",
                )
            if _canon_version(installed) == _canon_version(declared):
                return RuleResult(
                    rule_id=self.rule_id, status=Status.PASS,
                    message=f"installed policy-check {installed} matches policy_version {declared}",
                )
            return RuleResult(
                rule_id=self.rule_id, status=Status.FAIL,
                message=f"installed policy-check {installed} but policy_version declares {declared}",
            )

        repo = engine_cfg.get("repo") if isinstance(engine_cfg, dict) else None
        if not repo:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No conventions_engine.repo configured; R-23 not applicable.",
            )
        repo = repo.rstrip("/")  # 容忍 config 末尾斜線，避免真實 pin 靜默變 NA

        workflows_dir = ctx.repo_root / ".github" / "workflows"
        if not workflows_dir.is_dir():
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message="No .github/workflows directory; R-23 not applicable.",
            )

        declared = ctx.policy_version
        fails: list[str] = []
        warns: list[str] = []
        matched = 0

        for workflow in sorted(workflows_dir.iterdir()):
            if workflow.suffix not in (".yml", ".yaml") or not workflow.is_file():
                continue
            for line_no, line in enumerate(
                workflow.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
            ):
                m = _USES_RE.match(line)
                if not m:
                    continue
                target = m.group("target")
                if target.startswith("./"):
                    continue
                if not (target == repo or target.startswith(repo + "/")):
                    continue
                matched += 1
                ref = m.group("ref")
                comment = m.group("comment") or ""
                loc = f"{workflow.name}:{line_no}"

                if _SHA_RE.match(ref):
                    cm = _COMMENT_VER_RE.match(comment.strip())
                    if not cm:
                        warns.append(
                            f"{loc}: engine pinned by SHA without a leading '# vX.Y.Z' "
                            f"annotation; version not verifiable offline"
                        )
                        continue
                    version = cm.group(1)
                else:
                    loose = _TAG_LOOSE_RE.match(ref)
                    if not loose:
                        warns.append(
                            f"{loc}: engine ref '{ref}' is neither a version tag nor a "
                            f"40-char SHA; version not verifiable"
                        )
                        continue
                    version = loose.group(1)

                if version != declared:
                    fails.append(
                        f"{loc}: engine pinned at v{version} but policy_version declares {declared}"
                    )

        if matched == 0:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.PASS,
                message=f"No external pin of {repo}; R-23 not applicable.",
            )
        if fails:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.FAIL,
                message="engine pin out of sync with policy_version",
                detail="\n".join(fails + warns),
            )
        if warns:
            return RuleResult(
                rule_id=self.rule_id,
                status=Status.WARN,
                message="engine pin version not verifiable offline",
                detail="\n".join(warns),
            )
        return RuleResult(
            rule_id=self.rule_id,
            status=Status.PASS,
            message=f"engine pin aligned to policy_version {declared}",
        )
