import pytest

from policy_check import identity as ident


@pytest.fixture(autouse=True)
def _clear_cache():
    ident.identity.cache_clear()
    yield
    ident.identity.cache_clear()


def test_builtin_identity_matches_current_constants():
    got = ident.identity()
    assert got.canonical_org == "hamanpaul"
    assert got.engine_repo == "hamanpaul/paulsha-conventions"
    assert got.remote_base == "https://github.com"
    assert got.distribution_name == "paulsha-conventions"
    assert got.provider == "github"


def test_remote_urls_covers_three_forms():
    assert ident.identity().remote_urls() == {
        "https://github.com/hamanpaul/paulsha-conventions",
        "ssh://git@github.com/hamanpaul/paulsha-conventions",
        "git@github.com:hamanpaul/paulsha-conventions",
    }


def test_alternative_distribution_swaps_urls(monkeypatch):
    monkeypatch.setattr(ident, "_load_raw", lambda: {
        "canonical_org": "hamanpaul",
        "engine_repo": "hamanpaul/arc-conventions",
        "remote_base": "https://github.com",
        "distribution_name": "arc-conventions",
        "provider": "github",
    })
    got = ident.identity()
    assert got.distribution_name == "arc-conventions"
    assert "https://github.com/hamanpaul/arc-conventions" in got.remote_urls()


def test_incomplete_identity_is_fail_closed(monkeypatch):
    monkeypatch.setattr(ident, "_load_raw", lambda: {"canonical_org": "hamanpaul"})
    with pytest.raises(ident.IdentityError) as exc:
        ident.identity()
    assert "engine_repo" in str(exc.value)


def test_invalid_provider_is_rejected(monkeypatch):
    monkeypatch.setattr(ident, "_load_raw", lambda: {
        "canonical_org": "hamanpaul",
        "engine_repo": "hamanpaul/arc-conventions",
        "remote_base": "https://github.com",
        "distribution_name": "arc-conventions",
        "provider": "bitbucket",
    })
    with pytest.raises(ident.IdentityError):
        ident.identity()


def test_distribution_build_is_optional_and_int(monkeypatch):
    base = {
        "canonical_org": "hamanpaul",
        "engine_repo": "hamanpaul/arc-conventions",
        "remote_base": "https://github.com",
        "distribution_name": "arc-conventions",
        "provider": "github",
    }
    monkeypatch.setattr(ident, "_load_raw", lambda: dict(base))
    assert ident.identity().distribution_build is None

    ident.identity.cache_clear()
    monkeypatch.setattr(ident, "_load_raw", lambda: {**base, "distribution_build": 3})
    assert ident.identity().distribution_build == 3

    ident.identity.cache_clear()
    monkeypatch.setattr(ident, "_load_raw", lambda: {**base, "distribution_build": "x"})
    with pytest.raises(ident.IdentityError):
        ident.identity()
