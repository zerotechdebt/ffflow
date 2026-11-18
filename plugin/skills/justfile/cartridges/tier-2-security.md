# Justfile cartridge: Tier 2 — security # justfile-security compliance

## Purpose

Add Tier 2 justfile recipes — security scanning and compliance. Adopted when a project is deploying to production, handling sensitive data, or under regulatory requirements.

## Recipes

```just
# Vulnerability scanning (CRITICAL severity, fixable only)
vulns:
    <stack-specific scanner>

# License compliance check (fail on GPL/LGPL/AGPL in prod deps unless allowlisted)
lic:
    <stack-specific tool>

# Generate Software Bill of Materials (CycloneDX format)
sbom:
    <stack-specific tool>

# Environment health check (tools, versions, configuration)
doctor:
    <validate dev environment>
```

## Per-language implementations

The recipe bodies live in one file per stack under `tier-2-security/`. Load only the file for the stack you're activating — the concept (this file) stays language-agnostic.

| Stack | Detail file |
|---|---|
| Python | [`tier-2-security/python.md`](tier-2-security/python.md) |
| TypeScript | [`tier-2-security/typescript.md`](tier-2-security/typescript.md) |
| Java | [`tier-2-security/java.md`](tier-2-security/java.md) |
| Rust | [`tier-2-security/rust.md`](tier-2-security/rust.md) |

Adding a stack = add one file in `tier-2-security/`; do not edit this concept file.

## Rules

- **`vulns` runs on every PR in CI** (gates the merge).
- **`lic` runs on every PR in CI** (gates the merge for prod-dep changes).
- **`sbom` runs in CI on release builds** (artifact).
- **`doctor` is local-only** (helps new developers).
- **None of these go in `check-all` by default** — they're CI gates, not dev-loop fast checks.

## CI integration

`ci-gates` workflow includes (at `justfile_maturity` ≥ 2):

```yaml
  gate-security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: <stack install>
      - name: Vulnerabilities
        run: just vulns
      - name: Licenses
        run: just lic
```

This is a separate gate from the four-gate spec model — security/compliance is its own track. Failures block.

## Allowlists

For licenses, an allowlist file declares acceptable variants:

```
# license-allowlist.txt
GPL-2.0 with classpath exception
LGPL with linking exception
```

Match the stack's tool format. Audit the file as part of `/audit --type architecture` if it changes.

## Anti-patterns

- Suppressing vulnerability findings without an issue tracking the suppression. Each suppression has an expiry date.
- Permitting all licenses ("we'll deal with it later"). Pick the policy and enforce it.
- Running `sbom` on every commit. It's slow and the artifact is only needed at release.
- Skipping `doctor` for new developers. Ten minutes of "doctor failed → fix" saves an hour of "tests fail mysteriously."

## Friction addressed

- Vulnerabilities discovered at audit time, not at introduction.
- License surprises in legal review.
- Dev environment drift causing "works on my machine" issues.
