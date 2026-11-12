# The Production Director: one master prompt → a verified production

## Using it

Tell Claude Code what you want, in one message, as completely as you like:

> Build a polished, mobile-first, original game with a complete gameplay loop, progression, original visual
> identity, sound, levels, responsive controls and production-ready deployment.

That's all you have to do. Claude follows the `produce` skill:

1. `production_plan` with your prompt. GITCRAFT runs a read-only Discovery and opens the **Decision Room**.
2. You read the few material decisions (each with a recommendation) and approve the blueprint: `production_decide`.
3. `production_run`.
4. Each work order handed to it (the code, wiring the assets in, the logo and icon concepts in VectorCraft), followed by `production_submit`.
5. Repeat until the acceptance report says READY, or a genuine blocker remains.

You'll be asked only what matters:

- **The Decision Room:** once, before anything is built. It covers scope, architecture, design and icon direction, the engineering standard, cost and deployment, each with a recommended default.
- **Essential questions:** rare, because most choices have a safe default, which the report lists as an assumption.
- **Approvals:** choosing the app icon from its concepts, deploying, or replacing a file your project already has.

At the end you get the project, and a report listing every acceptance criterion with its measured evidence.

What you never need to know: which departments exist, which order they run in, which can run at the same time,
how files move between them, or which checks decide "done".

## "Run GITCRAFT"

Say "Run GITCRAFT", with whatever you have:

```text
Run GITCRAFT: a calm breathing timer for my phone, just for me
Run GITCRAFT on https://github.com/you/recipe-box — finish it
Run GITCRAFT: add a dark mode toggle                (in a session on an existing project)
Run GITCRAFT: the save button is broken             (a repair)
Run GITCRAFT: it looks dated, redesign it           (a redesign: the look only, compared before and after)
Run GITCRAFT: it's boring after a minute            (a gameplay pass: the play only, compared before and after)
Run GITCRAFT: a jump sound and a coin sound         (assets alone: straight to the department)
Run GITCRAFT: is this ready to launch?              (a question is an audit: measured and reported; nothing changes)
Run GITCRAFT                                         (in an existing project: it picks up where the project is)
```

Claude calls `production_start` with your words and the project folder. You never need the internal tools.

1. **Where the project is.** It looks for a local path, then a GitHub URL (matched to a clone in the workspace by its git
   remote), then the session's repository. An uncloned URL returns the exact clone command. The sandbox has no network,
   so Claude clones it and calls again.
2. **What state it is in** (`production/maturity.py`, read-only). It reads `new`, `partial`, `nearly_complete` or `finished`, and
   `game`, `app` or `site`, each with **evidence** and a **confidence** level. The evidence comes from:
   - entry point and code size;
   - README feature lists and roadmap checkboxes;
   - TODO/FIXME and stubs;
   - references to missing files;
   - tests, deployment configuration and git history.

   The inventory separates **working** features (kept as they are), **unfinished** ones, **defects** and **optional improvements**,
   each with the file it was found in. A stub is unfinished work, never a reason to rebuild.
3. **What you asked for** (`production/understanding.py`). The request is read as an **assignment**, and the reading
   quotes the words that decided it:

   | Assignment | Runs as | What is different about it |
   |---|---|---|
   | continue, complete | continue, complete | the maturity's default when nothing is asked |
   | feature | update | one named change; scores are reported, not imposed |
   | repair | fix | a defect described in any words ("falls through the floor", "won't load"), plus a regression check |
   | redesign | update | the look only. PIXELCRAFT audits the project **before** the change (`baseline.pixelcraft`), `design.direction` decides the new look, and `qa.pixelcraft` is a before/after `verify` that gates |
   | gameplay | update | the play only, games only. `baseline.playcraft` plays it first; `qa.playcraft` is a `verify` with the same probe |
   | polish | update | both comparisons; no new features, no redesign |
   | integrate | update | the department makes the named asset; it is wired in beside what exists |
   | audit | review | "review it", or any question about the project; no work order is ever issued |
   | rebuild | update | one essential question first: what may be thrown away, what carries over. Approval is refused until it is answered |

   With no request, the maturity decides: partial → continue, nearly complete → complete, finished → one question
   ("what should change?"). The `understanding` in the result carries the current state, the desired state, what is
   preserved, what "done" means and how it is proven; the same lines are in the Decision Room and every work order.

   A request for **assets and nothing else** is not a production: `production_start` returns `status: "direct"` with one
   step per named asset. A **tool** (CLI, library, script) is a deliverable of its own: no icon, credit or interface
   audit; `qa.tests` runs the project's own tests.
4. **The workflow:**

| Project | Workflow | Gates |
|---|---|---|
| new idea | optional Recon → Discovery → Decision Room → build → verify → deliver | everything in this document |
| partially built | continue: the unfinished features, most important first | QA bars + preservation |
| nearly complete | complete: genuine blockers and completion criteria, then final verification | QA bars + preservation |
| finished | update: only the requested change and the fixes it needs | loads, regression, preservation; PLAYCRAFT/PIXELCRAFT scores reported (advisory) |
| any | fix: the defect and a regression check | as update |
| any | review: TestCraft, PLAYCRAFT/PIXELCRAFT/DESIGNCRAFT and the standard measure it as it is | no build, nothing written to the project |
| existing game | as above, preserving gameplay, mechanics, saves and progression, levels, assets, art direction and engine | + game assets unchanged, every save key still used |

