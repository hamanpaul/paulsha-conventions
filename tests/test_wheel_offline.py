import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def test_venv_console_script_path_uses_entrypoint_name():
    venv_dir = Path("offline-venv")
    script = _venv_console_script(venv_dir)
    expected = venv_dir / ("Scripts" if os.name == "nt" else "bin") / (
        "policy-check.exe" if os.name == "nt" else "policy-check"
    )
    assert script == expected


def test_venv_preflight_console_script_path_uses_entrypoint_name():
    venv_dir = Path("offline-venv")
    script = _venv_console_script(venv_dir, "policy-preflight")
    expected = venv_dir / ("Scripts" if os.name == "nt" else "bin") / (
        "policy-preflight.exe" if os.name == "nt" else "policy-preflight"
    )
    assert script == expected


def test_offline_run_env_sanitizes_python_import_env():
    env = _offline_run_env(
        {
            "KEEP_ME": "1",
            "PYTHONPATH": "/source-checkout",
            "PYTHONHOME": "/source-home",
            "GITHUB_STEP_SUMMARY": "/tmp/summary",
        }
    )

    assert env["KEEP_ME"] == "1"
    assert "PYTHONPATH" not in env
    assert "PYTHONHOME" not in env
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["GITHUB_STEP_SUMMARY"] == ""


def test_packaging_gate_applies_only_to_offline_smoke():
    module_marks = globals().get("pytestmark", [])
    if not isinstance(module_marks, list):
        module_marks = [module_marks]
    smoke_marks = getattr(test_wheel_builds_installs_offline_and_runs, "pytestmark", [])
    if not isinstance(smoke_marks, list):
        smoke_marks = [smoke_marks]

    assert not module_marks
    assert any(mark.name == "skipif" for mark in smoke_marks)


def _venv_console_script(venv_dir: Path, name: str = "policy-check") -> Path:
    scripts_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    script_name = f"{name}.exe" if os.name == "nt" else name
    return scripts_dir / script_name


def _offline_run_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["GITHUB_STEP_SUMMARY"] = ""
    return env


def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


@pytest.mark.skipif(
    os.environ.get("PACKAGING") != "1",
    reason="離線 wheel smoke 僅在 PACKAGING=1（有 build 工具）環境跑",
)
def test_wheel_builds_installs_offline_and_runs(tmp_path):
    dist = tmp_path / "dist"
    vendor = tmp_path / "vendor"
    # 1) build engine wheel
    _run([sys.executable, "-m", "build", "--wheel", "--outdir", str(dist), str(REPO)])
    wheel = next(dist.glob("policy_check-*.whl"))

    # 2) 下載相依閉包到 vendor（build 階段可連網）
    _run([sys.executable, "-m", "pip", "download", "--dest", str(vendor), str(wheel)])

    # 3) 乾淨 venv，離線安裝（--no-index + --find-links）
    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    vpy = venv_dir / ("Scripts" if os.name == "nt" else "bin") / "python"
    _run(
        [
            str(vpy),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(vendor),
            str(wheel),
        ]
    )

    # 4) 離線執行：對最小 fixture repo 跑 policy-check
    policy_check = _venv_console_script(venv_dir)
    fixture = tmp_path / "repo"
    fixture.mkdir()
    (fixture / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.10\n", encoding="utf-8"
    )
    proc = subprocess.run(
        [str(policy_check), "--repo", str(fixture), "--only", "R-08"],
        capture_output=True,
        text=True,
        cwd=str(fixture),
        env=_offline_run_env(),
    )

    # R-08 對缺欄位的最小 config 可能 FAIL，但「能離線執行並產報告」才是本測試重點
    assert "Policy Check Report" in proc.stdout, proc.stderr

    # 5) 新增的 canonical preflight console entrypoint 也必須存在且可載入。
    preflight = _venv_console_script(venv_dir, "policy-preflight")
    help_proc = _run(
        [str(preflight), "--help"],
        cwd=str(fixture),
        env=_offline_run_env(),
    )
    assert help_proc.stdout.startswith("usage: policy-preflight")
