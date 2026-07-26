# preflight-ci skill ownership proposal

## Why

Issue 46 requires the agent-facing `preflight-ci` skill itself to be deployed
from `paulsha-conventions`. Keeping it canonical in another repository leaves
two ownership boundaries and still treats GitHub Actions configuration as the
main engine resolver.

## What Changes

- Add `skills/preflight-ci` as the canonical agent skill.
- Add a safe user-level symlink installer.
- Let the skill supply its adjacent verified source engine to
  `policy-preflight`.
- Require explicit repo-owned gates for a full skill run.
- Remove the former skill authority through a separate source-repo PR after
  cutover validation.