**Existing projects keep what they are.** By default there is no scaffolding, no redesign, no migration and no rebranding.
They get no HaveAnApp credit and no new icon: the Decision Room recommends `keep`/`leave` for each, and you can ask for them.
The engineering standard's findings in existing code are reported, not imposed. The build work order carries the inventory,
the save keys and the preservation rules.

**`qa.preserve`** compares the build against a baseline recorded in the production store at Discovery (the project itself is only read). It checks that:
- no existing file was deleted;
- `.env` and other secrets are untouched;
- CI, deployment and lockfiles are unchanged;
- for games, art, audio and levels are unchanged, and every save or progression key is still used.

An approved exception is added with `production_revise {overrides: {"mode": {"allow": ["assets/hero.png"]}}, reason}`. As a material change, it needs a new approval.

**GitHub issues.** When Claude can fetch the repository's open issues (the GitHub connection), it passes them to
`production_start {issues}`. Bugs join the inventory's defects and the rest become requests, done only if the blueprint
includes them. Without them, the Discovery Report says the issues were not read.

**Delivery** follows the project's own conventions: its branch and PR flow, its CI, its deployment. A deployment counts as live only with a check against the live URL.

**How "Run GITCRAFT" reaches a session, and its limits:**
- `scripts/setup-env.sh` (the cloud environment's setup script) installs from `main`.
- `scripts/install-global.sh` writes the instruction block into `~/.claude/CLAUDE.md` and installs the `produce` skill, whose description names "Run GITCRAFT". `tests/test_global.sh` checks both in a fresh HOME, and asks a signed-in headless Claude Code which tool "Run GITCRAFT" calls.
- The user-level SessionStart hook fast-forwards `~/.gitcraft/repo` from `main` **in the background**. A new GITCRAFT version is therefore served from the *next* session (or after `/mcp`), not the one that pulled it.
- `~/.gitcraft/runtime/.gitcraft-source` names the commit being served.
- A session where GITCRAFT was never installed (no setup script, no global install) cannot discover it. Run the setup script once (README → "Use GITCRAFT in every project").
- Open GitHub issues and the live site aren't read during Discovery (no network in the sandbox). Claude adds them when it has access, and the report says when they weren't checked.

## Going live

Every web project's Decision Room asks **where it goes live**:
- the project's own pipeline when it has one (recommended);
- Vercel (the connected account);
- GitHub Pages;
- or not at all.

You approve the deploy itself at release (`release.deploy` needs `deploy`). Claude deploys to that target, then proves it from its own shell (the tool sandbox has no network):

```bash
python3 -m production verify-live <production> https://your-app.vercel.app --submit
```

`verify-live` (`production/live.py`) checks the release by provenance and behaviour, not by file names
(`docs/release-verification.md` has the full policy):
1. **This release**: the deployment's commit (`--commit <sha>`, e.g. Vercel's `githubCommitSha`, or a commit meta tag in the
   live page) equals the project's HEAD; otherwise the live entry page must equal the released one once content-hashed
   asset names are masked (two builds of one commit legitimately produce different bundle names). A different commit, a
   different title or a login wall (Vercel deployment protection) is a BLOCKER; a page that differs with no provenance is UNVERIFIED.
2. Every same-origin file the **live** page references loads; files with stable names that ship verbatim are byte-identical.
3. Checks the deployed manifest and its icons at their sizes.
4. Checks the HaveAnApp Pulse script answers, when it was chosen or found by Discovery.
5. Opens the site in Chromium on a phone and a desktop: no page errors, no failed required requests, the byline visible. A
   third-party host the verifier cannot reach (proxy, DNS) or that answers 5xx is UNVERIFIED with its cause, never an app defect.

It writes `tasks/release.deploy/live-check.json` (status `ok`, `failed` or `incomplete`) and, with `--submit`, hands it to the
deployment gate. A deployment is recorded live only when it is `ok`; `incomplete` reads **DEPLOYED · VERIFICATION INCOMPLETE**.
The report then says **Delivered**, with the live URL.

TLS is always verified, and the check goes through the session's HTTPS proxy when there is one. Plain `http://` is refused, except a local test server with `GITCRAFT_LIVE_ALLOW_LOCAL=1` (tests only).

## Idea to delivery

One record per project (`production.json` in the store) carries it through every stage. `production_status` and
`production_list` show the stage and a one-line summary in plain words.

```
Idea ──► Recon (optional) ──► Discovery ──► Decisions ──► Approved ──► Building ──► Verified ──► Delivered
  │            │                 (read-only)    │ ▲                       │
  └─ parked / discarded          revision ◄─────┘ └── material change ◄───┘ (paused until approved)
```

