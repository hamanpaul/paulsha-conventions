<!-- managed-by: hamanpaul/paul-project-conventions@v1.0.0 -->
<!-- keep CLAUDE.md / AGENTS.md / GEMINI.md / .github/copilot-instructions.md in sync -->

policy_version: 1.0.0

# Agent Policy Checklist

This repository follows the hamanpaul project policy.

## Before Starting
- Work on feature/worktree branches, not `main`.
- Keep changes scoped and testable.

## Before Claiming Done
- Update `CHANGELOG.md` `[Unreleased]` when code behavior changes.
- Ensure tests pass.
- Ensure `python3 -m policy_check --repo .` reports no failures.
