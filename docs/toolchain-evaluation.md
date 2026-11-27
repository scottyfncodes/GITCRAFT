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

**Method (all stages).** Each run is one fresh headless Claude Code session (`claude -p`, the same model, the same
always-loaded GITCRAFT context except where the arm changes it) in its own throwaway copy. We record:
- cost, input and output tokens (input includes cache reads);
- tool calls, files read and wall time, from the session's own stream;
- diffs from git;
- tests from the project's own suite.

Samples are small (one or two runs per cell), so differences under about 10% are within run-to-run noise.

### Lean engineering pilot

pownow, two tasks, run in two interleaved rounds:
- **Baseline:** the previous global block, without the standard.
- **Lean:** the new block, with the standard.

The tasks:
- **Bug.** We seeded a regression in the shared `formatClock`: its negative-minute wrap was removed. It has 17 callers, and the
  existing tests don't catch it. The prompt is a user-style report ("leave time shows -1:-30 AM").
- **Small feature.** Show the total time away from home under "Home by" on the recommendation card.

**Measured**

| | Baseline (2 runs/task) | Lean (2 runs/task) | Change |
|---|--:|--:|--:|
| Cost, all four runs | $1.970 | $1.779 | −9.7% |
| Bug: cost per run | $0.583, $0.527 | $0.509, $0.477 | −11% |
| Feature: cost per run | $0.426, $0.433 | $0.385, $0.409 | −8% |
| Tool calls | 63 | 55 | −13% |
| Files read | 11 | 9 | |
| Lines added (code + tests) | 123 | 110 | −11% |
| Wall time | 658 s | 677 s | +3% |
| Full suite (684–687 tests), `tsc` | all pass | all pass | |

**Quality, from reading the diffs**
- Both arms found the root cause in all four bug runs.
- Both arms moved the wrap into one shared helper used by `formatClock`, `formatClockShort` and `formatWindowLabel`.
- Both arms also found and fixed a second, real latent bug the seeded one exposed: the calendar export's `icsLocal` writes
  a negative minute as a malformed time instead of the evening before.
- Both arms added regression tests every time.
- In round 1, the baseline also added a speculative wrap helper to the feature and exported a private function only to test
  it. The lean runs did neither.
- In round 2, the two arms' changes were nearly identical.

**Reading.** The saving is consistent but modest: about 10% after overhead, below the 15% target. Part of it is the smaller
always-loaded block, which every turn re-reads. The effect on behaviour is small and in the right direction, with no
regressions or loss of quality. The standard stays: it was approved for adaptation, it costs less context than what it
replaced, and it did no harm. Its own benefit beyond the context saving is **not proven** at this sample size. Per the
staged plan, this stage stops here; more runs would only narrow the error bars.

The first parallel run showed 2 UI-test timeouts in every copy, including unchanged code. Run one at a time, every suite
passed. The timeouts came from four suites competing for CPU, not from the changes.

### Graphify pilot

**Antlerboard's size justified the pilot.** It is above the threshold the audit estimated, about 300 source files or 50k
lines: 539 TS/TSX files, 63k lines, Next.js + Prisma, with many modules in `src/lib`.

**Graphify's own costs (measured)**
- Install: pinned `graphifyy==0.9.120` into an isolated venv in 4 s, 163 MB. The installed package matches the audited
  source commit; the only difference is one docs file.
- Index: `graphify update .` (AST only, no AI model, no network extraction) took 16 s cold. It produced 5,895 nodes,
  15,739 edges and 205 communities.
- Output: 7.9 MB (`graph.json` 6.6 MB, `GRAPH_REPORT.md` 30 KB).
- Coverage gaps: the 33 SQL migrations weren't indexed (that needs an extra dependency), and 3 pages were only partly parsed.
- Re-index: 7.1 s after a one-file change, 2.4 s with no change.
- Never done: no hooks, no `graphify install`, no committed graph (the output stayed git-excluded in the copy).

**Three navigation questions, each in a fresh session per arm** (ground truth read from the code beforehand; facts graded
automatically against it):
1. The trade-accept path, from the request to the roster changes and notifications (8 facts).
2. Cron authentication and the scheduled jobs (11 facts).
3. How keeper cost is computed and where that math lives (8 facts).

