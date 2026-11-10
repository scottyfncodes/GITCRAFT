---
name: produce
description: "Run GITCRAFT": the one entry point for any project. Use when the person says "Run GITCRAFT" (or "run gitcraft on …"), pastes a prompt or idea, describes an app/game/site to build, links a GitHub repository (github.com/owner/repo), or points at an existing project and wants it continued, finished, updated, fixed or reviewed. Also for a whole game, app, site or asset pack in one request ("build a polished mobile-first game with sound, levels and deployment", "make an original platformer", "create a landing page with a brand", "ship a sound pack") and "run the production", "produce this", "continue the production", and "Run GITCRAFT report" (one project report across every department). GITCRAFT reads the project's state (new, partial, nearly complete, finished; game/app/site), picks the workflow, preserves existing work, asks only for the decisions that matter, plans every department in dependency order with parallel waves, gates every result, turns failures into fix work orders, re-verifies and writes the acceptance report. Not for a single asset (use the gitcraft skill and the department tool directly).
---

# One master prompt → a verified production

The person should not have to pick tools, order them, or coordinate departments. The Production
Director does that; you do the work only you can do (code, wiring assets in, the 2D ArtCraft tools)
when it hands you a work order, and you never claim anything it did not measure.

## "Run GITCRAFT" (start here, always)

`production_start {text: <exactly what the person said>, project: <the session's repository folder, if any>}`.
It works out the rest; the person never needs to know these tools.

- **A new idea** (a sentence, a spec, a pasted master prompt): the New Build below (optional Recon → Discovery → Decision Room).
- **"Run GITCRAFT report"**: `production_start` returns `status: "report"`: one read-only report built from the latest
  analysis of every department (health, scorecards, blockers, cross-department findings, P0–P3 plan, changes since the
  last report, next actions), saved timestamped as report.json/.md/.html. Direct tool: `production_project_report
  {project, refresh: quick|full|none}`. Show the person the summary and the report.html path. Reporting never edits code,
  builds, merges or deploys; never present a department with no data as measured. See `docs/report.md`.
- **A GitHub URL**: if it returns `needs_checkout`, attach the repository to the session if needed (`add_repo`), clone it where
  the result says, and call `production_start` again with `project`. Never ask the person to clone it.
- **Assets and nothing else** ("a jump sound and a coin sound", "a logo for my bakery", "a 3D model of a barrel for my game"):
  `production_start` returns `status: "direct"` with one step per named asset (the department tool and its parameters). Call
  each, look at or listen to the output, hand the files over. No production, scaffold, icon or credit is made around an asset.
- **An existing project**: it is read without being changed: `maturity` (partial / nearly complete / finished),
  `kind` (game / app / site / tool), `confidence`, and the evidence. `understanding` names the **assignment** (with the words
  that decided it), what is preserved, what "done" means and how it is proven. Say that reading back to the person in a line:
  | Assignment | Asked like | What happens |
  |---|---|---|
  | **continue** | "keep going", or nothing asked of a partial project | finish the unfinished features, most important first; never rebuild what works |
  | **complete** | "finish it", or nothing asked of a nearly complete one | genuine blockers and completion criteria, then final verification |
  | **feature** | "add dark mode" | only the named change and the fixes it needs (a finished project with nothing asked gets one question) |
  | **repair** | "it's broken", "the player falls through the floor", "won't load" | the defect and a regression check; nothing else |
  | **redesign** | "redesign it", "it looks dated" | the look only. PIXELCRAFT measures it before anything changes; `design.direction` decides the new look; the result must not regress against the baseline |
  | **gameplay** | "it's boring", "the controls feel floaty", "too easy" | the play only. PLAYCRAFT plays it before the change; `design.direction` names the cause; verified with the same probe after |
  | **polish** | "polish it", "make it better" | the same product executed better: both comparisons, no new features, no redesign |
  | **integrate** | "make an explosion sound and put it in the game" | the department makes the asset, it is wired in beside what exists; nothing replaced |
  | **audit** | "review it", or any question ("is this any good?") | measured and reported; nothing changes, no work order |
  | **rebuild** | "start over", "rewrite it in Phaser" | nothing until the person answers what may be thrown away and what carries over |
  An existing game's saves, levels, assets and engine stay as they are in every assignment unless the Decision Room approves otherwise.
