from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import yaml

from policy_check import config as policy_config
from policy_check.runtime_bundle.integrity import (
    BundleError,
    load_and_verify_bundle,
)


FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ENGINE_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SAFE_REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
REMOTE_WORKFLOW_RE = re.compile(
    r"^(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/"
    r"\.github/workflows/[^@]+@(?P<ref>[0-9a-f]{40})$"
)
DEFAULT_STEP_TIMEOUT = 300
POLICY_TIMEOUT = 300
MANIFEST_SCHEMA = 1
CANONICAL_ENGINE_REPO = "hamanpaul/paulsha-conventions"


class PreflightUsageError(ValueError):
    """Invalid CLI/config/context input (exit 2)."""


class PreflightGateError(RuntimeError):
    """A resolver or execution gate failed (exit 1)."""


@dataclass(frozen=True)
class PullRequestContext:
    title: str
    body: str
    labels: tuple[str, ...]
    base: str
    head: str
    visibility: str


@dataclass(frozen=True)
class PreflightStep:
    name: str
    kind: str
    argv: tuple[str, ...]
    cwd: str
    when_path_exists: str | None
    timeout_seconds: int


@dataclass(frozen=True)
class EngineIdentity:
    kind: str
    display: str
    root: Path | None


def _sanitized_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    allowed = (
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "VIRTUAL_ENV",
        "SYSTEMROOT",
    )
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.setdefault("LC_ALL", "C")
    if extra:
        env.update(extra)
    return env


def _github_cli_env() -> dict[str, str]:
    auth = {
        key: os.environ[key]
        for key in ("GH_TOKEN", "GITHUB_TOKEN")
        if key in os.environ
    }
    return _sanitized_env(auth)


