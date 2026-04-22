# policy_check/rules/registry.py
from importlib import import_module
from pkgutil import iter_modules
from policy_check.rules.base import Rule

_RULE_MODULES = []  # 由各 rule module 透過 register() 填入


def register(rule_cls):
    _RULE_MODULES.append(rule_cls)
    return rule_cls


def load_all() -> list[Rule]:
    # 確保所有 rule module 被 import（觸發 register decorator）
    import policy_check.rules as pkg
    for m in iter_modules(pkg.__path__):
        if m.name.startswith("r") and m.name[1:3].isdigit():
            import_module(f"policy_check.rules.{m.name}")
    return [cls() for cls in _RULE_MODULES]
