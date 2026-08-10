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


class _FakeResource:
    """Stand-in for the `importlib.resources` Traversable `_load_raw` reads."""

    def __init__(self, *, text: str | None = None, error: Exception | None = None):
        self._text = text
        self._error = error

    def joinpath(self, _name: str) -> "_FakeResource":
        return self

    def read_text(self, encoding: str) -> str:  # noqa: ARG002 - signature match
        if self._error is not None:
            raise self._error
        assert self._text is not None
        return self._text


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("no such file"),
        PermissionError("permission denied"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
    ],
)
def test_load_raw_unreadable_file_is_identity_error(monkeypatch, error):
    monkeypatch.setattr(ident, "files", lambda _pkg: _FakeResource(error=error))
    with pytest.raises(ident.IdentityError, match="distribution.yml"):
        ident._load_raw()


def test_load_raw_invalid_yaml_is_identity_error(monkeypatch):
    monkeypatch.setattr(
        ident, "files", lambda _pkg: _FakeResource(text="canonical_org: [unterminated\n")
    )
    with pytest.raises(ident.IdentityError, match="YAML"):
        ident._load_raw()


@pytest.mark.parametrize(
    "text",
    [
        "- a\n- b\n",
        "just a scalar string\n",
        "42\n",
    ],
)
def test_load_raw_non_mapping_top_level_is_identity_error(monkeypatch, text):
    monkeypatch.setattr(ident, "files", lambda _pkg: _FakeResource(text=text))
    with pytest.raises(ident.IdentityError, match="mapping"):
        ident._load_raw()


def test_load_raw_empty_document_becomes_empty_mapping(monkeypatch):
    """空檔案（YAML 解析為 None）視為空 mapping，交由 identity() 的必填欄位檢查
    以清楚訊息 fail-closed，而不是在這裡就把型別問題吞掉。"""
    monkeypatch.setattr(ident, "files", lambda _pkg: _FakeResource(text=""))
    assert ident._load_raw() == {}


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


def test_yaml_import_is_lazy_not_module_level():
    """runtime_bundle 在最小環境（release buildenv）import 本模組不得因缺 PyYAML 爆炸。"""
    from pathlib import Path

    source = Path("policy_check/identity.py").read_text(encoding="utf-8")
    for line in source.splitlines():
        assert not line.startswith("import yaml"), "yaml 必須延後到 _load_raw() 內 import"
        assert not line.startswith("from yaml"), "yaml 必須延後到 _load_raw() 內 import"


def test_missing_pyyaml_is_fail_closed_identity_error(monkeypatch):
    import sys

    ident.identity.cache_clear()
    monkeypatch.setitem(sys.modules, "yaml", None)
    with pytest.raises(ident.IdentityError) as exc:
        ident.identity()
    assert "PyYAML" in str(exc.value)
