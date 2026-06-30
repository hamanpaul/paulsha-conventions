# policy_check/doc_drift/refs.py
from __future__ import annotations

import re

from policy_check.doc_drift.paths import LINK_RE, looks_like_path, path_candidates

_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
_CAMEL_RE = re.compile(r"^[A-Za-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*$")
# 限定式：A.b（含點，末段為 snake/Camel/簡單識別字）
_QUALIFIED_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")


def _is_symbol_token(tok: str) -> bool:
    if len(tok) < 3:
        return False
    return bool(_SNAKE_RE.match(tok) or _CAMEL_RE.match(tok) or _QUALIFIED_RE.match(tok))


def extract_refs(doc_rel: str, text: str):
    """yield (kind, token, payload)。kind=='path'→payload=候選list；'symbol'→payload=token。"""
    for m in LINK_RE.finditer(text):
        cands = path_candidates(doc_rel, m.group(1))
        if cands:
            yield ("path", m.group(1), cands)
    for m in _CODE_SPAN_RE.finditer(text):
        tok = m.group(1).strip()
        if looks_like_path(tok):
            cands = path_candidates(doc_rel, tok)
            if cands:
                yield ("path", tok, cands)
        elif _is_symbol_token(tok):
            yield ("symbol", tok, tok)
