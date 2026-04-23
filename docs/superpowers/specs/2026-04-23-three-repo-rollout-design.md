# Three-repo rollout design

- **Date**: 2026-04-23
- **Status**: Draft for review
- **Decision**: Use a three-repo model, but roll it out in two phases: design both missing repos now, create `hamanpaul/.github` first, then create `hamanpaul/new-project-template`.

## Context

`hamanpaul/paulsha-conventions` already exists and works as the policy engine:

- it owns the `policy_check` CLI
- it contains the reusable workflow and composite action
- it self-validates the policy with R-01 ~ R-16

What is still missing is the rest of the planned ecosystem:

1. `hamanpaul/.github`
2. `hamanpaul/new-project-template`

Without those two repos, the current system can be piloted, but it cannot yet provide account-level defaults or one-command bootstrap for new projects.

## Goals

- Separate long-lived policy logic from GitHub defaults and bootstrap scaffolding
- Reduce duplication and drift between repos
- Make new repo creation faster without freezing unstable conventions too early
- Allow gradual adoption by existing repos before full standardization

## Non-goals

- Do not move rule logic out of `paulsha-conventions`
- Do not make `.github` or the template repo another source of truth for policy
- Do not assume `v1.0.0`; the rollout should work during pilot / draft adoption

## Approaches considered

### Approach A: create `.github` first

Create the account defaults repo first, then create the template repo later.

**Pros**
- stabilizes PR template and community defaults early
- helps existing repos immediately

**Cons**
- new repos still need manual bootstrap
- template design is deferred

### Approach B: create `new-project-template` first

Create the new-project skeleton first, then add `.github` later.

**Pros**
- fastest path for spinning up a new compliant repo
- useful if new repo creation is the urgent pain point

**Cons**
- risks baking unstable conventions into copied files
- duplicates repo defaults before the account-level version is defined

### Approach C: design both now, implement `.github` first, then template

Define the boundaries of all three repos first, then create `.github` as the thinner integration layer, and only after that create the template repo.

**Pros**
- keeps boundaries clear
- avoids freezing unstable defaults into template copies
- lets the template inherit the already-decided account defaults

**Cons**
- needs a bit more up-front design discipline

## Recommendation

Choose **Approach C**.

The policy engine already exists. The next most important step is not more policy logic; it is clarifying what belongs in the central engine, what belongs in account-wide defaults, and what belongs in copied bootstrap files. Once those boundaries are stable, the template becomes much less likely to drift.

## Proposed repository boundaries

| Repo | Primary role | What it should contain | What it should not contain |
| --- | --- | --- | --- |
| `hamanpaul/paulsha-conventions` | Source of truth for policy logic | `policy_check` CLI, rule implementations, reusable workflow, composite action, helper scripts, self-dogfood tests and docs | account defaults, project-specific bootstrap copies |
| `hamanpaul/.github` | Account-wide GitHub defaults | default `pull_request_template.md`, issue templates if needed, `CONTRIBUTING.md`, `SECURITY.md`, and other community health files supported by a public account-level `.github` repo | rule logic, duplicated validation code, project bootstrap skeleton, workflow distribution responsibilities that are better handled by the project template |
| `hamanpaul/new-project-template` | New-project bootstrap skeleton | starter `.paul-project.yml`, `README.md`, `CHANGELOG.md`, `VERSION`, four agent convention files, starter workflow referencing `paulsha-conventions` | copied policy engine logic, account-level governance that belongs in `.github` |

## Architecture and change flow

The change flow should be one-directional:

1. **Policy logic changes happen in `paulsha-conventions`**
2. the template repo consumes that logic by referencing a pinned release or commit SHA
3. New repos are created from the template, then inherit account defaults from `.github`

This means:

- `paulsha-conventions` is the only place where rule behavior is implemented
- `.github` is a distribution layer for account-level community health defaults
- `new-project-template` is a bootstrap convenience layer, not a policy engine

## Rollout design

### Phase 0: freeze a consumable reference

Before broad adoption, choose one of these as the stable input for downstream repos:

- a pinned commit SHA from `paulsha-conventions`
- or, once ready, a pilot release tag such as `v0.0.1`

During pilot, **pinned commit SHA is acceptable**. Do not use branch refs such as `@main`.

### Phase 1: create `hamanpaul/.github`

Create the repo with a minimal scope:

- default `pull_request_template.md` aligned with policy expectations
- `CONTRIBUTING.md` explaining branch and PR flow
- `SECURITY.md`
- optional issue templates only if there is already a clear usage pattern

This repo should be intentionally thin. If a file needs to explain or enforce rule behavior, it should point back to `paulsha-conventions`, not re-implement it.

Because `hamanpaul` currently behaves like a personal account rather than an organization, do **not** rely on account-level workflow templates as a primary adoption path. Keep workflow wiring in the project template instead.

### Phase 2: create `hamanpaul/new-project-template`

Create the template only after `.github` scope is settled. The template should include:

- `.paul-project.yml`
- `README.md`
- `CHANGELOG.md`
- `VERSION`
- `CLAUDE.md`
- `AGENTS.md`
- `GEMINI.md`
- `.github/copilot-instructions.md`
- `.github/workflows/policy-check.yml`

The template should stay minimal. Its job is to give a new repo the correct starting shape, not to embed every future convention forever.

## Error handling and drift control

The main risk in this three-repo model is **drift**.

To control it:

- never duplicate rule logic outside `paulsha-conventions`
- keep `.github` limited to community defaults
- keep `new-project-template` limited to bootstrap content
- whenever `paulsha-conventions` changes downstream-facing behavior, update the pinned reference in `.github` and the template repo in the same rollout batch
- validate downstream changes using a pilot repo before broad rollout

## Validation strategy

The rollout should be considered healthy only if all three checks pass:

1. `paulsha-conventions` still passes self-dogfood checks
2. a pilot repo under the same account can pick up `.github` defaults and pass policy check
3. a throwaway new repo created from `new-project-template` can run the policy workflow successfully with no manual fixes beyond filling project-specific metadata

## Success criteria

The three-repo design is working when:

- pilot repos under the same account can adopt the policy with minimal manual steps
- new repos can start from the template and pass the policy gate quickly
- updates to policy logic still have exactly one source of truth
- repository enforcement can move from tribal knowledge to branch protection and required checks

## Immediate next step

Create `hamanpaul/.github` first, with only the smallest useful default set, and keep `hamanpaul/new-project-template` for the next phase after the account defaults are proven in one pilot repo.