def _run_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=str(cwd),
        env=dict(env or _sanitized_env()),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _run_or_error(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout: int = 60,
    gate: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = _run_command(argv, cwd=cwd, timeout=timeout)
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        error_type = PreflightGateError if gate else PreflightUsageError
        raise error_type(
            f"command unavailable, unreadable, or timed out: {argv[0]}"
        ) from exc
    if result.returncode != 0:
        error_type = PreflightGateError if gate else PreflightUsageError
        raise error_type(f"command failed ({result.returncode}): {argv[0]}")
    return result


def _safe_ref(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PreflightUsageError(f"{field} must be a non-empty ref")
    ref = value.strip()
    if (
        SAFE_REF_RE.fullmatch(ref) is None
        or ref.startswith("-")
        or ".." in ref
        or "//" in ref
    ):
        raise PreflightUsageError(f"{field} is not a safe git ref")
    return ref


def _repo_relative_path(value: object, *, field: str, allow_dot: bool = True) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PreflightUsageError(f"{field} must be a non-empty repo-relative path")
    raw = value.strip()
    if "\\" in raw:
        raise PreflightUsageError(f"{field} must use POSIX separators")
    raw_parts = raw.split("/")
    if (
        any(part in {"", ".."} for part in raw_parts)
        or ("." in raw_parts and raw != ".")
    ):
        raise PreflightUsageError(f"{field} contains an unsafe path segment")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise PreflightUsageError(f"{field} must not escape the repository")
    normalized = path.as_posix()
    if normalized == "." and not allow_dot:
        raise PreflightUsageError(f"{field} must not be the repository root")
    return normalized


def _resolve_inside(repo_root: Path, relative: str, *, field: str) -> Path:
    target = (repo_root / relative).resolve()
    try:
        target.relative_to(repo_root)
    except ValueError as exc:
        raise PreflightUsageError(f"{field} resolves outside the repository") from exc
    return target


def _parse_labels(raw: str | None) -> tuple[str, ...]:
    if raw is None or raw == "":
        return ()
    return tuple(label.strip() for label in raw.split(",") if label.strip())


def _default_base(repo_root: Path) -> str:
    try:
        symbolic = _run_command(
            ["git", "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
            cwd=repo_root,
            timeout=30,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise PreflightUsageError("cannot derive base; git is unavailable") from exc
    if symbolic.returncode == 0 and symbolic.stdout.strip().startswith("origin/"):
        return _safe_ref(symbolic.stdout.strip()[len("origin/"):], field="base")
    try:
        main_ref = _run_command(
            ["git", "show-ref", "--verify", "--quiet", "refs/remotes/origin/main"],
            cwd=repo_root,
            timeout=30,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise PreflightUsageError("cannot derive base; git is unavailable") from exc
    if main_ref.returncode == 0:
        return "main"
    raise PreflightUsageError("cannot derive base; pass --base explicitly")


def _default_head(repo_root: Path) -> str:
    result = _run_or_error(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=repo_root,
        timeout=30,
        gate=False,
    )
    return _safe_ref(result.stdout.strip(), field="head")


def _json_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    try:
        result = _run_command(argv, cwd=cwd, timeout=60, env=env)
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise PreflightUsageError(
            f"command unavailable, unreadable, or timed out: {argv[0]}"
        ) from exc
    if result.returncode != 0:
        raise PreflightUsageError(f"command failed ({result.returncode}): {argv[0]}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PreflightUsageError(f"{argv[0]} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise PreflightUsageError(f"{argv[0]} returned a non-object JSON payload")
    return payload


def _manual_context(args: argparse.Namespace, repo_root: Path) -> PullRequestContext:
    if not isinstance(args.pr_title, str) or not args.pr_title.strip():
        raise PreflightUsageError("manual mode requires --pr-title")
    if args.pr_body_file is None:
        raise PreflightUsageError("manual mode requires --pr-body-file")
    body_path = Path(args.pr_body_file).expanduser()
    try:
        body = body_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PreflightUsageError(f"cannot read --pr-body-file: {body_path}") from exc
    return PullRequestContext(
        title=args.pr_title.strip(),
        body=body,
        labels=_parse_labels(args.pr_labels),
        base=_safe_ref(args.base or _default_base(repo_root), field="base"),
        head=_safe_ref(args.head or _default_head(repo_root), field="head"),
        visibility=args.repo_visibility or "unknown",
    )


def _github_context(args: argparse.Namespace, repo_root: Path) -> PullRequestContext:
    if any(
        value is not None
        for value in (
            args.pr_title,
            args.pr_body_file,
            args.pr_labels,
            args.base,
            args.head,
            args.repo_visibility,
        )
    ):
        raise PreflightUsageError("--pr cannot be combined with manual PR context arguments")
    pr = _json_command(
        [
            "gh",
            "pr",
            "view",
            str(args.pr),
            "--json",
            "title,body,labels,baseRefName,headRefName",
        ],
        cwd=repo_root,
        env=_github_cli_env(),
    )
    repo = _json_command(
        ["gh", "repo", "view", "--json", "visibility"],
        cwd=repo_root,
        env=_github_cli_env(),
    )
    labels = pr.get("labels")
    if not isinstance(labels, list):
        raise PreflightUsageError("gh PR metadata is missing labels")
    label_names = tuple(
        str(entry["name"]).strip()
        for entry in labels
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    )
    visibility = str(repo.get("visibility") or "unknown").strip().lower()
    if visibility not in {"public", "private", "internal"}:
        visibility = "unknown"
    return PullRequestContext(
        title=str(pr.get("title") or "").strip(),
        body=str(pr.get("body") or ""),
        labels=label_names,
        base=_safe_ref(pr.get("baseRefName"), field="base"),
        head=_safe_ref(pr.get("headRefName"), field="head"),
        visibility=visibility,
    )


def _load_context(args: argparse.Namespace, repo_root: Path) -> PullRequestContext:
    context = _github_context(args, repo_root) if args.pr else _manual_context(args, repo_root)
    if not context.title:
        raise PreflightUsageError("PR title must not be empty")
    return context


def _validate_git_context(repo_root: Path, context: PullRequestContext) -> None:
    current_branch = _run_or_error(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=repo_root,
        timeout=30,
        gate=False,
    ).stdout.strip()
    if current_branch != context.head:
        raise PreflightUsageError(
            f"head context {context.head!r} does not match checkout {current_branch!r}"
        )
    _run_or_error(
        [
            "git",
            "rev-parse",
            "--verify",
            f"refs/remotes/origin/{context.base}^{{commit}}",
        ],
        cwd=repo_root,
        timeout=30,
        gate=False,
    )
    _run_or_error(
        ["git", "merge-base", f"origin/{context.base}", "HEAD"],
        cwd=repo_root,
        timeout=30,
        gate=False,
    )


def _parse_steps(config: Mapping[str, Any], repo_root: Path) -> list[PreflightStep]:
    block = config.get("preflight")
    if block is None:
        return []
    if not isinstance(block, dict):
        raise PreflightUsageError("preflight must be a mapping")
    raw_steps = block.get("steps")
    if raw_steps is None:
        return []
    if not isinstance(raw_steps, list):
        raise PreflightUsageError("preflight.steps must be a list")
    names: set[str] = set()
    steps: list[PreflightStep] = []
    for index, raw in enumerate(raw_steps):
        prefix = f"preflight.steps[{index}]"
        if not isinstance(raw, dict):
            raise PreflightUsageError(f"{prefix} must be a mapping")
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise PreflightUsageError(f"{prefix}.name must be a non-empty string")
        name = name.strip()
        if name in names:
            raise PreflightUsageError(f"duplicate preflight step name: {name}")
        names.add(name)
        kind = raw.get("kind")
        if kind not in {"validation", "tests"}:
            raise PreflightUsageError(f"{prefix}.kind must be validation or tests")
        argv = raw.get("argv")
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(item, str) or not item for item in argv)
        ):
            raise PreflightUsageError(f"{prefix}.argv must be a non-empty list of strings")
        timeout = raw.get("timeout_seconds", DEFAULT_STEP_TIMEOUT)
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
            raise PreflightUsageError(f"{prefix}.timeout_seconds must be a positive integer")
        cwd = _repo_relative_path(
            raw.get("cwd", "."),
            field=f"preflight step {name} cwd",
        )
        _resolve_inside(repo_root, cwd, field=f"preflight step {name} cwd")
        when = raw.get("when_path_exists")
        if when is not None:
            when = _repo_relative_path(
                when,
                field=f"preflight step {name} when_path_exists",
                allow_dot=False,
            )
            _resolve_inside(
                repo_root,
                when,
                field=f"preflight step {name} when_path_exists",
            )
        steps.append(
            PreflightStep(
                name=name,
                kind=kind,
                argv=tuple(argv),
                cwd=cwd,
                when_path_exists=when,
                timeout_seconds=timeout,
            )
        )
    return steps


def _normalized_version(value: str) -> str:
    return re.sub(r"-fix\.(\d+)$", r".post\1", value.strip().lstrip("v"))


def _installed_version() -> str | None:
    try:
        return importlib.metadata.version("policy-check")
    except importlib.metadata.PackageNotFoundError:
        return None


def _version_matches(installed: str | None, policy_version: str) -> bool:
    return installed is not None and _normalized_version(installed) == _normalized_version(
        policy_version
    )


def _is_canonical_checkout(repo_root: Path) -> bool:
    try:
        remote = _run_command(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_root,
            timeout=30,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        return False
    normalized_remote = remote.stdout.strip().removesuffix(".git")
    canonical_remotes = {
        f"https://github.com/{CANONICAL_ENGINE_REPO}",
        f"ssh://git@github.com/{CANONICAL_ENGINE_REPO}",
        f"git@github.com:{CANONICAL_ENGINE_REPO}",
    }
    return remote.returncode == 0 and normalized_remote in canonical_remotes


def _source_engine(
    engine_root: Path,
    config: Mapping[str, Any],
    *,
    display_prefix: str,
) -> EngineIdentity:
    engine_config = config.get("conventions_engine")
    if engine_config is not None and not isinstance(engine_config, dict):
        raise PreflightUsageError("conventions_engine must be a mapping")
    configured_repo = engine_config.get("repo") if isinstance(engine_config, dict) else None
    if configured_repo and configured_repo != CANONICAL_ENGINE_REPO:
        raise PreflightGateError(
            "source engine disagrees with conventions_engine.repo"
        )
    if not (engine_root / "policy_check" / "preflight.py").is_file():
        raise PreflightGateError("source engine is missing policy_check/preflight.py")
    if not _is_canonical_checkout(engine_root):
        raise PreflightGateError(
            f"source engine must be a checkout of {CANONICAL_ENGINE_REPO}"
        )
    version_file = engine_root / "VERSION"
    if not version_file.is_file():
        raise PreflightGateError("source engine is missing VERSION")
    actual = version_file.read_text(encoding="utf-8").strip()
    expected = str(config.get("policy_version") or "").strip()
    if actual != expected:
        raise PreflightGateError(
            f"source engine VERSION mismatch: expected {expected!r}, got {actual!r}"
        )
    status = _run_or_error(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=engine_root,
        timeout=30,
    ).stdout.strip()
    if status:
        raise PreflightGateError("source engine checkout must be clean")
    head = _run_or_error(
        ["git", "rev-parse", "HEAD"],
        cwd=engine_root,
        timeout=30,
    ).stdout.strip()
    if FULL_SHA_RE.fullmatch(head) is None:
        raise PreflightGateError("source engine HEAD is not a full SHA")
    return EngineIdentity(
        "source",
        f"{display_prefix}:{CANONICAL_ENGINE_REPO}@{head}",
        engine_root,
    )


def _self_engine(repo_root: Path, config: Mapping[str, Any]) -> EngineIdentity | None:
    engine_config = config.get("conventions_engine")
    if engine_config is not None and not isinstance(engine_config, dict):
        raise PreflightUsageError("conventions_engine must be a mapping")
    if isinstance(engine_config, dict) and engine_config.get("repo"):
        return None
    if not (repo_root / "policy_check" / "preflight.py").is_file():
        return None
    if not _is_canonical_checkout(repo_root):
        return None
    return _source_engine(repo_root, config, display_prefix="self")


def _workflow_pin(repo_root: Path, config: Mapping[str, Any]) -> tuple[str, str]:
    workflow = repo_root / ".github" / "workflows" / "policy-check.yml"
    if not workflow.is_file():
        raise PreflightGateError("missing .github/workflows/policy-check.yml")
    try:
        payload = yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise PreflightGateError("cannot parse policy-check workflow") from exc
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, dict):
        raise PreflightGateError("policy-check workflow has no jobs mapping")
    candidates: list[tuple[str, str, str]] = []
    for job in jobs.values():
        if not isinstance(job, dict) or not isinstance(job.get("uses"), str):
            continue
        match = REMOTE_WORKFLOW_RE.fullmatch(job["uses"].strip())
        if match is None:
            continue
        inputs = job.get("with")
        engine_ref = inputs.get("policy_engine_ref") if isinstance(inputs, dict) else None
        candidates.append((match.group("repo"), match.group("ref"), str(engine_ref or "")))
    if len(candidates) != 1:
        raise PreflightGateError("expected exactly one pinned remote policy workflow")
    engine_repo, uses_ref, engine_ref = candidates[0]
    if FULL_SHA_RE.fullmatch(engine_ref) is None:
        raise PreflightGateError("policy_engine_ref must be a full lowercase SHA")
    if uses_ref != engine_ref:
        raise PreflightGateError("workflow uses ref and policy_engine_ref do not match")
    configured = (config.get("conventions_engine") or {}).get("repo")
    if configured and configured != engine_repo:
        raise PreflightGateError("workflow engine repo disagrees with conventions_engine.repo")
    return engine_repo, engine_ref


def _git_value(repo: Path, *args: str) -> str:
    return _run_or_error(["git", *args], cwd=repo, timeout=60).stdout.strip()


def _manifest_payload(engine_repo: str, sha: str, checkout: Path) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA,
        "engine_repo": engine_repo,
        "commit": sha,
        "tree": _git_value(checkout, "rev-parse", "HEAD^{tree}"),
        "checkout": "repo",
    }


def _manifest_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _verify_cache(artifact: Path, engine_repo: str, sha: str) -> Path | None:
    manifest_path = artifact / "manifest.json"
    checkout = artifact / "repo"
    if not manifest_path.is_file() or not checkout.is_dir():
        return None
    try:
        envelope = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(envelope, dict):
        return None
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        return None
    if envelope.get("sha256") != _manifest_digest(payload):
        return None
    if (
        payload.get("schema_version") != MANIFEST_SCHEMA
        or payload.get("engine_repo") != engine_repo
        or payload.get("commit") != sha
        or payload.get("checkout") != "repo"
    ):
        return None
    try:
        if _git_value(checkout, "rev-parse", "HEAD") != sha:
            return None
        if _git_value(checkout, "rev-parse", "HEAD^{tree}") != payload.get("tree"):
            return None
        if _git_value(
            checkout,
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--ignored=matching",
        ):
            return None
    except PreflightGateError:
        return None
    return checkout


def _cache_artifact(cache_dir: Path, engine_repo: str, sha: str) -> Path:
    if ENGINE_REPO_RE.fullmatch(engine_repo) is None or FULL_SHA_RE.fullmatch(sha) is None:
        raise PreflightGateError("unsafe engine repo or SHA")
    owner, repo = engine_repo.split("/", 1)
    if any(
        segment in {"", ".", ".."} or not segment[0].isalnum()
        for segment in (owner, repo)
    ):
        raise PreflightGateError("unsafe engine repo or SHA")
    root = cache_dir.resolve()
    artifact = root / owner / repo / sha
    try:
        artifact.relative_to(root)
    except ValueError as exc:
        raise PreflightGateError("cache artifact escapes cache root") from exc
    return artifact


def _populate_cache(cache_dir: Path, engine_repo: str, sha: str) -> Path:
    artifact = _cache_artifact(cache_dir, engine_repo, sha)
    if artifact.exists():
        raise PreflightGateError(
            f"invalid cache artifact already exists for {engine_repo}@{sha}; remove it explicitly"
        )
    artifact.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".preflight-", dir=artifact.parent) as temp:
        temp_root = Path(temp)
        checkout = temp_root / "repo"
        _run_or_error(["git", "init", "--quiet", str(checkout)], cwd=temp_root, timeout=60)
        _run_or_error(
            [
                "git",
                "-C",
                str(checkout),
                "remote",
                "add",
                "origin",
                f"https://github.com/{engine_repo}.git",
            ],
            cwd=temp_root,
            timeout=60,
        )
        _run_or_error(
            ["git", "-C", str(checkout), "fetch", "--depth", "1", "origin", sha],
            cwd=temp_root,
            timeout=300,
        )
        _run_or_error(
            ["git", "-C", str(checkout), "checkout", "--detach", sha],
            cwd=temp_root,
            timeout=60,
        )
        if _git_value(checkout, "rev-parse", "HEAD") != sha:
            raise PreflightGateError("fetched engine did not resolve to the requested SHA")
        payload = _manifest_payload(engine_repo, sha, checkout)
        (temp_root / "manifest.json").write_text(
            json.dumps(
                {"payload": payload, "sha256": _manifest_digest(payload)},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temp_root, artifact)
    verified = _verify_cache(artifact, engine_repo, sha)
    if verified is None:
        raise PreflightGateError("new engine cache failed verification")
    return verified


def _installed_manifest_engine(
    manifest_path: Path,
    config: Mapping[str, Any],
) -> EngineIdentity:
    path = manifest_path.resolve()
    if path.name != "manifest.json" or not path.is_file():
        raise PreflightGateError("installed manifest path is invalid")
    try:
        manifest = load_and_verify_bundle(path.parent)
    except BundleError as exc:
        raise PreflightGateError(f"installed bundle verification failed: {exc}") from exc
    expected = str(config.get("policy_version") or "").strip()
    if manifest.get("policy_version") != expected:
        raise PreflightGateError(
            f"installed manifest version mismatch: need {expected}"
        )
    installed = _installed_version()
    if not _version_matches(installed, expected):
        raise PreflightGateError(
            f"installed policy-check version mismatch: need {expected}"
        )
    package_root = Path(__file__).resolve().parent
    prefix = Path(sys.prefix).resolve()
    try:
        package_root.relative_to(prefix)
    except ValueError as exc:
        raise PreflightGateError(
            "imported policy_check is outside the selected installed environment"
        ) from exc
    wheel_hashes = {
        str(entry.get("sha256"))
        for entry in manifest.get("wheels", [])
        if isinstance(entry, dict)
    }
    if not wheel_hashes or any(len(digest) != 64 for digest in wheel_hashes):
        raise PreflightGateError("installed manifest wheel identity is incomplete")
    _verify_installed_wheel_payload(path.parent, manifest)
    return EngineIdentity(
        "installed-bundle",
        (
            f"policy-check=={installed} "
            f"{manifest['release_tag']}@{manifest['release_commit']}"
        ),
        None,
    )


def _verify_installed_wheel_payload(
    bundle_root: Path,
    manifest: Mapping[str, Any],
) -> None:
    candidates: list[Path] = []
    for entry in manifest.get("wheels", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        wheel = bundle_root / entry["path"]
        if wheel.name.startswith("policy_check-") and wheel.suffix == ".whl":
            candidates.append(wheel)
    if len(candidates) != 1:
        raise PreflightGateError("installed manifest must identify one policy-check wheel")
    wheel = candidates[0]
    try:
        with zipfile.ZipFile(wheel) as archive:
            record_names = [
                name for name in archive.namelist() if name.endswith(".dist-info/RECORD")
            ]
            if len(record_names) != 1:
                raise PreflightGateError("policy-check wheel has ambiguous RECORD")
            rows = list(
                csv.reader(
                    io.StringIO(
                        archive.read(record_names[0]).decode("utf-8")
                    )
                )
            )
    except (OSError, UnicodeError, zipfile.BadZipFile) as exc:
        raise PreflightGateError("cannot inspect verified policy-check wheel") from exc

    try:
        distribution = importlib.metadata.distribution("policy-check")
    except importlib.metadata.PackageNotFoundError as exc:
        raise PreflightGateError("installed policy-check distribution is missing") from exc
    prefix = Path(sys.prefix).resolve()
    expected_preflight = Path(
        distribution.locate_file("policy_check/preflight.py")
    ).resolve()
    if Path(__file__).resolve() != expected_preflight:
        raise PreflightGateError(
            "imported preflight module does not belong to the installed distribution"
        )

    checked = 0
    for row in rows:
        if len(row) < 3:
            raise PreflightGateError("policy-check wheel RECORD is malformed")
        name, encoded_digest, _size = row[:3]
        if name == record_names[0]:
            continue
        if (
            name.startswith("/")
            or "\\" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))
        ):
            raise PreflightGateError("policy-check wheel RECORD path is unsafe")
        if not encoded_digest.startswith("sha256="):
            raise PreflightGateError("policy-check wheel RECORD lacks SHA-256")
        installed_path = Path(distribution.locate_file(name)).resolve()
        try:
            installed_path.relative_to(prefix)
        except ValueError as exc:
            raise PreflightGateError(
                "installed policy-check file escapes selected environment"
            ) from exc
        if not installed_path.is_file():
            raise PreflightGateError(f"installed policy-check file is missing: {name}")
        actual = base64.urlsafe_b64encode(
            hashlib.sha256(installed_path.read_bytes()).digest()
        ).decode("ascii").rstrip("=")
        expected = encoded_digest[len("sha256="):].rstrip("=")
        if actual != expected:
            raise PreflightGateError(f"installed policy-check file was modified: {name}")
        checked += 1
    if checked == 0:
        raise PreflightGateError("policy-check wheel RECORD verified no installed files")


def _resolve_engine(
    repo_root: Path,
    config: Mapping[str, Any],
    *,
    offline: bool,
    cache_dir: Path,
    engine_source: Path | None = None,
    installed_manifest: Path | None = None,
) -> EngineIdentity:
    if installed_manifest is not None:
        return _installed_manifest_engine(installed_manifest, config)
    if engine_source is not None:
        return _source_engine(
            engine_source.resolve(),
            config,
            display_prefix="skill",
        )
    self_identity = _self_engine(repo_root, config)
    if self_identity is not None:
        return self_identity
    policy_version = str(config.get("policy_version") or "")
    engine_config = config.get("conventions_engine") or {}
    if not isinstance(engine_config, dict):
        raise PreflightUsageError("conventions_engine must be a mapping")
    mode = engine_config.get("mode", "workflow")
    installed = _installed_version()
    if mode == "pip":
        if not _version_matches(installed, policy_version):
            raise PreflightGateError(
                f"installed policy-check version mismatch: need {policy_version}"
            )
        return EngineIdentity("installed", f"policy-check=={installed}", None)
    engine_repo, sha = _workflow_pin(repo_root, config)
    artifact = _cache_artifact(cache_dir, engine_repo, sha)
    cached = _verify_cache(artifact, engine_repo, sha)
    if cached is not None:
        return EngineIdentity("source", f"{engine_repo}@{sha}", cached)
    if offline and _version_matches(installed, policy_version):
        return EngineIdentity("installed", f"policy-check=={installed}", None)
    if offline:
        raise PreflightGateError(
            f"offline artifact missing: repo={engine_repo} sha={sha} version={policy_version}"
        )
    checkout = _populate_cache(cache_dir, engine_repo, sha)
    return EngineIdentity("source", f"{engine_repo}@{sha}", checkout)


def _gate_result(name: str, status: str, started: float, detail: str = "") -> None:
    duration = time.monotonic() - started
    suffix = f" ({detail})" if detail else ""
    print(f"{name}: {status} {duration:.2f}s{suffix}")


def _bounded_command_diagnostic(
    result: subprocess.CompletedProcess[str],
) -> str:
    text = (result.stderr or result.stdout).strip()
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    diagnostic = " | ".join(lines[-4:])
    if len(diagnostic) > 800:
        diagnostic = diagnostic[-800:]
    return diagnostic


def _run_policy(
    repo_root: Path,
    context: PullRequestContext,
    engine: EngineIdentity,
) -> bool:
    argv = [sys.executable]
    policy_cwd = repo_root
    if engine.root is None:
        argv.extend(["-P", "-I"])
    else:
        policy_cwd = engine.root
    argv.extend(["-m", "policy_check", "--repo", str(repo_root)])
    extra = {"PYTHONDONTWRITEBYTECODE": "1"}
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="policy-preflight-context-") as temp:
            event_path = Path(temp) / "event.json"
            event_path.write_text(
                json.dumps(
                    {
                        "pull_request": {
                            "title": context.title,
                            "body": context.body,
                            "labels": [{"name": label} for label in context.labels],
                            "base": {"ref": context.base},
                            "head": {"ref": context.head},
                        },
                        "repository": {"visibility": context.visibility},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            event_path.chmod(0o600)
            extra["GITHUB_EVENT_PATH"] = str(event_path)
            result = _run_command(
                argv,
                cwd=policy_cwd,
                timeout=POLICY_TIMEOUT,
                env=_sanitized_env(extra),
            )
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        _gate_result(
            "policy",
            "FAIL",
            started,
            "command unavailable, invalid output, or timeout",
        )
        return False
    ok = result.returncode == 0
    detail = f"exit={result.returncode}"
    if not ok:
        diagnostic = _bounded_command_diagnostic(result)
        if diagnostic:
            detail += f"; output={diagnostic}"
    _gate_result("policy", "PASS" if ok else "FAIL", started, detail)
    return ok


def _run_steps(
    repo_root: Path,
    steps: Sequence[PreflightStep],
    *,
    skip_tests: bool,
    policy_only: bool,
) -> bool:
    all_passed = True
    executed = 0
    conditionally_skipped = 0
    explicitly_skipped_tests = 0
    for step in steps:
        if policy_only:
            print(f"{step.name}: SKIP (policy-only)")
            continue
        if skip_tests and step.kind == "tests":
            print(f"{step.name}: SKIP (skip-tests)")
            explicitly_skipped_tests += 1
            continue
        if step.when_path_exists is not None and not _resolve_inside(
            repo_root,
            step.when_path_exists,
            field=f"preflight step {step.name}",
        ).exists():
            print(f"{step.name}: SKIP (when_path_exists missing)")
            conditionally_skipped += 1
            continue
        cwd = _resolve_inside(repo_root, step.cwd, field=f"preflight step {step.name}")
        executed += 1
        started = time.monotonic()
        try:
            result = _run_command(
                step.argv,
                cwd=cwd,
                timeout=step.timeout_seconds,
            )
        except OSError:
            _gate_result(
                step.name,
                "FAIL",
                started,
                "command unavailable or not executable",
            )
            all_passed = False
            continue
        except UnicodeError:
            _gate_result(step.name, "FAIL", started, "invalid output encoding")
            all_passed = False
            continue
        except subprocess.TimeoutExpired:
            _gate_result(step.name, "FAIL", started, "timeout")
            all_passed = False
            continue
        ok = result.returncode == 0
        _gate_result(
            step.name,
            "PASS" if ok else "FAIL",
            started,
            f"exit={result.returncode}",
        )
        all_passed = all_passed and ok
    if not policy_only and executed == 0:
        if (
            steps
            and explicitly_skipped_tests > 0
            and explicitly_skipped_tests + conditionally_skipped == len(steps)
        ):
            return all_passed
        if not steps:
            print("repo-gates: FAIL (no preflight steps declared)")
        else:
            print("repo-gates: FAIL (all eligible preflight steps were conditional skips)")
        return False
    return all_passed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="policy-preflight")
    parser.add_argument("--repo", default=".", help="Repository root")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--pr", help="GitHub PR number or URL")
    source.add_argument(
        "--offline",
        action="store_true",
        help="Disable network-capable resolver operations",
    )
    parser.add_argument("--pr-title")
    parser.add_argument("--pr-body-file")
    parser.add_argument("--pr-labels", help="Comma-separated; empty means no labels")
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument(
        "--repo-visibility",
        choices=("public", "private", "internal", "unknown"),
    )
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--policy-only", action="store_true")
    parser.add_argument("--cache-dir")
    engine = parser.add_mutually_exclusive_group()
    engine.add_argument(
        "--engine-source",
        help="Canonical paulsha-conventions checkout supplied by the owning skill",
    )
    engine.add_argument(
        "--installed-manifest",
        help="Verified deployed bundle manifest supplied by the stable selector",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print(
            "PREFLIGHT ERROR: policy-preflight requires Python 3.11 or newer",
            file=sys.stderr,
        )
        return 2
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo).resolve()
    if not repo_root.is_dir():
        parser.error(f"repository does not exist: {repo_root}")
    cache_dir = (
        Path(args.cache_dir).expanduser().resolve()
        if args.cache_dir
        else Path.home() / ".cache" / "paulsha-conventions" / "preflight"
    )
    try:
        config = policy_config.load(repo_root)
        context = _load_context(args, repo_root)
        _validate_git_context(repo_root, context)
        steps = _parse_steps(config, repo_root)
        if (args.engine_source or args.installed_manifest) and not args.policy_only and not steps:
            raise PreflightUsageError(
                "skill-driven full preflight requires at least one preflight step; "
                "use --policy-only for an explicit policy-only run"
            )
    except (policy_config.ConfigError, PreflightUsageError) as exc:
        print(f"PREFLIGHT ERROR: {exc}", file=sys.stderr)
        return 2

    print(
        "context:"
        f" base={context.base} head={context.head}"
        f" labels={len(context.labels)} visibility={context.visibility}"
    )
    engine_started = time.monotonic()
    try:
        engine = _resolve_engine(
            repo_root,
            config,
            offline=args.offline,
            cache_dir=cache_dir,
            engine_source=(
                Path(args.engine_source).expanduser()
                if args.engine_source
                else None
            ),
            installed_manifest=(
                Path(args.installed_manifest).expanduser()
                if args.installed_manifest
                else None
            ),
        )
    except PreflightUsageError as exc:
        print(f"PREFLIGHT ERROR: {exc}", file=sys.stderr)
        return 2
    except PreflightGateError as exc:
        _gate_result("engine", "FAIL", engine_started, str(exc))
        print("PREFLIGHT FAIL")
        return 1
    except (OSError, UnicodeError) as exc:
        _gate_result(
            "engine",
            "FAIL",
            engine_started,
            f"engine I/O failure: {exc.__class__.__name__}",
        )
        print("PREFLIGHT FAIL")
        return 1

    _gate_result("engine", "PASS", engine_started, engine.display)
    if args.offline:
        print(
            "offline: resolver network disabled; repo-owned commands remain under repo authority"
        )
    policy_passed = _run_policy(repo_root, context, engine)
    steps_passed = _run_steps(
        repo_root,
        steps,
        skip_tests=args.skip_tests,
        policy_only=args.policy_only,
    )
    if policy_passed and steps_passed:
        print("PREFLIGHT PASS")
        return 0
    print("PREFLIGHT FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
