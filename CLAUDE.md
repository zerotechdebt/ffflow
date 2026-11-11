# FFFlow — repository root

This repo is a Claude Code marketplace shipping two independent plugins: **fff** (`plugin/`; design in [`plugin/CLAUDE.md`](plugin/CLAUDE.md), [`plugin/docs/architecture.md`](plugin/docs/architecture.md)) and **ppp** (`ppp/`; design in [`ppp/CLAUDE.md`](ppp/CLAUDE.md), [`ppp/process.md`](ppp/process.md)). This file covers repo-level process.

## Layout

```
ffflow/
├── .claude-plugin/marketplace.json    # the catalog: lists both plugins; versions only itself
├── plugin/                            # fff (source: "./plugin")
│   ├── .claude-plugin/plugin.json     # fff manifest; fff's version
│   ├── docs/migrations.md             # migration ledger read by /fff:upgrade-ffflow
│   ├── tests/                         # unittest suite for fff skill scripts
│   └── CLAUDE.md                      # fff design (authoritative for fff skills)
├── ppp/                               # ppp (source: "./ppp")
│   ├── .claude-plugin/plugin.json     # ppp manifest; ppp's version
│   ├── CHANGELOG.md                   # ppp release history
│   ├── tests/                         # check.py unittest suite + fixtures
│   └── CLAUDE.md                      # ppp design (authoritative for ppp skills)
├── CHANGELOG.md                       # fff release history + catalog notes
├── README.md
└── LICENSE
```

## How we version

**A plugin's version lives in exactly one place: its own `.claude-plugin/plugin.json`.**
- fff → `plugin/.claude-plugin/plugin.json`
- ppp → `ppp/.claude-plugin/plugin.json`

Never put `version` in a `plugins[]` entry of `marketplace.json`. When both are set, plugin.json
wins silently, so a second copy can only drift and mislead.

**The catalog has its own version:** `metadata.version` in `marketplace.json`. It versions the
list, not the plugins:
- **minor** — a plugin is added or removed.
- **patch** — any existing entry changes (description, keywords, category, source).
- A plugin release on its own does not touch `marketplace.json`.

**Each plugin is semver'd independently, by content:**
- **patch** — additive or backward-compatible: new cartridges or recipes, restructured-but-equivalent
  content, doc fixes, new stack/language support, new check fixtures.
- **minor** — new skills, new user-facing capability, or a meaningful workflow addition.
- **major** — removing or renaming a skill, or breaking a documented interface (recipe names,
  `--type` values, config schema, PPP's bundle format or check rule codes).

**Always bump. This is mandatory, not hygiene.** Once a plugin.json carries a version, Claude Code
decides whether an installed copy is out of date by comparing that string. Users stay on their
cached copy until it changes. A change shipped without a bump never reaches existing installs.
(Only a plugin with no version anywhere follows the latest commit.) Every change to a plugin's
shipped files bumps that plugin's version, doc fixes included.

## Every release updates its plugin's ledgers

Versioning is only half the job. A release also has to tell **existing users and projects** what changed for them.

**fff:**
1. **`CHANGELOG.md`** (repo root) — for humans. Every fff release gets an entry.
2. **`plugin/docs/migrations.md`** — for `/fff:upgrade-ffflow`. Only **repo-affecting** releases get an entry: ones where an already-adopted project would be wrong or incomplete until something in it changes.

The test: *"If I upgrade the plugin and change nothing in my repo, is my repo now inconsistent with FFFlow?"* Yes → migration entry required. New skill that only reads existing artifacts, or a bug fix in a skill's own logic → changelog only.

**This is not optional bookkeeping.** The upgrade path is only as good as the ledger. A repo-affecting change shipped without a migration entry is invisible to every existing project forever — which is precisely the failure 0.4.0 exists to fix. Ledger entry schema and the full decision table live in `plugin/docs/migrations.md`.

Migration entry ids are permanent: never rename or reuse one, because unstamped repos duck-type against the whole ledger from 0.1.0 forward.

**ppp:** `ppp/CHANGELOG.md` only. PPP bundles are documents in each team's medium, with no repo state to migrate. A release that changes the bundle format says so in its changelog entry.

**Catalog:** a `metadata.version` change gets a line in the catalog note at the top of the root `CHANGELOG.md`.

**Process:** change a plugin → bump its plugin.json → its CHANGELOG (+ fff `migrations.md` if repo-affecting) → if `ppp/` changed, `python3 -m unittest discover -s ppp/tests` passes → if `plugin/` changed, `python3 -m unittest discover -s plugin/tests` passes → if `marketplace.json` changed, bump `metadata.version` and add the catalog note → one commit with all of it → push. No tags or release artifacts today; if that changes, document it here.