| Stage | Tool | What happens | Code |
|---|---|---|---|
| Idea | `production_idea` | Saves any input: a sentence, a rough idea, a spec, a pasted master prompt, a GitHub URL or a project folder. Records a **brief** (objective, outcome, requirements, constraints), using only sentences the person wrote. Nothing is read or built. | `lifecycle.brief` |
| Recon | `production_recon {depth}` → `{findings}` | Optional. **Quick** (≤ 6 searches) or **Deep** (≤ 20). It's the agent's research work order, because the sandbox has no network. Sections: Reality Check, Competition Radar, Identity Check, The Zag, and a Recommendation (build, pivot or park, with uncertainties). The findings are validated before they're kept (see below). Writes `recon/RECON.md`. | `recon.py` |
| Discovery | `production_promote` (or `production_plan` for a New Build) | Read-only: it never writes to the project and never creates the project folder. It reads the project, the engines, the existing assets and icons, the tests and git, plus what can run on this machine. Writes `DISCOVERY.md`: understanding, existing resources, recommended approach, alternatives, risks, decisions needing input, the plan in waves, and the acceptance criteria. | `discovery.py`, `lifecycle.discovery_report` |
| Decisions | `production_decide {answers}` | **The Decision Room.** Material decisions only: scope, architecture (existing code is reused), design direction, app icon (new, refine or keep), engineering standard (personal, public or sensitive), cost, deployment, and HaveAnApp credit for existing apps. Each has a plain question, a recommended default, the options and their trade-offs. An answer that changes the spec re-plans (still read-only). An answer that isn't one of the options is refused. | `lifecycle.decisions` |
| Approved | `production_decide {approve: true}` | Freezes the **blueprint**: every decision's answer (unanswered ones take the recommendation), the tasks, the criteria and the authorisations, with a hash. It is the source of truth. Settled decisions can't be reopened from the Decision Room, and every work order carries them. A plan with problems or an unanswered essential question can't be approved. | `lifecycle.blueprint` |
| Building | `production_run` | Only an approved blueprint can be built: Discovery approval is not build approval. This is the engine described below. | `engine.run` |
| Verified / Delivered | | Verified: the release passed but the deployment isn't verified live. Delivered: every criterion passed, including a deployment checked against its live URL when one was asked for. | `lifecycle.stage` |

**Recon evidence rules.** Recon may not invent evidence:
- every finding has a basis (`source`, `verified`, `assumption` or `inference`);
- a `source` or `verified` finding must cite the URL it came from;
- a domain or name is only "available" with a `verified` lookup;
- competitors are named;
- the verdict is build, pivot or park, with its reasoning and uncertainties;
- going over the budget is refused.

Recon is never a barrier: promoting without it (or before it finishes) is allowed, and is recorded.

**Deviations.** `production_revise {overrides, reason}`:
- **Before approval**, it simply re-plans.
- **After approval**, a change to the scope, platform, features, assets, authorisations, engineering profile, icon or attribution is
  **material**. The build pauses (`revision`, and `run` is refused), and `production_decide {approve: true}` applies it.
  Every task whose definition didn't change keeps its finished work, anything downstream of a changed task is redone, and the
  blueprint version goes up. `approve: false` discards the change.
- A change to the quality bar only is applied without a new approval.

**Compatibility.** Productions made before the lifecycle existed have no `lifecycle` record and run as before.

**The app standards.** Every web deliverable plans the App Icon Studio chain (`icon.concepts` → `icon.select` (a person
chooses) → `icon.master` → `icon.derivatives`) and three measured checks:
- `qa.icons`
- `qa.attribution` (the quiet "by HaveAnApp" credit)
- `qa.standards` (proportionate engineering checks)

See [app-standards.md](app-standards.md).

## The lifecycle

