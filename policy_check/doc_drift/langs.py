from __future__ import annotations

# ctags `language` 名稱 → 計為 public symbol 的 ctags kind（long name）白名單。
# 新增語言只動這張表，差集/比對演算法不變。
_LANG_KINDS: dict[str, set[str]] = {
    "Python": {"function", "class", "member"},
    "Sh": {"function"},
}


def public_kinds(language: str) -> set[str]:
    return set(_LANG_KINDS.get(language, set()))


def supported_languages() -> set[str]:
    return set(_LANG_KINDS)