- Existing projects get **no** scaffolding, redesign, migration, rebranding, HaveAnApp credit or new icon unless the person
  approves it in the Decision Room. `qa.preserve` measures this after the build: nothing deleted, secrets/CI/deploy
  untouched, game assets unchanged and every save key still used. Approved exceptions go in with `production_revise {overrides: {mode: {allow: [paths]}}}`.
- Show the person the Discovery Report's state, evidence and inventory in a few lines, and the Decision Room's recommendations.
  Approval (`production_decide {approve: true}`) is theirs. Then the loop below from **Run**.
- When you can read the repository's open issues (GitHub connection), pass them: `production_start {text, project, issues: [{number, title, labels}]}`.
- Deliver in the project's own way: its branch and PR conventions, its CI, its deployment. Give the PR link and, when it deploys,
  the live URL. After deploying, prove it from your shell: `python3 -m production verify-live <production> <url> --submit`
  (this release by commit provenance — pass `--commit <deployed sha>` — or the entry page modulo content hashes; every asset
  the live page loads; icons, Pulse, phone + desktop in Chromium). A login wall or an older deployment fails: fix the deployment,
  never the check. A host the sandbox cannot reach is UNVERIFIED, not a defect: report DEPLOYED · VERIFICATION INCOMPLETE, never
  READY and never NOT READY for it. Never say done or live without the report's evidence.
- **Direction first.** A new game, app or site, and any redesign, gameplay or polish pass, starts with the `design.direction`
  work order: write `direction.json` for this product before any code (`docs/direction.md`): one idea the look comes from, a
  palette with jobs and measured contrast, and for a game the loop, the feel numbers, a response for every action, the curve and
  the playtest questions. The gate refuses adjectives ("clean and modern"), placeholders and illegible palettes; it cannot judge
  taste, so look at what you build against it. The release report lists its playtest questions under **Needs a person**: pass
  them on, and never say a game is fun because its checks passed.
- **A tool** (CLI, library, script) gets no icon, credit or interface audit: it is built to its brief and `qa.tests` runs its own tests.
- New apps start from a starter (standards already wired in). Write `tests/gitcraft.features.json`: one check per planned
  feature, ending in what a person sees. `qa.features` runs them in Chromium.
- A backend (hosted Postgres) is set up only after the person approves `backend.provision`. Use the connected Neon account
  with separate development and production environments, put secrets only in the hosting env vars and a git-ignored `.env`,
  and write a `backend.json` with names only.

## The loop

0. **Idea / Recon (optional)** — when the person only wants to explore an idea, or asks "is this worth building?":
   `production_idea {text}` saves it (nothing is built). `production_recon {production, depth: quick|deep}` gives a bounded
   research work order: do it with your own web tools within the budget, then `production_recon {production, findings}`. Every
   claim cites the URL you opened or says `assumption`; never call a domain available without a lookup you ran; never invent a
   competitor, price or statistic. Then `production_promote` (build it) or `production_discard {park: true}`. A New Build can
   ask for Recon first with `production_plan {recon: "quick"}`. Recon is optional and never a reason to delay a build that was asked for.
1. **Plan** — `production_plan {prompt: <the whole master prompt, verbatim>, project: <the repo folder, if one exists>}`.
   This runs a read-only Discovery (it never writes to the project) and opens the **Decision Room**.
   Read the returned spec and `decision_room`, plus `DISCOVERY.md` (the 8-section Discovery Report).
   - If the interpretation is wrong, use `production_revise {overrides, reason}` (before approval it simply re-plans), e.g.
     `{"assets": {"levels": {"kind": "dungeon", "count": 4, "by_levelcraft": true}}}`, `{"quality": {"playcraft_min": 60}}`,
     `{"extra_tasks": [{id, department, action, params, depends_on, ship}]}`, `{"skip_tasks": ["qa.perf"]}`. A plan with `problems`
     cannot be approved. A criterion in `unmeasured_criteria` reports NOT PLANNED and the production cannot be READY.
   - A planned check that cannot run as planned is replaced, not skipped: an `extra_tasks` entry with
     `"replaces": "<task id>"` that is the same check (same department and action) measures the original's criterion.
     Skipping a criterion's only check leaves it NOT PLANNED. A pending revision shows `would_lose` / `would_measure`:
     tell the person what it does to the acceptance criteria when you ask them to approve it.
   - A check that failed without measuring anything (an execution or request failure, e.g. after a GITCRAFT fix)
     runs again with `production_run {retry: [task], retry_reason}`; a quality failure is never retried, it is fixed.
   - **Decision Room:** show the person the decisions in plain words: the question, your recommendation and the trade-off.
     These are the scope, the architecture, the design direction, the app icon (new, refine or keep), the engineering standard
     (personal, public or sensitive), the cost, the deployment, and the HaveAnApp credit for an existing app. Record their answers with
     `production_decide {answers}`, and approve with `production_decide {approve: true}` **only when the person has approved**.
     If they gave a complete master prompt and said to proceed, that is approval of the recommended defaults: say which defaults
     you approved. Discovery approval is not build approval. `production_run` refuses until the blueprint is approved.
   - The approved blueprint is the source of truth: don't reopen settled decisions. A material change later (scope, platform,
     features, authorisations, standard, icon) goes through `production_revise`. The build then pauses until the person approves it.
