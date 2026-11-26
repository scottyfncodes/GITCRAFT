# Toolchain evaluation: third-party Claude Code skills (2026-11)

HaveAnApp evaluated four third-party Claude Code skills against GITCRAFT's own toolchain:
- **Ponytail:** minimal code.
- **Graphify:** codebase knowledge graphs.
- **Impeccable:** frontend design.
- **Hallmark:** frontend design.

The aim is a more capable and efficient ecosystem, not more tools. GITCRAFT stays the engineering and delivery authority.
PIXELCRAFT and `ui-design` stay the visual authorities, and PLAYCRAFT stays the game-experience authority. A third-party
tool is only ever a subordinate capability.

Each fact below is labelled:
- **measured:** we ran it;
- **read:** taken from the tool's source;
- **estimate:** our reasoning, not a measurement;
- **claim:** upstream's own number.

## Decisions (approved 2026-11-26)

| Tool | Decision | Status |
|---|---|---|
| Ponytail (MIT, `DietrichGebert/ponytail` @ `ebd8654`) | **Adapted.** Its principles are now GITCRAFT's engineering standard. Nothing from Ponytail is installed. | Done (below) |
| Graphify (Apache-2.0, `Graphify-Labs/graphify` @ `02c27dc`, PyPI `graphifyy` 0.9.120) | **Conditional limited pilot** on Antlerboard. On demand only: no hooks, no committed graph, no automatic indexing, no external extraction. | Pilot: [results](#graphify-pilot) |
| Impeccable (Apache-2.0, `pbakaus/impeccable` @ `2fc5e14`) | **Rejected** | — |
| Hallmark (MIT, `nutlope/hallmark` @ `04977e1`) | **Limited design pilot**, preferring to adapt its checks into `ui-design` and PIXELCRAFT rather than install it | Pilot: [results](#hallmark-pilot) |

Adoption needs one of three things, with no new regressions, security compromises, unnecessary dependencies or loss of
product quality:
- net token savings of about 15% or more after overhead;
- clearly better product or engineering quality;
- clearly less recurring maintenance or friction.

Upstream benchmarks never count as evidence.

## Audit findings (read: source inspected at the commits above, nothing executed)

**Ponytail**
- **Injected context:**
  - At every session start and compaction, a hook injects its rules (about 800 tokens, estimate) and a regex code map
    (up to 2,000 characters).
  - A SubagentStart hook injects the rules into every subagent.
- **Files and settings:**
  - It writes mode flags and a status-line script into `~/.claude`.
  - It tells the model to "proactively offer" a `settings.json` change.
  - It keeps a per-project cost/token CSV in `~/.config/ponytail/band/`, on by default.
  - An optional webhook can post every turn's row.
  - Its "band" mod can run `open`/`xdg-open`.
- **Benchmarks:** upstream claims −53% lines and −45% output tokens. An independent JetBrains test reportedly measured about
  15% less code. We only saw that in a search result, so it is unverified here.
- **Conflict with GITCRAFT:** "a vague request gets the smallest version" conflicts with GITCRAFT's product standard. The
  adaptation keeps minimalism to the implementation.

**Graphify**
- **Dependencies:** about 26 tree-sitter grammar packages plus networkx, numpy and rapidfuzz. Needs Python ≥ 3.11.5.
- **Default Claude install:**
  - an always-on `CLAUDE.md` block;
  - PreToolUse hooks on Bash, Grep, Read and Glob (10 s timeout each; a strict mode can block reads);
  - a SessionStart(compact) hook;
  - optional git post-commit and post-checkout hooks.
- **Skill size:** the `/graphify` skill is 51 KB.
- **Extraction:** code is parsed locally (AST, no model, no key). Docs and images go to subagents, or to Gemini when a
  Gemini key is set.
- **Telemetry:** none (the query log is opt-in). There is a hosted-service signup prompt in interactive terminals.
- **Security history:** CVE-2026-51385 (code injection through URL fetchers, 0.3.2–0.4.29), GHSA-pcc4-rvhr-2pr8 (host
  files read during indexing) and GHSA-g6c9-j4vm-mwq4 (Windows SMB coercion). All are fixed in the pinned version.
  Indexing an untrusted repository has repeatedly been an attack surface.
- **Output size:** its own example turns 21 KB of source into a 140 KB `graph.json`, and it says the token reduction there is
  "~1×".

**Impeccable**
- **Hooks:** SessionStart, PostToolUse on every Edit/Write (5 s) and Stop (a 30 s "deep pass"), in every project.
- **Native binary:** the launcher downloads an engine binary from GitHub releases on first run (SHA-256 checked against a
  manifest; whether it matches the source isn't verifiable).
- **Network:** anonymous "choice pings" on by default (`DO_NOT_TRACK` turns them off), account sync of critiques and
  design-health counts once signed in, plus update and staleness checks.
- **Overlap:** it duplicates `ui-design` and PIXELCRAFT almost entirely.
- **Verdict:** rejected on surface area, telemetry and overlap.

**Hallmark**
- **Shape:** one skill. The `SKILL.md` is 18 KB and the references are large (`gates.md` 39 KB).
- **Hooks:** none by default (an opt-in edit-time lint).
- **Network:** only `imagegen.mjs` (Together AI, only when `TOGETHER_API_KEY` is set).
- **Photos:** a 755-photo Wikimedia list (CC0 / CC BY / CC BY-SA, credit required).
- **Existing designs:** it refuses to touch one unless named.
- **Risk:** it maps "games, kids, fun" to a "playful" genre and deals directions from a theme catalogue, which could make
  our games look alike unless the project's direction wins.

## Engineering standard (done)

The standard lives in the global instructions (`global/CLAUDE.md`). `scripts/install-global.sh` installs it into
`~/.claude/CLAUDE.md`, so it applies in every project:
- reuse first;
- prefer existing dependencies and native capabilities;
- no speculative abstractions;
- check callers before changing shared logic;
- fix root causes;
- add regression tests;
- never trade away security, validation, error handling, accessibility or anything requested;
- keep the implementation simple, never the product's functionality, polish, personality, creativity or delight.

There are deliberately no line-count limits.

The same change wrote down the authority order and cut duplication from the always-loaded block. Paragraphs that repeated
the `produce`, `playcraft`, `pixelcraft` and `creative-review` skills became one-line pointers, and the `produce` and
`creative-review` skill descriptions got shorter. The rules those paragraphs carried stay in the skills, which load when used.

**Always-loaded context (measured).** Each figure is the total input tokens of a one-turn headless session (`claude -p`) in an
empty folder in a cloud session. The block and the skill listing are isolated by removing each one in turn. Every
measurement ran twice and the two runs matched within 2 tokens.

| | Before | After | Change |
|---|--:|--:|--:|
| GITCRAFT block in `~/.claude/CLAUDE.md` | 3,094 tokens (8,160 bytes) | 1,763 tokens (4,632 bytes) | −43% |
| GITCRAFT skill descriptions (6 skills) | 1,599 tokens | 1,430 tokens | −11% |
| **GITCRAFT always-loaded total** | **4,693 tokens** | **3,193 tokens** | **−32%** |
| Whole session baseline (system prompt, tools, everything) | 49,710 tokens | 48,210 tokens | −3.0% |

**How it reaches every session.** No new mechanism was needed:
- A session with GITCRAFT attached runs its SessionStart hook, which runs `install-global.sh` from the clone of `main`.
- An environment that uses `scripts/setup-env.sh` installs from `main` when its container is built.
- An existing runtime is told an update is available and applies it with `~/.gitcraft/gitcraft-update` after review.

## Pilot

Staged testing with early stopping. Each stage runs in throwaway copies of the repositories, with their git remotes removed,
under the session scratch folder. Nothing touches a production app, a deployment or infrastructure.

**Repositories (measured: tracked files at `HEAD` of a shallow clone, 2026-11-26)**

| Repository | Stack | Source (tracked) | Designation |
|---|---|---|---|
| Antlerboard | Next.js + Prisma, Vitest | 539 TS/TSX files, 63,169 lines, plus 33 SQL migrations and 5 Python scripts | Complex app: confirmed |
| SCRAP TIDE | Vite + TypeScript game, Python tools | 112 TS files and 26,066 lines, plus 71 Python tool files and 10,408 lines | Complex game: confirmed |
| pownow | Vite + React app with an API and server | 213 TS/TSX files, 31,335 lines, 64 test files | **Not a small utility.** It is mid-sized. It is used as the lean-engineering control, as approved, but its results are not "small project" results |

Pilot results are recorded in the sections below as each stage completes.

### Lean engineering pilot

### Graphify pilot

### Hallmark pilot
