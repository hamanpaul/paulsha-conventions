## 1. Account defaults repository

- [x] 1.1 Create the public `hamanpaul/.github` repository and open a feature branch for the bootstrap work
- [x] 1.2 Add the policy skeleton files required for the repo itself (`.paul-project.yml`, `README.md`, `CHANGELOG.md`, `VERSION`, and synchronized agent convention files)
- [x] 1.3 Add the account-level default community health files (`.github/pull_request_template.md`, `CONTRIBUTING.md`, and `SECURITY.md`)
- [x] 1.4 Run `python3 -m policy_check --repo .` in the `.github` repository and merge the bootstrap PR after it passes

## 2. New project template repository

- [x] 2.1 Create the public `hamanpaul/new-project-template` repository and open a feature branch for the bootstrap work
- [x] 2.2 Add the template skeleton files (`.paul-project.yml`, `README.md`, `CHANGELOG.md`, `VERSION`, agent convention files, and `.github/workflows/policy-check.yml`)
- [x] 2.3 Point the template workflow at `hamanpaul/paulsha-conventions` by full commit SHA and mark the repository as a GitHub template
- [x] 2.4 Run `python3 -m policy_check --repo .` in the template repository and merge the bootstrap PR after it passes

## 3. End-to-end rollout validation

- [x] 3.1 Generate a temporary smoke-test repository from `hamanpaul/new-project-template`
- [x] 3.2 Fill only the smoke-test repository metadata needed for validation and confirm local `policy_check` passes
- [x] 3.3 Confirm the smoke-test repository picks up the account-level defaults and that the `Policy Check` workflow succeeds on a pull request
- [ ] 3.4 Delete the smoke-test repository after validation (remote cleanup remains blocked because the current `gh` token lacks `delete_repo` scope)
- [x] 3.5 Update `paulsha-conventions` documentation to link to the live rollout repositories
