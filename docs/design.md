# Interface design: Explore → Build → Audit → Refine

How GITCRAFT makes interfaces that look decided rather than generated, and why it does it with its own small skill
and an advisory PIXELCRAFT check instead of installing third-party design skills.

## Where design capability lives

| Phase | Where | Loaded |
|---|---|---|
| Explore: 2–3 genuinely different directions, same real screen, side by side; a person chooses | `ui-design` skill, `references/explore.md`, `scripts/directions.py` (stdlib comparison page) | only when there is no direction to follow |
| Build: tokens, type with a voice, layout, Mobile Safari rules, states, browser surfaces, refuse-by-default list | `references/craft.md`; motion in `references/motion.md`; games in `references/games.md` | only the phase's file |
| Audit: the rendered app, measured | PIXELCRAFT (`pixelcraft_audit`), plus its **generic design tells** (advisory, unscored, `docs/pixelcraft.md`) | when run |
| Refine: fix what was measured or seen, verify, stop | `ui-design` §5 + `pixelcraft_verify` | — |
| Taste judgement against the vision | Creative Review (only when asked) | — |

The skill is installed globally like the other GITCRAFT skills (`global/skills/ui-design/` → `~/.claude/skills/ui-design/`
by `scripts/install-global.sh`), so it works in every project. Always-loaded cost: its one-line description and a
six-line paragraph in the global instructions. Its SKILL.md (~80 lines) loads only when design work starts; each
reference loads only for its phase.

### Precedence

1. The person's words. 2. The project's own identity (its `CLAUDE.md` visual rules, art bible, style guide,
`DESIGN.md`, tokens, and anything marked retired). 3. An approved GITCRAFT vision / production identity.
4. The skill's defaults. An existing identity is refined, never replaced, unless the person asks for a redesign.
There is no GITCRAFT house style.

SCRAP TIDE (`docs/art-direction/STYLE-GUIDE.md`, `docs/brand/`, the `:root` tokens in `src/ui/styles.css`) and SNOW PATROL
(its `CLAUDE.md`, the Kessel art bible, tokens tested by `tests/art-direction.test.ts`, Inter and neon retired) already
document their identities; the skill sends every task to those files first and treats them as canonical. Their real
title screens raise no generic tells (validation below).

### Games

A game has two layers: the **world** (owned by its art direction, 3D through ForgeCraft/MeshCraft, feel through
PLAYCRAFT) and the **interface** (title, pause, HUD, menus), which this skill shapes inside the art direction's rules,
never as SaaS UI laid over the canvas (`references/games.md`).

## Evaluation of the candidates (November 2026)

Each was cloned and read (SKILL.md, references, scripts, installers, hooks, licence), nothing executed.
Stars and last push are from GitHub search at the time of review.

