# DESIGNCRAFT: game-design intelligence

DESIGNCRAFT reads a game repository, works out how the game is designed (its levels, missions, story,
characters, progression and difficulty) and explains where the design falls short and how to make it
better. For each significant weakness it writes three alternative designs. It scores the design out of 100
and shows the evidence, coverage and confidence behind every number.

It is a standalone product in the Craft ecosystem. The Python package is `gamedesign/`. It is called
`gamedesign` rather than `designcraft` because GITCRAFT already has a `designcraft` MCP server, which is
the ArtCraft page-layout app. The web app is published at `/designcraft/` on the GITCRAFT deployment.

```
python3 -m gamedesign assess <game-repo> --record --report report.md   # inspect, analyse, score, keep history
python3 -m gamedesign spec <assessment.json> <proposal-id>             # implementation-ready spec
python3 -m gamedesign history                                           # recorded runs
python3 -m gamedesign publish                                           # build the web app
tests/test_designcraft.py [--quick]                                     # 59 checks (browser included unless --quick)
```

DESIGNCRAFT needs only the Python standard library, plus Chromium/Playwright for the browser test.

## 1. Repository discovery (phase 0)

This is what was found before anything was built. Each item was checked in the code.

| Area | Finding | Decision |
|---|---|---|
| Ecosystem shape | GITCRAFT ships 7 ArtCraft MCP servers, MeshCraft/ForgeCraft (3D) and StudioCraft, which has 11 departments behind one contract (`studio/core/contract.py`: validated request → dependency check → action → hashed outputs → provenance). | DESIGNCRAFT follows the same ideas: it validates its inputs, says plainly when something is missing, and keeps a record of every run. It is **not** a 12th Studio department, because `tests/test_studio.py` pins the count at 11 and the brief says not to modify other products. |
| PLAYCRAFT | It plays the built game in Chromium and scores 10 categories with evidence levels (`verified / observed / inferred / not_tested`). Its discovery scanner (`studio/departments/playcraft/scan.py`) detects engine, genre and ~70 system signals. Its Game Quality History is in `history/playcraft/games/<owner--repo>/runs/*.json`. | **Reused, not duplicated.** DESIGNCRAFT imports `scan.py` and `genres.json` to get engine, genres and signals. It reads PLAYCRAFT runs as *simulated* evidence (`gamedesign/playcraft_bridge.py`). |
| PIXELCRAFT | It audits the rendered HTML UI. Its static site is published by `forgecraft/ui_server.py`. | DESIGNCRAFT stays out of UI quality. PLAYCRAFT's UI criteria (`px.text`, `mob.*`, `tech.*`) are not imported. |
| History | PLAYCRAFT and PIXELCRAFT keep committed, append-only histories, with "measured change only under the same method". | `history/designcraft/<game>/<run>.json` works the same way: a method hash and a content hash are stored, and each comparison is labelled *control*, *measured* or *method_changed*. |
| Deployment | Vercel project `gitcraft-3d` builds with `python3 forgecraft/ui_server.py --publish …` (standard library only) into `forgecraft/ui/dist`. | One step was added to `vercel.json`: `python3 -m gamedesign publish history/designcraft forgecraft/ui/dist/designcraft`. ForgeCraft's code was not changed. |
| Games available | The account's game repos keep their design as **TypeScript data**. ROCKSLIDE has `MISSIONS` (steps, requires, rewards) and `PADS`. UNDERWATCH has `JOBS`, case `CLUES/THREADS/ENDINGS`, `BARKS` and builder calls `b.person(...)`. TIDEBREAKERS has `ISLANDS`, `UPGRADES`, `MILESTONES` and the `FIRST_VOYAGE` chain. NIGHT-WATCH has `WAVES` and `ARCHETYPES`. PRIMORDIA has `ERAS` and `FORMS`. | The core of evidence collection is a parser that reads JS/TS data literals **without running any game code**. Five real games were assessed and committed as the demo history. |

## 2. Architecture