| Stage | What happens | Code |
|---|---|---|
| 1 Intake | The prompt becomes a spec: deliverable, 2D/3D, platform and viewports, engine, genres, features, the assets each department makes, a quality bar, authorisations (deploy, replacing assets, merging and spending are never pre-authorised), measurable acceptance criteria, assumptions, and questions (`essential` only when there's no safe default). `overrides` correct any field. | `intake.py`, `rules.json` |
| 2 Discovery | The project is read without running it: engine, entry, build folder, existing assets (an existing `jump.wav` means no new jump sound), tests, docs, git. The departments report what is ready on this machine (Studio `studio_status`, and ForgeCraft's probe for 3D). | `discovery.py` |
| 3 Analysis | Tasks that can't run here are known before anything starts (`blocked_up_front`, with the reason and the install command). | `planner.readiness` |
| 4 Planning | Every intake criterion stays in the plan; one no task measures is listed in `unmeasured_criteria`/`warnings`, reports NOT PLANNED and blocks READY. A task graph: stage, owner, department action and request, dependencies, hand-off references, what ships into the project, the gate, resources and retries. Parallel waves are computed from it. It is validated before running: unknown dependencies, cycles, unknown actions, and requests a department would refuse are all reported as `problems`. | `planner.py` |
| 5 Foundation | Project folders (never overwriting anything); the visual identity (agent + VectorCraft), whose palette the effects are tinted with. | `builtins.scaffold` |
| 6 Production | Department tasks run concurrently (4 workers; at most 2 browsers and 1 Blender at a time), each in its own process. | `engine.run`, `executors.py` |
| 7 Integration | Every passed output that ships is copied into the project, hash-verified, with a `.license.json` sidecar. Two different files for one path is a conflict (failed, nothing copied). Replacing a different existing file needs approval. Then the build work order lists every integrated asset. | `builtins.integrate` |
| 8 QA | TestCraft smoke (and perf when the bar asks for it), PLAYCRAFT (games), PIXELCRAFT (anything with a UI), DESIGNCRAFT (games; advisory), asset integrity (opens and is referenced by the build), and licences (AssetCraft). | `planner.py`, `gates.py` |
| 9 Release | The final regression smoke on the exact build, then the release report. Any QA evidence measured on an older project state is re-measured first. Deployment needs approval, and is only "verified" with a passing check against the live URL. | `engine._release` |
| 10 Memory | `production.json`, `events.jsonl`, hand-offs, work orders, every department's `.studio.json`, and `REPORT.md`. A run can be resumed at any time. | `store.py`, `report.py` |

## Dependency graph: plan v1 and v2

Every production record stores `plan_version`. New productions are **v2**; records made before it have no version and are
**v1**. A revision re-plans with the version the record was created with, so an existing production never changes graph
underneath its finished work. The review-only workflow plans the same tasks in both versions.

```
v1  scaffold → identity ─┐
    scaffold → assets… ──┼→ integrate.assets → build → QA… → release.regression → release.report → release.deploy
    icon.concepts → icon.select (person) → icon.master → icon.derivatives ┘
v2  scaffold → identity (→ design-stage tasks, PR 4 hook) → build          (placeholders; consumes every asset, never waits)
    each asset → integrate.<asset>   (as soon as it passes; one integration writer at a time)
    icon chain (person) → icon.derivatives → integrate.icon.derivatives
    every integrate.<asset> → integrate.final → build.wire (agent) → QA… → release.regression → release.report → release.deploy
    backend.provision (approval) → backend.wire (agent; the build runs on a local mock until then) → build.wire
```

- **Code starts early.** The build waits only for the foundation (and, from PR 4, the approved design). It uses placeholders;
  `build.wire` (automated, no approval) wires every integrated asset and the approved icon into the app. QA measures that final,
  wired build, so the icon choice is off the code path and on the release path (`qa.icons` and the release depend on it).
- **Transactional integration.** `integrate.<asset>` stages every file next to its destination, verifies each SHA-256, journals
  the destinations and their backups, commits with `os.replace`, then rewrites `gitcraft.assets.json` atomically. A failure
  during the commit restores the previous valid state; after a crash, the engine's recovery rolls the journal back before the
  task runs again. `integrate.final` checks that the ledger, the files and the manifest agree and nothing staged is left.
- **An earlier production's manifest.** A project GITCRAFT made before already carries `gitcraft.assets.json`. Those entries are
  the project's, not this production's: planning records them (`inherited_assets`, read-only, before anything is integrated),
  and `integrate.final` and the ownership check expect the manifest to list them unchanged beside this production's ledger. A
  task integrated again replaces its inherited entries as a set, as `integrate` does. An inherited entry edited or removed
  still fails. A record planned before this was recorded recovers the entries from the Discovery baseline while the manifest
  is byte-identical to it and nothing has been integrated; otherwise the checks stay as strict as they were.
- **Disjoint ownership.** Integration exclusively owns `gitcraft.assets.json` and every file it committed. An agent submission
  that names one, or that changed one, is rejected and its work order stays open. Two tasks shipping different files to one path
  is an integration conflict: the second fails, naming both, and nothing of it is copied. In v2 the first file stays (v1 copied
  nothing); either way the final integration and the release are blocked until the conflict is resolved.
- **One replace_assets approval.** Replacing a file the project already had (not one integration wrote) needs a person. In v2
  the request is presented once, when every asset has settled, listing every file and its new content
  (`production_approve task=replace_assets`). It authorises exactly those files with exactly that content; any other overwrite
  asks again. Every replacement is recorded (`replaced` on the integration, the approval history on the record).
- **Real references.** `qa.assets` (v2) counts a reference only in code or markup with comments removed, or in a JSON file the
  code loads. `gitcraft.assets.json` never counts, in v1 or v2.
- **Unchanged.** Every acceptance criterion, gate and approval of v1 (blueprint, icon choice, infrastructure, deployment).
  A failed asset still blocks its criterion, the final integration and the release; in v2 it no longer blocks the code build.

Rollback: an engine without v2 support reads a v2 record's `depends_on` edges only, which is stricter and still correct;
re-plan an in-flight v2 production with `production_revise` after a rollback.

### Optional criteria, unavailable capabilities and ownership (plan v2)

- **Required by default.** Every acceptance criterion carries `required` and `source`: *stated* (named in the prompt),
  *standard* (a release standard GITCRAFT holds, e.g. loads everywhere, licences, the engineering standard) or *implied*
  (an extra GITCRAFT added from the quality bar: sound effects for a "polished" game, music that comes with sound, an
  original identity). Only implied extras can become optional, and only by a person's answer to the Decision Room's
  **Extras** decision (recommended: required). Asking to make anything else optional is a plan problem, never applied.
  Changing it after approval is a material revision.
- **Optional never blocks.** An optional asset's integration *settles* the final integration (it is waited for in any end
  state) and measures the asset's own criterion, never `asset_integrity`. If it is not delivered, the criterion reads
  `optional_missing`: the verdict can still be READY, and the report and release summary list it under
  "Optional, not delivered". A required criterion is unchanged: if it does not pass, the release is not READY.
- **Unavailable is not a defect.** A department that reports `blocked` (its runtime or capability is missing here) is
  marked unavailable. A required criterion it measures reads `unavailable` → INCOMPLETE (never READY, never NOT READY).
- **Routed to the owner.** A department whose own output fails its gate re-runs (same action, seed varied by
  `REWORK_SEED` per round, deterministic). When `qa.assets` finds a defective file that integration committed, the
  department that produced it re-runs, the file is re-integrated (transactionally, under its original producer), and
  `qa.assets` measures again. Anything else, or a file no department produced, is the agent's fix work order. Every
  rework and fix records `routed_to` and `routed_because`.
- **Bounded, then a person.** Two re-runs per owning department (`DEPARTMENT_ROUNDS`, D5). After that a required
  criterion becomes one `escalate.<task>` decision: approve for exactly one more re-run, or decline (the criterion stays
  failed). An optional one is recorded as not delivered instead of asking anyone. Changing department is a plan revision.
- **v1 records are unchanged**: no optional criteria, no routing, no escalation.

### Layered QA (plan v2)

A build that completed is not a product that was verified. Every check belongs to one of three layers
(`production/qa.py`); the layers are a view over the checks, not a second verdict or a second routing system:
failures go through the remediation path above (owner, optionality, bounded rounds, escalation) and the verdict is
still the acceptance criteria's.

| Layer | What it checks | Tasks | A failure goes to |
|---|---|---|---|
| **Department QA** | each deliverable before hand-off: the department's own checks, plus `deliverables` (the files integration will ship exist and validate, by ship role and format) | every production task, the build, build.wire | that department (re-run, seed varied); the agent for code |
| **Integration QA** | the assembled product: transactional integration, the final manifest, every integrated asset opens and is loaded by the build, licences, the icon wired in, the build loads with no missing file | `integrate.*`, `qa.assets`, `qa.licences`, `qa.icons`, `qa.smoke` | the department that made a defective file; the agent for wiring |
| **Product QA** | the finished product against the request, plus the evaluators | `qa.request`, `qa.features`, PIXELCRAFT, PLAYCRAFT, DESIGNCRAFT, `qa.perf`, `qa.standards`, `qa.preserve`, `qa.attribution`, `release.regression` | the agent (code) |

`qa.request` (criterion `request_fulfilled`, required, a release standard) reads the project's source, never runs it,
and makes no model call. **Objective** (BLOCKER): the entry page exists and names the product; every requested feature
with a necessary, machine-checkable signal shows it: requested sound → the build plays audio; accounts → a sign-in
surface; mobile → a viewport, and touch or pointer input in a game; accessibility → a page language and alt text on
every image. Only what the person stated counts: an extra GITCRAFT implied is never a missing-feature blocker.
**Advisory** (never blocks, never routed, never re-run): unrequested additions (audio nobody asked for, a password
field without accounts) and coherence suggestions (the product's name on its page, the identity palette in the styles,
leftover TODO or lorem ipsum text). In an existing project `qa.request` is advisory, like the engineering standard.

Every report (`REPORT.md`, `production_status` → `qa`) shows the three layers (passed / failed / incomplete / pending /
not run), one line — `BUILT · PRODUCT VERIFIED`, `BUILT · NOT VERIFIED (…)` or `NOT BUILT (…)` — and every finding
with its layer, criterion (and whether it is optional), severity (blocker, incomplete, optional, advisory), owner, who it
was routed to, evidence, resolution (resolved in round n, being fixed, open, retries exhausted, escalated, declined,
not delivered (optional), unavailable, unverified, listed) and retry / escalation status (n of the limit). Known limits:
`qa.licences` reports counts, not files, so a licence failure is still the agent's; `qa.request`'s signals are
necessary conditions, not proof a feature works (`qa.features`, PLAYCRAFT and PIXELCRAFT measure that). v1 records get
neither `qa.request` nor the `deliverables` gate.

## Task states

| State | Meaning |
|---|---|
| `pending` | Waiting for its dependencies (or for a retry) |
| `in_progress` | A department or built-in is working on it |
| `awaiting_agent` | A work order is out; Claude must do it and submit |
| `complete` | The tool finished and its outputs validated. Only the gate decides what happens next (`complete` never means done) |
| `passed` | The gate held: dependent work may start |
| `failed` | The gate or the department failed. `failure` says which: `quality` (measured problem → remediation), `execution` (crash/timeout, retried first), `request` (bad request, never retried), `handoff`, `conflict` |
| `blocked` | It cannot run here (missing runtime, with the install command), or an upstream task failed (`blocked_by`) |
| `needs_approval` | A person must decide (deploy, replacing assets) |
| `skipped` | Declined by a person, or superseded |

The production's own status is one of `planned`, `needs_input`, `running`, `in_progress`, `awaiting_agent`, `needs_approval`, `passed` (`passed_not_deployed` / `passed_deploy_unverified` when a deployment was requested), `failed` or `blocked`.

## Gates and remediation

A gate is a list of conditions. For a department task, `status_ok` means the department's own validation and
checks passed. `min` needs a measured value at or above the bar; a value that wasn't measured fails. `referenced`
means every integrated asset is used by the build. Agent submissions must have every expected file inside the
workspace, opening as its format, with the expected JSON keys. A fix must actually change the project.

When a QA gate fails, the engine:

1. Creates `fix.<check>.r1`, a work order listing the measured findings (failed checks, PLAYCRAFT's plan, PIXELCRAFT's findings) with links to the evidence.
2. Creates `<check>.r1`, the same check depending on that fix. Dependents now wait on the re-verification.
3. Stops after `quality.max_rounds` rounds (2 standard, 3 polished). The check stays failed, the release is blocked and the report says NOT READY.

A review (`workflow: review`) measures and orders no fixes: a failed check stays failed and the run ends with its verdict.

## Evaluation: artifacts, target and verdict

The rules live in `production/artifacts.py` and hold for every game, app and site:

- **Evaluation output is never source.** A folder named `gitcraft-out` or `.gitcraft-work`, or holding the marker file
  `.gitcraft-artifacts` (written into every production store and task folder), is skipped by change detection. Writing a
  report, a screenshot or `production.json` cannot make the project look changed, so it cannot start another round of
  checks. If the source really keeps changing with no agent submission in between, QA is re-measured at most
  `STALE_ROUNDS` (2) times; then re-measuring stops and the verdict is INCOMPLETE, naming the files that kept changing.
- **Evaluation output lives outside the project.** The store is `$GITCRAFT_PRODUCTION_HOME`, else
  `<first root>/gitcraft-out/production`, unless that is inside the evaluated project (in a cloud session with one repo, the
  repo is the only root). Then it is another root's `gitcraft-out/production`, or the isolated home
  `$GITCRAFT_HOME/productions` (writable in the studiocraft sandbox). Productions are found by id in any of these stores.
  Task output (every department's `out_dir`, work orders, evidence, `designcraft.json`) goes to `store.output_root(prod)`:
  the store itself, or, when a production's store is inside the evaluated project (one made before this rule, or opened
  with an explicit store there), `$GITCRAFT_HOME/productions/<id>-outputs`. The record stays where it is; nothing a
  department writes lands in the project, so DESIGNCRAFT, which refuses output inside a game, always runs, and its
  executor refuses such a path itself. The release report, status and `Run GITCRAFT report` read the output from there.
- **One target, by an explicit policy.** Smoke, feature checks, performance, PLAYCRAFT, PIXELCRAFT and the final regression
  all get `$target`. `evaluation.target` (an override) is `auto` (default: the built app when `package.json` has a build
  script and a bundler, else the project folder), `build` or `source`. The build folder is the bundler's `outDir`, else `dist/`.
  A missing build blocks those checks with the build command; they never fall back to the unbuilt source. The policy is in the
  plan's decisions and the report, and the release checks that every browser check measured the same folder. Structural
  review (DESIGNCRAFT, standards, preservation, asset folders) reads the source.
- **Every run ends with a verdict**, in `production_run`/`production_status` (`verdict`, `verdict_reasons`), `production.json` and
  `REPORT.md` (a "Why …" section). **READY**: every criterion measured and passed. **NOT READY**: a criterion was measured and
  failed, or is NOT PLANNED. **INCOMPLETE**: nothing failed, but a check could not run (blocked, for example not built), could not be
  verified (`unverified`: the sandbox could not reach a service), has not finished (the time budget ran out, or it waits for the agent
  or a person), or measured a project that kept changing. A criterion measured only by advisory tasks is `advisory` and never blocks.
- **Every report leads with a release summary** (`production/verification.py`; `release` and `release_status` in `production_status`):
  deployment status, functional verification, security/blockers, visual audit, unverified checks with their causes, advisories,
  and the release status line: READY, NOT READY, **DEPLOYED · VERIFICATION INCOMPLETE** (the URL serves this release, no blocker,
  mandatory checks unverified) or VERIFICATION INCOMPLETE. See `docs/release-verification.md`.

## Departments and their contracts

`production_contracts` lists every department in one shape: what it accepts, produces and requires, how success
and failure are reported, where outputs go, and how provenance and licences are recorded. The Studio entries are
read from the manifests, so they can't drift from the code. Executors:

| Executor | Who | Called through |
|---|---|---|
| `studio` | AudioCraft, LevelCraft, FXCraft, MaterialCraft, WorldCraft, AnimCraft, CinematicCraft, TestCraft, AssetCraft, PLAYCRAFT, PIXELCRAFT | `studio/cli.py --call run` (the department contract) |
| `forgecraft` | the 3D Department (ForgeCraft → MeshCraft) | `forgecraft/cli.py call generate …`, then `library_export` at integration |
| `designcraft` | DESIGNCRAFT game-design review | `gamedesign` CLI, loaded by path |
| `builtin` | scaffold, integrate, licences, release | `production/builtins.py`, `engine._release` |
| `agent` | Claude: code, integration, the 2D ArtCraft tools | work orders + `production_submit` |

ForgeCraft keeps the 3D Department. The Director gives it a brief and records the result; it never reimplements routing, Blender work or the engine check.

### Hand-offs between departments

| Request | Chain | Gate |
|---|---|---|
| A 3D model | ForgeCraft `generate` → its exports become the task's outputs (role `model`) → `integrate.assets` exports the library asset (`asset.id`) and lists every file in the manifest the build is handed | `status_ok`; `qa.assets` `referenced` (a model's .blend and record are `model_source`) |
| An animated character ("…a 3D model of a pirate, animated") | model → AnimCraft `autorig` (humanoid / quadruped / chain from the brief) → AnimCraft `animate` (ships the animated GLB) → TestCraft `animation` | each `status_ok`; props are never auto-rigged (autorig replaces an armature) |
| Voice lines | the script work order → AudioCraft `voice` (`lines` handed on by `$from`; plan validation checks a hand-off when it resolves) | `status_ok` |
| An ocean | WorldCraft `ocean` beside terrain and sky | `status_ok` |
| A trailer | CinematicCraft `title_card` + `capture` (the evaluated build) → `assemble` (with the music when there is music) | `status_ok`; criterion `asset_trailer` |
| A failed PLAYCRAFT gate | the fix work order carries PLAYCRAFT's plan and findings plus DESIGNCRAFT's proposals (DESIGNCRAFT runs first and stays advisory) | the re-verification |
| A failed PIXELCRAFT gate | each finding becomes one readable instruction (title, severity, evidence, fix) | the re-verification |

