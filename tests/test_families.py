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
