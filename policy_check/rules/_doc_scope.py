from __future__ import annotations

from fnmatch import fnmatch

DEFAULT_DOC_PATHS = ("README.md", "docs/**")


def configured_doc_paths(config: dict | None) -> list[str]:
    raw = (config or {}).get("doc_paths") or list(DEFAULT_DOC_PATHS)
    return [str(item) for item in raw]


def matches_doc_path(rel: str, doc_paths: list[str]) -> bool:
    return any(fnmatch(rel, pattern) for pattern in doc_paths)


def is_canonical_doc(rel: str, config: dict | None) -> bool:
    return matches_doc_path(rel, configured_doc_paths(config))
