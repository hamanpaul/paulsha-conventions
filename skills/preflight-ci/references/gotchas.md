# Preflight CI gotchas

## Missing repo-owned gates

- **Symptom:** skill-driven full preflight exits 2 before running gates.
- **Why:** the target repo does not declare `.paul-project.yml.preflight.steps`.
- **Fix:** declare typed validation/test commands. Use `--policy-only` only
  when policy-only execution is intentional.

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
  not match the target repo's `.paul-project.yml.policy_version`.
- **Fix:** update the deployed conventions checkout and target policy version
  through the normal release/rollout process. Never fall back silently.

## Remote CI disagrees with local preflight

- **Symptom:** local preflight passes but a remote provider fails.
- **Why:** provider setup, stale event metadata, billing, or a target config
  drift can still differ from local execution.
- **Fix:** compare the exact PR head/context and provider logs. Keep remote CI
  as final verification, not as the first filtering layer.
