from pathlib import Path

import policy_check.rules as _rules_pkg
from policy_check.rules import families, registry


def test_family_of_known():
    assert families.family_of("R-05") == "VERSION"
    assert families.family_of("R-01") == "README"
    assert families.family_of("R-26") == "MARKER-SYNC"


def test_family_of_unknown_is_other():
    assert families.family_of("R-99") == "OTHER"


def test_ordered_families_excludes_other_and_matches_source():
    of = families.ordered_families()
    assert of == [fam for fam, _ in families.FAMILIES]
    assert "OTHER" not in of
    assert of[0] == "README"


def test_every_registered_rule_classified_exactly_once():
    reg_ids = sorted(r.rule_id for r in registry.load_all())
    classified = [rid for _fam, rids in families.FAMILIES for rid in rids]
    assert len(classified) == len(set(classified)), "FAMILIES 有重複 rule_id"
    classified_set = set(classified)
    missing = [rid for rid in reg_ids if rid not in classified_set]
    assert not missing, f"未分類規則：{missing}"
    unknown = [rid for rid in classified_set if rid not in set(reg_ids)]
    assert not unknown, f"FAMILIES 含未知 rule_id：{unknown}"


def test_every_rNN_module_registers_a_rule():
    # sanity：每個以 rNN_ 命名的規則檔都應被 registry.load_all() 發現並註冊一條規則。
    # 若新增 rNN_ 檔卻忘了 @register / import 失敗，載入數會少於檔案數 → 這裡擋下。
    # （非 rNN_ 命名的規則檔既不會被 load_all 發現、也逃過此檢查——見 families.py docstring 的命名約束。）
    rules_dir = Path(_rules_pkg.__file__).parent
    rnn_files = sorted(p.stem for p in rules_dir.glob("r[0-9][0-9]_*.py"))
    loaded = sorted(r.rule_id for r in registry.load_all())
    assert len(rnn_files) == len(loaded), (
        f"rNN_ 規則檔數({len(rnn_files)}) != 已載入規則數({len(loaded)})："
        f"檔案={rnn_files}；規則={loaded}"
    )
