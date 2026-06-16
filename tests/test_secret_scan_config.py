from policy_check.rules._secret_scan_config import load_baseline, resolve_markers


def test_baseline_loads_from_package_data():
    base = load_baseline()
    assert "bgw720" in base["markers"]
    assert "broadcom" in base["public_names"]


def test_resolve_extends_and_subtracts_public_names():
    repo_cfg = {"secret_scan": {"markers": ["foo123"], "public_names": ["bgw720"]}}
    eff = resolve_markers(repo_cfg)
    assert "foo123" in eff
    assert "bgw720" not in eff
    assert "broadcom" not in eff


def test_resolve_with_no_repo_config_uses_baseline():
    eff = resolve_markers({})
    assert "bgw720" in eff and "build20" in eff
    assert "broadcom" not in eff
