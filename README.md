# paul-project-conventions

Cross-repo policy checker for `hamanpaul/*` repositories. This project provides a policy engine, reusable CI workflows, and helper scripts to keep documentation, versioning, and PR hygiene consistent.

## Install

```bash
python3 -m pip install -e ".[test]"
```

## Usage

Run policy checks against the current repository:

```bash
python3 -m policy_check --repo .
```

Run selected rules only:

```bash
python3 -m policy_check --repo . --only R-01,R-02,R-03
```

### CLI Help

<!-- BEGIN: cli-help marker="policy-check-help" -->
usage: policy-check [-h] [--repo REPO] [--pr-title PR_TITLE]
                    [--pr-body PR_BODY] [--pr-labels PR_LABELS]
                    [--pr-base-ref PR_BASE_REF] [--pr-head-ref PR_HEAD_REF]
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
  --only ONLY           Comma-separated rule IDs (e.g. R-01,R-09)
<!-- END: cli-help marker="policy-check-help" -->

## Version

`VERSION` in repo root is the project version source of truth.
