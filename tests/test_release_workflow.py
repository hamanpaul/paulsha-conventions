"""release workflow 自我檢測。

發行流程的正確性無法靠事後觀察補救：tag 一旦推上去，workflow 就直接對外
publish。這裡把幾個「錯了就會發出壞 release」的結構性前提釘住。
"""
from pathlib import Path
import re
import tomllib

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "release.yml"


def _workflow() -> dict:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "release.yml 不是合法的 workflow mapping"
    return data


def _triggers(data: dict) -> dict:
    # PyYAML 把裸 `on:` 解析成 boolean key True。
    trigger = data.get("on", data.get(True))
    assert isinstance(trigger, dict), "release.yml 缺少 on: 觸發宣告"
    return trigger


def _min_python() -> tuple[int, int]:
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    requires = pyproject["project"]["requires-python"]
    match = re.search(r">=\s*(\d+)\.(\d+)", requires)
    assert match, f"無法解析 requires-python: {requires!r}"
    return int(match.group(1)), int(match.group(2))


def test_release_workflow_exists_and_parses():
    assert WORKFLOW.is_file(), "缺少 .github/workflows/release.yml"
    assert set(_workflow()["jobs"]) >= {"bundle", "publish"}


def test_triggers_only_on_policy_version_tags():
    patterns = _triggers(_workflow())["push"]["tags"]
    # policy 的版本格式為 <MAJOR>.<MINOR>.<PATCH>[-fix.N]；其餘 tag 不得發行。
    assert patterns == [
        "v[0-9]+.[0-9]+.[0-9]+",
        "v[0-9]+.[0-9]+.[0-9]+-fix.[0-9]+",
    ]


def test_publish_waits_for_every_bundle_job():
    # publish 必須 needs bundle：任一 ABI 的建置或安裝驗證失敗都不得發布。
    assert _workflow()["jobs"]["publish"]["needs"] == "bundle"


def test_bundle_matrix_covers_supported_pythons_only():
    matrix = _workflow()["jobs"]["bundle"]["strategy"]["matrix"]["python"]
    assert matrix, "bundle matrix 不得為空，否則不會產出任何 archive"
    minimum = _min_python()
    for version in matrix:
        parsed = tuple(int(part) for part in str(version).split("."))
        assert parsed >= minimum, (
            f"matrix Python {version} 低於 requires-python 下限 "
            f"{minimum[0]}.{minimum[1]}，建出的 bundle 裝不起來"
        )


def test_bundle_matrix_fails_fast():
    # 半套發行（只有部分 ABI 成功）比整批失敗更難收拾。
    assert _workflow()["jobs"]["bundle"]["strategy"]["fail-fast"] is True


def test_write_permission_is_scoped_to_publish_job():
    data = _workflow()
    assert data["permissions"] == {"contents": "read"}, "top-level 權限必須唯讀"
    assert data["jobs"]["publish"]["permissions"] == {"contents": "write"}
    assert "permissions" not in data["jobs"]["bundle"], "建置 job 不需要寫入權限"


def test_checkout_fetches_full_history_for_tag_attestation():
    # builder 的 clean-tag attestation 要 annotated tag object；shallow checkout
    # 會讓 `git cat-file -t <tag>` 解不出 tag，發行流程直接失敗。
    for job in ("bundle", "publish"):
        checkouts = [
            step
            for step in _workflow()["jobs"][job]["steps"]
            if str(step.get("uses", "")).startswith("actions/checkout")
        ]
        assert checkouts, f"{job} job 缺少 checkout"
        for step in checkouts:
            assert step["with"]["fetch-depth"] == 0, f"{job} job 的 checkout 必須取完整歷史"


def test_bundle_job_verifies_before_upload():
    steps = _workflow()["jobs"]["bundle"]["steps"]
    names = [str(step.get("name", "")) for step in steps]
    upload = next(
        index
        for index, step in enumerate(steps)
        if str(step.get("uses", "")).startswith("actions/upload-artifact")
    )
    verify = next(index for index, name in enumerate(names) if "Verify" in name)
    smoke = next(index for index, name in enumerate(names) if "install smoke" in name)
    assert verify < upload and smoke < upload, "digest 驗證與安裝 smoke 必須在上傳前完成"


def _smoke_run() -> str:
    return next(
        str(step["run"])
        for step in _workflow()["jobs"]["bundle"]["steps"]
        if "install smoke" in str(step.get("name", ""))
    )


def test_install_smoke_does_not_gate_on_a_policy_verdict():
    # `policy_check --repo <path>` 的 exit code 表達 policy 判定，不是 runtime 健康度。
    # tag push 沒有 PR context，判定本來就不會過；拿它當 smoke 會把「engine 正常但
    # repo 不符 policy」誤報成建置失敗，擋掉合法的 release。
    assert "-m policy_check --repo" not in _smoke_run()


def test_install_smoke_checks_the_installed_artifact_in_isolated_mode():
    run = _smoke_run()
    # 少了 -I，cwd 的 source 樹與 egg-info 會蓋過 venv 裡安裝的套件，
    # smoke 就變成在驗 checkout 而不是驗 bundle 產物。
    for command in ("-I -m policy_check --help", "-I -m policy_check.preflight --help"):
        assert command in run, f"smoke 缺少隔離模式指令：{command}"
    assert "-I -c 'from importlib.metadata import version" in run


def test_install_smoke_asserts_installed_version_matches_the_tag():
    run = _smoke_run()
    assert 'version("policy-check")' in run
    assert "VERSION" in run and 'if [ "$installed" != "$expected" ]' in run