| Candidate | What it actually is | Licence · activity | Footprint and risk | Decision |
|---|---|---|---|---|
| **Impeccable** (pbakaus) | A 24-command design skill (shape, critique, audit, polish, bolder…), a "craft floor", PRODUCT.md/DESIGN.md context, and a 62-rule slop detector shipped as a Rust binary | Apache-2.0 · ~107k★ · daily | Skill folder ≈2.2 MB (1.1 MB font index, 564 KB browser script); a launcher that downloads a platform binary on first run; a per-edit PostToolUse + Stop hook written into `settings.json`; writes `.impeccable/`, PRODUCT.md, DESIGN.md into projects | **Adapt.** Best content of the set. Its craft floor and anti-pattern list informed `references/craft.md` and PIXELCRAFT's tells. Not installed: the binary download breaks the no-network sandbox, the hooks add context on every edit (token cost, conflicts with GITCRAFT's own gates), and its commands duplicate PIXELCRAFT/Creative Review |
| **Taste Skill** (Leonxlnx) | "Anti-slop" marketing-website generator: house rules, section dealers, photo library, a browser gate | MIT · ~112k★ · daily | 41 MB (stock photos, 1 MB checker script), needs Node 22 + Chrome; a Stop hook that runs `node gate.mjs` at the end of every session; forces one-section-per-screen, stock photographs, shader effects on "gaming" sites | **Reject.** Its rules are a house style for company landing pages and would overwrite a game's or app's identity (stock photos, randomised "moments"); the always-on Stop hook is exactly the global side effect to avoid |
| **Emil Kowalski's skills** | 18 small markdown skills, mostly motion (animate, review-animations, choreograph, performance, gestures) plus Swift/Expo/Sonner | MIT · ~55k★ · daily | Text only, no scripts or hooks | **Adapt (motion).** The best motion standard available; its values and rules are condensed into `references/motion.md` with credit. Installing all 18 would add 18 always-loaded descriptions that overlap each other and the new skill |
| **Oil UI** | Design-direction skill: explore directions, comparison page, screenshot review | MIT · ~3k★ · active | Chinese-primary text; an update check that calls `ui.oiloil.org` and upsells the paid Pro edition; Python/Node scripts | **Adapt (Explore idea only).** "Directions differ on all but one axis", "start from something concrete", "the person chooses on one comparison page" shaped `references/explore.md` and `directions.py` (written new, standard library). Not installed: phone-home and freemium |
| **Stageshow** (Benji Taylor) | A React kit + skill for framed faux product UI in marketing stills and scripted demos | MIT · upstream site not reachable from this environment; reviewed through its Svelte port (`maven-ammar/svelte-stageshow`, which restates the skill) | A component library dependency (React or Svelte) | **Reject.** Marketing presentation, not product UI quality; GITCRAFT already composes store shots and trailers with DesignCraft, FilmCraft and CinematicCraft. Revisit only for an app-launch marketing page |
| **Dimensional Drawing** (enesozturk; the brief's `enesoztrk` URL is a typo) | Turns a component into an Apple-style monochrome dimensional spec sheet (+ a motion film) | MIT · ~2k★ · Oct 2026 | Text + templates; the film needs Playwright + ffmpeg | **Reject.** Documentation art, not better UI; no effect on what ships |
| **Brand Identity Skill** (fatihaydost) | Logo, type and palette sets measured (contrast, colour blindness, glyph coverage, font licences), compared as cards, then a guidelines kit | MIT · ~350★ · active | Python deps (fonttools, uharfbuzz, skia-pathops) fetched via uv; scrapes competitor sites | **Reject (overlap).** GITCRAFT's production already owns identity (`foundation.identity` with VectorCraft) and icons (App Icon Studio with measured small-size clarity); Explore covers side-by-side choice. Its font-licence check is worth revisiting if fonts become a recurring problem |
| **Awwwards MCP** (INSANE0777) | MCP server that searches Awwwards, captures and "recreates any site section by section" | MIT · ~530★ · active | 109 MB repo, Playwright + ffmpeg; needs network (blocked in GITCRAFT's sandbox); its own docs limit use to "personal, non-commercial inspiration" | **Reject.** Recreating award sites conflicts with originality and with each project's identity; terms of use and network needs rule it out for production |

No candidate is installed, so there are no new dependencies, services, permissions, hooks or recurring costs.

## Activation

- **Automatic, by relevance:** the skill's description matches design work ("design", "redesign", "polish", "make it
  look good", "looks generic", new screens, game HUD/menus). The global instructions name it once.
- **Not for:** logic, APIs, refactors with no visual change, single assets (the `gitcraft` skill and the 2D/3D tools).
- **PIXELCRAFT tells** run on every audit (`tells: false` to skip) and only ever inform: they never change a score,
  a finding, the plan or a verify verdict. `accept_tells` records a project's deliberate choices.

## Validation (this change)

- `tests/test_pixelcraft.py --quick`: the existing checks plus nine for tells (rules unit tests; all eight raised on
  `tests/fixtures/pixelcraft/tells_generic`; none on `tells_crafted`; accepted tells honoured with identical scores;
  never in metrics, findings, plan or regressions).
- Real games: built SCRAP TIDE and SNOW PATROL from `main` and audited their title screens at iPhone 17, iPhone 13 and
  desktop: zero tells raised on either (no false positives on two strong identities).
- Measurement blind spot confirmed: PIXELCRAFT scores the generic fixture 89.2 and the crafted one 86.3; the tells
  section is what tells them apart.
- `tests/test_global.sh`: the skill, its references and `directions.py` install at user level and the global
  instructions name it.
- `directions.py` checked by rendering a comparison at 1440 and 390 px (no page-level horizontal scroll; directions
  scroll inside their strip on phones).