2. **Run** — `production_run {production}`. It runs every ready task on parallel workers and stops when
   the deliverable is ready, or when it waits on you (`awaiting_agent`) or on a person (`needs_approval`).
3. **Work orders** — for each task in `awaiting_agent`, open its `WORK_ORDER.md` (path in `production_status`).
   It says what to make, with which tools, the inputs (the hand-off: upstream files with roles and hashes;
   for the build, every integrated asset), the findings to fix, and the expected outputs.
   - Do the work in the project, following its conventions. Use every integrated asset.
   - Commit on a feature branch in the project as you go (never the default branch).
   - `production_submit {production, task, files: [absolute paths], notes}`. The submission is validated
     (files exist, open as their format, expected keys; a fix must actually change the project). A rejected
     submission keeps the work order open: read the reason, fix, submit again. An accepted one continues the run.
4. **Quality gates** — a failed QA gate (TestCraft, PLAYCRAFT, PIXELCRAFT, asset integrity, licences)
   becomes a `fix.<check>.r<n>` work order with the measured findings, then the same check re-runs on the
   modified project. Fix the cause the findings name; never weaken a gate, edit a measurement, or
   skip a check to get green. After `quality.max_rounds` the gate stays failed and the report says NOT READY:
   tell the person what remains and why.
5. **Approvals** — `needs_approval` (the app icon choice, deployment, replacing an existing asset) is the person's decision.
   For `icon.select`, show the person the comparison sheet (`concepts.html`: every concept at full size and at 180, 64 and 32 px,
   light and dark) and your recommendation. Approve with `choice` only when they've chosen; if they want changes, decline with their note
   and new concepts are requested. Never pick an icon silently.
   Ask them; call `production_approve` only with their answer. A deployment counts as live only with
   `evidence`: a passing check record that ran against the live URL. Without it, say "deployed, not verified".
6. **Report** — `production_report {production}`: every criterion with its measured evidence and the verdict.
   Report exactly that: READY only when the report says READY. Give the person the project path, the
   verdict, the scores, what was fixed, and anything blocked with its install command.

## Resuming

Productions persist (`production_list`). After an interruption, `production_run` again: passed work is kept
(while its outputs still match their hashes), interrupted tasks run again, and QA evidence measured before the
project changed is re-measured before release. Never start a new production for work that already has one.

## The app standards (every web app, site and game)

- **App icon:** draw the concepts and the master with VectorCraft/PhotoCraft (`icon.concepts`, `icon.master`). They are distinctive, read at 32 px,
  have no tiny text, screenshots or framework art, and are the app's own (no shared GITCRAFT look). Wire in `icons.snippet.json` exactly, and remove old icon references.
- **HaveAnApp credit:** a quiet "by HaveAnApp" byline marked `data-haveanapp` (`production/kit/haveanapp`: HTML, CSS and React) in a footer,
  an About or Settings screen, or a title or pause screen. It is never in the icon, and linked only to the verified URL in `attribution.json`.
- **Engineering:** build to the approved profile. A personal app stays simple; public and sensitive apps get validation, error handling,
  pinned dependencies, auth and rate limits. `qa.standards` lists what it could not decide as review items: address them or say so.
- Docs: docs/app-standards.md.

## Rules

- One master prompt, verbatim, into `production_plan`; don't pre-chop it into tool calls.
- Don't run departments by hand for work the production covers; add an `extra_tasks` entry instead, so it is
  gated, recorded and integrated like everything else.
- Never write generated assets into another project; integration copies only into this production's project
  and never overwrites a different existing file without approval.
- No paid services, no merges, no production deploys without the person's explicit approval.
