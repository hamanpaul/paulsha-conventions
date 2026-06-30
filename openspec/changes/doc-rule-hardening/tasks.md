## 1. Shared canonical doc scope

- [ ] 1.1 Extend config loading and R-08 schema validation to support `doc_paths` with the legacy default of `README.md` and `docs/**`.
- [ ] 1.2 Update `R-18` to use `doc_paths` when deciding whether a code change includes a canonical docs update, and add regression tests for default and custom scopes.
- [ ] 1.3 Update `R-22` to derive candidate docs from `doc_paths` while preserving its built-in exclusions, and add regression tests for custom-scope scanning and excluded spec/fixture paths.

## 2. Deterministic coverage gate

- [ ] 2.1 Add schema validation for `doc_coverage`, including `mode`, `targets`, and extractor entry requirements.
- [ ] 2.2 Implement shared fact extraction helpers for the v1 built-in sources (`modules`, `rpc_methods`, `env_vars`, `cli_tree`) with deterministic fact identities.
- [ ] 2.3 Implement the coverage rule with `changed` and `all` modes, exact mention matching, and graceful WARN behavior when `changed` mode lacks diff context.
- [ ] 2.4 Add targeted tests for opt-in behavior, malformed config failures, target validation, diff-aware `changed` mode, and exact token/phrase matching.

## 3. Generated fact sync

- [ ] 3.1 Extract shared marker-sync and command-execution helpers from the current CLI help sync behavior without breaking existing `R-16` compatibility.
- [ ] 3.2 Add schema validation for `generated_facts` and implement the generic generated-fact sync rule with the documented marker protocol and execution contract.
- [ ] 3.3 Add targeted tests for not-applicable behavior, malformed config failures, missing markers, command failures, output mismatches, and coexistence with existing CLI help markers.

## 4. Dogfood, docs, and verification

- [ ] 4.1 Dogfood the new config surfaces in this repo where appropriate and update README / CHANGELOG documentation for `doc_paths`, `doc_coverage`, and `generated_facts`.
- [ ] 4.2 Run the targeted pytest coverage for the changed rules, then run `python3 -m pytest -q` and `python3 -m policy_check --repo .` to confirm the feature batch is ready for review and archive.
