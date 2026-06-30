from __future__ import annotations

import pytest

from policy_check import changelog as cl


# --- parse_fragment ---

def test_parse_fragment_extracts_type_and_body():
    text = "---\ntype: feat\nscope: changelog\nissue: 24\n---\n並行安全的碎片模型。\n"
    frag = cl.parse_fragment(text)
    assert frag.type == "feat"
    assert frag.scope == "changelog"
    assert frag.issue == 24
    assert frag.body == "並行安全的碎片模型。"


def test_parse_fragment_missing_type_raises():
    with pytest.raises(cl.FragmentError):
        cl.parse_fragment("---\nscope: x\n---\n沒有 type。\n")


def test_parse_fragment_optional_fields_default_none():
    frag = cl.parse_fragment("---\ntype: fix\n---\n只修一個 bug。\n")
    assert frag.type == "fix" and frag.scope is None and frag.issue is None
    assert frag.body == "只修一個 bug。"


def test_parse_fragment_no_frontmatter_raises():
    with pytest.raises(cl.FragmentError):
        cl.parse_fragment("沒有 frontmatter，只有內文。\n")


def test_parse_fragment_empty_body_raises():
    with pytest.raises(cl.FragmentError):
        cl.parse_fragment("---\ntype: feat\n---\n\n")


# --- render_section ---

def test_render_section_groups_by_type_in_fixed_order():
    frags = [
        cl.Fragment(type="fix", body="修 A。"),
        cl.Fragment(type="feat", body="加 B。"),
        cl.Fragment(type="refactor", body="重構 C。"),
    ]
    out = cl.render_section("1.0.9", "2026-06-30", frags)
    assert out.startswith("## [1.0.9] - 2026-06-30\n")
    assert out.index("### Added") < out.index("### Changed") < out.index("### Fixed")
    assert "- 加 B。" in out and "- 重構 C。" in out and "- 修 A。" in out


def test_render_section_unknown_type_raises():
    with pytest.raises(cl.FragmentError):
        cl.render_section("1.0.9", "2026-06-30", [cl.Fragment(type="wat", body="x")])


def test_render_section_preserves_within_group_order():
    frags = [cl.Fragment(type="feat", body="第一"), cl.Fragment(type="feat", body="第二")]
    out = cl.render_section("1.0.9", "2026-06-30", frags)
    assert out.index("- 第一") < out.index("- 第二")


# --- collate + CLI ---

def _write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_collate_inserts_section_and_clears_fragments(tmp_path):
    _write(tmp_path / "CHANGELOG.md",
           "# Changelog\n\n本專案變更記錄。\n\n## [1.0.8] - 2026-06-30\n\n### Added\n- 舊東西。\n")
    _write(tmp_path / "changelog.d" / ".gitkeep", "")
    _write(tmp_path / "changelog.d" / "24-frag.md", "---\ntype: feat\n---\n加新東西。\n")
    _write(tmp_path / "changelog.d" / "30-fix.md", "---\ntype: fix\n---\n修個 bug。\n")

    cl.collate(tmp_path, "1.0.9", "2026-07-01")

    text = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.index("## [1.0.9] - 2026-07-01") < text.index("## [1.0.8]")
    assert "- 加新東西。" in text and "- 修個 bug。" in text
    assert not (tmp_path / "changelog.d" / "24-frag.md").exists()
    assert not (tmp_path / "changelog.d" / "30-fix.md").exists()
    assert (tmp_path / "changelog.d" / ".gitkeep").exists()


def test_collate_no_fragments_is_noop(tmp_path):
    _write(tmp_path / "CHANGELOG.md", "# Changelog\n\n## [1.0.8] - 2026-06-30\n\n### Added\n- x。\n")
    _write(tmp_path / "changelog.d" / ".gitkeep", "")
    n = cl.collate(tmp_path, "1.0.9", "2026-07-01")
    assert n == 0
    assert "## [1.0.9]" not in (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")


def test_collate_cli_main(tmp_path):
    _write(tmp_path / "CHANGELOG.md", "# Changelog\n\n## [1.0.8] - 2026-06-30\n\n### Added\n- x。\n")
    _write(tmp_path / "changelog.d" / "24-frag.md", "---\ntype: feat\n---\nCLI 路徑。\n")
    rc = cl.main(["collate", "--repo", str(tmp_path), "--version", "1.0.9", "--date", "2026-07-01"])
    assert rc == 0
    assert "CLI 路徑。" in (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")


# --- code review hardening (I2 / M2 / M4) ---

def test_collate_inserts_above_dated_not_above_nondated_bucket(tmp_path):
    # I2: 新段必須插在第一個 *dated* 段之前，不可插在非-dated bucket（如 backlog）之上。
    _write(tmp_path / "CHANGELOG.md",
           "# Changelog\n\n## [pre-fragment backlog]\n\n### Added\n- 舊 backlog。\n\n"
           "## [1.0.8] - 2026-06-30\n\n### Added\n- 1.0.8。\n")
    _write(tmp_path / "changelog.d" / "24-frag.md", "---\ntype: feat\n---\n新。\n")
    cl.collate(tmp_path, "1.0.9", "2026-07-01")
    text = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.index("## [pre-fragment backlog]") < text.index("## [1.0.9] - 2026-07-01")
    assert text.index("## [1.0.9] - 2026-07-01") < text.index("## [1.0.8]")


def test_parse_fragment_non_numeric_issue_raises_fragment_error():
    # M2: 非數字 issue 應拋 FragmentError，而非裸 ValueError。
    with pytest.raises(cl.FragmentError):
        cl.parse_fragment("---\ntype: feat\nissue: not-a-number\n---\nbody。\n")


def test_collate_missing_changelog_raises_fragment_error(tmp_path):
    # M4: 有 fragment 但缺 CHANGELOG.md 應拋 FragmentError（不裸 FileNotFoundError、不破壞檔案）。
    _write(tmp_path / "changelog.d" / "24-frag.md", "---\ntype: feat\n---\nbody。\n")
    with pytest.raises(cl.FragmentError):
        cl.collate(tmp_path, "1.0.9", "2026-07-01")
    assert (tmp_path / "changelog.d" / "24-frag.md").exists()  # 未刪
