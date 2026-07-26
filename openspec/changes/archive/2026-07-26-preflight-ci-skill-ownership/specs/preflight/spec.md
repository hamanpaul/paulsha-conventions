## ADDED Requirements

### Requirement: preflight-ci skill authority belongs to paulsha-conventions
The repository MUST contain and deploy the canonical `preflight-ci` agent
skill. The skill wrapper MUST delegate to the adjacent
`policy_check.preflight` implementation and MUST NOT parse a GitHub Actions
workflow, clone/fetch an engine, or duplicate policy/OpenSpec/test
orchestration.

#### Scenario: installed skill resolves one canonical authority
- **WHEN** the user installs `preflight-ci` from a conventions checkout
- **THEN** `~/.agents/skills/preflight-ci` resolves to this repository's skill
  directory and no copy from another skill store is required

#### Scenario: skill execution does not require Actions resolution
- **WHEN** the skill runs against a target repository
- **THEN** it supplies its adjacent verified source engine directly, without
  reading or executing `.github/workflows/policy-check.yml`

### Requirement: skill source engine must fail closed
The source checkout supplied by the skill MUST have the canonical repository
origin, a clean worktree, a full HEAD SHA, and a `VERSION` matching the target
repo's `policy_version`. Any mismatch MUST fail the engine gate without
falling back to a workflow/default branch/other installed version.

#### Scenario: source version skew
- **WHEN** the deployed skill checkout VERSION differs from target policy_version
- **THEN** preflight exits nonzero before running policy or repo-owned steps

### Requirement: full skill mode requires repo-owned gates
When invoked through the canonical skill, full preflight MUST require an
explicit `.paul-project.yml.preflight` declaration. Absence MUST return exit 2
unless the caller explicitly requests `--policy-only`.

#### Scenario: missing target gate declaration
- **WHEN** a target repo has no `preflight` block and the skill runs without
  `--policy-only`
- **THEN** preflight rejects the incomplete local gate instead of printing
  `PREFLIGHT PASS`
