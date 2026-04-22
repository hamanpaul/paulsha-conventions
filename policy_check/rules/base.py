# policy_check/rules/base.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol, Optional


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"       # 豁免 label 生效
    WARN = "warn"       # 未來 MINOR 新 rule 的過渡期


@dataclass
class RuleResult:
    rule_id: str
    status: Status
    message: str
    detail: str = ""      # 供 report 展開（例 diff）
    exempt_label: Optional[str] = None


@dataclass
class RuleContext:
    repo_root: Path
    profile: str                          # stage-driven | flat
    policy_version: str
    config: dict = field(default_factory=dict)     # 解析後的 .paul-project.yml
    pr_title: Optional[str] = None
    pr_body: Optional[str] = None
    pr_labels: list[str] = field(default_factory=list)
    pr_base_ref: Optional[str] = None              # e.g. main
    pr_head_ref: Optional[str] = None              # e.g. feature/foo
    changed_files: list[str] = field(default_factory=list)
    latest_tag: Optional[str] = None


class Rule(Protocol):
    rule_id: str                                   # 例 "R-01"
    exempt_label: Optional[str]                    # 例 "policy-exempt:readme-sections" 或 None

    def check(self, ctx: RuleContext) -> RuleResult: ...
