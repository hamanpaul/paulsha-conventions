> **Fact:** `paulsha-conventions` 是 repo policy 與 change-integrity rule 的唯一 authority，負責跨 repo 文件、版號、分支、PR、generated facts 與 policy drift 的 deterministic enforcement。

# paulsha-conventions

> **[English](#english)** ｜ **[繁體中文](#繁體中文)**

> `hamanpaul/*` cross-repo policy gatekeeper — keeps docs, versions, branches, and PRs consistent, and prevents convention drift.
> `hamanpaul/*` 跨專案 policy 守門員 — 讓文件、版號、分支、PR 保持一致，防止規範漂移。

![paulsha-conventions — 20-second demo](docs/media/brag-en.gif)

> ▶ Full video with sound — [English](docs/media/brag-en.mp4) ｜ [繁體中文](docs/media/brag.mp4)

---

## Install

This README is the canonical install reference. Editable local install:

```bash
python3 -m pip install -e ".[test]"
```

For offline / air-gapped (vendored wheels) installs and CI integration, see [English → Install](#install-1) / [繁體中文 → 安裝](#安裝).

## Usage

Run the full rule set against the current repo:

```bash
python3 -m policy_check --repo .
```

Scope to specific rules with `--only R-01,R-09`. For CI (GitHub reusable workflow, GitLab merge-request pip gate), the helper scripts, and new-project bootstrap, see [English → Usage](#usage-1) / [繁體中文 → 使用](#使用).

## Version

The canonical project version lives in `VERSION`; release tags use `vX.Y.Z`. Version semantics (`profile: flat`) are described under [English → Versioning](#versioning) / [繁體中文 → 版本](#版本). Current version:

<!-- BEGIN: generated-fact marker="repo-version" -->
1.0.16
<!-- END: generated-fact marker="repo-version" -->

---

## English

A cross-repo **policy engine** covering every `hamanpaul/*` repository:

- **New repo bootstrap** — auto-seed a compliant skeleton (via `new-project-template`).
- **CI gate** — block non-compliant changes before they merge.
- **Agent checklist** — surface the conventions to an agent when it enters a session.
- **Forced synchronization** — code must move together with docs / CHANGELOG / VERSION.

This repository **dog-foods its own policy** (`profile: flat`; `policy_version` in `.project-policy.yml` / `VERSION`). The version lineage (policy_version ↔ engine tag/SHA) lives in [`RELEASES.md`](./RELEASES.md).

### What problem does it solve?

- "Changed code but forgot to update the CHANGELOG."
- "A CLI flag changed but the README was not updated."
- "Branch naming is inconsistent and version semantics drift."
- "The policy says comply — but the policy repo itself does not."

### Rules (R-01 ~ R-26)

| ID | Check | Fail condition | Exempt label |
|----|-------|----------------|--------------|
| R-01 | `README.md` exists | missing, or < 100 bytes | — |
| R-02 | `README.md` required sections | missing `## Install` / `## Usage` / `## Version` | `policy-exempt:readme-sections` |
| R-03 | `CHANGELOG.md` exists | missing | — |
| R-04 | `CHANGELOG.md` format | missing the `# Changelog` header (the fragment model no longer requires `[Unreleased]`) | `policy-exempt:changelog-format` |
| R-05 | `VERSION` exists | missing | — |
| R-06 | `VERSION` is semantic | does not match `<MAJOR>.<MINOR>.<PATCH>(-fix\.\d+)?` | — |
| R-07 | `VERSION` matches latest tag | mismatch without a `release:*` label | — |
| R-08 | `.project-policy.yml` exists & complete | missing, or missing `policy_profile` / `policy_version` | — |
| R-09 | code change ⇒ changelog fragment | code paths changed but this PR added no `changelog.d/*.md` fragment | `skip-changelog` |
| R-10 | PR title is conventional-commit | regex mismatch | `policy-exempt:pr-title` |
| R-11 | PR body checkboxes all ticked | a required box is unticked | auto-passes under `wip` |
| R-12 | branch source is correct | target = main but source ≠ `feature/*`; target = `feature/*` but source ≠ `wt/<feature>/*` | `policy-exempt:branch-name` |
| R-13 | agent convention files exist | missing `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md` | `policy-exempt:agent-files` |
| R-14 | agent-files single-source integrity (config-gated) | `copy` (default): the four files' `policy_version` disagrees with `.project-policy.yml`; `symlink`: a mirror file is not a symlink / does not resolve to `CLAUDE.md` / the canonical file is itself a symlink | — |
| R-15 | caller workflow pins by tag / SHA (this repo's policy-check dual-pinning path additionally requires a full 40-char SHA) | `uses:` points at a branch ref (`@main`, `@develop`) or has no ref | — |
| R-16 | CLI help in sync with docs | commands declared in `.project-policy.yml.cli` produce help output that differs from the marker block | `policy-exempt:cli-help` |
| R-17 | PR ↔ issue link | PR body contains `#N` but not in closing-keyword form (`Closes` / `Fixes` / `Resolves #N`) | `policy-exempt:issue-link` |
| R-18 | docs / README track code changes | code_paths changed but `README.md` / `docs/**` was not updated (**WARN**, does not block merge) | `policy-exempt:docs-sync` |
| R-19 | repo has tests ⇒ CI runs them | parsed `jobs.*.steps[].run` has no actual test command; comments/install lines do not count, conditional hits WARN, malformed YAML falls back with WARN, and `r19.strict: true` promotes these warnings to FAIL | `policy-exempt:ci-tests` |
| R-20 | workflow policy_version in sync | the literal `policy_version` / `POLICY_VERSION` declared in a workflow disagrees with `.project-policy.yml` | — |
| R-21 | visibility-aware secret scan | all tiers are scanned; `shareable` hits **FAIL**; for other tiers, public/unknown structural or credential hits **FAIL**, while marker-only and private/internal hits **WARN**; reports expose only relative `path:line`, detector class, and counts | `policy-exempt:secret-scan` |
| R-22 | docs have no dangling code references | a path / internal link / backtick symbol referenced inside the canonical doc scope (`doc_paths`) does not exist; symbols use a language-agnostic scoped identity (ctags `(language, kind, scope, name)` diff); newly introduced breakage **FAIL**, pre-existing dangling **WARN** | `policy-exempt:doc-reference` |
| R-23 | engine pin matches policy_version | a workflow `uses:` pointing at `conventions_engine.repo` pins an engine version (tag `@vX.Y.Z`, or SHA `@<sha>` + trailing `# vX.Y.Z`) that disagrees with `.project-policy.yml`'s `policy_version` | `policy-exempt:engine-pin` |
| R-24 | MOC aligned with this change | when a repo declares `moc`: `moc.static` out of sync (**WARN**) / `moc.map` has a dangling link (new breakage **FAIL**, pre-existing **WARN**) / an active openspec change・plan・spec is unlinked (**WARN**) | `policy-exempt:moc-alignment` |
| R-25 | doc coverage (omission gate, opt-in) | when a repo declares `doc_coverage`: a public fact extracted from the sources is not exactly mentioned in any target doc | — |
| R-26 | generated-fact marker sync (opt-in) | when a repo declares `generated_facts`: the marker block content disagrees with the command's normalized stdout, the marker is missing, the command exits non-zero, or the config is incomplete | — |

**Exemption label allowlist**: the `policy-exempt:*` / `skip-changelog` / `wip` labels listed above are the complete set of usable exemption labels; the gate honors only these — anything else counts as un-exempted.

### Doc-alignment governance (three tiers)

Doc staleness is governed in three tiers; only Tier 2 is a deterministic gate:

- **Tier 1 (prevention)** — when an agent changes code, it also updates the docs that reference that artifact (see the four agent convention-file checklists).
- **Tier 2 (deterministic gate)** — R-22 detects structural dangling references in `README.md` / `docs/**` in CI: newly introduced breakage FAILs, pre-existing dangling WARNs. The deterministic tier only looks at structural rot (a reference died); it does not judge semantics.
- **Tier 3 (semantic review)** — set GitHub Copilot as a PR reviewer to review semantic staleness ("the reference still resolves but the description is out of date") — advisory, does not block merge.

#### Standalone doc-drift Action (OSS-ready, #25)

The doc↔code drift core of R-22 / R-24 is factored into a language-agnostic, zero-config shared kernel (`policy_check/doc_drift/`, organized by refs / paths / symbols / coverage / langs / provision primitives) and packaged as a standalone composite action (`.github/actions/doc-drift/`, see its [README](.github/actions/doc-drift/README.md)) that any repo can `uses:`. It does not require the target repo to adopt `.project-policy.yml`; symbol extraction uses universal-ctags scoped identity `(language, kind, scope, name)` diff, supporting **Python / bash / C / C++**. The action offers `doc-drift` and `moc` modes and supplies its own base/head SHA (so it does not fail up front under shallow checkout); FAIL blocks merge with a non-zero exit, WARN is advisory.

> **Complementary to lychee**: this action only guards against dangling in-repo code-artifact references; external URL liveness / HTTP / anchors are delegated to [lychee](https://github.com/lycheeverse/lychee-action).

#### Cross-repo version propagation (mechanism layer, #23)

The deterministic three-tier doc-alignment is **intra-repo**; cross-repo `policy_version` drift is governed by a mechanism layer (the engine only enforces + detects + documents; it **does not** mutate downstream):

- **Enforce (block)** — the org ruleset's `Policy Freshness` required workflow runs `python3 -m policy_check.drift check`; a repo lagging behind canonical cannot merge its PR. See [`docs/org-ruleset-runbook.md`](docs/org-ruleset-runbook.md).
- **Detect (name)** — `python3 -m policy_check.drift report --org hamanpaul` read-only lists each repo's `policy_version` and drift state (`current` / `behind` / `ahead` / `unmanaged`).
- **Remediate (bump)** — a lagging repo self-bumps via its own agent following the "version propagation SOP" in [RELEASES.md](RELEASES.md).

> `policy_check.drift` is an ops tool, **not** an R-xx gate rule; it is not part of the FAIL set of `python3 -m policy_check --repo .`.

#### Document-rule config surfaces (`doc_paths` / `doc_coverage` / `generated_facts`)

`.project-policy.yml` exposes three document-governance surfaces, all backward compatible (unset ⇒ existing behavior preserved):

```yaml
# 1) canonical doc scope: shared by R-18 / R-22; defaults to README.md + docs/**
doc_paths:
  - "README.md"
  - "docs/**"
  - "CLAUDE.md"

# 2) doc_coverage (opt-in, R-25): catches "added X but never documented it" omission drift
doc_coverage:
  mode: "changed"          # changed (only newly added facts, default) | all
  targets: ["README.md"]   # canonical docs, must fall inside doc_paths
  sources:
    - kind: "modules"      # fact = repo-relative path
      include: ["pkg/**/*.py"]
      exclude: ["**/__init__.py"]
    - kind: "rpc_methods"  # fact = the single capture group of the pattern
      include: ["pkg/service.py"]
      pattern: 'method == "([^"]+)"'
    - kind: "env_vars"     # fact = PREFIX[A-Z0-9_]+ token
      include: ["pkg/**/*.py"]
      prefix: "APP_"
    - kind: "cli_tree"     # fact = one command path per stdout line
      command: "python3 scripts/list-cli-paths.py"

# 3) generated_facts (opt-in, R-26): generic marker-sync that generalizes R-16's cli-help pattern
generated_facts:
  - kind: "fact_list"
    command: "python3 scripts/render-rpc-facts.py"
    reflected_in: "README.md"
    marker: "rpc-methods"
```

- **Mention semantics**: R-25 uses case-sensitive exact token/phrase matching; a substring hit does not count as coverage.
- **`changed`-mode boundary**: when base diff context is missing (e.g. a local `--repo .`) it downgrades to WARN; `cli_tree` cannot snapshot the base, so it is only checked under `mode: all`.
- **Security note (command-executing rules)**: `R-16` (`cli`), R-25's `cli_tree` extractor and `R-26` (`generated_facts`) execute the commands declared in `.project-policy.yml` (no shell injection, but the command string itself is config-controlled and inherits the full environment). Therefore **do not** run `policy_check` on untrusted PR / fork branches; only enable it on trusted repo config.

R-19's staged rollout can be made strict per repository:

```yaml
r19:
  strict: true  # promote bypass-prone or conditional test-gate WARNs to FAIL
```

R-08 validates that `r19` is a mapping and `strict` is a boolean; omitted `r19` keeps the warning rollout default.

#### The `auto_build` block (LLM auto-build convention, #30)

`.project-policy.yml` may declare an optional `auto_build:` block carrying a per-project build flow, so an LLM auto-build agent can cold-read "how to build this project"; repos that do not build simply omit the whole block:

```yaml
auto_build:
  description: "router firmware image via docker build container"  # str: one-line build target
  setup:                       # list[str]: environment prep commands
    - "docker pull registry.example/fw-builder:latest"
  steps:                       # list[str]: build commands, run in order
    - "docker run --rm -v $PWD:/src fw-builder make -C /src image"
  artifacts:                   # list[str]: expected artifact globs
    - "out/*.img"
  verify:                      # list[str]: build-success verification commands
    - "test -s out/firmware.img"
```

- **R-08 only validates shape**: `auto_build` must be a mapping; `description` a str; `setup` / `steps` / `artifacts` / `verify` each a list[str]. **Unknown subkeys always pass** (per-project extension needs no engine release); there are no required subkeys, and an explicitly-null subkey is treated as unset.
- **The engine never executes it**: unlike command-executing config (`cli` / `cli_tree` / `generated_facts`), every command string under `auto_build` is pure data to the policy engine — no rule executes it. The consumer is the LLM agent reading the config; execution and its safety review are that agent's human-in-the-loop responsibility.

### CHANGELOG fragment model (parallel-safe)

To eliminate merge conflicts from parallel agents editing a shared `CHANGELOG.md [Unreleased]`, pending records use **one fragment file per PR** (the changesets / towncrier pattern, but agents write fragments and the gate validates them):

- **Each PR** adds `changelog.d/<issue>-<slug>.md` (without touching `CHANGELOG.md`):

  ```markdown
  ---
  type: feat        # required, conventional-commit type
  scope: changelog  # optional
  issue: 24         # optional
  ---
  One-line description (becomes a CHANGELOG bullet).
  ```

  Different issues naturally produce different files with zero shared lines ⇒ **parallel PRs never conflict**.
- **type → Keep-a-Changelog section** fixed mapping: `feat`→Added, `fix`→Fixed, `refactor`/`perf`/`change`→Changed, `remove`→Removed, `deprecate`→Deprecated, `security`→Security. Unknown type ⇒ collation fails. `docs`/`test`/`chore` go through `skip-changelog`.
- **Release convergence**: on a version bump, run

  ```bash
  python3 -m policy_check.changelog collate --version X.Y.Z --date YYYY-MM-DD
  ```

  which groups `changelog.d/*.md` by type into a `## [X.Y.Z] - <date>` section (Keep-a-Changelog format, R-04 still passes) and empties the directory.
- `R-09` now validates "did this PR add a fragment"; `R-04` no longer requires `[Unreleased]`. This is a behavior-bound hard cutover (downstream upgrades by pinning versions; unupgraded repos keep the old `[Unreleased]` behavior).

### Install

See the canonical [Install](#install) above for the editable install. For downstream CI that ships the engine as a wheel to a GitLab merge-request pipeline (offline / air-gapped runners), you **must** vendor the engine wheel together with its dependency closure; `pip install --no-index <wheel>` alone is not enough because the offline runner still needs `PyYAML` etc.

Build-time (networked) — build the wheel and dependency closure:

```bash
python3 -m pip wheel --no-deps --wheel-dir dist .
mkdir -p vendor
python3 -m pip download --dest vendor dist/policy_check-X.Y.Z-py3-none-any.whl
```

Gate-time — the **Python package install** can be offline, consuming only vendored files:

```bash
python3 -m pip install --no-index --find-links vendor policy-check==X.Y.Z
```

Keep the boundary clear: build-time / release needs network to build the wheel and fetch the full dependency closure; gate-time / MR-check installs `policy-check` and its vendored Python deps offline — but `universal-ctags` must still be pre-installed on the runner image or provided via an internal package mirror.

### Usage

#### 1. Local check (development)

```bash
python3 -m policy_check --repo .
# only specific rules:
python3 -m policy_check --repo . --only R-01,R-02,R-03
```

#### 2. Local/offline preflight

`policy-preflight` runs the policy gate and the repository-owned validation/test
steps declared in `.project-policy.yml`. Manual mode requires an explicit PR title
and body file so PR-only rules are evaluated with complete context:

`.project-policy.yml` is the public canonical name. The engine continues to
accept legacy-only `.paul-project.yml` with a deprecation warning. If both files <!-- doc-drift-ignore -->
exist, identical parsed YAML is allowed with a warning; any semantic difference
fails before policy execution.

The canonical agent-facing entrypoint is the `preflight-ci` skill owned by this
repository. Install or migrate the user-level skill symlink from a conventions
checkout:

```bash
scripts/install-preflight-skill.sh --replace
```

Then run it from the target repository:

```bash
~/.agents/skills/preflight-ci/scripts/preflight.sh \
  --pr-title "feat(preflight): add canonical local preflight" \
  --pr-body-file /path/to/pr-body.md \
  --base main \
  --head feature/local-preflight \
  --repo-visibility public
```

The skill supplies its adjacent `paulsha-conventions` checkout as the verified
source engine. It does not inspect or execute a GitHub Actions workflow, and it
does not clone/fetch an engine. The target repo's `policy_version` must match
the deployed conventions checkout. A full skill-driven run requires explicit
`.project-policy.yml.preflight.steps`; use `--policy-only` only when that reduced
scope is intentional.

```bash
policy-preflight \
  --repo . \
  --pr-title "feat(preflight): add canonical local preflight" \
  --pr-body-file /path/to/pr-body.md \
  --base main \
  --head feature/local-preflight \
  --repo-visibility public
```

When GitHub metadata is available, online mode can load it directly:

```bash
policy-preflight --repo . --pr 46
```

Offline mode disables network-capable **engine resolver** operations and accepts
only a matching installed distribution or a verified exact-SHA cache artifact.
PR metadata must be supplied manually. Repository-owned commands still execute
under the repository's authority and may have their own network behavior:

```bash
policy-preflight \
  --repo . \
  --offline \
  --pr-title "fix(policy): verify offline preflight" \
  --pr-body-file /path/to/pr-body.md \
  --base main \
  --head feature/offline-preflight \
  --repo-visibility private
```

Downstream repositories declare typed commands rather than shell strings:

```yaml
preflight:
  steps:
    - name: openspec
      kind: validation
      argv: ["openspec", "validate", "--all"]
      when_path_exists: "openspec"
      timeout_seconds: 300
    - name: tests
      kind: tests
      argv: ["python3", "-m", "pytest", "-q"]
      timeout_seconds: 1200
```

`--skip-tests` skips only `kind: tests`; if all other declared steps are
optional and unavailable, that explicit reduction is accepted. A run with only
conditional skips and no explicit test skip still fails. `--policy-only` skips
every repository-owned step while preserving engine resolution and the policy gate.
The effective head must match the current checkout branch, and `origin/<base>`
must exist with a valid merge base; otherwise preflight stops instead of
silently evaluating an empty changed-file set.
Configuration/input errors exit 2, a failed gate exits 1, and only complete
success exits 0.

#### 3. Versioned runtime bundle

`policy-runtime-bundle` builds one immutable release unit containing the
`policy-check` wheel, wheel-only dependency closure, `preflight-ci` skill,
stdlib installer manager plus its shared verifier, manifest, and `SHA256SUMS`. Production builds accept
only a clean canonical checkout at an annotated tag. The build host needs
Python 3.11+, `build`, and pip; dependency versions are constrained by the
bundle-owned lock input, and every resolved dependency wheel (including
transitive dependencies) must match one exact constraint:

```bash
policy-runtime-bundle build \
  --repo . \
  --tag vX.Y.Z \
  --output-dir /path/outside/the/repo
```

Verify the external archive digest and member safety, then install without a
source checkout:

```bash
policy-runtime-bundle extract \
  --archive /path/paulsha-conventions-vX.Y.Z.tar.gz \
  --sha256 <published-archive-sha256> \
  --output-dir /safe/staging
/safe/staging/paulsha-conventions-vX.Y.Z/install.sh
```

The stable deployed skill launcher reads the target repository's exact
`policy_version`, verifies the matching installed release, and invokes that
release's isolated venv with Python isolated mode. A missing version is a hard
failure; it never
falls back to `current`, a workflow checkout, another installed version, or the
network. Because dependency wheels can be ABI/platform specific, installation
also requires the exact Python major/minor, implementation, ABI, and platform
recorded by the builder. Upgrade activation happens only after offline install
and full preflight smoke. The install host must also provide `venv/ensurepip`
(commonly the `python3-venv` package), `git`, GNU `sha256sum`, and
`universal-ctags` with JSON output. All bootstrap/selector paths ignore ambient
`PYTHONPATH`/`PYTHONHOME`; installed attestation verifies every wheel
distribution and RECORD payload before the selected venv imports third-party
code, rejects startup customization/module shadows, and removes bootstrap-only
pip/setuptools after installation. Stable launchers also anchor the active
manifest digest and verify the current manager before executing it. The deployed
stable lifecycle wrapper repairs
links or switches to an already verified release:

```bash
~/.local/share/paulsha-conventions/bin/policy-runtime-bundle \
  activate --version X.Y.Z
~/.local/share/paulsha-conventions/bin/policy-runtime-bundle \
  rollback --version X.Y.Z
```

An existing unmanaged `preflight-ci` directory or source-checkout symlink must
first be moved to a reversible backup; the installer never adopts it. An active
release that fails tamper verification can be reconstructed from the same
externally verified artifact with `install --force-reinstall`; the
replacement is staged and smoked before the state-owned release is exchanged.

Pushing an annotated tag in the policy version format (`vX.Y.Z` or
`vX.Y.Z-fix.N`) triggers `.github/workflows/release.yml`, which builds one
bundle per supported Python minor version, verifies each archive digest,
smoke-installs it into an isolated HOME, and only then publishes a GitHub
Release carrying the archives, their `.sha256` files, and release notes composed
from that version's `CHANGELOG.md` section. Any failed check stops the release.
Because the dependency closure contains ABI-specific wheels, archives for the
same tag differ per Python minor version by design; reproducibility holds for a
given tag *and* interpreter version, not across versions.

See [the runtime bundle runbook](docs/runtime-bundle-runbook.md) for layout,
state, rollback, tamper diagnosis, the automated release flow, and the
publication boundary owned by #39.

#### 4. CI integration (downstream repos)

**GitHub reusable workflow** — call this repo's reusable workflow from `.github/workflows/policy-check.yml`:

```yaml
name: Policy Check
on: [pull_request]

jobs:
  policy:
    # Pin BOTH the reusable workflow and the policy engine to the SAME full 40-char commit SHA.
    # Do NOT use a tag or branch ref — a full SHA is required by the engine validation step.
    uses: hamanpaul/paulsha-conventions/.github/workflows/reusable-policy-check.yml@aabbccddeeff0011223344556677889900aabbcc
    with:
      policy_profile: stage-driven  # or flat
      policy_version: X.Y.Z        # example; use the version your pinned SHA corresponds to
      policy_engine_ref: aabbccddeeff0011223344556677889900aabbcc
```

**GitLab merge_request gate (pip mode)** — the downstream `.project-policy.yml` declares pip mode so R-23 validates the "installed package version" against `policy_version` in lockstep; the GitLab merge-request pipeline loads MR context from `CI_MERGE_REQUEST_*`, and R-12 is marked NA on the GitLab path:

```yaml
# .project-policy.yml
policy_profile: flat
policy_version: X.Y.Z
conventions_engine:
  mode: pip
```

#### 4. Helper scripts

`scripts/update-cli-help.sh` — actually runs each command declared in `.project-policy.yml.cli` and rewrites the marker blocks in the docs (the R-16 sync mechanism). CI does **not** auto-fix; developers run it locally and commit the updated docs. The script fixes `LC_ALL=C` to avoid locale-dependent output.

#### 5. New-project bootstrap

Use `hamanpaul/new-project-template` to create a new repo that automatically includes `.project-policy.yml`, the README / CHANGELOG / VERSION skeleton, the four agent convention files, and a `.github/workflows/policy-check.yml` calling this repo's reusable workflow:

```bash
gh repo create hamanpaul/<new-project> --template hamanpaul/new-project-template
```

#### Command-line help

<!-- BEGIN: cli-help marker="policy-check-help" -->
usage: policy-check [-h] [--repo REPO] [--pr-title PR_TITLE]
                    [--pr-body PR_BODY] [--pr-labels PR_LABELS]
                    [--pr-base-ref PR_BASE_REF] [--pr-head-ref PR_HEAD_REF]
                    [--repo-visibility {public,private,internal,unknown}]
                    [--only ONLY]

options:
  -h, --help            show this help message and exit
  --repo REPO           Repository root
  --pr-title PR_TITLE
  --pr-body PR_BODY
  --pr-labels PR_LABELS
                        Comma-separated
  --pr-base-ref PR_BASE_REF
  --pr-head-ref PR_HEAD_REF
  --repo-visibility {public,private,internal,unknown}
  --only ONLY           Comma-separated rule IDs (e.g. R-01,R-09)
<!-- END: cli-help marker="policy-check-help" -->

<!-- BEGIN: cli-help marker="policy-preflight-help" -->
usage: policy-preflight [-h] [--repo REPO] [--pr PR | --offline]
                        [--pr-title PR_TITLE] [--pr-body-file PR_BODY_FILE]
                        [--pr-labels PR_LABELS] [--base BASE] [--head HEAD]
                        [--repo-visibility {public,private,internal,unknown}]
                        [--skip-tests] [--policy-only] [--cache-dir CACHE_DIR]
                        [--engine-source ENGINE_SOURCE | --installed-manifest INSTALLED_MANIFEST]

options:
  -h, --help            show this help message and exit
  --repo REPO           Repository root
  --pr PR               GitHub PR number or URL
  --offline             Disable network-capable resolver operations
  --pr-title PR_TITLE
  --pr-body-file PR_BODY_FILE
  --pr-labels PR_LABELS
                        Comma-separated; empty means no labels
  --base BASE
  --head HEAD
  --repo-visibility {public,private,internal,unknown}
  --skip-tests
  --policy-only
  --cache-dir CACHE_DIR
  --engine-source ENGINE_SOURCE
                        Canonical paulsha-conventions checkout supplied by the
                        owning skill
  --installed-manifest INSTALLED_MANIFEST
                        Verified deployed bundle manifest supplied by the
                        stable selector
<!-- END: cli-help marker="policy-preflight-help" -->

<!-- BEGIN: cli-help marker="policy-runtime-bundle-help" -->
usage: policy-runtime-bundle [-h]
                             {build,verify,extract,install,rollback,recover,activate,uninstall}
                             ...

positional arguments:
  {build,verify,extract,install,rollback,recover,activate,uninstall}
    build               Build from a clean annotated tag
    verify              Verify an unpacked bundle
    extract             Verify archive digest/members and extract atomically

options:
  -h, --help            show this help message and exit
<!-- END: cli-help marker="policy-runtime-bundle-help" -->

### Distribution identity

The engine's distribution identity (canonical org, engine repo, remote base, distribution
name, provider) lives in `policy_check/data/distribution.yml`, fixed at **install time**
and **read-only at runtime**. It belongs to "this installed copy of the engine", not to
"the repo being checked" — a checked repo's `.project-policy.yml`
`conventions_engine.repo` may only declare a value that matches it, never redirect it;
any mismatch always raises `PreflightGateError`. Missing or invalid identity fails
closed — it never falls back to a default.

### Versioning

`VERSION` (repo root) is the single source of truth for the project version.

Version semantics (`profile: flat`):
- **MAJOR**: formal release (features reach externally-usable state).
- **MINOR**: features stabilized (all planned features landed + 7 days with no hotfix).
- **PATCH**: a completed feature batch (full rule list in `RELEASES.md` / `CHANGELOG.md`).
- **-fix.N**: post-landing bug fix (not a new feature, not stabilization, not a release).

### Related projects

- [`hamanpaul/.github`](https://github.com/hamanpaul/.github): account-level community defaults (PR template / Issue template / SECURITY / CONTRIBUTING).
- [`hamanpaul/new-project-template`](https://github.com/hamanpaul/new-project-template): new-project skeleton (for `gh repo create --template`).

### License

The license follows the repository owner's preference; see the `LICENSE` file at the repo root if present.

## 繁體中文

### 專案背景

本 repo 提供一套跨 `hamanpaul/*` 所有專案的 **policy engine**，目標：

- **新 repo 建立時**：自動帶入合規骨架（via `new-project-template`）
- **CI gate**：PR merge 前擋住不合規變更
- **Agent checklist**：進入 session 時自動看到規範
- **強制同步**：code 與 docs / CHANGELOG / VERSION 必須一起動

#### 解決什麼問題？
- 防止「改了 code 忘記改 CHANGELOG」
- 防止「CLI flag 改了但 README 沒更新」
- 防止「分支命名混亂、版號語意不一致」
- 防止「policy 說要遵守但 policy repo 自己不遵守」

本 repo 自身亦 **dog-food** 本套 policy（`profile: flat`；`policy_version` 見 `.project-policy.yml` / `VERSION`）。

版本譜系（policy_version ↔ engine tag/SHA 對照）見 [`RELEASES.md`](./RELEASES.md)。

### 規則總覽（R-01 ~ R-26）

| ID | 檢查項 | 失敗條件 | 豁免 label |
|----|--------|----------|------------|
| R-01 | `README.md` 存在 | 缺檔或 <100 byte | — |
| R-02 | `README.md` 必備段落 | 缺 `## Install` / `## Usage` / `## Version` | `policy-exempt:readme-sections` |
| R-03 | `CHANGELOG.md` 存在 | 缺檔 | — |
| R-04 | `CHANGELOG.md` 格式合規 | 缺 `# Changelog` 標頭（fragment 模型下不再要求 `[Unreleased]`） | `policy-exempt:changelog-format` |
| R-05 | `VERSION` 存在 | 缺檔 | — |
| R-06 | `VERSION` 符合語意 | 不匹配 `<MAJOR>.<MINOR>.<PATCH>(-fix\.\d+)?` | — |
| R-07 | `VERSION` 與最新 tag 一致 | 不一致且無 `release:*` label | — |
| R-08 | `.project-policy.yml` 存在且完整 | 缺檔或缺 `policy_profile` / `policy_version` | — |
| R-09 | Code 變動必有 changelog fragment | code path 有變動但本 PR 未新增 `changelog.d/*.md` fragment | `skip-changelog` |
| R-10 | PR title 符合 conventional-commit | regex 不匹配 | `policy-exempt:pr-title` |
| R-11 | PR body checkbox 全勾 | 必勾項未勾滿 | `wip` 時自動通過 |
| R-12 | 分支來源正確 | 目標=main 時來源非 `feature/*`；目標=`feature/*` 時來源非 `wt/<feature>/*` | `policy-exempt:branch-name` |
| R-13 | Agent convention files 存在 | 缺 `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md` | `policy-exempt:agent-files` |
| R-14 | Agent files 單一真檔完整性（config-gated） | `copy`（預設）：四檔 `policy_version` 與 `.project-policy.yml` 不符；`symlink`：鏡像檔非 symlink／未 resolve 到 `CLAUDE.md`／canonical 自身為 symlink | — |
| R-15 | Caller workflow 用 tag / SHA 鎖定（本 repo 的 policy-check dual-pinning path 另要求完整 40 字元 SHA） | `uses:` 指向 branch ref（`@main`、`@develop`）或無 ref | — |
| R-16 | CLI help 與 docs 同步 | `.project-policy.yml.cli` 宣告項目，實跑 help 輸出與 marker 區塊不一致 | `policy-exempt:cli-help` |
| R-17 | PR↔issue 連結 | PR body 出現 `#N` 但非 closing-keyword（`Closes`/`Fixes`/`Resolves #N`）形式 | `policy-exempt:issue-link` |
| R-18 | docs/README 對齊 code 變動 | code_paths 有變動但 `README.md` / `docs/**` 未同步（**WARN**，不擋 merge） | `policy-exempt:docs-sync` |
| R-19 | repo 有測試則 CI 必須執行 | 結構化解析 `jobs.*.steps[].run` 後沒有實際測試指令；註解／安裝行不算，條件式命中 WARN，YAML 解析失敗回退並 WARN，`r19.strict: true` 將這些 WARN 提升為 FAIL | `policy-exempt:ci-tests` |
| R-20 | Workflow policy_version 與 config 同步 | workflow 內宣告的 `policy_version` / `POLICY_VERSION` 字面值與 `.project-policy.yml` 的 `policy_version` 不一致 | — |
| R-21 | visibility-aware 機密掃描 | 所有 tier 都掃描；`shareable` 命中一律 **FAIL**；其他 tier 的 public/unknown 結構或憑證命中 **FAIL**，僅 marker 及 private/internal 命中 **WARN**；報告只揭露相對 `path:line`、detector 類別與筆數 | `policy-exempt:secret-scan` |
| R-22 | docs 對 code 產物引用無懸空 | canonical doc scope（`doc_paths`，預設 `README.md` / `docs/**`）引用的路徑／內部連結／反引號 symbol 在 repo 不存在；symbol 改用**語言無關 scoped identity**（ctags `(language, kind, scope, name)` 差集，限定式 token 精準命中、結構化裸名 snake/Camel 多 scope 同名只 WARN、純單字不偵測以避免常見字誤報）；本次變更新破壞 **FAIL**、陳年懸空 **WARN**、無 diff context（本地）降 WARN；`openspec/**`・`docs/superpowers/**`・fixtures 內建排除 | `policy-exempt:doc-reference` |
| R-23 | 引擎 pin 版本與 policy_version 對齊 | workflow `uses:` 指向 `conventions_engine.repo` 的引擎版本（tag `@vX.Y.Z` 或 SHA `@<sha>` + 尾註 `# vX.Y.Z`）與 `.project-policy.yml` 的 `policy_version` 不一致 **FAIL**；純 SHA 無註解 **WARN**；`./` 在地引用或未設 `conventions_engine.repo` 則 NA | `policy-exempt:engine-pin` |
| R-24 | MOC 與本次變更對齊 | repo 宣告 `moc` 時：`moc.triggers` 命中但 `moc.static` 未同步（**WARN**）／`moc.map` 連結懸空（本次新破壞 **FAIL**、陳年 **WARN**）／active openspec change・plan・spec 未被連結（**WARN**，永不 FAIL）；orphan/freshness 改呼叫共用核心，受治理前綴**參數化**（預設沿用既有前綴）；未宣告 `moc` 則 NA | `policy-exempt:moc-alignment` |
| R-25 | 文件覆蓋（omission gate，opt-in） | repo 宣告 `doc_coverage` 時：extractor 抽出的 public fact 未在任一 target doc 被精確 mention 則 **FAIL**（`mode: changed` 只查本次新增 fact、`mode: all` 查全部）；`mode: changed` 缺 base diff context 降 **WARN**；target 超出 `doc_paths`／不存在／extractor 設定無效 **FAIL**；未宣告 `doc_coverage` 則 NA | — |
| R-26 | 生成事實 marker 同步（opt-in） | repo 宣告 `generated_facts` 時：`generated-fact` marker 區塊內容與 command 正規化 stdout 不一致、marker 缺失、command 非 0 結束、或設定不完整則 **FAIL**；與 R-16 的 `cli-help` marker 並存不互相覆蓋；未宣告 `generated_facts` 則 NA | — |

**Exemption Labels 白名單**：上表所列 `policy-exempt:*` / `skip-changelog` / `wip` 即所有可用豁免 label；gate 只認這些，其他一律視同未豁免。

### Doc-alignment governance（三層）

文件陳舊分三層治理，只有 Tier 2 為確定性 gate：

- **Tier 1（預防）**：agent 改 code 時同步更新引用該產物的 docs（見四份 agent 慣例檔 checklist）。
- **Tier 2（確定性 gate）**：R-22 在 CI 偵測 `README.md` / `docs/**` 的結構化懸空引用——本次新破壞 FAIL、陳年 WARN。確定性層只看「結構性 rot」（引用死掉），不判斷語意。
- **Tier 3（語意複審）**：建議將 GitHub Copilot 設為 PR reviewer，複審「引用仍在但描述已過時」的語意陳舊（advisory，不擋 merge）。

#### 獨立 doc-drift Action（OSS-ready，#25）

R-22/R-24 的 doc↔code 漂移核心抽成語言無關、零設定的共用核心（`policy_check/doc_drift/`，按
refs/paths/symbols/coverage/langs/provision primitive 組織），並包成可被**任意 repo** `uses:` 的
獨立 composite action（`.github/actions/doc-drift/`，詳見其 [README](.github/actions/doc-drift/README.md)）。
不要求目標 repo 採用 `.project-policy.yml`；symbol 抽取改用 universal-ctags 的 scoped identity
`(language, kind, scope, name)` 差集，支援 **Python / bash / C / C++**，消除原本 Python-only 與同名 fail-open 兩個限制。
Action 提供 `doc-drift` 與 `moc` 兩 mode，自理 base/head SHA 供給（shallow checkout 下不前置失敗），
FAIL 以非零 exit 擋 merge、WARN advisory。

> **與 lychee 的互補**：本 Action 只管 in-repo code 產物引用不懸空；外部 URL 活性／HTTP／anchor 交由 [lychee](https://github.com/lycheeverse/lychee-action)。

#### 跨 repo 升版傳播（機制層，#23）

確定性的三層 doc-alignment 是 **intra-repo**；跨 repo 的 `policy_version` 漂移由本機制層治理（engine 只強制＋偵測＋文件，**不主動改下游**）：

- **強制（擋）**：org ruleset 的 `Policy Freshness` required workflow 跑 `python3 -m policy_check.drift check`，落後 canonical 的 repo PR 無法 merge。設定見 [`docs/org-ruleset-runbook.md`](docs/org-ruleset-runbook.md)。
- **偵測（點名）**：`python3 -m policy_check.drift report --org hamanpaul` 唯讀列出各 repo `policy_version` 與漂移狀態（`current` / `behind` / `ahead` / `unmanaged`）。
- **修復（升）**：落後 repo 由其自身 agent 依 [RELEASES.md](RELEASES.md) 的「升版傳播 SOP」自助升版。

> `policy_check.drift` 是 ops 工具，**非 R-xx gate 規則**，不進 `python3 -m policy_check --repo .` 的 FAIL 集合。

#### 文件規則設定面（`doc_paths` / `doc_coverage` / `generated_facts`）

`.project-policy.yml` 提供三個文件治理設定面，皆向後相容（未宣告即維持既有行為）：

```yaml
# 1) canonical doc scope：R-18 / R-22 共用；未宣告時預設 README.md + docs/**
doc_paths:
  - "README.md"
  - "docs/**"
  - "CLAUDE.md"

# 2) doc_coverage（opt-in，R-25）：抓「新增了 X 卻沒記」的 omission drift
doc_coverage:
  mode: "changed"          # changed（只查本次新增 fact，預設）| all（查全部）
  targets: ["README.md"]   # 必須落在 doc_paths 內的 canonical docs
  sources:
    - kind: "modules"      # fact = repo-relative 路徑
      include: ["pkg/**/*.py"]
      exclude: ["**/__init__.py"]
    - kind: "rpc_methods"  # fact = pattern 的單一 capture group
      include: ["pkg/service.py"]
      pattern: 'method == "([^"]+)"'
    - kind: "env_vars"     # fact = PREFIX[A-Z0-9_]+ token
      include: ["pkg/**/*.py"]
      prefix: "APP_"
    - kind: "cli_tree"     # fact = command stdout 一行一個命令路徑
      command: "python3 scripts/list-cli-paths.py"

# 3) generated_facts（opt-in，R-26）：通用 marker-sync，把 R-16 的 cli-help 模式一般化
generated_facts:
  - kind: "fact_list"
    command: "python3 scripts/render-rpc-facts.py"
    reflected_in: "README.md"
    marker: "rpc-methods"
```

- **mention 判定**：R-25 採區分大小寫的精確 token/phrase 比對，子字串命中不算覆蓋（例如 `session.closed` 不滿足 `session.close`）。
- **changed 模式邊界**：缺 base diff context（如本地 `--repo .`）時降 WARN，不在無證據下 FAIL；`cli_tree` 無法快照 base，僅在 `mode: all` 受檢。
- **generated-fact marker 語法**：`<!-- BEGIN: generated-fact marker="<name>" -->` … `<!-- END: generated-fact marker="<name>" -->`；command 以 `shlex.split` 不經 shell 執行、`cwd=repo_root`、`LC_ALL=C`、固定 30 秒 timeout，只比對正規化 stdout。
- **安全注意（命令執行型規則）**：`R-16`（`cli`）、`R-25` 的 `cli_tree` extractor 與 `R-26`（`generated_facts`）會執行 `.project-policy.yml` 宣告的命令（無 shell injection，但命令字串本身受 config 控制並繼承完整環境）。因此**不應**在未信任的 PR／fork 分支上執行 `policy_check`；只在可信任的 repo config 上啟用。`cli_tree` 在 `mode: changed` 不會被執行（僅 `mode: all` 才跑）。

R-19 的分階段 rollout 可由各 repo 自行提前切換 strict：

```yaml
r19:
  strict: true  # 將可繞過或條件式測試 gate 的 WARN 提升為 FAIL
```

R-08 會驗證 `r19` 必須是 mapping、`strict` 必須是 boolean；省略 `r19` 維持預設的 WARN rollout。

#### `auto_build` 區塊（LLM auto build 慣例，#30）

`.project-policy.yml` 可宣告 optional 的 `auto_build:` 區塊，承載 per-project build flow，
供 LLM auto build agent 冷讀即得「怎麼 build 這個專案」；不用 build 的 repo 整塊不寫、零負擔：

```yaml
auto_build:
  description: "router firmware image via docker build container"  # str：一句話 build 目標
  setup:                       # list[str]：環境準備命令
    - "docker pull registry.example/fw-builder:latest"
  steps:                       # list[str]：建置命令，依序執行
    - "docker run --rm -v $PWD:/src fw-builder make -C /src image"
  artifacts:                   # list[str]：預期產物 glob
    - "out/*.img"
  verify:                      # list[str]：建置成功驗證命令
    - "test -s out/firmware.img"
```

- **R-08 只驗形狀**：`auto_build` 須為 mapping；`description` str；`setup`/`steps`/`artifacts`/`verify`
  各為 list[str]。**未知 subkey 一律放行**（per-project 擴充與欄位演進不需 engine release），
  無必填 subkey；顯式 null 的 subkey（如 `steps:` 後無值）視同未宣告（與其他 optional 區塊一致）。
- **engine 永不執行**：與 `cli`（R-16）、`cli_tree`（R-25）、`generated_facts`（R-26）等命令執行型
  設定不同，`auto_build` 內所有命令字串對 policy engine 而言是純資料，任何規則都不會執行它們。
  消費者是讀 config 的 LLM agent；執行與否及其安全審查由該 agent 的 Human-in-the-loop 流程負責。

### CHANGELOG fragment 模型（並行安全）

為消除並行 agent 改共用 `CHANGELOG.md [Unreleased]` 的 merge conflict，待發布記錄改採
**每 PR 一個 fragment 檔**（changesets / towncrier 模式，但 agent 寫碎片、gate 驗碎片）：

- **每個 PR** 新增 `changelog.d/<issue>-<slug>.md`（不碰 `CHANGELOG.md`）：
  ```markdown
  ---
  type: feat        # 必填，conventional-commit type
  scope: changelog  # 選填
  issue: 24         # 選填
  ---
  一句話描述（成為 CHANGELOG 的一條 bullet）。
  ```
  不同 issue 天然不同檔、零共用行 → **並行 PR 永不衝突**。
- **type → Keep-a-Changelog 段** 固定映射：`feat`→Added、`fix`→Fixed、
  `refactor`/`perf`/`change`→Changed、`remove`→Removed、`deprecate`→Deprecated、`security`→Security。
  未知 type → collate 失敗。`docs`/`test`/`chore` 走 `skip-changelog`。
- **release 收斂**：升版時跑
  ```bash
  python3 -m policy_check.changelog collate --version X.Y.Z --date YYYY-MM-DD
  ```
  把 `changelog.d/*.md` 依 type 分組產出 `## [X.Y.Z] - <date>` 段（KaC 格式，R-04 仍過）並清空目錄。
- `R-09` 改驗「本 PR 有無 fragment」、`R-04` 不再要求 `[Unreleased]`。屬行為綁版本的 hard cutover
  （下游靠 pin 版本主動升級，未升級者用舊 `[Unreleased]` 行為）。

### 安裝
```bash
python3 -m pip install -e ".[test]"
```

#### 離線 pip 安裝（給 GitLab gate / air-gapped runner）

若下游 CI 不走 GitHub reusable workflow，而是把引擎當成 wheel 發佈到 GitLab merge request pipeline，**必須**一併 vendor 引擎 wheel 與相依閉包；只做 `pip install --no-index <wheel>` 並不足夠，因為離線 runner 仍需要 `PyYAML` 等相依。

build-time（可連網）先做 wheel 與相依閉包：

```bash
python3 -m pip wheel --no-deps --wheel-dir dist .
mkdir -p vendor
python3 -m pip download --dest vendor dist/policy_check-X.Y.Z-py3-none-any.whl
```

gate-time 的 **Python 套件安裝** 可離線，只吃已 vendored 的檔案：

```bash
python3 -m pip install --no-index --find-links vendor policy-check==X.Y.Z
```

界線請分清楚：

- **build-time / 發行階段**：需要網路，負責 build wheel 並抓完整相依閉包。
- **gate-time / MR 檢查階段**：`policy-check` 與其 vendored Python 相依可離線安裝；但 `universal-ctags` 仍需預裝在 runner image，或透過公司內部 package mirror 提供。

### 使用
#### 1. 本地檢查（開發階段）

對當前 repo 跑完整檢查：

```bash
python3 -m policy_check --repo .
```

只跑指定規則（例如：快速檢查文件結構）：

```bash
python3 -m policy_check --repo . --only R-01,R-02,R-03
```

#### 2. 本地／離線 Preflight

`policy-preflight` 會依序執行 policy gate，以及 `.project-policy.yml`
宣告的 repo-owned validation/test steps。手動模式必須明確提供 PR title 與
body file，確保 PR-only 規則拿到完整脈絡：

`.project-policy.yml` 是公開 canonical 名稱；相容期仍接受 legacy-only
`.paul-project.yml`，但會發出 deprecation warning。兩檔同時存在時，解析後 <!-- doc-drift-ignore -->
語意相同可帶 warning 繼續，任何語意差異一律先 FAIL。

Agent-facing canonical 入口是由本 repo 擁有的 `preflight-ci` skill。從
`paulsha-conventions` checkout 安裝或遷移 user-level skill symlink：

```bash
scripts/install-preflight-skill.sh --replace
```

之後在目標 repo 執行：

```bash
~/.agents/skills/preflight-ci/scripts/preflight.sh \
  --pr-title "feat(preflight): 新增 canonical local preflight" \
  --pr-body-file /path/to/pr-body.md \
  --base main \
  --head feature/local-preflight \
  --repo-visibility public
```

Skill 直接把相鄰的 `paulsha-conventions` checkout 當作經驗證 source engine，
不讀取或執行 GitHub Actions workflow，也不 clone/fetch engine。目標 repo 的
`policy_version` 必須與已部署的 conventions checkout 一致。Skill-driven 完整
執行要求明確宣告 `.project-policy.yml.preflight.steps`；只有刻意縮成 policy-only
時才使用 `--policy-only`。

```bash
policy-preflight \
  --repo . \
  --pr-title "feat(preflight): 新增 canonical local preflight" \
  --pr-body-file /path/to/pr-body.md \
  --base main \
  --head feature/local-preflight \
  --repo-visibility public
```

可連 GitHub 時，可直接讀取 PR metadata：

```bash
policy-preflight --repo . --pr 46
```

離線模式只禁止 preflight 的 **engine resolver** 執行可連網操作，並只接受
版本相符的 installed distribution 或通過驗證的 exact-SHA cache；PR metadata
必須由手動參數／檔案提供。Repo-owned commands 仍受該 repo 自身 authority
管轄，可能另有自己的網路行為：

```bash
policy-preflight \
  --repo . \
  --offline \
  --pr-title "fix(policy): 驗證離線 preflight" \
  --pr-body-file /path/to/pr-body.md \
  --base main \
  --head feature/offline-preflight \
  --repo-visibility private
```

下游 repo 以 typed argv 宣告命令，不使用 shell 字串：

```yaml
preflight:
  steps:
    - name: openspec
      kind: validation
      argv: ["openspec", "validate", "--all"]
      when_path_exists: "openspec"
      timeout_seconds: 300
    - name: tests
      kind: tests
      argv: ["python3", "-m", "pytest", "-q"]
      timeout_seconds: 1200
```

`--skip-tests` 只跳過 `kind: tests`；若其餘宣告步驟都屬目前不存在的 optional
path，這個明確縮減可通過；沒有明確 test skip、只有 conditional SKIP 時仍失敗。
`--policy-only` 會跳過所有 repo-owned steps，但仍執行 engine resolution 與 policy gate。參數／設定錯誤回 exit 2，
effective head 必須等於目前 checkout branch，且 `origin/<base>` 必須存在並可建立
merge base；否則會直接停止，不會用空 changed-files 集合繼續。
任一 gate 失敗回 exit 1，全部通過才回 exit 0。

#### 3. 版本化 Runtime Bundle

`policy-runtime-bundle` 從 clean canonical annotated tag 建立單一不可變
release unit，原子包含 engine wheel、wheel-only 相依閉包、`preflight-ci`
skill、stdlib installer manager 與共用 verifier、manifest 與 `SHA256SUMS`。建置主機需有
Python 3.11+、`build` 與 pip；相依版本由 bundle 自有 constraint 鎖定：

```bash
policy-runtime-bundle build \
  --repo . \
  --tag vX.Y.Z \
  --output-dir /repo/外的輸出目錄
```

先驗外部 archive digest 與 member safety，再離線安裝：

```bash
policy-runtime-bundle extract \
  --archive /path/paulsha-conventions-vX.Y.Z.tar.gz \
  --sha256 <published-archive-sha256> \
  --output-dir /safe/staging
/safe/staging/paulsha-conventions-vX.Y.Z/install.sh
```

部署後的 stable launcher 會讀目標 repo 的 exact `policy_version`，驗證相同
版本的 installed release，再用該 venv 的 Python isolated mode 執行。缺版直接失敗，
不會 fallback 到 `current`、workflow、其他版本或網路。升級須在離線安裝與
完整 preflight smoke 都通過後才 activation。相依 wheel 可能綁 ABI/platform，
因此安裝主機必須符合 manifest 記錄的 Python major/minor、implementation、ABI
與 platform，並具備 `venv/ensurepip`（Debian/Ubuntu 通常是 `python3-venv`）；
安裝主機也需有 `git`、GNU `sha256sum` 與支援 JSON output 的
`universal-ctags`；每個 resolved dependency wheel（含 transitive dependency）
也必須命中 exact constraint。bootstrap/selector 不採用 ambient
`PYTHONPATH`/`PYTHONHOME`，installed attestation 會驗證每個 wheel distribution
與 RECORD payload，且在 selected venv import 第三方 code 前拒絕 startup
customization/module shadow；安裝後也會移除僅供 bootstrap 的 pip/setuptools。
stable launcher 另會錨定 active manifest digest，並在執行 current manager 前
核對其 hash。既有未受管
`preflight-ci` 目錄或 source-checkout symlink 須先移到可逆 backup，installer
不會自動接管；rollback 只切到既有 VERIFIED release。active release 若被竄改，
可用同一份已核對外部 digest 的 artifact 執行 `install --force-reinstall`；
新 release 仍須先完成 staging 與 smoke 才替換。操作細節見
[runtime bundle runbook](docs/runtime-bundle-runbook.md)。

#### 4. CI 整合（下游 repo）

##### GitHub reusable workflow

在下游專案 `.github/workflows/policy-check.yml` 中呼叫本 repo 提供的 **reusable workflow**：

```yaml
# .github/workflows/policy-check.yml
name: Policy Check
on: [pull_request]

jobs:
  policy:
    # Pin both the reusable workflow and the policy engine to the SAME full 40-char commit SHA.
    # Do NOT use a tag or branch ref — full SHA is required by the policy engine validation step.
    uses: hamanpaul/paulsha-conventions/.github/workflows/reusable-policy-check.yml@aabbccddeeff0011223344556677889900aabbcc
    with:
      policy_profile: stage-driven  # 或 flat
      policy_version: X.Y.Z  # 範例；填你釘選 SHA 對應的實際版本
      # 必須傳入完整 40 字元 hex commit SHA，指向 hamanpaul/paulsha-conventions。
      # 不可使用 tag、short SHA 或 github.workflow_sha（那是 caller 自己 repo 的 SHA）。
      # uses: 與 policy_engine_ref 兩者必須鎖定到同一個 SHA。
      policy_engine_ref: aabbccddeeff0011223344556677889900aabbcc
```

Workflow 會自動：
- Checkout PR context
- 從 `hamanpaul/paulsha-conventions` 取得 policy engine（含 PyYAML 依賴）
- 跑完整規則檢查
- 在 GitHub Actions Summary 輸出結果

##### GitLab merge_request gate（pip mode）

下游 repo 的 `.project-policy.yml` 需顯式宣告 pip mode，讓 R-23 改驗「已安裝套件版號」與 `policy_version` lockstep；GitLab merge request pipeline 亦會自 `CI_MERGE_REQUEST_*` 載入 MR context，R-12 在 GitLab 路徑標示為 NA。

```yaml
# .project-policy.yml
policy_profile: flat
policy_version: X.Y.Z
conventions_engine:
  mode: pip
```

GitLab CI job 可採最小 gate：

```yaml
policy-check:
  image: python:3.11
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  variables:
    GIT_DEPTH: "0"
  before_script:
    # 若 runner image 未預裝 universal-ctags，這一步仍需網路或公司內部 APT mirror
    - apt-get update && apt-get install -y universal-ctags
    # Python 套件安裝可離線，只吃 build-time 已 vendored 的 wheel 與相依
    - python3 -m pip install --no-index --find-links vendor policy-check==X.Y.Z
  script:
    - policy-check --repo .
```

此範例假設 runner 在 gate-time 已取得 build-time 產出的 `vendor/` 內容。若要讓 MR gate 不碰外部網路，請把 `universal-ctags` 預裝進 runner image；否則至少需接公司內部 APT / package mirror。換言之，這裡的離線保證只涵蓋 **Python wheel / vendored 相依安裝** 這一段。**Artifactory / 內部 PyPI / GitLab Package Registry** 哪一條作為正式發行管道，仍屬需由公司決定的 follow-up。

#### 4. Helper Scripts

##### `scripts/update-cli-help.sh`

**用途**：實跑 `.project-policy.yml.cli` 宣告的每個 command，自動回寫 docs 內的 marker 區塊（R-16 同步機制）。

**使用**：
```bash
cd <下游專案>
bash /path/to/paulsha-conventions/scripts/update-cli-help.sh
```

**注意**：
- CI **不** auto-fix（避免 PR 在沒有 dev 意識下被改）
- 開發者在本地跑，commit 更新後的 docs
- 此 script 固定 `LC_ALL=C` 避免多語系輸出差異

#### 5. 新專案 Bootstrap

使用 `hamanpaul/new-project-template` 建立新 repo，自動包含：
- `.project-policy.yml`（需填入 profile / version）
- `README.md` / `CHANGELOG.md` / `VERSION` 骨架
- 四份 agent convention files（`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md`）
- `.github/workflows/policy-check.yml` 呼叫本 repo reusable workflow

目前已落地的 live rollout repos：
- [`hamanpaul/.github`](https://github.com/hamanpaul/.github)：提供 account-level PR template / CONTRIBUTING / SECURITY defaults
- [`hamanpaul/new-project-template`](https://github.com/hamanpaul/new-project-template)：提供新專案 bootstrap skeleton 與 dual-pinned `Policy Check` workflow

這條 bootstrap 路徑已用 fresh smoke repo 驗證：只補 smoke metadata 的 PR 即可直接通過 generated `Policy Check` workflow，無需手改 workflow 檔。暫時只剩遠端 smoke repo 清理尚未完成，因目前 `gh` token 缺少 `delete_repo` scope。

```bash
gh repo create hamanpaul/<new-project> --template hamanpaul/new-project-template
```

#### CLI Help

（見 [English → Command-line help](#command-line-help)）

### Distribution identity

引擎的發行身分（canonical org、engine repo、remote base、distribution name、provider）
記於 `policy_check/data/distribution.yml`，於**安裝期**決定、**執行期唯讀**。
它屬於「被安裝的這份引擎」，不屬於「被檢查的 repo」——`.project-policy.yml` 的
`conventions_engine.repo` 只能宣告與其一致，不能改指向；不一致一律
`PreflightGateError`。缺漏或不合法時 fail-closed，不回退預設值。

### 版本
`VERSION` 檔（repo root）為專案版號 single source of truth。

**本 repo 版號語意**（`profile: flat`）：
- **MAJOR**: 正式 release（feature 達到對外可用狀態）
- **MINOR**: 功能穩定（已規劃 feature 全 landed + 7 天無 hotfix）
- **PATCH**: 累積已完成的 feature batch 計數（完整規則清單見 `RELEASES.md` / `CHANGELOG.md`）
- **-fix.N**: 落地後 bug fix（非新 feature、非穩定、非 release）

當前版本（權威值見 `VERSION`）：

當前版本見上方 [Version](#version) 區塊（權威值：`VERSION`）。

### 相關專案

- [`hamanpaul/.github`](https://github.com/hamanpaul/.github)：GitHub 社群預設（PR template / Issue template / SECURITY / CONTRIBUTING）
- [`hamanpaul/new-project-template`](https://github.com/hamanpaul/new-project-template)：新專案骨架（供 `gh repo create --template` 使用）

### License

授權依 repository owner 的偏好；repo 根目錄若有 `LICENSE` 檔案請以其為準。
