from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class AtomicWriteFsyncTests(unittest.TestCase):
    """Finding 3750029140: temporary-file content must be fsync'd to disk
    *before* the rename that publishes it, or a crash between rename and
    content flush can leave the published file empty/truncated."""

    def test_atomic_write_bytes_fsyncs_temp_fd_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "target.bin"
            calls: list[str] = []
            real_fsync = os.fsync
            real_replace = os.replace

            def record_fsync(descriptor):
                calls.append("fsync")
                return real_fsync(descriptor)

            def record_replace(source, destination):
                calls.append("replace")
                return real_replace(source, destination)

            with mock.patch.object(manager.os, "fsync", side_effect=record_fsync), \
                    mock.patch.object(manager.os, "replace", side_effect=record_replace):
                manager._atomic_write_bytes(path, b"payload")

            names = calls
            self.assertIn("fsync", names)
            self.assertIn("replace", names)
            self.assertLess(
                names.index("fsync"),
                names.index("replace"),
                f"fsync must precede replace, got order: {names}",
            )
            self.assertEqual(path.read_bytes(), b"payload")

    def test_atomic_write_bytes_removes_temporary_on_fsync_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "target.bin"
            path.write_bytes(b"original")

            def failing_fsync(_descriptor):
                raise OSError("simulated fsync failure")

            with mock.patch.object(manager.os, "fsync", side_effect=failing_fsync):
                with self.assertRaises(OSError):
                    manager._atomic_write_bytes(path, b"payload")

            leftovers = [
                item
                for item in Path(temporary).iterdir()
                if item.name.startswith(".target.bin.")
            ]
            self.assertEqual(leftovers, [])
            self.assertEqual(path.read_bytes(), b"original")

    def test_write_json_atomic_fsyncs_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            calls: list[str] = []
            real_fsync = os.fsync
            real_replace = os.replace

            def record_fsync(descriptor):
                calls.append("fsync")
                return real_fsync(descriptor)

            def record_replace(source, destination):
                calls.append("replace")
                return real_replace(source, destination)

            with mock.patch.object(manager.os, "fsync", side_effect=record_fsync), \
                    mock.patch.object(manager.os, "replace", side_effect=record_replace):
                manager._write_json_atomic(path, {"schema_version": 1})

            self.assertLess(calls.index("fsync"), calls.index("replace"))
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"schema_version": 1},
            )

    def test_restore_regular_file_fsyncs_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bin" / "policy-preflight"
            calls: list[str] = []
            real_fsync = os.fsync
            real_replace = os.replace

            def record_fsync(descriptor):
                calls.append("fsync")
                return real_fsync(descriptor)

            def record_replace(source, destination):
                calls.append("replace")
                return real_replace(source, destination)

            with mock.patch.object(manager.os, "fsync", side_effect=record_fsync), \
                    mock.patch.object(manager.os, "replace", side_effect=record_replace):
                manager._restore_regular_file(path, (b"#!/bin/sh\n", 0o755))

            self.assertLess(calls.index("fsync"), calls.index("replace"))
            self.assertEqual(path.read_bytes(), b"#!/bin/sh\n")
            self.assertEqual(path.stat().st_mode & 0o777, 0o755)

    def test_install_launcher_fsyncs_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "runtime"
            release = _release(root, "1.0.13")
            calls: list[str] = []
            real_fsync = os.fsync
            real_replace = os.replace

            def record_fsync(descriptor):
                calls.append("fsync")
                return real_fsync(descriptor)

            def record_replace(source, destination):
                calls.append("replace")
                return real_replace(source, destination)

            with mock.patch.object(manager.os, "fsync", side_effect=record_fsync), \
                    mock.patch.object(manager.os, "replace", side_effect=record_replace):
                manager._install_launcher(root, release, only="preflight")

            self.assertLess(calls.index("fsync"), calls.index("replace"))
            self.assertTrue((root / "bin" / "policy-preflight").is_file())

    def test_three_sites_share_one_atomic_write_helper(self) -> None:
        """Guards against the fix regressing into three copy-pasted writers."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "runtime"
            release = _release(root, "1.0.13")
            invoked: list[str] = []
            real_atomic_write = manager._atomic_write_bytes

            def record(path, content, **kwargs):
                invoked.append(Path(path).name)
                return real_atomic_write(path, content, **kwargs)

            with mock.patch.object(manager, "_atomic_write_bytes", side_effect=record):
                manager._write_json_atomic(root / "state.json", {"a": 1})
                manager._restore_regular_file(
                    root / "bin" / "policy-runtime-bundle", (b"data", 0o755)
                )
                manager._install_launcher(root, release, only="preflight")

            self.assertIn("state.json", invoked)
            self.assertIn("policy-runtime-bundle", invoked)
            self.assertIn("policy-preflight", invoked)


class RecoverTrustBoundaryTests(unittest.TestCase):
    """Finding 3750029213: recover() must never let a self-consistent but
    unrequested journal dictate which skill-target path gets overwritten."""

    def test_recover_without_explicit_target_rejects_forged_journal_skill_target(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "runtime"
            root.mkdir(parents=True)
            old = _release(root, "1.0.13")
            trusted_default = Path(temporary) / "trusted" / "skills" / "preflight-ci"
            decoy_target = Path(temporary) / "attacker-writable" / "payload"

            snapshots = {step: None for step in manager._ACTIVATION_STEPS}
            journal_path, anchor_path = manager._journal_paths(root)
            manager._append_activation_event(
                journal_path,
                anchor_path,
                sequence=1,
                previous_digest=None,
                event="begin",
                payload={
                    "runtime_root": str(root.resolve()),
                    "skill_target": str(decoy_target.absolute()),
                    "release": str(old.resolve()),
                    "steps": list(manager._ACTIVATION_STEPS),
                    "snapshots": snapshots,
                },
            )

            with mock.patch.object(
                manager, "_default_skill_target", return_value=trusted_default
            ):
                with self.assertRaises(manager.RuntimeBundleError):
                    manager.recover(root)

            self.assertFalse(decoy_target.exists())
            self.assertFalse(decoy_target.parent.exists())
            self.assertFalse(trusted_default.exists())
            self.assertFalse(trusted_default.parent.exists())
            self.assertTrue(journal_path.exists())
            self.assertTrue(anchor_path.exists())

    def test_recover_without_explicit_target_succeeds_when_journal_matches_default(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "runtime"
            old = _release(root, "1.0.13")
            trusted_default = Path(temporary) / "skills" / "preflight-ci"
            trusted_default.parent.mkdir(parents=True)
            trusted_default.symlink_to(old / "artifact" / "skills" / "preflight-ci")

            state_path = root / "state.json"
            state = {
                "schema_version": 1,
                "current": "1.0.13",
                "previous": None,
                "installed": ["1.0.13"],
            }
            state_path.write_text(
                json.dumps(state, sort_keys=True) + "\n", encoding="utf-8"
            )
            (root / "current").symlink_to(old)
            manager._install_launcher(root, old)

            snapshots = manager._activation_snapshot(root, trusted_default)
            journal_path, anchor_path = manager._journal_paths(root)
            manager._append_activation_event(
                journal_path,
                anchor_path,
                sequence=1,
                previous_digest=None,
                event="begin",
                payload={
                    "runtime_root": str(root.resolve()),
                    "skill_target": str(trusted_default.absolute()),
                    "release": str(old.resolve()),
                    "steps": list(manager._ACTIVATION_STEPS),
                    "snapshots": snapshots,
                },
            )

            with mock.patch.object(
                manager, "_default_skill_target", return_value=trusted_default
            ):
                self.assertTrue(manager.recover(root))

            self.assertFalse(journal_path.exists())
            self.assertFalse(anchor_path.exists())

    def test_recover_rejects_mismatched_explicit_skill_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "runtime"
            root.mkdir(parents=True)
            old = _release(root, "1.0.13")
            recorded_target = Path(temporary) / "skills" / "preflight-ci"
            requested_target = Path(temporary) / "other-skills" / "preflight-ci"

            snapshots = {step: None for step in manager._ACTIVATION_STEPS}
            journal_path, anchor_path = manager._journal_paths(root)
            manager._append_activation_event(
                journal_path,
                anchor_path,
                sequence=1,
                previous_digest=None,
                event="begin",
                payload={
                    "runtime_root": str(root.resolve()),
                    "skill_target": str(recorded_target.absolute()),
                    "release": str(old.resolve()),
                    "steps": list(manager._ACTIVATION_STEPS),
                    "snapshots": snapshots,
                },
            )

            with self.assertRaises(manager.RuntimeBundleError):
                manager.recover(root, requested_target)

            self.assertFalse(requested_target.exists())
            self.assertFalse(recorded_target.exists())
            self.assertTrue(journal_path.exists())

    def test_recover_cleans_up_committed_journal_without_skill_target_even_if_mismatched(
        self,
    ) -> None:
        """A *committed* journal never writes to skill_target — it only
        deletes its own journal/anchor files under the trusted runtime_root
        — so a caller with no opinion on skill_target (e.g. uninstall())
        must still be able to clean it up, regardless of what the journal's
        recorded skill_target says. This is what keeps the fail-closed check
        in the restore path from breaking that legitimate call pattern."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "runtime"
            root.mkdir(parents=True)
            old = _release(root, "1.0.13")
            recorded_target = Path(temporary) / "custom-skills" / "preflight-ci"

            snapshots = {step: None for step in manager._ACTIVATION_STEPS}
            journal_path, anchor_path = manager._journal_paths(root)
            sequence, digest = manager._append_activation_event(
                journal_path,
                anchor_path,
                sequence=1,
                previous_digest=None,
                event="begin",
                payload={
                    "runtime_root": str(root.resolve()),
                    "skill_target": str(recorded_target.absolute()),
                    "release": str(old.resolve()),
                    "steps": list(manager._ACTIVATION_STEPS),
                    "snapshots": snapshots,
                },
            )
            for step in manager._ACTIVATION_STEPS:
                sequence, digest = manager._append_activation_event(
                    journal_path,
                    anchor_path,
                    sequence=sequence,
                    previous_digest=digest,
                    event="prepare",
                    payload={"step": step},
                )
                sequence, digest = manager._append_activation_event(
                    journal_path,
                    anchor_path,
                    sequence=sequence,
                    previous_digest=digest,
                    event="complete",
                    payload={"step": step},
                )
            manager._append_activation_event(
                journal_path,
                anchor_path,
                sequence=sequence,
                previous_digest=digest,
                event="commit",
                payload={},
            )

            with mock.patch.object(
                manager,
                "_default_skill_target",
                return_value=Path(temporary) / "unrelated" / "preflight-ci",
            ):
                self.assertTrue(manager.recover(root))

            self.assertFalse(journal_path.exists())
            self.assertFalse(anchor_path.exists())


if __name__ == "__main__":
    unittest.main()
