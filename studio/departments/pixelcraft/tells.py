"""PIXELCRAFT generic design tells: advisory, unscored.

The probe (`TELLS` in probe.mjs) reads the rendered page for the defaults an unguided build reaches for: gradient text,
violet gradients, glow halos, stripe-bordered cards, nested cards, emoji as icons, eyebrow labels and one default sans
for everything. Each one is a *question* for the person or agent who owns the design, not a defect: a project's own
art direction can choose any of them on purpose (a neon arcade HUD glows), so

  - tells never become metrics or findings, never enter the plan, and never change a score or the METHOD;
  - a tell the project chose is passed as `accept_tells: [{id, reason}]` and is listed as accepted, not raised;
  - verify lists tells resolved / persisting / new, for information; a new tell is never a regression.

The rules are GITCRAFT's own, informed by the published anti-pattern lists of Impeccable (Apache-2.0) and
Emil Kowalski's skills (MIT); see docs/design.md.
"""

RULES = {
    "gradient_text": ("Gradient text",
                      "A gradient painted through the letters is the most common tell of generated UI and costs legibility.",
                      "Carry emphasis with weight, size or the palette's one accent colour."),
    "violet_gradient": ("Violet/blue gradient surface",
                        "A purple-to-blue gradient on a hero, panel or button is the default palette of generated interfaces, not this product's.",
                        "Take the colour from the project's own world (its palette file, art bible or tokens); a flat surface in a chosen colour reads as decided."),
    "glow_shadow": ("Coloured glow used as depth",
                    "A zero-offset coloured halo reads as decoration, not light: nothing in the scene casts it.",
                    "Use a shadow with an offset and soft blur in a tint of the surface, or no shadow; keep glow for things that emit light in the world."),
    "accent_stripe": ("Thick coloured stripe on one side",
                      "A 3 px+ coloured border down one edge of cards, list items or alerts is a template habit.",
                      "Mark state or category with an icon, a label or the surface colour; if a stripe is part of the identity, accept it."),
    "nested_cards": ("Cards nested in cards",
                     "A padded, rounded, bordered box inside another one adds frames without adding structure.",
                     "Flatten the inner level: separate with spacing, a divider or a heading instead of a second container."),
    "emoji_icons": ("Emoji standing in for icons",
                    "Emoji render differently on every platform and never match the interface's stroke, weight or palette.",
                    "Use one drawn icon set (authored SVG in the project's style, e.g. made with VectorCraft) at one stroke weight."),
    "eyebrow": ("Eyebrow label above a heading",
                "A small tracked-out uppercase kicker over every heading is a template rhythm, and the heading usually says it already.",
                "Delete the label and let the heading carry the section; keep a label only when it carries information the heading does not."),
    "default_type": ("One default sans for everything",
                     "Nearly all text is set in a default UI face (Inter, Roboto, Arial, the system font): no typographic voice of its own.",
                     "Choose a display face that belongs to the product's world and pair it with a readable text face; keep the default only if the identity calls for it."),
}
ORDER = list(RULES)


def _accepted(accept):
    out = {}
    for a in accept or []:
        if isinstance(a, str): out[a] = ""
        elif isinstance(a, dict) and a.get("id"): out[a["id"]] = a.get("reason") or ""
    return out


def aggregate(captures, accept=None):
    """captures: probe captures with `tells`. Returns the advisory block stored in audit.json."""
    acc = _accepted(accept)
    rules, errors, seen = {}, [], 0
    for c in captures:
        t = c.get("tells")
        if t is None: continue
        if "_error" in t: errors.append(f"{c['screen']} @ {c['viewport']}: {t['_error']}"); continue
        seen += 1
        for rid, v in t.items():
            if rid not in RULES: continue
            r = rules.setdefault(rid, {"id": rid, "title": RULES[rid][0], "why": RULES[rid][1], "ask": RULES[rid][2], "count": 0, "where": [], "examples": []})
            r["count"] += v.get("count", 0); r["where"].append({"screen": c["screen"], "viewport": c["viewport"], "count": v.get("count", 0)})
            for ex in v.get("examples", [])[:3]:
                if len(r["examples"]) < 4 and (ex.get("sel"), ex.get("text")) not in {(e.get("sel"), e.get("text")) for e in r["examples"]}:
                    r["examples"].append(dict(ex, screen=c["screen"], viewport=c["viewport"]))
    found = [rules[k] for k in ORDER if k in rules]
    for r in found:
        r["screens"] = sorted({w["screen"] for w in r["where"]})
        if r["id"] in acc: r["accepted"] = acc[r["id"]] or "accepted by the project"
    return {"advisory": True, "scored": False, "captures_checked": seen, "rules_checked": ORDER,
            "raised": [r for r in found if "accepted" not in r], "accepted": [r for r in found if "accepted" in r],
            "accept": [{"id": k, "reason": v} for k, v in acc.items()], "errors": errors}


def compare(before, after):
    """Informational before/after (never a regression)."""
    b = {r["id"] for r in (before or {}).get("raised", [])}; a = {r["id"] for r in (after or {}).get("raised", [])}
    return {"resolved": sorted(b - a), "persisting": sorted(b & a), "new": sorted(a - b), "checked_before": bool(before)}


def markdown(T):
    if not T: return []
    L = ["", "## Generic design tells (advisory, not scored)", "",
         "Defaults that unguided builds reach for, read from the rendered page. Each is a question, not a defect: the project's own art direction wins. "
         "Accept a deliberate one with `accept_tells: [{id, reason}]`.", ""]
    if not T["raised"]: L.append(f"None raised on {T['captures_checked']} captures.")
    for r in T["raised"]:
        ex = "; ".join(f"`{e['sel']}`" + (f" \"{e['text']}\"" if e.get("text") else "") + f" ({e['screen']} @ {e['viewport']})" for e in r["examples"][:3])
        L += [f"- **{r['title']}** — {r['count']}× across {len(r['where'])} captures ({', '.join(r['screens'])}). {r['why']} *Ask:* {r['ask']}" + (f" Examples: {ex}." if ex else "")]
    for r in T["accepted"]: L.append(f"- Accepted: **{r['title']}** ({r['count']}×) — {r['accepted']}")
    if T.get("errors"): L.append(f"- Not checked: {'; '.join(T['errors'][:3])}")
    return L
