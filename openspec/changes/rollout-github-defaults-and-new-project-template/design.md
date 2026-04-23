## Context

`hamanpaul/paulsha-conventions` already contains the policy engine, reusable workflow, and self-dogfood tests, but the surrounding adoption path is incomplete. The remaining gap is operational rather than algorithmic: repositories under the `hamanpaul` account do not yet have a central source of community health defaults, and there is no template repository that creates a new project with the required policy skeleton and workflow wiring already in place.

The owner currently behaves like a personal GitHub account rather than an organization. That matters because public account-level `.github` repositories can provide default community health files, while workflow template discoverability is oriented around organization flows. The design therefore needs to keep `.github` narrow and place workflow wiring inside the new project template instead.

## Goals / Non-Goals

**Goals:**
- Create a public `hamanpaul/.github` repository that provides account-level defaults for pull request templates and contributor/security guidance.
- Create a public `hamanpaul/new-project-template` repository that can be used with `gh repo create --template`.
- Keep `hamanpaul/paulsha-conventions` as the only source of truth for policy logic and reusable workflow behavior.
- Validate the rollout through a smoke-test repository before treating the setup as ready for wider adoption.

**Non-Goals:**
- Do not move rule logic, helper scripts, or test logic out of `hamanpaul/paulsha-conventions`.
- Do not rely on `.github/workflow-templates` as the primary delivery path for the policy workflow.
- Do not treat this rollout as a `v1.0.0` stabilization milestone; it remains compatible with pilot adoption and pinned-commit consumption.

## Decisions

### 1. Split responsibilities across three repositories

`hamanpaul/paulsha-conventions` remains the policy engine, `hamanpaul/.github` becomes the account-level defaults repository, and `hamanpaul/new-project-template` becomes the bootstrap repository.

**Why:** This keeps policy logic centralized while preventing copied template files from becoming a second source of truth.

**Alternative considered:** Keep everything inside `paulsha-conventions` and document manual copy steps. Rejected because it would not provide a reusable bootstrap path or GitHub-native defaults.

### 2. Keep `.github` limited to community health defaults

The `.github` repo will contain the default PR template, `CONTRIBUTING.md`, `SECURITY.md`, and any future community health files that GitHub supports at the account level.

**Why:** GitHub officially supports account-level community health defaults for personal accounts, but workflow templates are not the main delivery path here. Narrow scope reduces drift and prevents the `.github` repo from becoming a shadow policy implementation.

**Alternative considered:** Put workflow distribution in `.github`. Rejected because it adds ambiguity for a personal-account rollout and duplicates responsibility with the template repo.

### 3. Keep the policy workflow pinned inside `new-project-template`

The template repo will include `.github/workflows/policy-check.yml` that:
- References `hamanpaul/paulsha-conventions/.github/workflows/reusable-policy-check.yml` by full commit SHA
- Passes an explicit `policy_engine_ref` input (tag or pinned SHA) pointing at `hamanpaul/paulsha-conventions`

The `policy_engine_ref` input is required by the reusable workflow to specify which version of the policy engine to checkout. In cross-repo workflows, `github.workflow_sha` refers to the caller's repository, not to paulsha-conventions, so an explicit ref prevents silent version drift.

**Why:** Dual pinning (workflow ref + policy_engine_ref) ensures both the reusable workflow logic and the policy engine implementation stay locked to the same version, satisfying the existing policy rules and making template-generated repositories deterministic during pilot adoption.

**Alternative considered:** Reference `@main` or a floating tag, or pass `github.workflow_sha` to the policy engine checkout. Rejected because the current rules explicitly disallow branch refs, and `github.workflow_sha` in a cross-repo workflow context points to the caller's repository, not to paulsha-conventions.

### 4. Validate with a smoke-test repository before broader rollout

After both new repositories exist, create a throwaway repository from `new-project-template`, confirm account defaults are visible, and verify the `Policy Check` workflow succeeds.

**Why:** The smoke repo proves that the three-repo flow works end to end instead of validating each piece in isolation.

**Alternative considered:** Trust repository contents without an integration check. Rejected because the risk here is cross-repo drift and broken consumption paths.

## Risks / Trade-offs

- **Pinned commit drift** → The template may lag behind `paulsha-conventions` updates. Mitigation: batch any downstream-facing policy change with a template reference update and smoke validation.
- **Scope creep in `.github`** → Community defaults repo could start carrying workflow or policy logic. Mitigation: keep its charter explicit and reject files that duplicate logic from `paulsha-conventions`.
- **Template fossilization** → `new-project-template` could preserve outdated scaffolding. Mitigation: keep the template minimal and update it only when rollout validation passes.
- **Personal-account platform limits** → Some GitHub defaults behavior is less discoverable than org-native workflows. Mitigation: put critical automation inside the template repo, not inside account-level workflow templates.

## Migration Plan

1. Finish the local rename from `paul-project-template` to `new-project-template` in the planning and README documents.
2. Create and merge `hamanpaul/.github` with only the approved community health files.
3. Create and merge `hamanpaul/new-project-template` with the pinned `Policy Check` workflow and required skeleton files.
4. Generate a smoke-test repository from the template and verify account defaults plus workflow success.
5. Once the smoke test passes, update `paulsha-conventions` documentation to link to the live repositories instead of planned names.

Rollback is simple: remove the new repositories from documentation and stop recommending the rollout path. No migration of persistent application data is involved.

## Open Questions

- Which first real downstream repository should replace the smoke-test repository after the rollout is proven?
- When should the pinned commit SHA in `new-project-template` be replaced with a pilot tag such as `v0.0.1`?