| Arm | Cost (3 questions) | Tool calls | Files read | Wall time | Facts correct |
|---|--:|--:|--:|--:|--:|
| Native (the repo as it is) | **$1.025** | 16 | 7 | 102 s | 26/27 |
| Native + architecture map (37 lines in `CLAUDE.md`) | $1.086 | 21 | 8 | 119 s | 27/27 |
| Graphify available, its own `CLAUDE.md` rule, no hooks | $1.064 | 20 | 10 | 108 s | 27/27 |
| Graphify, prompt tells the model to query it first | $1.121 | 19 | 5 | 121 s | 25/27 |

- **Unprompted, Graphify was never used:** 0 `graphify` calls in 3 sessions, despite the rule. The model greps instead. Only
  the hooks we declined would change that.
- **Told to use it, it made 9 `graphify` calls.** That cost 9% more than native and was slightly less accurate: it missed
  the cron fail-closed rule and the skipped keeper seasons.
- **The architecture map did not pay either.** Generating it once cost $1.23 and 181 s. Per question it cost 6% more than
  native. On this evidence it never amortises.

**Reading.** Antlerboard's code is well named and cohesive, so native search answers architecture questions accurately for
about $0.34 each. There is no net saving to amortise. Any number of repeated uses multiplies a per-question cost that is
already higher than native, while index upkeep and the graph's size add to it. Graphify, and the architecture map,
**do not meet the adoption bar**. Per the staged plan, testing stops here. A large repository with poor naming or
cross-language links might still behave differently; that is untested.

### Hallmark pilot

**Stage 1: Hallmark's gates compared with `ui-design` and PIXELCRAFT (read).** Hallmark defines about 90 gates in
`references/gates.md`. We compared each with three sources:
- the `ui-design` craft floor, motion and games references;
- PIXELCRAFT's measured checks (`docs/pixelcraft.md`);
- PIXELCRAFT's generic-design tells (`tells.py`).

- **Already covered (about 35).** Gradient text, violet gradients, glow as depth, side stripes, cards in cards, three equal
  icon cards, eyebrows, default type, mono costume, `vh` vs `dvh`, horizontal scroll, 45–75 character measure, touch
  targets, contrast, focus visible, reduced motion, animating layout properties, every control and view state, and emoji as
  icons. PIXELCRAFT measures most of them.
- **New and worth adapting (12).** They are concrete and checkable, and they don't impose a look, so they fit apps and games:
  1. Content hidden at rest that only JavaScript reveals: `opacity: 0` reveals that ship a blank page when a script fails.
  2. Fake success: a form or control that says "Sent", "Saved" or "Thanks" with no request behind it.
  3. Invented metrics, testimonials, logo walls or counts. Some projects already say this in their own `CLAUDE.md`.
  4. A focus ring that fades in instead of appearing instantly. Tooltip focus delay equal to hover delay.
  5. Auto-rotating content with no pause on hover or focus, and no pause control.
  6. Input states that break: the border width shifts between states, the focus ring is built from `border`, an input is
     taller or shorter than the button beside it, or disabled is shown by opacity alone.
  7. A button label or primary nav link that wraps at any width from 320 to 1920.
  8. Two `position: sticky; top: 0` elements that slide under each other.
  9. Text painted under another element (PIXELCRAFT checks covered controls, not covered text).
  10. Image grid tracks on bare `1fr`, and display headings without `overflow-wrap` and `min-width: 0`: the causes of overflow
      that PIXELCRAFT reports as outcomes.
  11. A decorative `<svg>` or `<canvas>` with neither `aria-hidden` nor a label. Directly relevant to game canvases.
  12. `loading="lazy"` on the largest image, and autoplaying video that isn't `muted`.
- **Not adopted (about 40): they would push products toward one look.** These are house rules for marketing pages, and many
  would fight our games' art direction:
  - bans on tracked-caps labels, eyebrows in any form, middle-dot separators and bounce easing;
  - "the named look" (cream paper, serif, terracotta);
  - section gaps of at least 120 px, at most 80 words per screen, hero geometry and `h2` of at least 40 px;
  - a CSS "stamp", and a build log that forbids repeating a layout;
  - the theme catalogue and genre routing ("games, kids, fun" → "playful").

**Stage 2: limited comparison (measured).** One run per arm, each in a throwaway copy outside every repository:
- **Arm A:** `ui-design`.
- **Arm B:** `ui-design` + Hallmark, pinned at `04977e1` and installed per-project. Its image generation, hook and installer
  scripts were removed, and no API key was set.

