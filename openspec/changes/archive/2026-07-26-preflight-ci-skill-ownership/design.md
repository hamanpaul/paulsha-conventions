# preflight-ci skill ownership design

## Authority

The skill and engine share one repository and release authority. The wrapper
does not parse Actions YAML, clone an engine, or execute tests itself.

## Source engine

`--engine-source` accepts only a clean checkout whose origin is
`hamanpaul/paulsha-conventions`, whose `VERSION` matches the target
`policy_version`, and whose HEAD is a full SHA. This explicit source takes
precedence over legacy workflow/pip resolution.

## Deployment

The installer creates `~/.agents/skills/preflight-ci` as a symlink. Migration
of an existing different symlink requires `--replace`; non-symlink targets are
never removed.

## Repository gates

A full skill run fails configuration validation when `preflight.steps` is
absent. This prevents policy-only execution from being mislabeled as a full
preflight. Explicit `--policy-only` remains available.
