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


def pr_meta_from_event(event: dict) -> dict:
    pr = event.get("pull_request") or {}
    has_pr = bool(pr)
    return {
        "pr_title": pr.get("title"),
        "pr_body": pr.get("body"),
        "pr_labels": [l["name"] for l in pr.get("labels", [])] if has_pr else None,
        "pr_base_ref": (pr.get("base") or {}).get("ref"),
        "pr_head_ref": (pr.get("head") or {}).get("ref"),
    }


def changed_files(base_ref: str | None, repo_root: Path) -> list[str]:
    if not base_ref:
        return []
    cmd = ["git", "-C", str(repo_root), "diff", "--name-only", f"origin/{base_ref}...HEAD"]
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
