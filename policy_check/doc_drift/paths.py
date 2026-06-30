# policy_check/doc_drift/paths.py
from __future__ import annotations

# 共用既有實作（單一真相）；doc_drift 對外只暴露穩定名稱。
from policy_check.rules._doc_links import (  # noqa: F401
    LINK_RE, looks_like_path, path_candidates, git_tracked, resolve_base,
)
