import os

from policy_check import pr_context as prc


def _clear(mp):
    for k in list(os.environ):
        if k.startswith("CI_MERGE_REQUEST_") or k in ("GITHUB_EVENT_PATH",):
            mp.delenv(k, raising=False)


def test_gitlab_pr_meta_maps_and_strips_labels(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "7")
    monkeypatch.setenv("CI_MERGE_REQUEST_TITLE", "feat: x")
    monkeypatch.setenv("CI_MERGE_REQUEST_DESCRIPTION", "body")
    monkeypatch.setenv("CI_MERGE_REQUEST_LABELS", "wip, policy-exempt:docs-sync ,")
    monkeypatch.setenv("CI_MERGE_REQUEST_SOURCE_BRANCH_NAME", "fix-x")
    monkeypatch.setenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "main")
    m = prc.gitlab_pr_meta()
    assert m["pr_title"] == "feat: x"
    assert m["pr_body"] == "body"
    assert m["pr_labels"] == ["wip", "policy-exempt:docs-sync"]
    assert m["pr_head_ref"] == "fix-x" and m["pr_base_ref"] == "main"
    assert m["provider"] == "gitlab"


def test_gitlab_labels_unset_is_empty_list(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "7")
    assert prc.gitlab_pr_meta()["pr_labels"] == []


def test_load_pr_meta_dispatches_github_event(monkeypatch):
    _clear(monkeypatch)
    assert prc.load_pr_meta() == {}
    monkeypatch.setattr(
        prc,
        "load_event_payload",
        lambda: {
            "pull_request": {
                "title": "gh title",
                "body": "gh body",
                "labels": [{"name": "wip"}],
                "base": {"ref": "main"},
                "head": {"ref": "feature/x"},
            }
        },
    )
    m = prc.load_pr_meta()
    assert m["provider"] == "github"
    assert m["pr_title"] == "gh title"
    assert m["pr_body"] == "gh body"
    assert m["pr_labels"] == ["wip"]
    assert m["pr_base_ref"] == "main"
    assert m["pr_head_ref"] == "feature/x"


def test_load_pr_meta_prefers_gitlab_over_github_event(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "7")
    monkeypatch.setenv("CI_MERGE_REQUEST_TITLE", "gl title")
    monkeypatch.setenv("CI_MERGE_REQUEST_DESCRIPTION", "gl body")
    monkeypatch.setattr(
        prc,
        "load_event_payload",
        lambda: {"pull_request": {"title": "gh title", "body": "gh body"}},
    )
    m = prc.load_pr_meta()
    assert m["provider"] == "gitlab"
    assert m["pr_title"] == "gl title"
    assert m["pr_body"] == "gl body"