We captured each result at iPhone 13 (390×844) with Playwright and measured its touch targets, small text, overflow and
fonts.

| Task | Arm | Cost | Wall time | Tool calls | Result |
|---|---|--:|--:|--:|---|
| pownow: new "How POW NOW decides" screen | A | $2.22 | 328 s | 58 | Complete. Built on the app's tokens and face (Archivo), follows the project's design guardrails, 44 px entry link, no overflow or tiny text, 688 tests pass |
| | B | $2.96 (+33%) | 666 s (2×) | 92 | Complete. Very close in quality: sentence-case section heads, and it also covers the "can't call it" state. It moved the verdict thresholds into one table that the engine and the screen share (a sound refactor). It left a `.hallmark/log.json` in the repo. 687 tests pass |
| SCRAP TIDE: polish the Settings sheet | A | $1.89 | 292 s | 46 | Complete. It stays in the game's world (stencil heads, hazard stripes, brass slider knobs). Whole-row 56 px switches, 44 px sliders, and a thumb-reachable Done button. Every setting is kept; 524 tests pass |
| | B | $2.65+ | 1,117 s+ | 53 | **Did not finish:** the account's usage limit ended the run. The partial work builds and passes 524 tests and stays in the world (ship's-wheel knobs). It changed the game's tracked-caps "TAPE DECK" label to sentence case "Music tape", which is Hallmark's house rule acting against the game's identity |

**Reading.** On the evidence we have, Hallmark:
- costs a third more and takes two to three times as long per design task;
- produces work about as good as `ui-design` alone, slightly more complete on the new app screen;
- shows the homogenising pull we expected on the game, small but real;
- adds bookkeeping files to the project.

That is not "clearly improved quality" at an acceptable cost, so Hallmark itself **does not meet the adoption bar**. Its
value is the twelve new checks listed above. These are concrete and look-neutral, and they belong in `ui-design`'s craft floor
and, where measurable, as PIXELCRAFT checks. That adaptation needs separate approval. The second SCRAP TIDE run was cut short
by the usage limit, so this stage rests on three complete runs and one partial run.

## Outcome

| Tool | Result | Recommendation |
|---|---|---|
| Ponytail | Adapted. The global standard is in place, and always-loaded context fell by 32% | Keep. Re-measure on real work later; its behavioural effect beyond context is modest (about 10% cheaper, n = 2) |
| Graphify | Pilot stopped early: no net benefit on Antlerboard (+6% to +9% cost, no accuracy gain), and unused unless forced | **Reject.** Don't install it. Re-evaluate only for a large, poorly named or multi-language codebase |
| Architecture map in `CLAUDE.md` | Measured alongside Graphify: no saving on these questions | Don't add maps by default |
| Impeccable | Rejected at audit | — |
| Hallmark | No clear gain over `ui-design`; +33% cost and 2× time; homogenising pull on a game | **Rejected.** 10 of its 12 look-neutral checks are adapted into `ui-design` (one in part), 2 of them also as measured PIXELCRAFT checks (below) |

Graphify, generated architecture maps and Hallmark stay rejected (confirmed 2026-11-27).

The pilot copies, run streams and screenshots were deleted on 2026-11-27, after every finding above was recorded here.
No production app, deployment, infrastructure or global setting outside GITCRAFT's own managed block was changed, and no
third-party tool was installed.

## Hallmark's checks, integrated (2026-11-27)

The 12 look-neutral checks from the Hallmark comparison were reviewed one by one. A check was adopted only when it is:
- a defect in any product, whatever its style (a reliability, honesty or accessibility failure);
- not already covered by `ui-design` or PIXELCRAFT.

Nothing was adopted that prefers a look, a typeface, a convention or a default. The project's own art direction remains
the highest creative authority. Hallmark itself is not installed, no dependency was added, and nothing was added to the
always-loaded global instructions: the checks live in the on-demand skill references, which load only when UI is built,
and in PIXELCRAFT, which runs only when called.

