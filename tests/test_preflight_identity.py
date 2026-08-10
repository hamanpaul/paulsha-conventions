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


def test_offline_does_not_touch_unreachable_remote(monkeypatch, tmp_path):
    """--offline 時走已安裝版本比對路徑，不得對 remote_base 發出網路請求。"""
    ident.identity.cache_clear()
    monkeypatch.setattr(ident, "_load_raw", lambda: {
        "canonical_org": "hamanpaul",
        "engine_repo": "hamanpaul/arc-conventions",
        "remote_base": "https://unreachable.invalid",
        "distribution_name": "arc-conventions",
        "provider": "github",
    })

    calls: list[list[str]] = []

    def _spy(cmd, *args, **kwargs):
        calls.append(list(cmd))
        raise AssertionError(f"offline path must not run: {cmd}")

    monkeypatch.setattr(preflight, "_run_or_error", _spy)
    try:
        assert preflight._version_matches("1.0.15", "1.0.15") is True
        assert calls == []
    finally:
        ident.identity.cache_clear()
