# preflight-ci ownership migration risks

| Risk | Guard | Rollback |
| --- | --- | --- |
| Two canonical skill copies drift | Installer points only to the conventions copy; source removal is a dependent PR | Revert source removal |
| Symlink cutover replaces user data | Installer replaces only an existing symlink and refuses real files/directories | Repoint symlink to prior checkout |
| Skill silently falls back to Actions workflow | Wrapper always appends verified `--engine-source`; tests forbid workflow/clone/fetch logic | Run CLI without the skill to use legacy resolver explicitly |
| Target repo omits test gates | Skill-driven full mode exits 2 unless `preflight.steps` exists | Declare steps or intentionally use `--policy-only` |
| Engine/source version skew | Source `VERSION` must match target `policy_version` | Update target policy pin or deployed conventions release |
| Existing Python override is lost | New wrapper retains `PSC_PREFLIGHT_PYTHON`; step argv owns test interpreter | Repoint to old skill before source removal |
