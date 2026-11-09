# Creative Review

An advisory, evidence-cited judgement of a product against its vision. It adds what the measuring departments
cannot do: someone looks at the rendered product and asks whether it delivers what it promises, what genuinely
works, and what the biggest opportunities are, including ones beyond the stated vision.

```
production_vision   {project, action: draft|approve|show, fields, version, approved_by}
production_creative {action: pack, project, captures: [<playcraft out_dir>, <pixelcraft out_dir>]}  → pack.json + BRIEF.md
                    {action: submit, pack, review}                                             → history/creative/<project>/<id>/
                    {action: show, project}
python3 -m production vision draft|approve|show <project> [--fields f.json] [--version N --by "who"]
python3 -m production creative pack <project> --capture <dir> [--capture <dir>]
python3 -m production creative submit <pack.json> --review <review.json>
tests/test_creative.py
```

The `creative-review` skill drives it. It runs **only when a person asks**: a Production Report reads the latest
review and never starts one, and no GITCRAFT code calls a model.

## How it stays separate from scores and gates

| Rule | Enforced by |
|---|---|
| No score: no number, rating or points anywhere in a review | validator refuses score/rating/points keys; not in `scoring.RUBRICS`; not a department |
| Not a gate: never changes an acceptance criterion or the Director's verdict, never becomes a work order | `report.py`, `engine.py` and `scoring.py` never read it; test compares the technical report with and without a review |
| Not in the plan: stays out of P0–P3 and the technical top three | it is read after the plan is built; same test |
| Labelled: `observed_render`, `observed_interaction`, `source_analysis`, `hypothesis_playtest` | validator: "observed" needs a cited capture the reviewer listed as viewed; fun, engaging, satisfying, boring… only as a playtest hypothesis, each with how to test it |
| No deltas or trends | reviews are never compared or charted |
| Wording | "assessment against the vision", never "verdict" |

## The vision is a reference, not a constraint

`history/vision/<owner--repo>/vN.json`, append-only. A draft is prefilled from the README with its source and lists
what is not stated as open questions; approval is a new version made only on a person's word. Reviews against a draft
are allowed and labelled "unapproved draft" everywhere. A review judges how well the product delivers each clause,
and may propose opportunities beyond the vision: those are marked `beyond_vision` and always need approval, as does
anything that changes a mechanic, the identity, scope or audience.

## Evidence

The pack only indexes what departments already produced: PLAYCRAFT play frames and probe metrics, PIXELCRAFT
screenshots, and every department finding in the Production Report (so the review builds on them instead of
repeating them). Each item has an id and a SHA-256. Without captures a review can only be source-based. On submit,
the cited images are copied into the review's folder so the citations stay checkable.

## Staleness

A review is bound to the commit it reviewed, the vision version (and its hash) and the fingerprint of every cited
item. The report shows it as a current assessment only when all three still match; otherwise it says it is stale (or
unverified, without a checkout) and shows none of its content as current.

## In the Production Report

A dashed, clearly advisory "Creative opportunities" card after the executive summary (the assessment and the top
three opportunities, with their evidence labels and approval markers), and a full "Creative Review (advisory)"
section with the vision assessment, opportunities, strengths, the gameplay split and the captures it cites. The
technical top three, scores, gates and verdict are unchanged.

## Deferred

Fresh Eyes (an isolated second reviewer), new capture infrastructure, a Studio department wrapper and planted-flaw
fixtures. They are worth adding only if this version proves useful.
