---
description: 'GitHub Actions workflow conventions for duploctl'
applyTo: '.github/workflows/*.yml, .github/actions/*/action.yml'
---

# GitHub Actions Workflow Conventions

Applies to the CI workflows and composite actions. YAML formatting comes from
[yaml.instructions.md](./yaml.instructions.md); this file is the
Actions-specific rules. These are hard conventions; flag violations.

## Naming

- Every **job** has a `name` that says what it does.
- Every **step** has a `name`. Add an `id` only when a later step reads its
  outputs.

## No `${{ }}` inside `run:` scripts

GitHub interpolates `${{ }}` into the script before the shell runs, which is
a shell-injection risk and makes the step impossible to run outside Actions.
Bind the expression to the step's `env:` and read the plain `$VAR`.

```yaml
# Bad
- name: Tag image
  run: docker tag app:latest app:${{ inputs.tag }}

# Good
- name: Tag image
  env:
    TAG: ${{ inputs.tag }}
  run: docker tag app:latest "app:$TAG"
```

## Keep `run:` blocks pure

- Explain a step with a YAML comment **above** it, not inside the script.
- One logical function per step. Split build, sign and upload into separate
  steps so a failure names the exact one.
- Pass a value from one step to the next with a step output
  (`echo "key=value" >> "$GITHUB_OUTPUT"`). Write to `GITHUB_ENV` only when
  most of the job needs the value.

## Action versions

- **Release tags, never commit SHAs.** Use the floating major (`@v7`) where the
  publisher keeps it current, so patches arrive on their own, and the exact
  release (`@v1.1.0`) where it does not. zizmor's `ref-pin` policy
  (`.github/zizmor.yml`) enforces a ref, and CodeQL's `actions/unpinned-tag`
  query is excluded for the same reason.
- First-party `duplocloud/*` actions are used at `@main`.
- **Verify, don't guess.** Before adding or bumping a pin, check the latest
  release: `gh api repos/<owner>/<repo>/releases/latest --jq .tag_name`.
- A version written as a plain string (a tool `version:` input, a default
  Python version) gets a `# renovate: datasource=... depName=...` comment on
  the line above it, so Renovate can see it
  (`.github/actions/renovate/config.json`).

## In-repo actions and workflows

- Reference this repo's composite actions and reusable workflows with `$/`
  (`uses: $/.github/actions/setup`). It resolves to the running commit with no
  checkout, so a pull request tests its own copy.
- Check out and install through `$/.github/actions/setup`. It mints the GitHub
  App token from `vars.GH_CLIENT_ID` and `secrets.GH_APP_KEY`, limited to
  `contents: read` unless the job passes `contents: write`, and falls back to
  the job token on a fork, where secrets are absent.

## Security

- `permissions: contents: read` at the top of every workflow; each job asks
  for anything more in its own block. A called workflow gets no more than its
  calling job grants.
- `actions/checkout` always sets `persist-credentials: false`.
- Pass secrets to a called workflow by name. `secrets: inherit` only where the
  callee reads environment-scoped secrets, with a zizmor ignore comment.
- Never `echo` a secret or put one in a step name or output.

## Runners

- `runs-on: ubuntu-26.04`, never `ubuntu-latest`.

## Reports vs failures

- **`quality.yml` reports.** Scanners and audits (CodeQL, zizmor, Grype,
  pip-audit, dependency review, TruffleHog, Scorecard) send findings to code
  scanning, annotations or the job summary, and never fail on a finding.
  Advisories land on code that has not changed, so a merge does not wait on
  them, and none of these is a required check.
- **Everything else fails.** Unit and integration tests, builds, and
  `lint.yml` (ruff, hadolint) fail on a problem only a change in this repo can
  cause or fix. Only these are required checks.
