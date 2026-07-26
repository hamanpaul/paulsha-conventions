from __future__ import annotations

import json
import base64
import hashlib
import subprocess
import sys
import zipfile
from argparse import Namespace
from pathlib import Path
from typing import Sequence

import pytest

from policy_check import preflight


def _config(*, mode: str = "workflow") -> dict:
    return {
        "policy_profile": "flat",
        "policy_version": "1.0.12",
        "conventions_engine": {
            "repo": "hamanpaul/paulsha-conventions",
            "mode": mode,
        },
    }


def _write_workflow(
    repo: Path,
    *,
    uses_ref: str = "a" * 40,
    engine_ref: str = "a" * 40,
) -> None:
    workflow = repo / ".github" / "workflows" / "policy-check.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "jobs:\n"
        "  policy:\n"
        "    uses: hamanpaul/paulsha-conventions/.github/workflows/"
        f"reusable-policy-check.yml@{uses_ref}\n"
        "    with:\n"
        f"      policy_engine_ref: {engine_ref}\n",
        encoding="utf-8",
    )


def _args(repo: Path, body: Path, **overrides) -> Namespace:
    values = {
        "repo": str(repo),
        "pr": None,
        "offline": False,
        "pr_title": "feat: test",
        "pr_body_file": str(body),
        "pr_labels": "",
        "base": "main",
        "head": "feature/test",
        "repo_visibility": "public",
        "skip_tests": False,
        "policy_only": False,
        "cache_dir": None,
    }
    values.update(overrides)
    return Namespace(**values)


def test_parser_rejects_pr_with_offline() -> None:
    parser = preflight.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--pr", "46", "--offline"])
    assert exc.value.code == 2


def test_github_auth_tokens_are_scoped_to_github_cli(monkeypatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "test-gh-token")
    monkeypatch.setenv("GITHUB_TOKEN", "test-github-token")

    assert "GH_TOKEN" not in preflight._sanitized_env()
    assert "GITHUB_TOKEN" not in preflight._sanitized_env()
    assert preflight._github_cli_env()["GH_TOKEN"] == "test-gh-token"
    assert preflight._github_cli_env()["GITHUB_TOKEN"] == "test-github-token"


def test_manual_context_requires_body_file(tmp_path) -> None:
    args = _args(tmp_path, tmp_path / "missing", pr_body_file=None)
    with pytest.raises(preflight.PreflightUsageError, match="pr-body-file"):
        preflight._manual_context(args, tmp_path)


def test_manual_context_allows_explicit_empty_labels(tmp_path) -> None:
    body = tmp_path / "body.md"
    body.write_text("Fixes #46\n", encoding="utf-8")
    context = preflight._manual_context(_args(tmp_path, body), tmp_path)
    assert context.labels == ()
    assert context.visibility == "public"