Built-in tasks are gated like department tasks (`status_ok`), so a partial integration failure cannot pass. Which departments judge an
existing project follows its kind (game, app, site or tool), read by `production/maturity.py` with its own confidence and evidence, shown in
the Decision Room (`kind`), and asked as an essential question when the reading is weak; the kind the person names wins.

A **tool** is a CLI, library, toolchain or MCP server: at least two tool signals (declared command-line entry points, `cli.py` /
`__main__.py` / `bin/` modules, shell scripts, MCP servers, a README that describes one), no web entry page, no web framework, and
nothing playable (no engine project files, and no page for a game loop to run in). A tool gets no PLAYCRAFT, DESIGNCRAFT, PIXELCRAFT
or smoke test, and its engineering standard skips the browser checks (`n/a`). Code that ships with a project but is not its product
(`tests/`, `fixtures/`, `starters/`, `templates/`, `examples/`, `vendor/`, `acceptance/`) gives no evidence for the kind and is left
out of the product checks of the engineering standard; a secret found there is a review item (confirm it is a fake), not a failure.

## Correcting the plan

`production_plan` takes `overrides`, deep-merged into the spec. For example:

- `{"quality": {"playcraft_min": 60, "max_rounds": 2}}` raises the gameplay bar and limits remediation to two rounds.
- `{"assets": {"levels": {"kind": "dungeon", "count": 4, "by_levelcraft": true}}}` asks for four LevelCraft dungeons.
- `{"extra_tasks": [{"id": "audio.boss", "department": "audiocraft", "action": "music", "params": {"mood": "tense"}, "ship": {"dest": "$project/assets/audio", "roles": ["music"], "formats": ["ogg"]}}]}` adds a task. Extra tasks are validated, gated and integrated like the rest.
- `{"skip_tasks": ["qa.licences"]}` drops a task (the skip is recorded as a decision). Acceptance criteria are never
  dropped: one that no remaining task measures reports **NOT PLANNED** and the production cannot be READY. To remove
  a requirement, change the spec that creates it instead (e.g. `{"quality": {"perf": false}}`), so the change is explicit.
