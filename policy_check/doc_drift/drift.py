# policy_check/doc_drift/drift.py
from __future__ import annotations

from policy_check.doc_drift.symbols import Identity


def removed_identities(base: set[Identity], head: set[Identity]) -> set[Identity]:
    return base - head


def _scope_matches(ident_scope: str, ref_scope: str) -> bool:
    # 限定式引用的 scope 段可比 ctags scope 的末段（A.B.close 的 ref "B" 命中 scope "A.B"）
    if not ident_scope:
        return False
    return ident_scope == ref_scope or ident_scope.split(".")[-1] == ref_scope


def classify_symbol_token(
    token: str, removed: set[Identity], head: set[Identity]
) -> str | None:
    """回 'FAIL' / 'WARN' / None。token 可為限定式（Foo.close）或裸名（close）。"""
    removed_names = {name for (_l, _k, _s, name) in removed}
    head_names = {name for (_l, _k, _s, name) in head}

    if "." in token:
        ref_scope, _, name = token.rpartition(".")
        ref_scope = ref_scope.split(".")[-1]
        # head 仍有相符 identity → 該限定式引用未懸空。先查 head 可避免同名異 scope
        # 的 false FAIL（doc 引用 X.B.close、僅移除 A.B.close 時，末段同為 B 不該誤判）。
        for (_l, _k, scope, nm) in head:
            if nm == name and _scope_matches(scope, ref_scope):
                return None
        for (_l, _k, scope, nm) in removed:
            if nm == name and _scope_matches(scope, ref_scope):
                return "FAIL"
        # 無任何 scoped 命中：可能是 top-level symbol（ctags scope 為空，_scope_matches
        # 永不命中），如 `mod.func`。退化為裸名語義（以末段 name 判定），避免限定式引用
        # top-level 被移除時被靜默放過。
    else:
        name = token

    if name not in removed_names:
        return None
    if name in head_names:
        return "WARN"   # 部分移除、同名仍留存 → 歧義
    return "FAIL"        # 完全消失
