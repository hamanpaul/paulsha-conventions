## ADDED Requirements

### Requirement: Account-level community defaults repository
The system SHALL provide a public `hamanpaul/.github` repository that acts as the account-level source for supported GitHub community health defaults.

#### Scenario: Repository contains the required default files
- **WHEN** a maintainer opens `hamanpaul/.github`
- **THEN** the repository includes a default pull request template, `CONTRIBUTING.md`, and `SECURITY.md`

#### Scenario: Repository stays policy-aligned
- **WHEN** `python3 -m policy_check --repo /path/to/.github` is run against the repository
- **THEN** the repository passes the current policy checks without failures

### Requirement: Downstream repositories inherit account defaults
Repositories under the `hamanpaul` account that do not define their own local community health files MUST inherit the supported defaults from `hamanpaul/.github`.

#### Scenario: Contributing and security guidance resolve through GitHub community profile
- **WHEN** a maintainer queries the community profile for a downstream smoke-test repository that does not contain local `CONTRIBUTING.md` or `SECURITY.md`
- **THEN** GitHub reports contributing and security files as available through the account defaults

#### Scenario: Pull request creation uses the default template
- **WHEN** a maintainer opens a pull request in a downstream repository that does not contain its own pull request template
- **THEN** the pull request form is prefilled from `hamanpaul/.github/.github/pull_request_template.md`