- `{"extra_tasks": [{"id": "qa.smoke.dist", "department": "testcraft", "action": "smoke", "params": {...}, "replaces": "qa.smoke"}]}`
  stands an equivalent check in for a planned one that cannot run as planned. It must be the same check (same kind,
  department and action). It measures what the original measured (criterion, stage, advisory flag, gate and resources are
  inherited; a different criterion is refused), the original is skipped, and whatever depended on the original depends on
  the replacement. Nothing is inferred: an extra task without `replaces` measures only the criterion it names. Work and
  build plans and review plans both honour `extra_tasks`, `skip_tasks` and `replaces`.
- After approval, a revision that changes tasks is material and pauses the build. The pending revision shows its effect
  on the acceptance criteria before anyone approves it: `would_lose` (criteria no task would measure: NOT PLANNED),
  `would_measure`, `unmeasured_after` and `problems`. A revision with problems cannot be approved. Approving keeps the
  earlier approvals: the previous blueprint goes to `blueprint_history`, and approved, declined and applied revisions stay in
  `decisions` across re-planning.
- `production_run {retry: ["qa.designcraft"], retry_reason: "…"}` (CLI: `run <id> --retry qa.designcraft --retry-reason "…"`)
  runs a failed check again. Only a check that failed without measuring the project (an `execution` or `request` failure,
  e.g. one GITCRAFT itself refused before a framework fix) can be retried; a gate (quality) failure is refused, because it is
  fixed in the project by its fix work order. The earlier attempts stay in the task's history, the retry and its reason
  are recorded, and what failed or was blocked because of it runs again.

