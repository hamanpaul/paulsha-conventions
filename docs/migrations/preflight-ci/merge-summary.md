# preflight-ci ownership migration summary

## Sources

- Existing agent-facing skill and shell orchestration in
  `hamanpaul/custom-skills`.
- Canonical `policy_check.preflight` engine introduced by issue 46.
- A source working-tree compatibility change for `PSC_PREFLIGHT_PYTHON` that
  was present but not committed when migration started.

## Selected strategy

This is a governed authority migration:

1. `paulsha-conventions/skills/preflight-ci` becomes the only canonical skill.
2. Its wrapper delegates to the adjacent source engine with
   `--engine-source`; it owns no resolver/gate implementation.
3. Target repositories own validation/test argv in `.paul-project.yml`.
4. The user-level `~/.agents/skills/preflight-ci` symlink is switched only
   after tests and a real skill smoke pass.
5. The old source skill is removed in a separate dependent PR after the new
   authority is usable.

The source working-tree Python override is preserved as
`PSC_PREFLIGHT_PYTHON` for starting the engine. Test interpreter selection is
now explicit in each repo-owned step.

## Validation

- Unit tests cover source-engine precedence, version skew, delegation, and
  safe symlink migration.
- A real installed-symlink smoke must run the canonical skill against this
  repository.
- Full pytest, policy, OpenSpec, wheel, and adversarial review remain required
  before updating PR 47.

## Rollback

Before the old source PR merges, repoint the user-level symlink to the former
checkout. After removal merges, revert that source PR and repoint the symlink.
No target repository data or cache must be deleted.
