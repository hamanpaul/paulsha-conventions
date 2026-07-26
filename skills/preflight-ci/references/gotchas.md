# Preflight CI gotchas

## Missing repo-owned gates

- **Symptom:** skill-driven full preflight exits 2 before running gates.
- **Why:** the target repo does not declare `.project-policy.yml.preflight.steps`
  (or its deprecated legacy alias).
- **Fix:** declare typed validation/test commands. Use `--policy-only` only
  when policy-only execution is intentional.

## Repo-owned step failure reproducibility

- **Symptom:** preflight reports `<step>: FAIL ... (exit=N)` without the command's
  captured stdout/stderr.
- **Why:** the step output is intentionally not echoed; its executable contract
  remains the typed `argv`, `cwd`, and timeout in the project policy manifest.
- **Fix:** from the same checkout and environment, change to the declared `cwd`
  and rerun that step's exact `argv`. Do not reinterpret it through a shell or
  add PR metadata flags that are not part of the declared command.

## R-17 issue links

- **Symptom:** policy reports R-17 failure.
- **Why:** PR body contains a bare `#N` without `Closes`, `Fixes`, or
  `Resolves`.
- **Fix:** use a closing keyword, remove the `#`, or apply the allowlisted
  issue-link exemption with a reason.

## R-09 changelog

- **Symptom:** policy reports R-09 failure.
- **Why:** code changed without a `changelog.d/*.md` fragment.
- **Fix:** add the fragment required by the target repo policy.

## R-22 after archive, rename, or removal

- **Symptom:** local preflight reports a newly dangling documentation
  reference.
- **Why:** canonical docs still reference the old path or symbol.
- **Fix:** update every reference before rerunning preflight.

## OpenSpec archive creates a placeholder purpose

- **Symptom:** canonical spec contains a `TBD` purpose after archive.
- **Why:** OpenSpec created a new main spec from a delta.
- **Fix:** replace the placeholder with the real capability purpose and run
  `openspec validate --all`.

## Source engine version skew

- **Symptom:** engine gate reports a VERSION mismatch.
- **Why:** the installed skill's adjacent `paulsha-conventions/VERSION` does
  not match the target repo's `.project-policy.yml.policy_version`.
- **Fix:** update the deployed conventions checkout and target policy version
  through the normal release/rollout process. Never fall back silently.

## Invalid cache artifact removal

- **Symptom:** `_populate_cache` reports `invalid cache artifact already exists`.
- **Why:** an interrupted resolve step created a partial cache at
  `~/.cache/paulsha-conventions/preflight/<repo-owner>/<repo>/<sha>`.
- **Fix:** confirm the exact `<repo>@<sha>` target from the error and quarantine
  or trash only that directory (example:
  `~/.cache/paulsha-conventions/preflight/hamanpaul/paulsha-conventions/<sha>/`).
  Never delete parent directories like `~/.cache/paulsha-conventions/preflight/` or
  `~/.cache/paulsha-conventions/` wholesale.

## Remote CI disagrees with local preflight

- **Symptom:** local preflight passes but a remote provider fails.
- **Why:** provider setup, stale event metadata, billing, or a target config
  drift can still differ from local execution.
- **Fix:** compare the exact PR head/context and provider logs. Keep remote CI
  as final verification, not as the first filtering layer.
