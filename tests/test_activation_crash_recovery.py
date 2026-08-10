from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from policy_check.runtime_bundle import manager


_CHILD_SCRIPT = r'''
import os
import signal
import sys
from pathlib import Path

from policy_check.runtime_bundle import manager

root = Path(sys.argv[1])
skill = Path(sys.argv[2])
release = Path(sys.argv[3])
step_to_kill = sys.argv[4]
state = {
    "schema_version": 1,
    "current": release.name,
    "previous": "1.0.13",
    "installed": ["1.0.13", release.name],
}

def kill_after(step):
    if step == step_to_kill:
        os.kill(os.getpid(), signal.SIGKILL)

real_write = manager._write_json_atomic
real_symlink = manager._atomic_symlink
real_launcher = manager._install_launcher

def write(path, value):
    real_write(path, value)
    if Path(path).name == "state.json":
        kill_after("state")

def symlink(target, link):
    real_symlink(target, link)
    name = "skill" if link == skill else Path(link).name
    kill_after(name)

def launcher(root_path, release_path, *, only=None):
    real_launcher(root_path, release_path, only=only)
    kill_after(only)

manager._write_json_atomic = write
manager._atomic_symlink = symlink
manager._install_launcher = launcher
manager._switch_active_release(root, skill, release, state)
'''


def _release(runtime_root: Path, version: str) -> Path:
    release = runtime_root / "releases" / version
    artifact = release / "artifact"
    skill = artifact / "skills" / "preflight-ci"
    skill.mkdir(parents=True)
    runtime = artifact / "runtime" / "runtime_manager.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("# test runtime manager\n", encoding="utf-8")
    manifest = {
        "runtime": {
            "path": "runtime/runtime_manager.py",
            "sha256": manager._sha256(runtime),
        }
    }
    (artifact / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (release / "VERIFIED").write_text("verified\n", encoding="utf-8")
    return release


class ActivationCrashRecoveryTests(unittest.TestCase):
    def test_every_activation_interruption_point_recovers_old_generation(self) -> None:
        for step in ("state", "current", "preflight", "lifecycle", "skill"):
            with self.subTest(step=step), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "runtime"
                old = _release(root, "1.0.13")
                new = _release(root, "1.0.14")
                skill = Path(temporary) / "skills" / "preflight-ci"
                (root / "current").symlink_to(old)
                skill.parent.mkdir(parents=True)
                skill.symlink_to(old / "artifact" / "skills" / "preflight-ci")
                old_state = {
                    "schema_version": 1,
                    "current": "1.0.13",
                    "previous": None,
                    "installed": ["1.0.13", "1.0.14"],
                }
                state_path = root / "state.json"
                state_path.write_text(
                    json.dumps(old_state, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                manager._install_launcher(root, old)
                before = {
                    "state": state_path.read_bytes(),
                    "current": os.readlink(root / "current"),
                    "skill": os.readlink(skill),
                    "preflight": (root / "bin" / "policy-preflight").read_bytes(),
                    "lifecycle": (root / "bin" / "policy-runtime-bundle").read_bytes(),
                }

                environment = dict(os.environ)
                environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        _CHILD_SCRIPT,
                        str(root),
                        str(skill),
                        str(new),
                        step,
                    ],
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, -signal.SIGKILL, result.stderr)
                self.assertTrue((root / "activation.journal").is_file())
                self.assertTrue((root / "activation.journal.anchor").is_file())

                self.assertTrue(manager.recover(root, skill))
                self.assertEqual(state_path.read_bytes(), before["state"])
                self.assertEqual(os.readlink(root / "current"), before["current"])
                self.assertEqual(os.readlink(skill), before["skill"])
                self.assertEqual(
                    (root / "bin" / "policy-preflight").read_bytes(),
                    before["preflight"],
                )
                self.assertEqual(
                    (root / "bin" / "policy-runtime-bundle").read_bytes(),
                    before["lifecycle"],
                )
                self.assertFalse((root / "activation.journal").exists())
                self.assertFalse((root / "activation.journal.anchor").exists())


if __name__ == "__main__":
    unittest.main()
