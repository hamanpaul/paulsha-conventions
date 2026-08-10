from pathlib import Path

import pytest

from policy_check import identity as ident
from policy_check import preflight


ARC = {
    "canonical_org": "hamanpaul",
    "engine_repo": "hamanpaul/arc-conventions",
    "remote_base": "https://github.com",
    "distribution_name": "arc-conventions",
    "provider": "github",
}


@pytest.fixture
def arc_identity(monkeypatch):
    ident.identity.cache_clear()
    monkeypatch.setattr(ident, "_load_raw", lambda: dict(ARC))
    yield
    ident.identity.cache_clear()


def test_canonical_remote_set_follows_identity(arc_identity):
    urls = ident.identity().remote_urls()
    assert "https://github.com/hamanpaul/arc-conventions" in urls
    assert "https://github.com/hamanpaul/paulsha-conventions" not in urls


def test_repo_config_cannot_redirect_engine(arc_identity, tmp_path):
    """核心不變式：被檢查的 repo 不能把 authority 指到別處。"""
    engine_root = tmp_path / "engine"
    (engine_root / "policy_check").mkdir(parents=True)
    (engine_root / "policy_check" / "preflight.py").write_text("", encoding="utf-8")
    config = {
        "policy_version": "1.0.15",
        "conventions_engine": {"repo": "attacker/evil-conventions"},
    }
    with pytest.raises(preflight.PreflightGateError) as exc:
        preflight._source_engine(engine_root, config, display_prefix="test")
    message = str(exc.value)
    assert "conventions_engine.repo" in message
    assert "hamanpaul/arc-conventions" in message
    assert "attacker/evil-conventions" in message


def _write_arc_workflow(repo: Path, sha: str) -> None:
    workflow = repo / ".github" / "workflows" / "policy-check.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "jobs:\n"
        "  policy:\n"
        "    uses: hamanpaul/arc-conventions/.github/workflows/"
        f"reusable-policy-check.yml@{sha}\n"
        "    with:\n"
        f"      policy_engine_ref: {sha}\n",
        encoding="utf-8",
    )


def test_offline_does_not_touch_unreachable_remote(monkeypatch, tmp_path):
    """--offline 時走已安裝版本比對路徑，即使 identity().remote_base 不可達，也不得嘗試任何網路操作。

    _populate_cache（本 task 改為由 identity().remote_base 組出 fetch URL）與
    _run_or_error（實際發出 git/網路指令的唯一入口）在此路徑上都必須完全不被呼叫；
    只要有一個被叫到，代表 offline 短路失效、程式會嘗試連向不可達的 remote_base。
    """
    ident.identity.cache_clear()
    monkeypatch.setattr(ident, "_load_raw", lambda: {
        "canonical_org": "hamanpaul",
        "engine_repo": "hamanpaul/arc-conventions",
        "remote_base": "https://unreachable.invalid",
        "distribution_name": "arc-conventions",
        "provider": "github",
    })
    try:
        sha = "a" * 40
        _write_arc_workflow(tmp_path, sha)
        config = {
            "policy_profile": "flat",
            "policy_version": "1.0.15",
            "conventions_engine": {"repo": "hamanpaul/arc-conventions", "mode": "workflow"},
        }

        monkeypatch.setattr(preflight, "_self_engine", lambda *_a: None)
        monkeypatch.setattr(preflight, "_installed_version", lambda: "1.0.15")
        monkeypatch.setattr(preflight, "_verify_cache", lambda *_a: None)
        monkeypatch.setattr(
            preflight,
            "_populate_cache",
            lambda *_a: pytest.fail(
                "offline path must not populate cache from remote_base"
            ),
        )

        def _spy(cmd, *args, **kwargs):
            raise AssertionError(f"offline path must not run: {cmd}")

        monkeypatch.setattr(preflight, "_run_or_error", _spy)

        result = preflight._resolve_engine(
            tmp_path,
            config,
            offline=True,
            cache_dir=tmp_path / "cache",
        )
        assert result.kind == "installed"
        assert result.root is None
    finally:
        ident.identity.cache_clear()
