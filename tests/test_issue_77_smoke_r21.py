from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from policy_check import config as policy_config
from policy_check import preflight
from policy_check.rules.base import RuleContext, Status
from policy_check.rules.r21_secret_scan import R21SecretScan
from policy_check.runtime_bundle import manager


class Issue77SmokeR21Tests(unittest.TestCase):
    def test_smoke_fixture_allowlists_absolute_interpreter_for_r21(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            interpreter = "/".join(("", "home", "someuser", ".venv", "bin", "python3"))
            with patch.object(manager.sys, "executable", interpreter):
                repo, _body = manager._make_smoke_repo(root, "1.0.13")

            context = RuleContext(
                repo_root=repo,
                profile="flat",
                policy_version="1.0.13",
                config=policy_config.load(repo),
                repo_visibility="public",
            )
            result = R21SecretScan().check(context)

        self.assertEqual(result.status, Status.PASS)

    def test_bounded_diagnostic_prioritizes_failure_lines(self) -> None:
        result = subprocess.CompletedProcess(
            ["policy-check"],
            1,
            stdout="\n".join(
                (
                    "## :x: R-01 - FAIL",
                    "R-01 detail",
                    "## :white_check_mark: R-02 - PASS",
                    "## :x: R-03 - FAIL",
                    "R-03 detail",
                    "## :x: R-04 - FAIL",
                    "PREFLIGHT FAIL",
                )
            ),
            stderr="",
        )

        diagnostic = preflight._bounded_command_diagnostic(result)

        self.assertIn("## :x: R-01 - FAIL", diagnostic)
        self.assertIn("## :x: R-03 - FAIL", diagnostic)
        self.assertIn("## :x: R-04 - FAIL", diagnostic)
        self.assertIn("PREFLIGHT FAIL", diagnostic)

    def test_bounded_diagnostic_keeps_last_four_lines_without_failures(self) -> None:
        result = subprocess.CompletedProcess(
            ["policy-check"],
            0,
            stdout="one\ntwo\nthree\nfour\nfive\n",
            stderr="",
        )

        self.assertEqual(
            preflight._bounded_command_diagnostic(result),
            "two | three | four | five",
        )


if __name__ == "__main__":
    unittest.main()
