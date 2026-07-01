import contextlib
import io
import re

from policy_check.report import emit
from policy_check.rules.base import RuleResult, Status


def _cap(results, families=None, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = emit(results, families)
    return buf.getvalue(), rc


def _mk(rid, status=Status.PASS):
    return RuleResult(rid, status, f"msg {rid}")


def _rule_block_count(out):
    # 逐條規則區塊標題形如 "## :icon: R-NN — status"；family 標題為 "### FAM"
    return len(re.findall(r"^## :", out, re.M))


def test_grouped_output_has_family_headers_in_order(monkeypatch):
    results = [_mk("R-05"), _mk("R-01"), _mk("R-06")]
    fam = {"R-05": "VERSION", "R-01": "README", "R-06": "VERSION"}
    out, rc = _cap(results, fam, monkeypatch)
    assert "### README" in out and "### VERSION" in out
    assert out.index("### README") < out.index("### VERSION")
    assert out.index("R-05") < out.index("R-06")  # family 內按 rule_id
    assert rc == 0


def test_families_none_is_flat_backward_compat(monkeypatch):
    results = [_mk("R-05"), _mk("R-01")]
    out, rc = _cap(results, None, monkeypatch)
    assert "###" not in out
    assert out.index("R-01") < out.index("R-05")
    assert rc == 0


def test_unclassified_rule_goes_to_other_and_count_matches(monkeypatch):
    results = [_mk("R-01"), _mk("R-99")]  # R-99 不在 map
    fam = {"R-01": "README"}
    out, rc = _cap(results, fam, monkeypatch)
    assert "### OTHER" in out
    assert "R-99" in out
    assert _rule_block_count(out) == 2  # body 區塊數 == summary 總數


def test_exit_code_1_on_fail_regardless_of_grouping(monkeypatch):
    _, rc = _cap([_mk("R-01", Status.FAIL)], {"R-01": "README"}, monkeypatch)
    assert rc == 1