def test_github_context_uses_live_metadata(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GH_TOKEN", "test-gh-token")
    monkeypatch.setenv("GITHUB_TOKEN", "test-github-token")
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-reach-gh")
    replies = iter(
        [
            {
                "title": "feat: live",
                "body": "Fixes #46",
                "labels": [{"name": "wip"}],
                "baseRefName": "main",
                "headRefName": "feature/live",
            },
            {"visibility": "PRIVATE"},
        ]
    )
    seen_envs = []

    def fake_json(*_args, **kwargs):
        seen_envs.append(kwargs["env"])
        return next(replies)

    monkeypatch.setattr(preflight, "_json_command", fake_json)
    args = _args(
        tmp_path,
        tmp_path / "unused",
        pr="46",
        pr_title=None,
        pr_body_file=None,
        pr_labels=None,
        base=None,
        head=None,
        repo_visibility=None,
    )
    context = preflight._github_context(args, tmp_path)
    assert context == preflight.PullRequestContext(
        title="feat: live",
        body="Fixes #46",
        labels=("wip",),
        base="main",
        head="feature/live",
        visibility="private",
    )
    assert len(seen_envs) == 2
    assert all(env["GH_TOKEN"] == "test-gh-token" for env in seen_envs)
    assert all(env["GITHUB_TOKEN"] == "test-github-token" for env in seen_envs)
    assert all("UNRELATED_SECRET" not in env for env in seen_envs)


def test_github_context_rejects_manual_visibility_override(tmp_path) -> None:
    args = _args(
        tmp_path,
        tmp_path / "unused",
        pr="46",
        pr_title=None,
        pr_body_file=None,
        pr_labels=None,
        base=None,
        head=None,
        repo_visibility="public",
    )
    with pytest.raises(preflight.PreflightUsageError, match="cannot be combined"):
        preflight._github_context(args, tmp_path)


def test_parse_steps_rejects_path_traversal(tmp_path) -> None:
    config = {
        "preflight": {
            "steps": [
                {
                    "name": "escape",
                    "kind": "tests",
                    "argv": ["pytest"],
                    "cwd": "../outside",
                }
            ]
        }
    }
    with pytest.raises(preflight.PreflightUsageError, match="escape"):
        preflight._parse_steps(config, tmp_path)


@pytest.mark.parametrize("value", ["a/./b", "a//b", "./subdir"])
def test_parse_steps_rejects_dot_segments(tmp_path, value: str) -> None:
    config = {
        "preflight": {
            "steps": [
                {
                    "name": "unsafe",
                    "kind": "tests",
                    "argv": ["pytest"],
                    "cwd": value,
                }
            ]
        }
    }
    with pytest.raises(preflight.PreflightUsageError, match="unsafe"):
        preflight._parse_steps(config, tmp_path)


def test_parse_steps_rejects_duplicate_names(tmp_path) -> None:
    config = {
        "preflight": {
            "steps": [
                {"name": "same", "kind": "tests", "argv": ["pytest"]},
                {"name": "same", "kind": "validation", "argv": ["check"]},
            ]
        }
    }
    with pytest.raises(preflight.PreflightUsageError, match="duplicate"):
        preflight._parse_steps(config, tmp_path)


def test_validate_git_context_rejects_claimed_head(tmp_path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    context = preflight.PullRequestContext(
        "feat: x",
        "",
        (),
        "main",
        "feature/claimed",
        "public",
    )
    with pytest.raises(preflight.PreflightUsageError, match="does not match checkout"):
        preflight._validate_git_context(tmp_path, context)


def test_workflow_pin_rejects_uses_ref_mismatch(tmp_path) -> None:
    _write_workflow(tmp_path, uses_ref="a" * 40, engine_ref="b" * 40)
    with pytest.raises(preflight.PreflightGateError, match="do not match"):
        preflight._workflow_pin(tmp_path, _config())


def test_resolve_engine_populates_fresh_online_cache(monkeypatch, tmp_path) -> None:
    _write_workflow(tmp_path)
    checkout = tmp_path / "resolved"
    checkout.mkdir()
    calls: list[tuple[Path, str, str]] = []
    monkeypatch.setattr(preflight, "_self_engine", lambda *_a: None)
    monkeypatch.setattr(preflight, "_installed_version", lambda: None)
    monkeypatch.setattr(preflight, "_verify_cache", lambda *_a: None)
    monkeypatch.setattr(
        preflight,
        "_populate_cache",
        lambda cache, repo, sha: calls.append((cache, repo, sha)) or checkout,
    )
    identity = preflight._resolve_engine(
        tmp_path,
        _config(),
        offline=False,
        cache_dir=tmp_path / "cache",
    )
    assert identity.root == checkout
    assert calls == [
        (tmp_path / "cache", "hamanpaul/paulsha-conventions", "a" * 40)
    ]


def test_resolve_engine_uses_verified_cached_offline(monkeypatch, tmp_path) -> None:
    _write_workflow(tmp_path)
    checkout = tmp_path / "verified"
    checkout.mkdir()
    monkeypatch.setattr(preflight, "_self_engine", lambda *_a: None)
    monkeypatch.setattr(preflight, "_installed_version", lambda: None)
    monkeypatch.setattr(preflight, "_verify_cache", lambda *_a: checkout)
    monkeypatch.setattr(
        preflight,
        "_populate_cache",
        lambda *_a: pytest.fail("offline path must not populate cache"),
    )
    identity = preflight._resolve_engine(
        tmp_path,
        _config(),
        offline=True,
        cache_dir=tmp_path / "cache",
    )
    assert identity.root == checkout


def test_cache_artifact_rejects_dot_segment_repo(tmp_path) -> None:
    with pytest.raises(preflight.PreflightGateError, match="unsafe"):
        preflight._cache_artifact(tmp_path, ".hidden/repo", "a" * 40)
    with pytest.raises(preflight.PreflightGateError, match="unsafe"):
        preflight._cache_artifact(tmp_path, "owner/..", "a" * 40)


def test_installed_manifest_engine_is_exact_and_does_not_resolve_source(
    monkeypatch,
    tmp_path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}\n", encoding="utf-8")
    manifest = {
        "policy_version": "1.0.12",
        "release_tag": "v1.0.12",
        "release_commit": "a" * 40,
        "wheels": [{"sha256": "b" * 64}],
    }
    monkeypatch.setattr(preflight, "load_and_verify_bundle", lambda _root: manifest)
    monkeypatch.setattr(preflight, "_installed_version", lambda: "1.0.12")
    monkeypatch.setattr(
        preflight,
        "_verify_installed_wheel_payload",
        lambda *_a: None,
    )
    monkeypatch.setattr(
        preflight,
        "__file__",
        str(Path(sys.prefix) / "lib" / "policy_check" / "preflight.py"),
    )
    monkeypatch.setattr(
        preflight,
        "_self_engine",
        lambda *_a: pytest.fail("installed mode must not inspect source checkout"),
    )
    monkeypatch.setattr(
        preflight,
        "_workflow_pin",
        lambda *_a: pytest.fail("installed mode must not inspect workflow"),
    )
    identity = preflight._resolve_engine(
        tmp_path,
        _config(),
        offline=True,
        cache_dir=tmp_path / "cache",
        installed_manifest=manifest_path,
    )
    assert identity.kind == "installed-bundle"
    assert "v1.0.12@" in identity.display


def test_installed_wheel_payload_attests_imported_files(
    monkeypatch,
    tmp_path,
) -> None:
    prefix = tmp_path / "venv"
    installed_root = prefix / "lib"
    package = installed_root / "policy_check"
    dist_info = installed_root / "policy_check-1.0.12.dist-info"
    package.mkdir(parents=True)
    dist_info.mkdir()
    files = {
        "policy_check/__init__.py": b"",
        "policy_check/preflight.py": b"# installed preflight\n",
        "policy_check-1.0.12.dist-info/METADATA": b"Name: policy-check\nVersion: 1.0.12\n",
    }
    for name, content in files.items():
        path = installed_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def digest(content: bytes) -> str:
        encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest())
        return encoded.decode("ascii").rstrip("=")

    record_name = "policy_check-1.0.12.dist-info/RECORD"
    record = "".join(
        f"{name},sha256={digest(content)},{len(content)}\n"
        for name, content in files.items()
    ) + f"{record_name},,\n"
    wheel = tmp_path / "bundle" / "wheels" / "policy_check-1.0.12-py3-none-any.whl"
    wheel.parent.mkdir(parents=True)
    with zipfile.ZipFile(wheel, mode="w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        archive.writestr(record_name, record)

    class FakeDistribution:
        def locate_file(self, name):
            return installed_root / str(name)

    monkeypatch.setattr(preflight.sys, "prefix", str(prefix))
    monkeypatch.setattr(
        preflight,
        "__file__",
        str(package / "preflight.py"),
    )
    monkeypatch.setattr(
        preflight.importlib.metadata,
        "distribution",
        lambda _name: FakeDistribution(),
    )
    manifest = {
        "wheels": [
            {"path": f"wheels/{wheel.name}", "sha256": "a" * 64}
        ]
    }
    preflight._verify_installed_wheel_payload(tmp_path / "bundle", manifest)
    (package / "preflight.py").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(preflight.PreflightGateError, match="modified"):
        preflight._verify_installed_wheel_payload(tmp_path / "bundle", manifest)


def test_resolve_engine_offline_missing_artifact_fails_without_network(
    monkeypatch,
    tmp_path,
) -> None:
    _write_workflow(tmp_path)
    monkeypatch.setattr(preflight, "_self_engine", lambda *_a: None)
    monkeypatch.setattr(preflight, "_installed_version", lambda: None)
    monkeypatch.setattr(preflight, "_verify_cache", lambda *_a: None)
    monkeypatch.setattr(
        preflight,
        "_populate_cache",
        lambda *_a: pytest.fail("offline path invoked network resolver"),
    )
    with pytest.raises(preflight.PreflightGateError, match="offline artifact missing"):
        preflight._resolve_engine(
            tmp_path,
            _config(),
            offline=True,
            cache_dir=tmp_path / "cache",
        )


def test_populate_cache_builds_and_verifies_requested_sha(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_dir = tmp_path / "cache"
    engine_repo = "hamanpaul/paulsha-conventions"
    sha = "a" * 40
    calls: list[tuple[str, ...]] = []

    def fake_run_or_error(
        argv: Sequence[str],
        *,
        cwd: Path,
        timeout: int = 60,
        gate: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        command = tuple(argv)
        calls.append(command)
        if len(command) == 4 and command[:3] == ("git", "init", "--quiet"):
            Path(command[3]).mkdir(parents=True)
            return subprocess.CompletedProcess(command, 0, "", "")
        if (
            len(command) == 7
            and command[0] == "git"
            and command[1] == "-C"
            and command[3] == "remote"
            and command[4] == "add"
            and command[5] == "origin"
            and command[6] == f"https://github.com/{engine_repo}.git"
        ):
            return subprocess.CompletedProcess(command, 0, "", "")
        if (
            len(command) == 8
            and command[0] == "git"
            and command[1] == "-C"
            and command[3] == "fetch"
            and command[4] == "--depth"
            and command[5] == "1"
            and command[6] == "origin"
            and command[7] == sha
        ):
            return subprocess.CompletedProcess(command, 0, "", "")
        if (
            len(command) == 6
            and command[0] == "git"
            and command[1] == "-C"
            and command[3] == "checkout"
            and command[4] == "--detach"
            and command[5] == sha
        ):
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ("git", "status", "--porcelain", "--untracked-files=all"):
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ("git", "status", "--porcelain", "--untracked-files=all", "--ignored=matching"):
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ("git", "rev-parse", "HEAD"):
            return subprocess.CompletedProcess(command, 0, f"{sha}\n", "")
        if command == ("git", "rev-parse", "HEAD^{tree}"):
            return subprocess.CompletedProcess(command, 0, "tree-sha\n", "")
        raise AssertionError(f"unexpected command: {command} (cwd={cwd})")

    monkeypatch.setattr(preflight, "_run_or_error", fake_run_or_error)
    checkout = preflight._populate_cache(cache_dir, engine_repo, sha)
    assert (cache_dir / "hamanpaul" / "paulsha-conventions" / sha / "repo").is_dir()
    assert checkout == cache_dir / "hamanpaul" / "paulsha-conventions" / sha / "repo"

    manifest = json.loads(
        (cache_dir / "hamanpaul" / "paulsha-conventions" / sha / "manifest.json").read_text(encoding="utf-8")
    )
    payload = manifest["payload"]
    assert payload["engine_repo"] == engine_repo
    assert payload["commit"] == sha
    assert manifest["sha256"] == preflight._manifest_digest(payload)
    assert preflight._verify_cache(
        cache_dir / "hamanpaul" / "paulsha-conventions" / sha,
        engine_repo,
        sha,
    ) == checkout
    assert any(
        (
            command[0] == "git"
            and command[1] == "-C"
            and command[3:8]
            == ("fetch", "--depth", "1", "origin", sha)
        )
        for command in calls
    )
    assert any(
        (
            command[0] == "git"
            and command[1] == "-C"
            and command[3:6] == ("checkout", "--detach", sha)
        )
        for command in calls
    )


def test_populate_cache_rejects_existing_artifact(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    artifact = preflight._cache_artifact(cache_dir, "hamanpaul/paulsha-conventions", "a" * 40)
    artifact.mkdir(parents=True)
    (artifact / "stale-marker").write_text("stale\n", encoding="utf-8")
    with pytest.raises(
        preflight.PreflightGateError,
        match="invalid cache artifact already exists",
    ):
        preflight._populate_cache(cache_dir, "hamanpaul/paulsha-conventions", "a" * 40)


def test_resolve_engine_pip_version_skew_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(preflight, "_self_engine", lambda *_a: None)
    monkeypatch.setattr(preflight, "_installed_version", lambda: "1.0.11")
    with pytest.raises(preflight.PreflightGateError, match="version mismatch"):
        preflight._resolve_engine(
            tmp_path,
            _config(mode="pip"),
            offline=True,
            cache_dir=tmp_path / "cache",
        )


def test_self_engine_does_not_bypass_configured_downstream_engine(tmp_path) -> None:
    package = tmp_path / "policy_check"
    package.mkdir()
    (package / "preflight.py").write_text("# decoy\n", encoding="utf-8")
    (tmp_path / "VERSION").write_text("1.0.12\n", encoding="utf-8")

    assert preflight._self_engine(tmp_path, _config()) is None


def test_self_engine_requires_canonical_origin(monkeypatch, tmp_path) -> None:
    package = tmp_path / "policy_check"
    package.mkdir()
    (package / "preflight.py").write_text("# decoy\n", encoding="utf-8")
    (tmp_path / "VERSION").write_text("1.0.12\n", encoding="utf-8")
    monkeypatch.setattr(
        preflight,
        "_run_command",
        lambda *_a, **_kw: subprocess.CompletedProcess(
            [],
            0,
            "git@github.com:someone/downstream.git\n",
            "",
        ),
    )

    config = _config()
    config["conventions_engine"]["repo"] = ""
    assert preflight._self_engine(tmp_path, config) is None


def test_resolve_engine_prefers_skill_source_without_workflow(
    monkeypatch,
    tmp_path,
) -> None:
    engine_root = tmp_path / "engine"
    engine_root.mkdir()
    expected = preflight.EngineIdentity(
        "source",
        "skill:hamanpaul/paulsha-conventions@" + "a" * 40,
        engine_root,
    )
    monkeypatch.setattr(
        preflight,
        "_source_engine",
        lambda root, _config, *, display_prefix: (
            expected
            if root == engine_root.resolve() and display_prefix == "skill"
            else pytest.fail("unexpected source engine arguments")
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_workflow_pin",
        lambda *_a: pytest.fail("skill source must not inspect GitHub Actions workflow"),
    )

    identity = preflight._resolve_engine(
        tmp_path,
        _config(),
        offline=True,
        cache_dir=tmp_path / "cache",
        engine_source=engine_root,
    )
    assert identity == expected


def test_source_engine_rejects_version_skew(monkeypatch, tmp_path) -> None:
    package = tmp_path / "policy_check"
    package.mkdir()
    (package / "preflight.py").write_text("# engine\n", encoding="utf-8")
    (tmp_path / "VERSION").write_text("1.0.11\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "_is_canonical_checkout", lambda _root: True)

    with pytest.raises(preflight.PreflightGateError, match="VERSION mismatch"):
        preflight._source_engine(tmp_path, _config(), display_prefix="skill")


def test_is_canonical_checkout_returns_bool_all_branches(monkeypatch, tmp_path) -> None:
    def remote_result(remote: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["git", "remote", "get-url", "origin"], 0, f"{remote}\n", "")

    monkeypatch.setattr(
        preflight,
        "_run_command",
        lambda *_args, **_kwargs: remote_result(
            "https://github.com/hamanpaul/paulsha-conventions"
        ),
    )
    assert preflight._is_canonical_checkout(tmp_path) is True

    monkeypatch.setattr(
        preflight,
        "_run_command",
        lambda *_args, **_kwargs: remote_result("https://github.com/other/repo"),
    )
    assert preflight._is_canonical_checkout(tmp_path) is False

    def fail_command(*_args, **_kwargs) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(["git", "remote", "get-url", "origin"], 1)

    monkeypatch.setattr(preflight, "_run_command", fail_command)
    assert preflight._is_canonical_checkout(tmp_path) is False


def test_verified_cache_requires_manifest_hash_and_clean_checkout(tmp_path) -> None:
    artifact = tmp_path / "cache" / "hamanpaul" / "paulsha-conventions" / ("a" * 40)
    checkout = artifact / "repo"
    checkout.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=checkout, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=checkout, check=True)
    (checkout / "VERSION").write_text("1.0.12\n", encoding="utf-8")
    subprocess.run(["git", "add", "VERSION"], cwd=checkout, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=checkout, check=True)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
    payload = preflight._manifest_payload("hamanpaul/paulsha-conventions", sha, checkout)
    (artifact / "manifest.json").write_text(
        json.dumps({"payload": payload, "sha256": preflight._manifest_digest(payload)}),
        encoding="utf-8",
    )
    assert preflight._verify_cache(
        artifact,
        "hamanpaul/paulsha-conventions",
        sha,
    ) == checkout
    (checkout / "VERSION").write_text("dirty\n", encoding="utf-8")
    assert preflight._verify_cache(
        artifact,
        "hamanpaul/paulsha-conventions",
        sha,
    ) is None


def test_verified_cache_rejects_ignored_bytecode(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    checkout = artifact / "repo"
    checkout.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=checkout,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=checkout, check=True)
    (checkout / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    (checkout / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=checkout, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=checkout, check=True)
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        text=True,
    ).strip()
    payload = preflight._manifest_payload("hamanpaul/paulsha-conventions", sha, checkout)
    (artifact / "manifest.json").write_text(
        json.dumps({"payload": payload, "sha256": preflight._manifest_digest(payload)}),
        encoding="utf-8",
    )
    (checkout / "engine.pyc").write_bytes(b"untrusted")
    assert preflight._verify_cache(
        artifact,
        "hamanpaul/paulsha-conventions",
        sha,
    ) is None


def test_run_steps_honors_skip_tests_and_policy_only(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(argv, **_kwargs):
        calls.append(tuple(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(preflight, "_run_command", fake_run)
    steps = [
        preflight.PreflightStep("spec", "validation", ("spec",), ".", None, 10),
        preflight.PreflightStep("tests", "tests", ("tests",), ".", None, 10),
    ]
    assert preflight._run_steps(
        tmp_path,
        steps,
        skip_tests=True,
        policy_only=False,
    )
    assert calls == [("spec",)]
    calls.clear()
    assert preflight._run_steps(
        tmp_path,
        steps,
        skip_tests=False,
        policy_only=True,
    )
    assert calls == []


def test_run_steps_fails_when_every_declared_step_is_conditionally_skipped(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    step = preflight.PreflightStep(
        "optional",
        "validation",
        ("check",),
        ".",
        "missing-path",
        10,
    )
    monkeypatch.setattr(
        preflight,
        "_run_command",
        lambda *_a, **_kw: pytest.fail("skipped step must not execute"),
    )
    assert not preflight._run_steps(
        tmp_path,
        [step],
        skip_tests=False,
        policy_only=False,
    )
    assert "no declared preflight step executed" in capsys.readouterr().out


def test_run_steps_requires_policy_only_when_no_steps_are_declared(
    tmp_path,
    capsys,
) -> None:
    assert not preflight._run_steps(
        tmp_path,
        [],
        skip_tests=False,
        policy_only=False,
    )
    assert "no declared preflight step executed" in capsys.readouterr().out
    assert preflight._run_steps(
        tmp_path,
        [],
        skip_tests=False,
        policy_only=True,
    )


def test_run_steps_timeout_is_failure(monkeypatch, tmp_path) -> None:
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["pytest"], 1)

    monkeypatch.setattr(preflight, "_run_command", timeout)
    step = preflight.PreflightStep("tests", "tests", ("pytest",), ".", None, 1)
    assert not preflight._run_steps(
        tmp_path,
        [step],
        skip_tests=False,
        policy_only=False,
    )


@pytest.mark.parametrize(
    "raised",
    [
        PermissionError("not executable"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"),
    ],
)
@pytest.mark.parametrize(
    ("gate", "expected"),
    [
        (True, preflight.PreflightGateError),
        (False, preflight.PreflightUsageError),
    ],
)
def test_run_or_error_normalizes_execution_errors(
    monkeypatch,
    tmp_path,
    raised: Exception,
    gate: bool,
    expected: type[Exception],
) -> None:
    def fail(*_args, **_kwargs):
        raise raised

    monkeypatch.setattr(preflight, "_run_command", fail)
    with pytest.raises(
        expected,
        match="command unavailable, unreadable, or timed out",
    ):
        preflight._run_or_error(["verify"], cwd=tmp_path, gate=gate)


def test_run_steps_execution_error_fails_and_continues(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(argv, **_kwargs):
        command = tuple(argv)
        calls.append(command)
        if command == ("broken",):
            raise PermissionError("not executable")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(preflight, "_run_command", fake_run)
    steps = [
        preflight.PreflightStep("broken", "validation", ("broken",), ".", None, 10),
        preflight.PreflightStep("after", "validation", ("after",), ".", None, 10),
    ]
    assert not preflight._run_steps(
        tmp_path,
        steps,
        skip_tests=False,
        policy_only=False,
    )
    output = capsys.readouterr().out
    assert calls == [("broken",), ("after",)]
    assert "broken: FAIL" in output
    assert "after: PASS" in output


def test_run_policy_passes_complete_context_and_source_root(monkeypatch, tmp_path) -> None:
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        captured["env"] = kwargs["env"]
        captured["cwd"] = kwargs["cwd"]
        captured["event"] = json.loads(
            Path(kwargs["env"]["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")
        )
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(preflight, "_run_command", fake_run)
    context = preflight.PullRequestContext(
        "feat: x",
        "Fixes #46",
        ("wip",),
        "main",
        "feature/x",
        "private",
    )
    engine_root = tmp_path / "engine"
    engine_root.mkdir()
    assert preflight._run_policy(
        tmp_path,
        context,
        preflight.EngineIdentity("source", "test", engine_root),
    )
    assert context.title not in captured["argv"]
    assert context.body not in captured["argv"]
    assert captured["event"]["pull_request"]["body"] == "Fixes #46"
    assert captured["event"]["pull_request"]["labels"] == [{"name": "wip"}]
    assert captured["event"]["repository"]["visibility"] == "private"
    assert captured["cwd"] == engine_root
    assert "PYTHONPATH" not in captured["env"]


def test_run_policy_isolates_installed_engine_from_repo_shadowing(
    monkeypatch,
    tmp_path,
) -> None:
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(preflight, "_run_command", fake_run)
    context = preflight.PullRequestContext(
        "feat: x",
        "",
        (),
        "main",
        "feature/x",
        "public",
    )
    assert preflight._run_policy(
        tmp_path,
        context,
        preflight.EngineIdentity("installed", "test", None),
    )
    assert captured["argv"][1:3] == ["-P", "-I"]


def test_main_returns_one_when_any_gate_fails(monkeypatch, tmp_path) -> None:
    body = tmp_path / "body.md"
    body.write_text("Fixes #46\n", encoding="utf-8")
    monkeypatch.setattr(
        preflight.policy_config,
        "load",
        lambda _repo: {"policy_profile": "flat", "policy_version": "1.0.12"},
    )
    monkeypatch.setattr(
        preflight,
        "_resolve_engine",
        lambda *_a, **_kw: preflight.EngineIdentity("installed", "test", None),
    )
    monkeypatch.setattr(preflight, "_validate_git_context", lambda *_a: None)
    monkeypatch.setattr(preflight, "_run_policy", lambda *_a, **_kw: False)
    monkeypatch.setattr(preflight, "_run_steps", lambda *_a, **_kw: True)
    rc = preflight.main(
        [
            "--repo",
            str(tmp_path),
            "--pr-title",
            "feat: x",
            "--pr-body-file",
            str(body),
            "--base",
            "main",
            "--head",
            "feature/x",
        ]
    )
    assert rc == 1


def test_main_skill_mode_requires_repo_owned_steps(monkeypatch, tmp_path) -> None:
    body = tmp_path / "body.md"
    body.write_text("Fixes #46\n", encoding="utf-8")
    monkeypatch.setattr(
        preflight.policy_config,
        "load",
        lambda _repo: {"policy_profile": "flat", "policy_version": "1.0.12"},
    )
    monkeypatch.setattr(preflight, "_validate_git_context", lambda *_a: None)
    rc = preflight.main(
        [
            "--repo",
            str(tmp_path),
            "--engine-source",
            str(tmp_path / "engine"),
            "--pr-title",
            "feat: x",
            "--pr-body-file",
            str(body),
            "--base",
            "main",
            "--head",
            "feature/x",
        ]
    )
    assert rc == 2


@pytest.mark.parametrize(
    "policy_body",
    [
        {"policy_profile": "flat", "policy_version": "1.0.12", "preflight": {}},
        {
            "policy_profile": "flat",
            "policy_version": "1.0.12",
            "preflight": {"steps": []},
        },
    ],
)
def test_main_skill_mode_requires_repo_owned_preflight_steps(
    monkeypatch,
    tmp_path,
    policy_body: dict[str, object],
) -> None:
    body = tmp_path / "body.md"
    body.write_text("Fixes #46\n", encoding="utf-8")
    monkeypatch.setattr(preflight.policy_config, "load", lambda _repo, conf=policy_body: conf)
    monkeypatch.setattr(preflight, "_validate_git_context", lambda *_a: None)
    rc = preflight.main(
        [
            "--repo",
            str(tmp_path),
            "--engine-source",
            str(tmp_path / "engine"),
            "--pr-title",
            "feat: x",
            "--pr-body-file",
            str(body),
            "--base",
            "main",
            "--head",
            "feature/x",
        ]
    )
    assert rc == 2


def test_main_skill_mode_allows_empty_steps_when_policy_only(monkeypatch, tmp_path) -> None:
    body = tmp_path / "body.md"
    body.write_text("Fixes #46\n", encoding="utf-8")
    monkeypatch.setattr(
        preflight.policy_config,
        "load",
        lambda _repo: {
            "policy_profile": "flat",
            "policy_version": "1.0.12",
            "preflight": {"steps": []},
        },
    )
    monkeypatch.setattr(preflight, "_validate_git_context", lambda *_a: None)
    monkeypatch.setattr(preflight, "_run_policy", lambda *_a, **_kw: True)
    monkeypatch.setattr(preflight, "_run_steps", lambda *_a, **_kw: True)
    monkeypatch.setattr(
        preflight,
        "_resolve_engine",
        lambda *_a, **_kw: preflight.EngineIdentity("installed", "test", None),
    )
    rc = preflight.main(
        [
            "--repo",
            str(tmp_path),
            "--engine-source",
            str(tmp_path / "engine"),
            "--policy-only",
            "--pr-title",
            "feat: x",
            "--pr-body-file",
            str(body),
            "--base",
            "main",
            "--head",
            "feature/x",
        ]
    )
    assert rc == 0


@pytest.mark.parametrize(
    "resolver_error",
    [
        preflight.PreflightGateError("engine failed"),
        PermissionError("cache is read-only"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"),
    ],
)
def test_main_engine_resolve_failure_still_prints_final_fail(
    monkeypatch,
    tmp_path,
    capsys,
    resolver_error: Exception,
) -> None:
    body = tmp_path / "body.md"
    body.write_text("Fixes #46\n", encoding="utf-8")
    monkeypatch.setattr(
        preflight.policy_config,
        "load",
        lambda _repo: {"policy_profile": "flat", "policy_version": "1.0.12"},
    )
    monkeypatch.setattr(preflight, "_validate_git_context", lambda *_a: None)

    def fail_resolve(*_args, **_kwargs) -> preflight.EngineIdentity:
        raise resolver_error

    monkeypatch.setattr(preflight, "_resolve_engine", fail_resolve)
    rc = preflight.main(
        [
            "--repo",
            str(tmp_path),
            "--pr-title",
            "feat: x",
            "--pr-body-file",
            str(body),
            "--base",
            "main",
            "--head",
            "feature/x",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "engine: FAIL" in captured.out
    assert "PREFLIGHT FAIL" in captured.out


def test_main_prints_pass_only_when_all_selected_gates_pass(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    body = tmp_path / "body.md"
    body.write_text("Fixes #46\n", encoding="utf-8")
    monkeypatch.setattr(
        preflight.policy_config,
        "load",
        lambda _repo: {"policy_profile": "flat", "policy_version": "1.0.12"},
    )
    monkeypatch.setattr(
        preflight,
        "_resolve_engine",
        lambda *_a, **_kw: preflight.EngineIdentity("installed", "test", None),
    )
    monkeypatch.setattr(preflight, "_validate_git_context", lambda *_a: None)
    monkeypatch.setattr(preflight, "_run_policy", lambda *_a, **_kw: True)
    monkeypatch.setattr(preflight, "_run_steps", lambda *_a, **_kw: True)
    rc = preflight.main(
        [
            "--repo",
            str(tmp_path),
            "--pr-title",
            "feat: x",
            "--pr-body-file",
            str(body),
            "--base",
            "main",
            "--head",
            "feature/x",
        ]
    )
    assert rc == 0
    assert capsys.readouterr().out.rstrip().endswith("PREFLIGHT PASS")
