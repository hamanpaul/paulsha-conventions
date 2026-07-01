from __future__ import annotations

from pathlib import Path

from policy_check import config as cfg
from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(
    repo_root: Path,
    labels: list[str] | None = None,
    provider: str | None = None,
) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.3",
        config=cfg.load(repo_root),
        pr_labels=labels or [],
        provider=provider,
    )


def get_rule():
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert "R-21" in loaded, "R-21 is not registered"
    return loaded["R-21"]


def _git_init(path: Path) -> None:
    # _iter_text_files 走 git ls-files；tmp repo 的檔案需先被 git 追蹤才會被掃描
    import subprocess

    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)


def test_r21_pass_when_shareable_clean(fixture_repo):
    repo = fixture_repo("secret-scan/shareable-clean")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.PASS


def test_r21_fail_when_shareable_has_marker(fixture_repo):
    repo = fixture_repo("secret-scan/shareable-leak")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.FAIL
    assert "BGW720" in result.detail or "platform.py" in result.detail


def test_r21_pass_when_work_tier_has_marker(fixture_repo):
    repo = fixture_repo("secret-scan/work-leak")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.PASS
    assert "work" in result.message


def test_r21_skip_with_exemption_label(fixture_repo):
    repo = fixture_repo("secret-scan/shareable-leak")
    result = get_rule().check(
        make_ctx(repo, labels=["policy-exempt:secret-scan"])
    )
    assert result.status == Status.SKIP
    assert result.exempt_label == "policy-exempt:secret-scan"


def test_r21_gitlab_does_not_honor_secret_scan_exemption_label(fixture_repo):
    repo = fixture_repo("secret-scan/shareable-leak")
    result = get_rule().check(
        make_ctx(
            repo,
            labels=["policy-exempt:secret-scan"],
            provider="gitlab",
        )
    )
    assert result.status == Status.FAIL
    assert result.exempt_label is None


def test_r21_respects_config_allowlist(fixture_repo):
    repo = fixture_repo("secret-scan/shareable-allowlisted")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.PASS


def test_r21_exempts_own_rule_file(tmp_path):
    # 模擬 repo 內含本規則檔（其 denylist 字串不應觸發）
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n",
        encoding="utf-8",
    )
    rules_dir = tmp_path / "policy_check" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "r21_secret_scan.py").write_text(
        'MARKERS = "brcm broadcom BGW720"\n', encoding="utf-8"
    )
    from policy_check import config as cfg
    ctx = RuleContext(
        repo_root=tmp_path, profile="flat", policy_version="1.0.3",
        config=cfg.load(tmp_path),
    )
    assert get_rule().check(ctx).status == Status.PASS


def test_r21_skips_gitignored_files(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n",
        encoding="utf-8",
    )
    (tmp_path / ".gitignore").write_text("build/\n", encoding="utf-8")
    (tmp_path / "clean.py").write_text("x = 1\n", encoding="utf-8")
    build = tmp_path / "build"
    build.mkdir()
    (build / "artifact.txt").write_text("leaked BGW720 marker\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    from policy_check import config as cfg
    ctx = RuleContext(
        repo_root=tmp_path, profile="flat", policy_version="1.0.3",
        config=cfg.load(tmp_path),
    )
    # build/ is gitignored → its marker file is untracked → R-21 must not scan it
    assert get_rule().check(ctx).status == Status.PASS


def test_structural_detectors_always_on(tmp_path):
    # 結構偵測器（/home/<user>/ 絕對路徑）恆開，不受 markers 設定影響
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n"
        "secret_scan:\n  public_names: [bgw720, build20]\n", encoding="utf-8")
    (tmp_path / "f.txt").write_text("see /home/paul_chen/secret\n", encoding="utf-8")
    _git_init(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.FAIL


def test_structural_path_detector_is_case_insensitive(tmp_path):
    # 個人絕對路徑須不分大小寫命中（大寫 username），還原原 IGNORECASE 行為
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n", encoding="utf-8")
    (tmp_path / "f.txt").write_text("path /home/Paul/secret\n", encoding="utf-8")
    _git_init(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.FAIL


def test_public_vendor_name_not_flagged(tmp_path):
    # 廠商／OS 名（baseline public_names）已減敏，不再觸發
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n", encoding="utf-8")
    (tmp_path / "doc.md").write_text("supports broadcom brcm prplOS marvell\n", encoding="utf-8")
    _git_init(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS


def test_marker_token_still_flagged(tmp_path):
    # 內部代號（baseline markers）仍觸發
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n", encoding="utf-8")
    (tmp_path / "doc.md").write_text("verify on BGW720 board\n", encoding="utf-8")
    _git_init(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.FAIL


def test_repo_can_extend_markers(tmp_path):
    # 每 repo 的 secret_scan.markers 會「疊加」到 baseline，新代號也應觸發
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n"
        "secret_scan:\n  markers: [\"acme9000\"]\n", encoding="utf-8")
    (tmp_path / "x.md").write_text("internal acme9000 board\n", encoding="utf-8")
    _git_init(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.FAIL


def test_repo_public_names_suppresses(tmp_path):
    # 每 repo 的 secret_scan.public_names 會抑制對應代號（即使屬 baseline markers）
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.3\ntier: shareable\n"
        "secret_scan:\n  public_names: [\"bgw720\"]\n", encoding="utf-8")
    (tmp_path / "x.md").write_text("legacy BGW720 note\n", encoding="utf-8")
    _git_init(tmp_path)
    assert get_rule().check(make_ctx(tmp_path)).status == Status.PASS