| # | Check (Hallmark gate) | Decision | Where | Why |
|---|---|---|---|---|
| 1 | Content hidden at rest until a script reveals it (62) | **Adopted** | `ui-design` craft floor | A reliability defect: the screen ships blank when a script fails |
| 2 | Fake success: "Sent" or "Saved" with no request behind it (70) | **Adopted** | `ui-design` craft floor | Honesty; independent of style |
| 3 | Invented metrics, testimonials, logos or counts (46a) | **Adopted** | `ui-design` craft floor | Honesty. Some projects already ban it locally; now every UI build sees it |
| 4 | Focus ring that fades in; tooltip delayed on focus (15, 17) | **Adopted** | `ui-design` accessibility | Keyboard accessibility. A rendered transition is not measured reliably, so it is not a PIXELCRAFT check |
| 5 | Auto-moving content without pause (18) | **Adopted** | `ui-design` accessibility | WCAG 2.2.2 |
| 6 | Input states that shift or rely on opacity (39a) | **Adopted in part** | `ui-design` craft floor | Constant border width (no layout shift) and disabled shown by more than opacity are defects. "An input as tall as the button beside it" was **rejected** as a layout preference |
| 7 | Button or nav label wrapping at any width (49a) | **Rejected** | — | Whether a two-line label is wrong depends on the design; actual overflow and truncation are already measured |
| 8 | Two sticky elements sliding under each other (56) | **Adopted** | `ui-design` craft floor | A layout bug in any style |
| 9 | Text painted under another element (73) | **Adopted + measured** | `ui-design`; PIXELCRAFT `layout.text_unobscured` / `layout.text_obscured` | Objectively measurable: what is on top at the text's centre. PIXELCRAFT checked covered controls, not covered text |
| 10 | Grid `minmax(0, 1fr)` and `overflow-wrap` on display heads (50) | **Rejected** | — | A CSS technique for an outcome (overflow) that PIXELCRAFT already measures; prescribing the technique adds nothing |
| 11 | `<svg>`/`<canvas>` neither hidden nor named (33) | **Adopted + measured** | `ui-design` accessibility and games; PIXELCRAFT `a11y.graphics_named` / `a11y.graphic_unnamed` | WCAG 1.1.1. axe checks only `role="img"`, and has no canvas rule; game canvases are directly affected |
| 12 | Lazy-loaded largest image; unmuted autoplay (28a) | **Adopted** | `ui-design` craft floor | Defects in any style. Not a PIXELCRAFT check: load performance belongs to TestCraft |

**PIXELCRAFT measurement rules**

The two checks are scored metrics with findings:
- **Covered text:** `layout`, a major finding.
- **Unnamed graphics:** `accessibility`, a minor finding.

What doesn't count:
- **Covered text** counts only an opaque cover (a box with a background, media, or other text) at the capture's own scroll
  position. It excludes fixed or sticky chrome (as Hallmark's own rule does), an open dialog, a full-screen game canvas and
  text that cannot be hit-tested (`pointer-events: none`).
- **Graphics** counts only an `<svg>` or `<canvas>` of 24 px or more. It is named by `aria-label`/`aria-labelledby`, an svg
  `<title>`, a canvas's fallback text, or a named link or button around it; `aria-hidden` and `role="presentation"` mark it
  decorative.

**Method change.** Because the measurement changed, the method moved from `pixelcraft-1.0` to `pixelcraft-1.1`. A 1.0
baseline is re-audited rather than compared, and `history/pixelcraft/` is untouched.

**Regression coverage** (`tests/test_pixelcraft.py`):
- **Unit tests:** the metric values and the findings.
- **A rendered fixture page** (`tests/fixtures/pixelcraft/covered_graphics`). It contains:
  - text under an opaque box, which must be found and must name the cover;
  - text under fixed chrome, which must not be found;
  - a bare svg and a bare canvas, which must be found;
  - aria-hidden, `<title>` and `aria-label` graphics and a named button's icon, which must not be.

**Context footprint (measured).** The always-loaded context is unchanged by this integration (the global block and every skill description are untouched); see the table below. The
on-demand cost when a UI build loads the references grew by 1,559 bytes (about 390 tokens, estimated at 4 bytes per
token): `craft.md` went from 4,020 to 5,466 bytes and `games.md` from 2,553 to 2,666 bytes.

| Always loaded in every session | Before the evaluation | Final |
|---|--:|--:|
| GITCRAFT block | 3,094 tokens | 1,763 tokens |
| GITCRAFT skill descriptions | 1,599 tokens | 1,430 tokens |
| **GITCRAFT total** | **4,693 tokens** | **3,193 tokens (−32%)** |
| Whole one-turn session in an empty folder | 49,710 tokens | 48,207 tokens (after PR #95 it was 48,210, the same within run-to-run variation) |
