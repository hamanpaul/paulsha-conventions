from __future__ import annotations

import re
from fnmatch import fnmatch

from policy_check.rules.base import RuleContext, RuleResult, Status
from policy_check.rules.registry import register
from policy_check.rules._doc_links import (
    LINK_RE, looks_like_path, path_candidates, git_tracked, resolve_base,
)

_GOVERNED_PREFIXES = ("openspec/changes/", "docs/superpowers/")
_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")


@register
class R24MocAlignment:
    rule_id = "R-24"
    exempt_label = "policy-exempt:moc-alignment"

    def check(self, ctx: RuleContext) -> RuleResult:
        if self.exempt_label in ctx.pr_labels:
            return RuleResult(self.rule_id, Status.SKIP,
                              f"Skipped by exemption label: {self.exempt_label}.",
                              exempt_label=self.exempt_label)

        moc = (ctx.config or {}).get("moc") or {}
        if not isinstance(moc, dict) or not moc:
            return RuleResult(self.rule_id, Status.PASS, "No moc declared; R-24 not applicable.")

        fails: list[str] = []
        warns: list[str] = []

        changed = set(ctx.changed_files or [])
        static = moc.get("static")
        triggers = [t for t in (moc.get("triggers") or []) if isinstance(t, str)]
        if isinstance(static, str) and static and triggers and changed:
            hit = sorted(f for f in changed if any(fnmatch(f, g) for g in triggers))
            if hit and static not in changed:
                warns.append(
                    f"static MOC '{static}' 未隨 trigger 變更同步；命中：{', '.join(hit[:5])}"
                )

        map_rel = moc.get("map")
        root = ctx.repo_root
        head_files = git_tracked(root)
        if isinstance(map_rel, str) and map_rel:
            if map_rel not in head_files:
                warns.append(f"moc.map '{map_rel}' 已宣告但 repo 中找不到")
            else:
                try:
                    text = (root / map_rel).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = ""
                base = resolve_base(root, ctx.pr_base_ref)
                base_files = git_tracked(root, base) if base else set()
                for token, cands in self._map_refs(map_rel, text):
                    if any(c in head_files for c in cands):
                        continue
                    if base and any(c in base_files for c in cands):
                        fails.append(f"{map_rel} -> {token}（本次移除）")
                    else:
                        warns.append(f"{map_rel} -> {token}")

                linked = {c for _t, cs in self._map_refs(map_rel, text) for c in cs}
                # plans / specs：精確檔路徑須被 link
                for rel in sorted(head_files):
                    if rel.endswith(".md") and rel.startswith(
                        ("docs/superpowers/plans/", "docs/superpowers/specs/")
                    ) and rel not in linked:
                        warns.append(f"孤兒：{rel} 未被 {map_rel} 連結")
                # active openspec changes：change dir 下任一連結即算
                change_names = sorted({
                    rel.split("/")[2] for rel in head_files
                    if rel.startswith("openspec/changes/")
                    and not rel.startswith("openspec/changes/archive/")
                    and len(rel.split("/")) >= 3
                })
                for name in change_names:
                    prefix = f"openspec/changes/{name}/"
                    if not any(t.startswith(prefix) for t in linked):
                        warns.append(f"孤兒：openspec change '{name}' 未被 {map_rel} 連結")

        return self._verdict(fails, warns)

    @staticmethod
    def _map_refs(map_rel: str, text: str):
        """yield (token, candidates)：markdown link 與 backtick path token，僅取指向受治理產物者。"""
        seen: set[str] = set()
        tokens = [m.group(1) for m in LINK_RE.finditer(text)]
        tokens += [t for t in (m.group(1).strip() for m in _CODE_SPAN_RE.finditer(text))
                   if looks_like_path(t)]
        for tok in tokens:
            if tok in seen:
                continue
            cands = [c for c in path_candidates(map_rel, tok)
                     if c.startswith(_GOVERNED_PREFIXES)]
            if cands:
                seen.add(tok)
                yield tok, cands

    def _verdict(self, fails, warns) -> RuleResult:
        if fails:
            return RuleResult(self.rule_id, Status.FAIL,
                              f"MOC map has {len(fails)} dangling reference(s) introduced by this change.",
                              detail="\n".join(fails[:20]))
        if warns:
            return RuleResult(self.rule_id, Status.WARN,
                              f"MOC alignment: {len(warns)} advisory item(s).",
                              detail="\n".join(warns[:20]))
        return RuleResult(self.rule_id, Status.PASS, "MOC aligned with this change.")