Request parameters can reference upstream results:

- `"$project/…"` is the project folder.
- `{"$from": "<task>", "role": …, "format": …}` is an upstream output's path.
- `{"$from": "<task>", "role": "palette", "json": "accent", "as": "rgb"}` is a value read from an upstream JSON output.

## Safety

- Everything runs inside the studiocraft sandbox: workspace roots, its state, the shared libraries, and no network. The sandbox now also reads (never writes) the code of the departments the Director delegates to: `production/`, `forgecraft/`, `gitcraft3d/`, `meshcraft/` and `gamedesign/`, as ForgeCraft's sandbox already did. The 3D Department's model cache is writable for the same reason.
- The production store and the project must be inside the roots (the store may also be the isolated home, and is never inside the project). Submitted files outside the roots are refused, and the guard refuses relative paths, so submit absolute ones.
- Integration never silently overwrites a file, and two deliverables can never ship to one path.
- Deploying, replacing existing assets, merging and spending are never authorised by the intake. A deployment without evidence is never recorded as live.
- One runner per production (a file lock). A second one is refused with a clear message.

## CLI

```bash
python3 -m production start "Run GITCRAFT: <anything>" [--project DIR]
python3 -m production verify-live <id> <url> [--submit]          # after deploying, from your own shell
python3 -m production idea "<idea>" [--project DIR]
python3 -m production recon <id> [--depth quick|deep] [--findings FILE]
python3 -m production promote <id>
python3 -m production plan "<master prompt>" [--project DIR] [--overrides JSON] [--recon quick|deep]
python3 -m production decide <id> [--answers JSON] [--approve | --decline] [--note TEXT]
python3 -m production revise <id> --overrides JSON --reason TEXT
python3 -m production discard <id> [--park]
python3 -m production run <id>            # run or resume
python3 -m production status <id>
python3 -m production submit <id> <task> --files /abs/a /abs/b --notes "…" [--run]
python3 -m production approve <id> <task> [--decline] [--choice ID]
python3 -m production report <id>
python3 -m production list | contracts
```

