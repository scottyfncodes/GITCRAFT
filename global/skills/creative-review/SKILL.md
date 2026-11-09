---
name: creative-review
description: Run a GITCRAFT Creative Review, only when the person explicitly asks for one ("Run Creative Review", "creative review of this game/app", "is this product actually good / distinctive / delivering its vision"). An advisory, evidence-cited judgement of the rendered product against its vision contract, with opportunities (including proposals beyond the vision), earned strengths and, for games, observed play vs source analysis vs playtest hypotheses. It never scores, never changes department scores, the overall score, release gates, the Director's verdict, P0–P3 or the technical plan, and is never run as part of a normal Production Report.
---

# Creative Review

A model's judgement, done by you in this session, written to a strict schema and validated by GITCRAFT
(`production/creative.py`). Run it **only when the person asks**. A Production Report reads the latest review; it
never starts one.

## 1. The vision (a reference, not a constraint)

```
production_vision {project: "<repo>", action: "show"}
production_vision {project: "<repo>", action: "draft", fields: {promise, audience, context, identity, pillars: [...], differentiators: [...], non_goals: [...], success_signals: [...]}}
```

- Draft from what the project and the person actually say (README, docs, the person's words). Unstated fields stay
  open questions; never invent an audience or a pillar.
- A review against an unapproved draft is allowed and is labelled "unapproved draft" everywhere.
- `action: "approve"` only when the person has approved it in their own words (`approved_by` records who).

## 2. Evidence: reuse existing captures

The pack indexes what departments already captured. It never captures anything itself.

- Games: a PLAYCRAFT pass output folder (`playcraft_pass` writes `play/*.png`, `play_contact_sheet.png`, `play.json`).
- Apps, sites and game HUDs: a PIXELCRAFT audit output folder (`gallery/`, `screens/`, `contact_sheet.png`).
- If none exists for the current commit, run those departments first, on the current build. Without images, the
  review can only be source-based and cannot claim to have seen anything.

```
production_creative {action: "pack", project: "<repo>", captures: ["<playcraft out_dir>", "<pixelcraft out_dir>"]}
```

## 3. Look, then judge

Read `BRIEF.md`. **Open every image you cite** with the Read tool and list it in `coverage.viewed`. Then write the
review JSON (schema in the brief):

- `vision_assessment`: how well each clause is delivered (`delivers`, `gaps`), cited.
- `opportunities`: the few that matter most, tiered transformative / substantial / polish (at most 5 polish).
  Include opportunities beyond the vision when they are compelling: `beyond_vision: true`, `needs_approval: true`.
  Do not repeat findings the departments already report (they are listed in the brief); build on them instead.
- `strengths`: what genuinely works, with evidence, and what to protect. Never forced; `strengths_note` if none.
- Games: `gameplay.observed` (automated play: frames, probe metrics), `gameplay.source_based` (code and design data),
  `gameplay.hypotheses` (what only a person playing can answer, each with how to test it).
- Fun, engaging, satisfying, boring: playtest hypotheses only. Screenshots and probe metrics cannot show them.
- No scores, ratings or points anywhere. Say "assessment", never "verdict".

```
production_creative {action: "submit", pack: "<pack.json>", review: "<review.json>"}
```

A refused submission lists every problem: fix them; never weaken a claim's label to get it through.

## 4. Report

`production_project_report` (or the next production run) shows a current review as an advisory card near the top and a
full section. It is bound to the commit, the vision version and the evidence fingerprints: once any changes, it is
shown as stale, not as a current assessment. Tell the person what the review found that the departments did not, and
that every recommendation is advisory; proposals that change the vision, a mechanic, the identity or scope need their
approval before anyone builds them.
