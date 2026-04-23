## ADDED Requirements

### Requirement: New project template repository
The system SHALL provide a public `hamanpaul/new-project-template` repository that can be used as the standard bootstrap source for new repositories.

#### Scenario: Template contains required policy skeleton files
- **WHEN** a maintainer inspects `hamanpaul/new-project-template`
- **THEN** the repository includes `.paul-project.yml`, `README.md`, `CHANGELOG.md`, `VERSION`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`, and `.github/workflows/policy-check.yml`

#### Scenario: Template repository is marked as a GitHub template
- **WHEN** a maintainer checks the repository settings for `hamanpaul/new-project-template`
- **THEN** the repository is marked as a template repository

### Requirement: Template wires new repositories to the policy engine
The template MUST connect generated repositories to `hamanpaul/paulsha-conventions` by a pinned reusable workflow reference.

#### Scenario: Template workflow uses a pinned reusable workflow reference with explicit policy engine ref
- **WHEN** a maintainer opens `.github/workflows/policy-check.yml` in `hamanpaul/new-project-template`
- **THEN** the workflow BOTH:
  - References `hamanpaul/paulsha-conventions/.github/workflows/reusable-policy-check.yml` by full commit SHA, AND
  - Passes an explicit `policy_engine_ref` input pointing at the same version (full 40-character commit SHA) of `hamanpaul/paulsha-conventions`

#### Scenario: Generated repository passes local policy validation
- **WHEN** a maintainer creates a smoke-test repository from `hamanpaul/new-project-template` and fills only project-specific metadata
- **THEN** `python3 -m policy_check --repo .` passes in the generated repository

### Requirement: Generated repositories validate the rollout end to end
The rollout MUST be proven with a generated smoke-test repository before the template is treated as ready for wider adoption.

#### Scenario: Smoke-test workflow succeeds
- **WHEN** a maintainer opens a pull request from the smoke-test repository
- **THEN** the `Policy Check` workflow completes successfully

#### Scenario: Smoke-test repository can be discarded after verification
- **WHEN** the smoke-test repository has proven account defaults and workflow success
- **THEN** the repository can be deleted without affecting the policy engine or the two rollout repositories