## Verification

- `tests/test_entry.py` (~1 min) covers "Run GITCRAFT": a new idea, a partial, nearly complete and finished app and an existing game
  (maturity, kind, evidence, confidence, inventory), intent routing, repository URLs with and without a clone, read-only Discovery,
  the existing-project defaults (no scaffolding, icon, branding or redesign), the essential question, the approval gate, preservation
  (deleted files, secrets, CI, game assets, saves) and the invocation wiring (skill, global instructions, the MCP tool).
- `tests/test_lifecycle.py` (~1 min) covers briefs, standalone Recon (evidence rules, budget, park and discard), Recon in a New Build, read-only Discovery
  (byte-identical project, no folder created), the Decision Room (answers re-plan, invalid answers refused, existing-app attribution choice),
  the approval boundary, the frozen blueprint, material and non-material revisions (pause, approve with preserved work, decline), legacy productions,
  the icon codec and checks, attribution, the standards profiles, and a real app production from icon concepts to delivered.

- `tests/test_production.py` (~1 min) covers intake, planning, validation, gates, store, lock and fingerprints, plus a real production through the sandboxed server: plan, run, idempotent resume, and redoing a task whose output was deleted.
- `tests/test_evaluation.py` (~20 s) covers the WAR-BALLOON evaluation failures: writing evaluation output never triggers another round (and real source churn is bounded), one target for every browser check under the source-vs-build policy, a store outside the game so DESIGNCRAFT runs and the game is untouched, and a READY / NOT READY / INCOMPLETE verdict with reasons for every run.
- `tests/acceptance_production.py` (~6 min) is the master-prompt run:
  - **Part A:** the Lantern Drift prompt, end to end. Interpretation, discovery, the Decision Room (refused before approval, then approved), the App Icon Studio (three VectorCraft concepts, a person's choice, the master, the icon set), the HaveAnApp credit and the engineering standard measured, department selection, ordering, measured parallelism, the palette → effects hand-off, integration of 27 assets, a real defect caught by TestCraft and a real PLAYCRAFT shortfall (54 against a bar of 55, then 63 after the fix work order), re-verification, stale evidence re-measured, release on the exact build, deployment refused without evidence, and resume.
  - **Part B:** a refused plan, a missing runtime (blocked and propagated), a failed department (retried, then failed), an invalid agent output, an integration conflict, overwrite protection, a run killed mid-production and resumed, and a quality gate exhausted (NOT READY).

## Direction first

Plan v2 decides before it builds. A new game, app or site, and any redesign, gameplay or polish pass, starts with the
`design.direction` work order: `direction.json`, written for this product, gated on what can be measured, and the
specification the build is held to. The release report hands its playtest questions to a person under **Needs a
person**; they are never counted as passed. Format, gate and a worked example: [direction.md](direction.md).

## Limits

- **The assignment reading is rule-based too.** It quotes its reason and the Decision Room's scope decision corrects it. A request that mixes jobs ("fix the crash and redesign the menu") is read as one job, the first that matches in the table's order (a repair before a redesign before a gameplay pass); say so in the Decision Room if that is wrong.
- **The direction gate measures completeness, not taste.** A direction can pass and still be a poor idea. Only looking at the build, PIXELCRAFT, PLAYCRAFT and a person can say.
- **The direction steers the build and the identity, not yet the departments.** Sound, level and effect tasks take their parameters from the prompt at planning time and run in parallel with the direction.

- **Intake is rule-based** (`rules.json`) and deterministic. It records why it chose each value, but it can misread an unusual prompt. Claude is expected to read the spec and correct it with `overrides`.
- **Code is the agent's job.** The engine can't write a game. It hands Claude a work order with every input and verifies the result by measuring the build.
- **The 2D ArtCraft tools can't be driven from inside the studiocraft sandbox**, so their work is a work order for Claude to run with those MCP tools. The returned files are validated.
- **Deployment verification needs a check that ran against the live URL.** The default sandbox has no network, so in a default session a deployment is recorded as unverified rather than live.
- **Scores carry the departments' own noise.** PLAYCRAFT reports its confidence and measured noise band; the gate compares the measured overall against the bar exactly.
