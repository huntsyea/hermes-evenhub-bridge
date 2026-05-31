# Repository governance

This repository is configured for a small, safe open-source workflow.

## Required checks

`main` should require the CI matrix checks:

- `lint-and-test (3.11)`
- `lint-and-test (3.12)`
- `lint-and-test (3.13)`

After the CodeQL workflow has run on a pull request, also require:

- `Analyze (python)`
- `Analyze (actions)`

The gateway integration job is intentionally non-blocking because it depends on the
external Hermes gateway package.

## Review gates

`main` should require pull requests, one approving review, stale review dismissal,
conversation resolution, and code owner review. Admin enforcement should be enabled so
maintainers use the same path as contributors.

The repository owner, `huntsyea`, is the only pull-request review bypass user. This
lets the owner merge their own changes after required checks pass, while everyone else
still needs the review gate. This bypass does not skip required status checks, tag
protection, or conversation resolution.

## Release tags

Release tags should be protected with rulesets:

- `v*`
- `sidecar-v*`

Only maintainers should create or update those tags, force pushes and deletions should
remain blocked, and sidecar tags should point at commits already on `main`.

## Repository features

Use issues, issue forms, pull requests, security advisories, and releases as the public
project surface. Keep dependency graph, Dependabot alerts, and Dependabot security
updates enabled. Disable wiki and projects unless they become actively maintained.

## Applying settings

Repository settings are external GitHub state, so they are not changed by normal code
review. Maintainers can preview the intended API calls with:

```bash
bash scripts/apply-github-governance.sh --dry-run
```

After approving the exact changes, apply them with:

```bash
bash scripts/apply-github-governance.sh --apply
```

Apply this after the workflow and community-file changes have landed on `main`.
The branch protection policy requires CodeQL checks, so the CodeQL workflow must be
present on the default branch before the settings are enabled.