```
game repo (read-only)
   │  extract/repo.py      walk, read; never write or execute
   │  extract/jsparse.py   tolerant JS/TS literal parser → values with file:line
   │  + JSON data, Tiled (.tmj), LDtk (.ldtk), Ink (.ink), Yarn (.yarn), Markdown docs, test names, screenshots
   │  + PLAYCRAFT scan.py (engine, genres, signals)          ← reused
   ▼
evidence bundle ──► model.py  classify collections by shape/name/type → entities, links, limitations
                     GAME → WORLDS → LEVELS → MISSIONS → OBJECTIVES → ENCOUNTERS → CHARACTERS → STORY → PROGRESSION
   ▼
departments/  (deterministic analysis: facts are source_verified, judgements inferred)
   levelcraft  missioncraft  storycraft  progressioncraft  experiencecraft (reads the other four + PLAYCRAFT)
   ▼
alternatives.py   3 proposals per significant finding (conservative / ambitious / wild card), plus 3 per mission for the Lab
scoring.py        100 points in 8 categories; criteria; untested earns nothing; ceiling; coverage; confidence
history.py        append-only runs, method + content hashes, comparisons
report.py         Markdown assessment and per-proposal specs
site.py + web/    static web app (vanilla JS, hand-drawn SVG, no dependencies)
```

Principles, and where each one is enforced:

1. **Read-only.** `extract/` only opens files for reading and never runs a subprocess or game code. The CLI refuses to write an output inside the game repo. A test hashes the fixture before and after a run.
2. **Evidence collection is separate from interpretation.** `extract/` and `model.py` only collect and classify. Departments compute facts, then state a judgement.
3. **Deterministic analysis is separate from design judgement.** Each finding has `evidence[]`, where each fact carries its own level (`source_verified`, `simulated`), and a `level` for the claim about players. That claim level is `inferred` unless the finding is a factual defect, such as a dangling reference or a docs-vs-data contradiction.
4. **Everything is traceable.** Every entity keeps `ev = {file, line, symbol}`. The web app links each one to GitHub at the assessed commit.
5. **Nothing is invented.** A collection the model cannot classify is listed as *unclassified* and is not guessed at. A department with no data says so (`note`). Cast members inferred from recurring names are marked `inferred`.
6. **Reviewable changes.** Proposals and specs are documents. Refinements in the Lab are saved as new versions, and the original stays untouched. Nothing edits the game.
7. **Extensible.** A department is a module with `NAME, TITLE, CATEGORY, analyse(M, ctx)` registered in `departments/__init__.py`. A proposal generator is one function in `alternatives.GEN`.

### Evidence levels (phase 5)

| Level | Meaning | Source in DESIGNCRAFT |
|---|---|---|
| Source verified | Confirmed by the project's files | counts, values, missing references, doc/data mismatches |
| Simulated | Observed in automated play or a scenario | PLAYCRAFT `verified`/`observed` criteria and metrics (e.g. `time_to_play_ms`) |
| Playtested | Observed while a person played | not produced automatically; reserved for recorded human playtests |
| Inferred | Reasoned design assessment | every claim about how players will feel; every proposal's expected outcome |
| Untested | Not evaluated | scoring criteria whose data is missing |

### Scoring (phase 6)

Level 15 · Mission 15 · Narrative 15 · Progression & pacing 15 · Agency 10 · Difficulty 10 · Worldbuilding 10 · Variety & replay 10.

Each category is the mean of 4–7 criteria, each scored 0–1. An untested criterion scores 0 and raises the **ceiling** (the score the category would have if every untested criterion were perfect), so the shortfall shows up as lower **coverage**. Confidence is `high` only when automated play or a playtest backs a category with at least 80% coverage. Source evidence alone never gives more than `medium`. An empty repository scores 0 with a ceiling of 100. Having code does not earn points.

### Departments (phase 1) — what each one actually measures

- **LEVELCRAFT**: named places vs. mission destinations (unused space), occupancy grid over the playable extent (empty zones), mission routes measured from objective coordinates (travel spikes, forced return-to-hub legs), Gini of discoveries per place, landmarks and navigation aids, checkpoints vs. fail states (saving counts as recovery), variety of place kinds, Tiled/LDtk layers and objects.
- **MISSIONCRAFT**: objective verbs and their entropy, travel share, repeated structures (identical verb skeletons), thin missions, family balance, alternate solutions (`mode: any` with several targets, a choice of vehicles), optional objectives, reward vs. effort (CV, Spearman), fail conditions, the prerequisite graph (depth, dangling ids, cycles), escalation by unlock depth, dead-end missions, brief length.
- **STORYCRAFT**: the cast from data, builder calls, dialogue speakers, or recurring names (marked inferred); mentions, lines and missions per character; underdeveloped and one-scene characters; unattributed dialogue; broken story links; README counts vs. data counts; endings and scripted choices; story density across the campaign's thirds; missions that name no character; co-mention relationships.
- **PROGRESSIONCRAFT**: stage tables (waves, eras, levels) with step ratios, spikes, plateaus and new enemy types per stage. The first step and sentinel values such as `99` are excluded from spike detection. It also measures campaign income vs. total prices, missions per unlock, unlock structure, long-term goals and replay sources.
- **EXPERIENCECRAFT**: the player journey (missions in unlock order, with an *inferred* intensity estimate, story words and newly introduced verbs). It also looks for flat tension or no release, overlong guided chains, friction that compounds across departments, agency gaps, a story/gameplay split, the lack of signature actions, long runs of the same mission kind, and PLAYCRAFT's simulated findings.

