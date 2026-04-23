## Why

`hamanpaul/paulsha-conventions` already provides the policy engine, but the planned three-repo rollout is incomplete because the account-level `.github` defaults repo and the project bootstrap template repo do not exist yet. Finishing those two repos now turns the current policy from a pilot-only engine into a repeatable adoption flow for both new repositories and downstream contributors.

## What Changes

- Create `hamanpaul/.github` as the public account-level defaults repo for community health files such as the default pull request template, `CONTRIBUTING.md`, and `SECURITY.md`.
- Create `hamanpaul/new-project-template` as the starter repository for new projects, including `.paul-project.yml`, `README.md`, `CHANGELOG.md`, `VERSION`, agent convention files, and a pinned `Policy Check` workflow.
- Define the rollout validation flow with a smoke-test repository so the account defaults and template behavior are verified together before broader adoption.
- Update the local planning documents so the rollout uses `new-project-template` consistently and no longer refers to the retired `paul-project-template` name.

## Capabilities

### New Capabilities
- `account-defaults`: Provide account-level community health defaults through a public `.github` repository for repositories owned by `hamanpaul`.
- `new-project-bootstrap`: Provide a reusable new-project template repository that consumes `paulsha-conventions` through a pinned workflow reference and includes the required policy skeleton files.

### Modified Capabilities
- None.

## Impact

- New GitHub repositories: `hamanpaul/.github` and `hamanpaul/new-project-template`
- New default contributor experience for repositories under the `hamanpaul` account
- New bootstrap path for future repositories created from the template
- Existing local design and rollout documents in `docs/superpowers/specs/` and `docs/superpowers/plans/`
