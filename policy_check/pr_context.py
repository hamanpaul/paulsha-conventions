# policy_check/pr_context.py
import json
import os
import subprocess
from pathlib import Path


def load_event_payload() -> dict:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text())


def _normalize_visibility(value) -> str | None:
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    if v in {"public", "private", "internal", "unknown"}:
        return v
    return None


def pr_meta_from_event(event: dict) -> dict:
    pr = event.get("pull_request") or {}
    has_pr = bool(pr)
    repo_visibility = _normalize_visibility((event.get("repository") or {}).get("visibility"))
    if repo_visibility is None:
        private = (event.get("repository") or {}).get("private")
        if isinstance(private, bool):
            repo_visibility = "private" if private else "public"
    return {
        "pr_title": pr.get("title"),
        "pr_body": pr.get("body"),
        "pr_labels": [l["name"] for l in pr.get("labels", [])] if has_pr else None,
        "pr_base_ref": (pr.get("base") or {}).get("ref"),
        "pr_head_ref": (pr.get("head") or {}).get("ref"),
        "repo_visibility": repo_visibility,
        "provider": "github" if has_pr else None,
        "pr_base_sha": None,
    }


def changed_files(
    base_ref: str | None, repo_root: Path, base_sha: str | None = None
) -> list[str]:
    if base_sha:
        rng = f"{base_sha}...HEAD"
    elif base_ref:
        rng = f"origin/{base_ref}...HEAD"
    else:
        return []
    cmd = ["git", "-C", str(repo_root), "diff", "--name-only", rng]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return []
    return [l.strip() for l in out.splitlines() if l.strip()]


def latest_tag(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), "describe", "--tags", "--abbrev=0"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip() or None
    except subprocess.CalledProcessError:
        return None


def gitlab_pr_meta() -> dict:
    """從 GitLab merge_request pipeline 的 CI_MERGE_REQUEST_* 組與 GitHub 等效的 meta。"""

    def _env(k):
        v = os.environ.get(k)
        return v if v not in (None, "") else None

    labels_raw = os.environ.get("CI_MERGE_REQUEST_LABELS")
    labels = (
        [t.strip() for t in labels_raw.split(",") if t.strip()]
        if labels_raw is not None else []
    )
    return {
        "pr_title": _env("CI_MERGE_REQUEST_TITLE"),
        "pr_body": _env("CI_MERGE_REQUEST_DESCRIPTION"),
        "pr_labels": labels,
        "pr_base_ref": _env("CI_MERGE_REQUEST_TARGET_BRANCH_NAME"),
        "pr_head_ref": _env("CI_MERGE_REQUEST_SOURCE_BRANCH_NAME"),
        "pr_base_sha": _env("CI_MERGE_REQUEST_DIFF_BASE_SHA"),
        "repo_visibility": _normalize_visibility(os.environ.get("CI_PROJECT_VISIBILITY")),
        "provider": "gitlab",
    }


def load_pr_meta() -> dict:
    """provider 分派：GitLab MR > GitHub event > 空 {}（恆為 dict）。"""
    if os.environ.get("CI_MERGE_REQUEST_IID"):
        return gitlab_pr_meta()
    event = load_event_payload()
    if event:
        return pr_meta_from_event(event)
    return {}
