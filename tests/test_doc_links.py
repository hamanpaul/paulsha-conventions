from __future__ import annotations

from policy_check.rules._doc_links import looks_like_path, path_candidates, LINK_RE


def test_looks_like_path_accepts_code_ext_and_dotslash():
    assert looks_like_path("docs/x.md")
    assert looks_like_path("./LICENSE.md")
    assert not looks_like_path("feature/<slug>")
    assert not looks_like_path("hamanpaul/paulsha-conventions")  # org/repo slug, no ext


def test_path_candidates_normalizes_doc_relative_and_root():
    cands = path_candidates("docs/MOC.md", "plans/x.md")
    assert "docs/plans/x.md" in cands
    assert "plans/x.md" in cands


def test_link_re_extracts_markdown_target():
    assert LINK_RE.findall("see [x](docs/a.md) and [y](b.md)") == ["docs/a.md", "b.md"]
