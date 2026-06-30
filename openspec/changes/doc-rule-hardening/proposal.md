## Why

Issue #26 exposed a real gap in the current documentation rules: the engine can still PASS when canonical docs have already drifted from the repo's actual public facts. Today `R-18` and `R-22` only understand `README.md` and `docs/**`, so they miss root-level and repo-specific canonical docs, and they have no deterministic way to catch omission-style drift such as "a new module or RPC was added but never documented."

## What Changes

- Add a repo-declared canonical documentation scope (`doc_paths`) that documentation-related rules can share instead of hard-coding `README.md` and `docs/**`.
- Extend `R-18` and `R-22` to consume the shared canonical doc scope while preserving `R-22`'s current diff-aware dangling-reference behavior and built-in exclusions for specs/fixtures.
- Add an opt-in deterministic doc coverage capability that checks whether newly introduced or explicitly scoped public facts are mentioned in canonical docs.
- Add an opt-in generated-fact sync capability that generalizes the existing marker-sync pattern beyond CLI help output.
- Keep pure semantic/narrative correctness outside the blocking deterministic gate and treat it as an advisory review layer only.

## Capabilities

### New Capabilities
- `canonical-doc-scope`: Allow a repo to declare which files count as canonical docs so multiple documentation rules can share the same scope.
- `doc-coverage`: Provide an opt-in deterministic rule that detects omission-style drift when configured public facts are not mentioned in canonical docs.
- `generated-fact-sync`: Provide an opt-in deterministic marker-sync mechanism for generated structured documentation facts.

### Modified Capabilities
- `doc-reference`: Change the doc-reference capability to scan repo-declared canonical docs instead of only `README.md` and `docs/**`, while preserving current exclusions and diff-aware severity behavior.

## Impact

- Affected config surface: `.paul-project.yml` (`doc_paths`, `doc_coverage`, `generated_facts`)
- Affected rules: `R-08`, `R-18`, `R-22`, plus new deterministic rules/helpers for coverage and generated-fact sync
- Affected tests: config schema tests, `R-18`/`R-22` regressions, and new coverage/sync tests
- Affected docs: OpenSpec capability specs, `README.md`, changelog, and planning/spec artifacts for issue #26
