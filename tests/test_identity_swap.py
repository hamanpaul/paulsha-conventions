"""swap 演練：驗證「日後切到 ARC GitLab 只需換設定」這項承諾。"""
import pytest

from policy_check import identity as ident


GITLAB_ARC = {
    "canonical_org": "mcu",
    "engine_repo": "mcu/ti/arc-conventions",
    "remote_base": "https://vcs-sw2.arcadyan.com.tw",
    "distribution_name": "arc-conventions",
    "provider": "github",
}


@pytest.fixture
def gitlab_identity(monkeypatch):
    ident.identity.cache_clear()
    monkeypatch.setattr(ident, "_load_raw", lambda: dict(GITLAB_ARC))
    yield
    ident.identity.cache_clear()


def test_remote_urls_follow_non_github_base(gitlab_identity):
    assert ident.identity().remote_urls() == {
        "https://vcs-sw2.arcadyan.com.tw/mcu/ti/arc-conventions",
        "ssh://git@vcs-sw2.arcadyan.com.tw/mcu/ti/arc-conventions",
        "git@vcs-sw2.arcadyan.com.tw:mcu/ti/arc-conventions",
    }


def test_bundle_verification_follows_swapped_identity(gitlab_identity):
    from policy_check.runtime_bundle import verification

    # _require_manifest_shape 的完整必填欄位（package/wheels/skill/runtime/
    # runtime_compatibility/prerequisites）與 identity swap 無關；補齊它們
    # 只是讓 manifest 通過既有的一般 shape 檢查，才能真正驗到本測試關心的
    # repository/engine_repo 參數化行為（Task 4 report 的已知缺口，見
    # test_manifest_repository_is_checked_against_argument 的相同修法）。
    manifest = {
        "schema_version": verification.SCHEMA_VERSION,
        "policy_version": "1.0.15",
        "skill_version": "1.0.15",
        "repository": "mcu/ti/arc-conventions",
        "release_tag": "v1.0.15",
        "release_commit": "0" * 40,
        "package": {
            "name": "policy-check",
            "version": "1.0.15",
            "requires_python": ">=3.11",
        },
        "wheels": [
            {
                "path": "wheels/policy_check-1.0.15-py3-none-any.whl",
                "sha256": "a" * 64,
            }
        ],
        "skill": {"path": "skills/preflight-ci", "sha256": "a" * 64},
        "runtime": {
            "path": "runtime/runtime_manager.py",
            "sha256": "a" * 64,
            "verifier_path": "runtime/runtime_verifier.py",
            "verifier_sha256": "a" * 64,
        },
        "runtime_compatibility": {
            "implementation": "cpython",
            "python": "3.11",
            "abi": "cp311",
            "platform": "linux",
        },
        "prerequisites": ["git"],
    }
    verification._require_manifest_shape(manifest, ident.identity().engine_repo)
