# tests/test_doc_drift_coverage.py
from policy_check.doc_drift import coverage

DEFAULT_PREFIXES = ("openspec/changes/", "docs/superpowers/plans/", "docs/superpowers/specs/")


def test_orphan_detects_unlinked_plan():
    head_files = {"docs/superpowers/plans/X.md", "docs/MOC.md"}
    linked = set()  # MOC 沒連到 X
    orphans = coverage.orphans(head_files, linked, prefixes=DEFAULT_PREFIXES)
    assert "docs/superpowers/plans/X.md" in orphans


def test_custom_prefix_scopes_orphan_check():
    head_files = {"specs/X.md", "docs/superpowers/plans/Y.md"}
    linked = set()
    orphans = coverage.orphans(head_files, linked, prefixes=("specs/",))
    assert "specs/X.md" in orphans
    assert "docs/superpowers/plans/Y.md" not in orphans  # 不在自訂前綴內