### Design alternatives (phase 3)

There are 49 generators, one per finding kind. Each writes three proposals. Each proposal states: existing design, problem, why it matters, the change (concrete steps that name the game's own missions, places, characters, numbers and `file:line`), expected experience, complexity with its reason, trade-offs, and validation with a metric, its current value, a target and a method. Priority is impact ÷ effort. Wild cards are weighted 0.6 because they are speculative. The engine is rule-based design knowledge filled in with real content, so it is honest about being rule-based. For open-ended creative work, the Lab hands a proposal and its evidence to Claude Code ("Copy for Claude Code").

### Web app (phases 4, 7, 8)

Overview · Game map · LevelCraft · MissionCraft · StoryCraft · Progression · Experience · Design Lab · Reports.

The visualisations are hand-drawn SVG built from the game's data: the game-model graph, level layout with mission routes and an occupancy grid, the mission dependency DAG, a mission × verb variety matrix, reward vs. effort, cast presence, co-mention relationships, a story timeline, normalised stage curves with their exact values, economy (income vs. prices), progression trees, and the player journey.

In the **Design Lab** you pick a mission or a finding, read the original design (shown as read-only) and its weaknesses, compare up to three alternatives side by side, and refine one in a conversation. The refiner is rule-based and deterministic. It understands *simpler, bolder, keep X, phone, story / a character's name, validate, non-violent, accessibility, new players, experts*, says so when it does not understand, and keeps every version. You can save alternatives (stored in this browser), export a Markdown spec, export everything saved as JSON, or copy a prompt for Claude Code.

## 3. Results on five real games (committed in `history/designcraft/`)

| Game | Score | Ceiling | Coverage | Why |
|---|---|---|---|---|
| ROCKSLIDE | 57 | 72 | 85% | Rich mission data. Main weaknesses: zero objectives with alternatives, no fail states, no story branches, 20 of 45 named places never used by a mission, and buying every unlock costs 5.1× the campaign's income. |
| UNDERWATCH | 43 | 73 | 70% | A strong case and endings system. Weaknesses: the jobs are short (8 of 9 have two objectives or fewer) and faceless, and the named suspects are barely written. |
| TIDEBREAKERS | 25 | 85 | 40% | Its design is a world and an economy with no mission data, so mission scoring is untested and the ceiling stays high. 14 crew/NPC characters are defined but barely written, and the guided first voyage is 13 steps. |
| PRIMORDIA | 18 | 91 | 27% | Stage curves only. `ERAS` escalates smoothly (the first step and the sentinel `mutationsToLeap: 99` are not counted as spikes); 21 forms have no unlock structure. |
| NIGHT WATCH | 12 | 95 | 17% | Waves and upgrades only. `WAVES` escalates smoothly after the intro wave; 17 upgrades have no structure. |

The low scores for code-driven games reflect how little design data DESIGNCRAFT could find, not a verdict on the games. The ceiling and coverage columns show this.

## 4. Known limitations

- Design that exists only as logic (AI, spawn code, physics) is not executed or simulated. It is visible only through PLAYCRAFT runs.
- The parser reads literals. Values computed by functions (`Array(n).fill().map(...)`) stay as markers, and the rows that depend on them drop out of curves.
- Classification is by shape and name. Unusual schemas can be missed: they are listed as *unclassified* in the Game map so a person can check them.
- Godot, Unity and Unreal scene formats are detected and counted but not read yet.
- Intensity in the journey is a model, labelled inferred. Proposal outcomes are inferred until a PLAYCRAFT pass or a playtest measures them.
- The Lab's refiner is rule-based. Saved alternatives live in the browser's localStorage, so they are not shared across devices.
- A proposal names real content, but its wording comes from design patterns per finding kind and is not written uniquely for each game.

## 5. Deployment

The Vercel build (`vercel.json`) runs the existing ForgeCraft publish step and then `python3 -m gamedesign publish history/designcraft forgecraft/ui/dist/designcraft`. To add a game:

```
python3 -m gamedesign assess /path/to/game --record   # writes history/designcraft/<owner--repo>/<run>.json
git add history/designcraft && git commit             # the next deploy shows it at /designcraft/
```
