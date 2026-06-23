from __future__ import annotations

from pathlib import Path

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status

REPO = "hamanpaul/paulsha-conventions"
ENGINE = f"{REPO}/.github/workflows/reusable-policy-check.yml"


def _rule():
    return {r.rule_id: r for r in registry.load_all()}["R-23"]


def _ctx(repo_root: Path, *, policy_version="1.0.5", configured=True, labels=None):
    config = {"conventions_engine": {"repo": REPO}} if configured else {}
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version=policy_version,
        config=config,
        pr_labels=labels or [],
    )


def _wf(tmp_path: Path, uses_line: str):
    d = tmp_path / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / "policy-check.yml").write_text(f"jobs:\n  check:\n    {uses_line}\n", encoding="utf-8")
    return tmp_path


def test_r23_pass_on_tag_match(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.5")
    assert _rule().check(_ctx(repo)).status == Status.PASS


def test_r23_fail_on_tag_mismatch(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.2")
    result = _rule().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "1.0.2" in result.detail and "1.0.5" in result.detail


def test_r23_pass_on_sha_with_matching_comment(tmp_path):
    sha = "a" * 40
    repo = _wf(tmp_path, f"uses: {ENGINE}@{sha}  # v1.0.5")
    assert _rule().check(_ctx(repo)).status == Status.PASS


def test_r23_fail_on_sha_with_mismatching_comment(tmp_path):
    sha = "a" * 40
    repo = _wf(tmp_path, f"uses: {ENGINE}@{sha}  # v1.0.2")
    assert _rule().check(_ctx(repo)).status == Status.FAIL


def test_r23_warn_on_bare_sha(tmp_path):
    sha = "b" * 40
    repo = _wf(tmp_path, f"uses: {ENGINE}@{sha}")
    assert _rule().check(_ctx(repo)).status == Status.WARN


def test_r23_na_on_local_uses(tmp_path):
    repo = _wf(tmp_path, "uses: ./.github/workflows/reusable-policy-check.yml")
    assert _rule().check(_ctx(repo)).status == Status.PASS


def test_r23_na_when_engine_not_configured(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.2")
    assert _rule().check(_ctx(repo, configured=False)).status == Status.PASS


def test_r23_skip_on_exempt_label(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.2")
    result = _rule().check(_ctx(repo, labels=["policy-exempt:engine-pin"]))
    assert result.status == Status.SKIP


def test_r23_fail_on_partial_major_tag(tmp_path):
    # 偏 semver tag（無法等於完整 policy_version）必須 FAIL，而非 WARN（非阻擋）
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1")
    assert _rule().check(_ctx(repo)).status == Status.FAIL


def test_r23_fail_on_minor_only_tag(tmp_path):
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0")
    assert _rule().check(_ctx(repo)).status == Status.FAIL


def test_r23_warn_on_ambiguous_sha_comment(tmp_path):
    # 尾註非「以 vX.Y.Z 起首」時不得誤取任意 token → 視為無法驗證（WARN）
    sha = "c" * 40
    repo = _wf(tmp_path, f"uses: {ENGINE}@{sha}  # previous v1.0.5; actual v1.0.6")
    assert _rule().check(_ctx(repo)).status == Status.WARN


def test_r23_normalizes_trailing_slash_repo(tmp_path):
    # malformed config（trailing slash）不得讓真實 pin 靜默變成 NA
    repo = _wf(tmp_path, f"uses: {ENGINE}@v1.0.2")
    ctx = RuleContext(
        repo_root=repo,
        profile="flat",
        policy_version="1.0.5",
        config={"conventions_engine": {"repo": REPO + "/"}},
    )
    assert _rule().check(ctx).status == Status.FAIL
