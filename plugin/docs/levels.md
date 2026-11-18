# The L0–L3 Methodology Dial

Authoritative source for the dial's semantics is [`architecture.md`](architecture.md) §2.4. This doc is the friendly summary.

## TL;DR

Same skills at every level. The dial changes:

- The format of artifacts (prose vs. structured prose vs. Gherkin vs. full FFFlow)
- The test conventions required
- The audit gates enforced

A project declares its level in `.ffflow/config.yaml`. No config = L0.

## Level summary

| Level | Spec format | Test conventions | Gates enforced |
|---|---|---|---|
| **L0** | Informal prose, no structure required | Standard TDD in the project's existing framework | Lint + tests pass |
| **L1** | Structured prose, hexagonal layering, `<!-- INTENT?: ... -->` annotations | + Defect-driven spec entries | + CLAUDE.md audit, architecture audit |
| **L2** | Gherkin 6 scenarios with `Rule:` blocks, `@known-defect`/`@unverified-intent` tags | + Spec-first TDD, contract-anchored mocks | + Spec freshness audit, contract enforcement |
| **L3** | Gherkin + RID tags + `@property-based` | + Mutation testing, full FFFlow Total Specification | + Four quality gates (Structure, Correctness, Coverage, Maintainability) |

## What stays the same across levels

- The three-artifact model (Spec / Plan / Issues)
- The planning pipeline (`plan-chat → plan-breakdown → plan-capture`)
- The execution loop (`work-issue` follows red/green/refactor → spec update → gates → PR)
- The audit subsystem dispatching to per-type auditors
- Plan Mode discipline, PR-checkpoint protocol, local-validation gate

## What changes

### L0 → L1
- Adopt hexagonal architecture (`hexagonal-architecture` reference rulebook)
- Adopt defect-driven specification (`defect-driven-specification` reference rulebook)
- Enable `/audit --type claude-md` and `/audit --type architecture`

### L1 → L2
- Adopt Gherkin 6 (`writing-specs` reference rulebook)
- Adopt spec-first development (`spec-first-development` reference rulebook)
- Adopt contract enforcement (`contract-enforcement` reference rulebook)
- Enable `/audit --type spec` and `/audit --type char-tests`

### L2 → L3
- Adopt RID traceability (`rid-traceability` reference rulebook)
- Adopt total specification (`total-specification` reference rulebook)
- Adopt four quality gates (`quality-gates` reference rulebook)
- Enable `/audit --type rid` (wraps `specdrive audit`)
- Enable mutation testing in the stack
- Set `features.property_based_testing: true`, `mutation_testing: true`, `rid_traceability: true`, `four_quality_gates: true` in `.ffflow/config.yaml`

## Choosing a level

- **L0** — Forever-valid for projects that want lightweight discipline without ceremony. A solo project. A throwaway prototype that ended up sticking around. A codebase whose primary value is its existence, not its conformance.
- **L1** — When the project has more than one contributor or has outlived its first refactor. The cost of hexagonal layering pays back in testability.
- **L2** — When acceptance criteria are escaping into Jira/Notion/Slack and being lost. Gherkin gives behavior a home.
- **L3** — When the code is load-bearing — when a regression is expensive, when compliance asks for traceability, when the team is large enough that "the senior engineer remembered" is not a strategy.

Promote when the friction of the current level exceeds the cost of the next. Don't promote because it would be "more rigorous."

## Justfile maturity is a separate dial

Don't confuse FFFlow level with `justfile` (0–4). They answer different questions:

- **FFFlow level (L0–L3)**: how rigorous is the spec discipline?
- **Justfile maturity (0–4)**: how complete is the build interface? Declared as `justfile_maturity` in `.ffflow/stack.yaml`.

A project at FFFlow L1 might have justfile maturity 0 (just bootstrapped), 2 (deploying to prod), or 4 (polyglot monorepo). Pick each independently. See `justfile` for the maturity ladder.

## Stack assessment

`/stack-assess` reads your level and current state, then reports gaps. Use it when:
- Onboarding a project from another tool ("what would L2 require here?").
- Considering a level upgrade ("show me the diff to reach L3").
- Checking conformance after a long absence.

It's read-only — the actual changes happen via `/stack-init`.
