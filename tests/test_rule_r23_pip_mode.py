from pathlib import Path
import policy_check.rules.r23_engine_pin_attestation as r23m
from policy_check.rules.r23_engine_pin_attestation import R23EnginePinAttestation
from policy_check.rules.base import RuleContext, Status


def _ctx(policy_version, mode=None, repo=None):
    ce = {}
    if mode is not None:
        ce["mode"] = mode
    if repo is not None:
        ce["repo"] = repo
    return RuleContext(repo_root=Path("."), profile="flat",
                       policy_version=policy_version, config={"conventions_engine": ce})


def test_pip_mode_match_pass(monkeypatch):
    monkeypatch.setattr(r23m, "_installed_version", lambda: "1.0.11")
    assert R23EnginePinAttestation().check(_ctx("1.0.11", mode="pip")).status == Status.PASS


def test_pip_mode_policy_version_may_have_v_prefix(monkeypatch):
    monkeypatch.setattr(r23m, "_installed_version", lambda: "1.0.11")
    assert R23EnginePinAttestation().check(_ctx("v1.0.11", mode="pip")).status == Status.PASS


def test_pip_mode_fix_maps_to_post(monkeypatch):
    # policy -fix.N ↔ 安裝版 PEP440 .postN
    monkeypatch.setattr(r23m, "_installed_version", lambda: "1.0.11.post1")
    assert R23EnginePinAttestation().check(_ctx("1.0.11-fix.1", mode="pip")).status == Status.PASS


def test_pip_mode_mismatch_fail(monkeypatch):
    monkeypatch.setattr(r23m, "_installed_version", lambda: "1.0.10")
    assert R23EnginePinAttestation().check(_ctx("1.0.11", mode="pip")).status == Status.FAIL


def test_pip_mode_not_installed_fail_closed(monkeypatch):
    def _boom():
        from importlib.metadata import PackageNotFoundError
        raise PackageNotFoundError("policy-check")
    monkeypatch.setattr(r23m, "_installed_version", _boom)
    assert R23EnginePinAttestation().check(_ctx("1.0.11", mode="pip")).status == Status.FAIL


def test_pip_mode_independent_of_repo(monkeypatch):
    # mode:pip + repo 未設 + 版本不符 → FAIL（非 NA 早退）
    monkeypatch.setattr(r23m, "_installed_version", lambda: "9.9.9")
    assert R23EnginePinAttestation().check(_ctx("1.0.11", mode="pip")).status == Status.FAIL
