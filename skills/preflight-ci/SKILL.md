---
name: preflight-ci
description: >-
  Run a repository's policy, OpenSpec, and test gates locally before push, PR,
  or merge. This skill is owned and deployed by paulsha-conventions and uses
  its canonical policy-preflight engine instead of relying on GitHub Actions
  as the first filtering layer.
---

# Preflight CI

## Authority

This skill and `policy_check.preflight` are both owned by
`hamanpaul/paulsha-conventions`.

- The skill owns agent-facing routing and the local execution entrypoint.
- `policy-preflight` owns PR context, engine identity, gate orchestration, and
  the final verdict.
- The target repository owns validation/test commands through
  `.paul-project.yml.preflight.steps`.
- GitHub or GitLab CI remains a remote merge gate, but it is not the primary
  place where avoidable policy/test failures are discovered.

Do not copy resolver or gate logic into this skill. The wrapper must delegate
to the adjacent canonical engine checkout.

## Workflow

1. Finish code, changelog, and documentation changes.
2. Draft the exact PR title, body, labels, base, and head.
3. Confirm the target repo declares its gates:

   ```yaml
   preflight:
     steps:
       - name: openspec
         kind: validation
         argv: ["openspec", "validate", "--all"]
         when_path_exists: "openspec"
       - name: tests
         kind: tests
         argv: ["python3", "-m", "pytest", "-q"]
   ```

4. Before the PR exists, run:

   ```bash
   ~/.agents/skills/preflight-ci/scripts/preflight.sh \
     --pr-title "<title>" \
     --pr-body-file <body.md> \
     --pr-labels "<a,b>" \
     --base main
   ```

5. For an existing PR, run:

   ```bash
   ~/.agents/skills/preflight-ci/scripts/preflight.sh --pr <N>
   ```

6. Push or merge only after `PREFLIGHT PASS`. Verify remote checks and review
   threads afterward; do not use a green remote run to excuse a failed local
   preflight.

## Modes

- `--offline`: no network-capable engine resolver operation; manual PR
  metadata is required. The skill-owned source engine is already local.
- `--policy-only`: explicitly run only policy. This is also the only allowed
  skill mode when the target repo has not declared `preflight.steps`.
- `--skip-tests`: skip only steps declared with `kind: tests`.
- `PSC_PREFLIGHT_PYTHON`: optional Python interpreter used to start the
  canonical engine. Project test interpreters belong in each step's `argv`.

## Failure handling

Read [references/gotchas.md](references/gotchas.md) before diagnosing a
repeated policy/OpenSpec failure. Never print PR metadata, matched secrets, or
tokens in troubleshooting output.
