"""PIXELCRAFT measurement: turn the probe's rendered-page evidence into metrics and findings.

Every metric is computed from what the browser rendered (DOM geometry, computed styles, the element really hit at
a point, axe-core results, real hover/press/Tab interactions, scripted journeys). Each metric has a value in 0..1
for one area of the rubric (see rubric.py), the number of samples it saw, and an evidence kind:

  measured        DOM geometry / computed styles / interactions in the rendered page
  accessibility   axe-core rule results
  screenshot      pixels of the screenshots (screen comparison), or a visual judgement recorded by a person/agent
  source          CSS/source-level only (e.g. design tokens declared); never used to claim a visual result

Findings group every occurrence of the same problem (rule) across screens and viewports, so one defect that appears
on six screens is one finding with frequency 6, not six findings."""
import math, re, statistics
from collections import Counter, defaultdict

SEV = {"critical": 5, "major": 3, "minor": 2, "cosmetic": 1}


# ------------------------------------------------------------------ small helpers
def _gap(a, b):
    """Edge-to-edge distance between two rects [x, y, w, h] (0 when they touch or overlap) and the axis."""
    dx = max(b[0] - (a[0] + a[2]), a[0] - (b[0] + b[2]), 0); dy = max(b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3]), 0)
    return math.hypot(dx, dy), ("x" if dx >= dy else "y")


def _overlap(a, b):
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]); h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0, w) * max(0, h)


def _lum(c):
    def ch(v):
        v /= 255; return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True); return (la + 0.05) / (lb + 0.05)


def _dist(a, b): return math.sqrt(sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])))


def _sat(c):
    mx, mn = max(c[:3]), min(c[:3]); return 0 if mx == 0 else (mx - mn) / mx


def _clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))


class Capture:
    """One screen at one viewport, with index helpers over its elements."""
    def __init__(self, c, vp):
        self.raw, self.vp = c, vp
        self.screen, self.viewport = c["screen"], c["viewport"]
        d = c.get("dom") or {}
        self.els = d.get("els", [])
        # the profile's CSS size: on an emulated phone an overflowing page widens innerWidth, which would hide the overflow
        self.vw, self.vh = vp.get("width") or d.get("cw") or d.get("vw"), vp.get("height") or d.get("vh")
        for e in self.els:   # inside a fixed/sticky bar (tab bars, headers): positioned against the viewport, not the page
            par = self.els[e["p"]] if e.get("p") is not None and e["p"] < len(self.els) else None
            e["inbar"] = bool(par and (par.get("vr") or par.get("inbar")))
            if e["inbar"] and par.get("pos") == "fixed" or (par and par.get("fixedbar")): e["fixedbar"] = True
        self.mobile = bool(vp.get("mobile")); self.dom = d
        self.children = defaultdict(list)
        for e in self.els:
            if e.get("p") is not None: self.children[e["p"]].append(e)
        self.controls = [e for e in self.els if e.get("inter")]
        self.canvas_heavy = d.get("canvas_area", 0) > 0.55   # a game/canvas surface: the DOM does not describe what is drawn
        self.shot, self.full = c.get("shot"), c.get("full")

    def doc_rect(self, e):
        return e["r"]

    def where(self, e, **measured):
        return {"screen": self.screen, "viewport": self.viewport, "selector": e.get("sel") or e.get("tag"), "rect": e["r"], "fixed": bool(e.get("vr")),
                "label": (e.get("name") or e.get("t") or "")[:50], "measured": measured}

    def inline_link(self, e):
        """A link inside running text (WCAG 2.5.8 exempts it from target size)."""
        if e.get("k") != "link" or e.get("p") is None: return False
        par = self.els[e["p"]] if e["p"] < len(self.els) else None
        return bool(par and (par.get("tl") or 0) > (len(e.get("name") or "") + 15))

    def is_target(self, e):
        return e.get("inter") and not e.get("dis") and e.get("k") not in ("label", "region") and not self.inline_link(e) and e["r"][2] >= 6 and e["r"][3] >= 6


# ------------------------------------------------------------------ the metric collector
class Collector:
    def __init__(self):
        self.metrics = []      # {area, id, title, value, samples, evidence, screen?, viewport?}
        self.findings = {}     # rule id -> finding

    def metric(self, area, mid, title, value, samples=1, evidence="measured", **ctx):
        if value is None: return
        self.metrics.append(dict(area=area, id=mid, title=title, value=round(_clamp(value), 4), samples=samples, evidence=evidence, **ctx))

    def find(self, rule, *, category, area, title, severity, evidence, explanation, recommendation, cost=2, occurrence=None, impact=None):
        f = self.findings.get(rule)
        if not f:
            f = self.findings[rule] = dict(id=rule, category=category, area=area, title=title, severity=severity, evidence=evidence, explanation=explanation,
                                           recommendation=recommendation, cost=cost, impact=impact or SEV[severity], occurrences=[])
        elif SEV[severity] > SEV[f["severity"]]: f["severity"] = severity; f["impact"] = max(f["impact"], SEV[severity])
        if occurrence: f["occurrences"].append(occurrence)
        return f


def _simple(cap, e):
    """A simple control/box: one short label (and maybe an icon), not a rich card with blocks of content."""
    kids = cap.children.get(e["i"], [])
    blocks = [k for k in kids if (k.get("disp") or "").startswith(("block", "flex", "grid", "list-item")) and (k.get("t") or cap.children.get(k["i"]))]
    return len(blocks) == 0 and len((e.get("name") or e.get("t") or "")) <= 40 and e["r"][3] <= 72


# ------------------------------------------------------------------ VISUAL QUALITY
def spacing(cap, C):
    vals, offgrid = [], Counter()
    for e in cap.els:
        for v in (e.get("pad") or []):
            if v > 0: vals.append(v)
        if e.get("gap"): vals.append(e["gap"])
    # vertical gaps between stacked siblings (what the eye reads as rhythm)
    groups_even, groups, uneven = 0, 0, []
    for pid, kids in cap.children.items():
        kids = [k for k in kids if k["r"][3] > 4 and not k.get("vr") and k.get("pos") not in ("absolute",)]
        if len(kids) < 2: continue
        stacked = sorted(kids, key=lambda k: k["r"][1])
        gaps = []
        for a, b in zip(stacked, stacked[1:]):
            if b["r"][1] >= a["r"][1] + a["r"][3] - 1 and min(a["r"][0] + a["r"][2], b["r"][0] + b["r"][2]) - max(a["r"][0], b["r"][0]) > 0:
                g = b["r"][1] - (a["r"][1] + a["r"][3]); gaps.append(g)
                if 0 < g < 160: vals.append(g)
        # related siblings: the same tag + class signature, three or more stacked → the gaps should match
        sigs = Counter((k["tag"], (k.get("sel") or "").split(">")[-1].split(":")[0]) for k in stacked)
        sig, n = sigs.most_common(1)[0]
        if n >= 3 and len(gaps) == len(stacked) - 1 and all(g >= 0 for g in gaps):
            same = [g for (a, b), g in zip(zip(stacked, stacked[1:]), gaps) if (a["tag"], (a.get("sel") or "").split(">")[-1].split(":")[0]) == sig]
            if len(same) >= 2:
                groups += 1; spread = max(same) - min(same); med = statistics.median(same)
                if spread > max(4, 0.35 * max(med, 1)): uneven.append((cap.els[pid], same, spread))
                else: groups_even += 1
    on = [v for v in vals if v <= 2 or min(v % 4, 4 - v % 4) <= 1]
    for v in vals:
        if not (v <= 2 or min(v % 4, 4 - v % 4) <= 1): offgrid[round(v)] += 1
    if vals:
        frac = len(on) / len(vals); distinct = len({round(v) for v in vals})
        C.metric("spacing", "spacing.scale", "spacing values on a 4-px scale", _clamp((frac - 0.35) / 0.55) * 0.75 + 0.25 * _clamp(10 / max(distinct, 1)), len(vals),
                 screen=cap.screen, viewport=cap.viewport, detail={"on_scale": round(frac, 2), "distinct": distinct, "off_scale_examples": [v for v, _ in offgrid.most_common(6)]})
        if frac < 0.7 and len(vals) >= 8:
            C.find("spacing.off_scale", category="visual", area="spacing", title="Spacing does not follow a consistent scale", severity="minor", evidence="measured", cost=2,
                   explanation="Paddings, gaps and margins use many unrelated values, so the rhythm between elements looks accidental rather than designed.",
                   recommendation="Adopt a spacing scale (4/8-px steps: 4, 8, 12, 16, 24, 32) as tokens and replace one-off values with the nearest step.",
                   occurrence={"screen": cap.screen, "viewport": cap.viewport, "selector": None, "rect": None,
                               "measured": {"on_scale_share": round(frac, 2), "distinct_values": len({round(v) for v in vals}), "off_scale_values_px": [v for v, _ in offgrid.most_common(8)]}})
    if groups:
        C.metric("spacing", "spacing.evenness", "related elements evenly spaced", groups_even / groups, groups, screen=cap.screen, viewport=cap.viewport)
    for par, same, spread in uneven:
        C.find("spacing.uneven", category="visual", area="spacing", title="Uneven spacing between related elements", severity="major" if spread >= 8 else "minor", evidence="measured", cost=1,
               explanation="Items of the same kind in one list or stack are separated by different gaps, which reads as grouping that isn't there and makes the list look broken.",
               recommendation="Give the container one gap (flex/grid `gap`, or one margin rule for all items) instead of per-item margins.",
               occurrence=cap.where(par, gaps_px=same, spread_px=spread))
    # crowding: text touching the edge of its own box; excessive empty bands
    crowded, boxed = [], 0
    for e in cap.els:
        if not e.get("st") or not e.get("trect") or e["r"][2] < 20: continue
        if e.get("k") in ("checkbox", "radio", "input", "select") or e.get("media") or not _simple(cap, e): continue
        r, t = e["r"], e["trect"]
        left, right = t[0] - r[0], (r[0] + r[2]) - (t[0] + t[2]); top, bot = t[1] - r[1], (r[1] + r[3]) - (t[1] + t[3])
        if min(left, right, top, bot) < -1: continue   # text larger than its box: clipping/overflow, measured elsewhere
        boxed += 1
        if min(left, right) < 4 or min(top, bot) < 1: crowded.append((e, round(min(left, right)), round(min(top, bot))))
    if boxed:
        C.metric("spacing", "spacing.breathing", "text has room inside its box", 1 - len(crowded) / boxed, boxed, screen=cap.screen, viewport=cap.viewport)
    for e, h, v in crowded[:6]:
        C.find("spacing.cramped", category="visual", area="spacing", title="Text is cramped against the edge of its box", severity="minor", evidence="measured", cost=1,
               explanation="Text inside a filled or bordered box sits within a few pixels of the edge, which looks unfinished.",
               recommendation="Give boxed text at least 8 px horizontal and 4 px vertical padding (12-16 px for cards).", occurrence=cap.where(e, horizontal_padding_px=h, vertical_padding_px=v))
    content = sorted([e for e in cap.els if (e.get("t") or e.get("media") or e.get("inter")) and not e.get("vr") and not e.get("inbar")], key=lambda e: e["r"][1])
    bands = []
    bottom = None
    for e in content:
        if bottom is not None and e["r"][1] - bottom > 0.4 * cap.vh: bands.append((e, round(e["r"][1] - bottom)))
        bottom = max(bottom or 0, e["r"][1] + e["r"][3])
    if content: C.metric("spacing", "spacing.no_voids", "no unexplained empty bands", 1 - min(1, 0.5 * len(bands)), 1, screen=cap.screen, viewport=cap.viewport)
    for e, gap in bands[:2]:
        C.find("spacing.void", category="visual", area="spacing", title="Excessive empty gap between sections", severity="minor", evidence="measured", cost=1,
               explanation=f"A {gap}-px band with no content separates sections — more than 40% of the screen height — so users may think the page ended.",
               recommendation="Reduce the gap to the section spacing used elsewhere, or fill it intentionally (imagery, a section heading).", occurrence=cap.where(e, empty_gap_px=gap, viewport_height=cap.vh))


def layout(cap, C):
    d = cap.dom
    over = d.get("sw", 0) - cap.vw
    C.metric("layout", "layout.overflow", "no horizontal overflow", 0.0 if over > 1 else 1.0, 1, screen=cap.screen, viewport=cap.viewport)
    if over > 1:
        culprits = [e for e in cap.els if e["r"][0] + e["r"][2] > cap.vw + 1 and not (e.get("vr") and e.get("pos") == "fixed") and not e.get("fixedbar")]
        far = max([e["r"][0] + e["r"][2] for e in culprits] or [0])
        widest = min([e for e in culprits if e["r"][0] + e["r"][2] >= far - 2], key=lambda e: e.get("d", 99)) if culprits else None
        C.find("layout.overflow", category="visual", area="layout", title="Page scrolls sideways (horizontal overflow)", severity="critical" if cap.mobile else "major", evidence="measured", cost=1,
               explanation=f"The page is {d.get('sw')} px wide in a {cap.vw} px viewport: content is cut off and the whole page wobbles sideways when scrolled with a thumb.",
               recommendation="Let the offending element shrink (max-width: 100%, min-width: 0 on flex children) or scroll it inside its own container (overflow-x: auto).",
               occurrence=(cap.where(widest, page_width_px=d.get("sw"), viewport_px=d.get("cw"), overflow_px=over) if widest else {"screen": cap.screen, "viewport": cap.viewport, "measured": {"overflow_px": over}}))
    clipped = [e for e in cap.els if e.get("clip")]
    if clipped:
        C.metric("layout", "layout.clipping", "text not truncated", 1 - min(1, len(clipped) / 4), len(clipped), screen=cap.screen, viewport=cap.viewport)
        for e in clipped[:4]:
            C.find("layout.truncated", category="visual", area="layout", title="Text is truncated", severity="minor", evidence="measured", cost=1,
                   explanation="Content is cut off with an ellipsis or clipped; on phones important words (task names, prices) disappear.",
                   recommendation="Allow two lines (line-clamp: 2) for primary labels, or give the label the space the trailing controls take.",
                   occurrence=cap.where(e, content_width_px=e["clip"][0], visible_width_px=e["clip"][1]))
    else: C.metric("layout", "layout.clipping", "text not truncated", 1.0, 1, screen=cap.screen, viewport=cap.viewport)
    # alignment: left edges that miss a common edge by a few pixels
    def _in_row(e):
        par = cap.els[e["p"]] if e.get("p") is not None and e["p"] < len(cap.els) else {}
        return par.get("dir") in ("row", "grid")
    lefts = [e for e in cap.els if (e.get("t") or e.get("st") or e.get("media")) and not e.get("vr") and not e.get("inbar") and e["r"][2] > 30 and e["r"][0] >= 0
             and (e.get("disp") or "").startswith(("block", "flex", "grid", "list-item", "table")) and not _in_row(e)]
    if len(lefts) >= 6 and not cap.canvas_heavy:
        cnt = Counter(round(e["r"][0]) for e in lefts)
        popular = [x for x, n in cnt.items() if n >= 3]
        near = []
        for e in lefts:
            x = round(e["r"][0])
            if x in popular: continue
            # only against neighbours a reader compares: same container (parent or grandparent), stacked within 200 px
            fam = {e.get("p"), (cap.els[e["p"]].get("p") if e.get("p") is not None and e["p"] < len(cap.els) else None)} - {None}
            m = [o for o in lefts if o is not e and 2 <= abs(round(o["r"][0]) - x) <= 6 and round(o["r"][0]) in popular
                 and ({o.get("p"), (cap.els[o["p"]].get("p") if o.get("p") is not None and o["p"] < len(cap.els) else None)} & fam)
                 and min(abs(o["r"][1] - (e["r"][1] + e["r"][3])), abs(e["r"][1] - (o["r"][1] + o["r"][3]))) < 200]
            if m: near.append((e, x, round(min(m, key=lambda o: abs(o["r"][0] - x))["r"][0])))
        C.metric("layout", "layout.alignment", "elements align to shared edges", 1 - min(1, 3 * len(near) / len(lefts)), len(lefts), screen=cap.screen, viewport=cap.viewport)
        for e, x, p in near[:4]:
            C.find("layout.misaligned", category="visual", area="layout", title="Elements miss a shared edge by a few pixels", severity="minor", evidence="measured", cost=1,
                   explanation="An element's left edge is a few pixels off the edge most nearby content uses, so columns look ragged.",
                   recommendation="Align to the shared content edge (same container padding / grid line) instead of nudging with margins.",
                   occurrence=cap.where(e, left_px=x, shared_edge_px=p, off_by_px=abs(x - p)))
    # obscured controls
    obs = [e for e in cap.controls if e.get("obs")]
    if cap.controls:
        C.metric("layout", "layout.unobscured", "controls not covered by other elements", 1 - len(obs) / len(cap.controls), len(cap.controls), screen=cap.screen, viewport=cap.viewport)
    for e in obs[:5]:
        C.find("controls.obscured", category="visual", area="controls", title="A control is covered by another element", severity="major", evidence="measured", cost=2,
               explanation="Tapping the centre of this control hits a different element (often a fixed bar or floating button), so the control is hard or impossible to use.",
               recommendation="Reserve space for fixed/floating elements (padding-bottom on the scroll area equal to their height) or move the floating element.",
               occurrence=cap.where(e, covered_by=e["obs"]))
    # use of space: desktop column that ignores the width; phone gutters that waste it
    content = [e for e in cap.els if (e.get("t") or e.get("media") or e.get("inter")) and not e.get("vr") and not e.get("inbar") and e["r"][2] > 0]
    if content and not cap.canvas_heavy:
        x0 = min(e["r"][0] for e in content); x1 = max(e["r"][0] + e["r"][2] for e in content)
        width = (min(x1, cap.vw) - max(0, x0)) / max(1, cap.vw)
        if cap.vw >= 1200:
            # a centred column (~45-60% of a wide window) is a valid layout; a phone-width strip is not
            C.metric("layout", "layout.utilisation", "layout uses the available width", _clamp((width - 0.25) / 0.2), 1, screen=cap.screen, viewport=cap.viewport, detail={"content_width_share": round(width, 2)})
            stretched = [e for e in cap.controls if e.get("k") in ("button", "input", "select") and e["r"][2] > max(640, 0.6 * cap.vw) and not e.get("inbar")]
            for e in stretched[:2]:
                C.find("layout.stretched_control", category="visual", area="layout", title="Controls stretch across the desktop window", severity="minor", evidence="measured", cost=1,
                       explanation=f"A {e['r'][2]}-px-wide {e.get('k')} on a {cap.vw}-px screen: the mobile full-width style was never adapted, so the control looks bloated and the eye travels far.",
                       recommendation="Cap form and button widths on desktop (max-width 480-560 px) or lay forms out in a constrained column.", occurrence=cap.where(e, width_px=e["r"][2]))
            if width < 0.42:
                C.find("layout.narrow_desktop", category="visual", area="layout", title="Desktop layout is a stretched phone column", severity="minor", evidence="measured", cost=3,
                       explanation=f"All content sits in {round(width * 100)}% of a {cap.vw}-px window, leaving most of the screen empty; on desktop this reads as unfinished, not minimal.",
                       recommendation="Add a desktop breakpoint: a two-column layout, a side navigation, or wider cards in a grid (keep text columns at 60-80 characters).",
                       occurrence={"screen": cap.screen, "viewport": cap.viewport, "selector": None, "rect": [round(x0), 0, round(x1 - x0), cap.vh], "measured": {"content_width_share": round(width, 2)}})
        elif cap.mobile and cap.vw < 600:
            C.metric("layout", "layout.utilisation", "layout uses the available width", _clamp((width - 0.7) / 0.2), 1, screen=cap.screen, viewport=cap.viewport, detail={"content_width_share": round(width, 2)})
    cls = (cap.raw.get("cls") or {}).get("cls")
    if cls is not None and not cap.raw.get("steps_reached"):
        C.metric("layout", "layout.stability", "layout does not jump while loading (CLS)", _clamp(1 - (cls - 0.05) / 0.2), 1, screen=cap.screen, viewport=cap.viewport, detail={"cls": cls})
        if cls > 0.1:
            C.find("layout.shift", category="visual", area="layout", title="Layout jumps while the screen loads", severity="major" if cls > 0.25 else "minor", evidence="measured", cost=2,
                   explanation=f"Cumulative layout shift {cls:.2f} (Chromium's layout-shift entries; 0.1 is the 'good' limit): content moves under the user's thumb as images, fonts or data arrive.",
                   recommendation="Reserve space for late content (width/height or aspect-ratio on media, skeletons with final sizes, font-display with metric overrides).",
                   occurrence={"screen": cap.screen, "viewport": cap.viewport, "selector": None, "rect": None, "measured": {"cls": cls, "shifts": (cap.raw.get("cls") or {}).get("shifts")}})
    # nesting: long chains of unstyled single-child wrappers
    deep = 0
    for e in cap.els:
        if e.get("d", 0) > 18 and (e.get("t") or e.get("inter")): deep += 1
    if cap.els: C.metric("layout", "layout.nesting", "shallow structure", 1 - min(1, deep / max(10, len(cap.els) / 4)), 1, screen=cap.screen, viewport=cap.viewport, detail={"deeply_nested": deep})


def typography(cap, C):
    texts = [e for e in cap.els if e.get("t") and (e.get("tl") or 0) >= 2 and e.get("fs")]
    if not texts or cap.canvas_heavy and len(texts) < 5: return
    small_lim = 12 if cap.mobile else 11
    small = [e for e in texts if e["fs"] < small_lim]
    C.metric("typography", "type.min_size", "text large enough to read", 1 - min(1, 2 * len(small) / len(texts)), len(texts), screen=cap.screen, viewport=cap.viewport)
    for e in sorted(small, key=lambda e: e["fs"])[:4]:
        C.find("type.too_small", category="visual", area="typography", title="Text is too small to read comfortably", severity="major" if e["fs"] < 11 else "minor", evidence="measured", cost=1,
               explanation=f"{e['fs']:g}-px text is below the {small_lim}-px minimum for {'phones' if cap.mobile else 'screens'}; secondary information (dates, tags, captions) becomes hard to read.",
               recommendation="Use at least 12 px (13-14 px preferred) for secondary text and keep hierarchy with weight and colour rather than very small sizes.",
               occurrence=cap.where(e, font_size_px=e["fs"]))
    sizes = Counter(round(e["fs"]) for e in texts)
    C.metric("typography", "type.scale", "a small set of font sizes", _clamp(1 - (len(sizes) - 6) / 6), len(texts), screen=cap.screen, viewport=cap.viewport, detail={"sizes": sorted(sizes)})
    plain = [e for e in texts if not e.get("h") and not e.get("inter")] or texts
    body = statistics.median([e["fs"] for e in plain if (e.get("tl") or 0) >= 20] or [e["fs"] for e in plain])
    heads = [e for e in texts if e.get("h")]
    top = max([e["fs"] for e in heads] or [0])
    if heads:
        ratio = top / body
        C.metric("typography", "type.hierarchy", "headings stand out from body text", _clamp((ratio - 1.05) / 0.4), len(heads), screen=cap.screen, viewport=cap.viewport, detail={"largest_heading_px": top, "body_px": body})
        inv = [(a, b) for a in heads for b in heads if a["h"] < b["h"] and a["fs"] + 0.5 < b["fs"]]
        if inv:
            a, b = inv[0]
            C.find("type.inverted", category="visual", area="typography", title="Heading levels are visually inverted", severity="minor", evidence="measured", cost=1,
                   explanation=f"An h{a['h']} ({a['fs']:g} px) is smaller than an h{b['h']} ({b['fs']:g} px) on the same screen, so the visual hierarchy contradicts the document structure.",
                   recommendation="Make heading sizes follow their level, or change the element level to match its visual role.", occurrence=cap.where(a, heading_px=a["fs"], lower_heading_px=b["fs"]))
        if ratio < 1.15:
            C.find("type.flat", category="visual", area="typography", title="Weak typographic hierarchy", severity="minor", evidence="measured", cost=1,
                   explanation=f"The largest heading ({top:g} px) is barely larger than body text ({body:g} px); the screen has no clear entry point.",
                   recommendation="Use a type scale with at least a 1.25× step between levels, and weight for emphasis.", occurrence=cap.where(max(heads, key=lambda e: e["fs"]), heading_px=top, body_px=body))
    else:
        C.metric("typography", "type.hierarchy", "headings stand out from body text", 0.4, 1, screen=cap.screen, viewport=cap.viewport, detail={"headings": 0})
    paras = [e for e in texts if (e.get("tl") or 0) >= 60 and e.get("trect") and e["trect"][3] > 1.6 * (e.get("lh") or e["fs"] * 1.2)]
    if paras:
        bad_lh = [e for e in paras if e.get("lh") and (e["lh"] / e["fs"] < 1.3 or e["lh"] / e["fs"] > 2.0)]
        long = [e for e in paras if e["trect"][2] / (0.5 * e["fs"]) > 95]
        C.metric("typography", "type.readability", "comfortable line height and length", 1 - (len(bad_lh) + len(long)) / (2 * len(paras)), len(paras), screen=cap.screen, viewport=cap.viewport)
        for e in bad_lh[:2]:
            C.find("type.line_height", category="visual", area="typography", title="Paragraph line height is cramped", severity="minor", evidence="measured", cost=1,
                   explanation=f"Multi-line text uses a {e['lh'] / e['fs']:.2f} line-height ratio; below 1.3 lines crowd each other and reading slows.",
                   recommendation="Use line-height 1.4-1.6 for body text.", occurrence=cap.where(e, line_height_ratio=round(e["lh"] / e["fs"], 2)))
        for e in long[:2]:
            C.find("type.line_length", category="visual", area="typography", title="Lines of text are too long", severity="minor", evidence="measured", cost=1,
                   explanation=f"About {round(e['trect'][2] / (0.5 * e['fs']))} characters per line; beyond ~80 the eye loses its place.",
                   recommendation="Cap text columns at 60-75ch (max-width: 70ch).", occurrence=cap.where(e, approx_chars_per_line=round(e["trect"][2] / (0.5 * e["fs"]))))


def controls(cap, C):
    targets = [e for e in cap.controls if cap.is_target(e)]
    if not targets: return
    need = 44 if cap.mobile else 24
    scores, small = [], []
    for e in targets:
        r = e.get("hit") or e["r"]; m = min(r[2], r[3])
        scores.append(1.0 if m >= need else (_clamp((m - 24) / (need - 24)) * 0.8 if need > 24 else 0.0))
        if m < need: small.append((e, m))
    C.metric("controls", "controls.target_size", f"touch/click targets at least {need} px", sum(scores) / len(scores), len(targets), screen=cap.screen, viewport=cap.viewport)
    for e, m in sorted(small, key=lambda t: t[1])[:6]:
        C.find("controls.small_target" if cap.mobile else "controls.small_target_desktop", category="visual", area="controls",
               title="Touch target is too small" if cap.mobile else "Click target is below 24 px", severity=("major" if m < 32 else "minor") if cap.mobile else "minor", evidence="measured", cost=1,
               explanation=(f"{e['r'][2]}×{e['r'][3]} px: under the 44×44 pt Apple HIG minimum (24 px is the WCAG 2.2 floor); thumbs miss and hit neighbours." if cap.mobile
                            else f"{e['r'][2]}×{e['r'][3]} px: under the WCAG 2.2 24×24 px minimum target size."),
               recommendation="Enlarge the hit area to 44×44 (padding, min-height/min-width, or an ::after hit-area) while keeping the visible glyph size.",
               occurrence=cap.where(e, width_px=e["r"][2], height_px=e["r"][3], minimum_px=need))
    # accidental proximity: two small targets nearly touching
    close = []
    for i, a in enumerate(targets):
        for b in targets[i + 1:]:
            if bool(a.get("vr")) != bool(b.get("vr")): continue
            g, axis = _gap(a["r"], b["r"])
            if g < 8 and _overlap(a["r"], b["r"]) == 0 and min(a["r"][2], a["r"][3], b["r"][2], b["r"][3]) < 44:
                close.append((a, b, round(g)))
    C.metric("controls", "controls.spacing", "neighbouring targets not crowded", 1 - min(1, len(close) / max(1, len(targets) / 2)), len(targets), screen=cap.screen, viewport=cap.viewport)
    for a, b, g in close[:5]:
        destructive = re.search(r"delete|remove|✕|×|close|sign out", (a.get("name", "") + " " + b.get("name", "")), re.I)
        C.find("controls.too_close", category="usability" if cap.mobile else "visual", area="mobile" if cap.mobile else "controls", title="Controls are too close together",
               severity="major" if (cap.mobile and destructive) else "minor", evidence="measured", cost=1,
               explanation=f"'{a.get('name') or a.get('sel')}' and '{b.get('name') or b.get('sel')}' are {g} px apart and at least one is under 44 px: an easy mis-tap" + (" — and one of them is destructive." if destructive else "."),
               recommendation="Keep at least 8 px between targets (more next to destructive actions), or merge rarely used actions into one overflow menu.",
               occurrence=dict(cap.where(a, gap_px=g, neighbour=b.get("sel")), rect=[min(a["r"][0], b["r"][0]), min(a["r"][1], b["r"][1]), max(a["r"][0] + a["r"][2], b["r"][0] + b["r"][2]) - min(a["r"][0], b["r"][0]), max(a["r"][1] + a["r"][3], b["r"][1] + b["r"][3]) - min(a["r"][1], b["r"][1])]))
    # label/icon alignment inside the control
    mis = []
    for e in targets:
        t = e.get("trect"); r = e["r"]
        if not t or r[3] < 20 or e.get("k") in ("input", "select", "link") and not e.get("st"): continue
        if not e.get("st") or not _simple(cap, e) or t[3] > 0.8 * r[3] + 2 or e["tag"] in ("td", "th", "tr", "li", "div", "section", "article"): continue
        dy = (t[1] + t[3] / 2) - (r[1] + r[3] / 2)
        if abs(dy) > max(2.5, 0.08 * r[3]): mis.append((e, round(dy, 1)))
        if e.get("icon") and t and e["icon"][3] < r[3]:
            di = (e["icon"][1] + e["icon"][3] / 2) - (t[1] + t[3] / 2)
            if abs(di) > 3 and e["icon"][0] + e["icon"][2] <= t[0] + 2: mis.append((e, round(di, 1)))
    boxed = [e for e in targets if e.get("st") and e.get("trect") and _simple(cap, e)]
    if boxed: C.metric("controls", "controls.label_alignment", "labels centred in their controls", 1 - len(mis) / len(boxed), len(boxed), screen=cap.screen, viewport=cap.viewport)
    for e, dy in mis[:4]:
        C.find("controls.label_offcentre", category="visual", area="controls", title="Button label is not vertically centred", severity="minor", evidence="measured", cost=1,
               explanation=f"The label sits {abs(dy)} px {'below' if dy > 0 else 'above'} the button's centre (uneven padding or line-height), which looks off at a glance.",
               recommendation="Use symmetric vertical padding with a fixed height and align-items: center; avoid padding hacks per variant.", occurrence=cap.where(e, offset_px=dy))
    # equivalent controls in a row with different heights
    rows = defaultdict(list)
    for e in targets:
        if e.get("k") in ("button", "link", "clickable") and e.get("st") and e.get("p") is not None: rows[e["p"]].append(e)
    rowsc, bad = 0, []
    for p, es in rows.items():
        if len(es) < 2: continue
        ys = [e["r"][1] + e["r"][3] / 2 for e in es]
        if max(ys) - min(ys) > 30: continue   # not one row
        rowsc += 1; hs = [e["r"][3] for e in es]
        if max(hs) - min(hs) > 4: bad.append((cap.els[p], hs, es))
    if rowsc: C.metric("controls", "controls.row_consistency", "buttons in one row share a height", 1 - len(bad) / rowsc, rowsc, screen=cap.screen, viewport=cap.viewport)
    for p, hs, es in bad[:3]:
        C.find("controls.mixed_heights", category="visual", area="controls", title="Buttons side by side have different heights", severity="major", evidence="measured", cost=1,
               explanation=f"Buttons in one row are {', '.join(str(h) for h in hs)} px tall; equivalent controls look like different components and the row looks unbalanced.",
               recommendation="Use one button size per row (a size token: e.g. 44 px on mobile) and change emphasis with fill/outline, not padding.",
               occurrence=cap.where(p, heights_px=hs, buttons=[e.get("name") for e in es]))
    # primary action prominence
    viewport_btns = [e for e in targets if e.get("bg") and e.get("ebg") is not None and e["r"][1] < cap.vh and e.get("k") in ("button", "link", "clickable") and e["r"][2] >= 40]
    filled = []
    for e in viewport_btns:
        par = cap.els[e["p"]] if e.get("p") is not None and e["p"] < len(cap.els) else None
        behind = (par or {}).get("ebg") or [255, 255, 255]
        if _dist(e["bg"], behind) > 90 and _sat(e["bg"]) > 0.35: filled.append(e)
    if viewport_btns:
        strong = sorted(filled, key=lambda e: -e["r"][2] * e["r"][3])
        compete = []
        for i, a in enumerate(strong):
            for b in strong[i + 1:]:
                same_row = abs((a["r"][1] + a["r"][3] / 2) - (b["r"][1] + b["r"][3] / 2)) < 24 and a.get("p") == b.get("p")
                if same_row and 0.6 < (a["r"][2] * a["r"][3]) / max(1, b["r"][2] * b["r"][3]) < 1.7: compete.append((a, b))
        C.metric("controls", "controls.primary", "one clear primary action per group", 0.4 if compete else 1.0, 1, screen=cap.screen, viewport=cap.viewport)
        for a, b in compete[:2]:
            C.find("controls.competing_primary", category="visual", area="controls", title="Two primary actions compete", severity="minor", evidence="measured", cost=1,
                   explanation=f"'{a.get('name')}' and '{b.get('name')}' are both strongly filled, similar in size and side by side, so neither reads as the main action.",
                   recommendation="Keep one filled primary button per group; make the other secondary (outline or tonal).",
                   occurrence=dict(cap.where(a, fill_a=a["bg"], fill_b=b["bg"], other=b.get("name")),
                                   rect=[min(a["r"][0], b["r"][0]), min(a["r"][1], b["r"][1]), max(a["r"][0] + a["r"][2], b["r"][0] + b["r"][2]) - min(a["r"][0], b["r"][0]), max(a["r"][3], b["r"][3])]))


def visual_consistency(cap, C):
    btns = [e for e in cap.controls if e.get("st") and e.get("k") in ("button", "clickable") and not e.get("dis")]
    if len(btns) >= 3:
        radii = {round(e.get("rad", 0) / 2) * 2 for e in btns if e.get("rad", 0) < 100}
        fills = []
        for e in btns:
            c = tuple(e.get("bg") or (255, 255, 255))[:3]
            if all(_dist(c, f) > 40 for f in fills): fills.append(c)
        C.metric("consistency_v", "visual.controls", "controls share radii and a small palette", _clamp(1 - (max(0, len(radii) - 3) * 0.2 + max(0, len(fills) - 4) * 0.15)), len(btns),
                 screen=cap.screen, viewport=cap.viewport, detail={"radii": sorted(radii), "fills": len(fills)})
    fams = {e.get("ff") for e in cap.els if e.get("ff")}
    if fams: C.metric("consistency_v", "visual.fonts", "few font families", _clamp(1 - max(0, len(fams) - 2) * 0.3), 1, screen=cap.screen, viewport=cap.viewport, detail={"families": sorted(fams)})


# ------------------------------------------------------------------ USABILITY
def mobile(cap, C, vp):
    if not cap.mobile: return
    d = cap.dom; safe = vp.get("safe") or {}
    meta = d.get("meta") or ""
    C.metric("mobile", "mobile.viewport_meta", "responsive viewport meta", 1.0 if "width=device-width" in meta else 0.0, 1, screen=cap.screen, viewport=cap.viewport)
    if "width=device-width" not in meta:
        C.find("mobile.no_viewport_meta", category="usability", area="mobile", title="No responsive viewport meta tag", severity="critical", evidence="measured", cost=1,
               explanation="Without <meta name=viewport content='width=device-width'> phones render the desktop layout zoomed out.",
               recommendation="Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">.", occurrence={"screen": cap.screen, "viewport": cap.viewport, "measured": {"meta": meta}})
    # iOS zooms the page when an input with font-size < 16px is focused
    small_inputs = [e for e in cap.controls if e.get("ifs") and e["ifs"] < 16 and e.get("k") in ("input", "select")]
    inputs = [e for e in cap.controls if e.get("ifs")]
    if inputs: C.metric("mobile", "mobile.input_zoom", "inputs do not trigger iOS zoom", 1 - len(small_inputs) / len(inputs), len(inputs), screen=cap.screen, viewport=cap.viewport)
    for e in small_inputs[:3]:
        C.find("mobile.input_zoom", category="usability", area="mobile", title="Focusing a field zooms the page on iPhone", severity="major", evidence="measured", cost=1,
               explanation=f"The field's font-size is {e['ifs']:g} px; iOS Safari zooms in on any input under 16 px and leaves the page zoomed after typing.",
               recommendation="Use font-size: 16px (1rem) for inputs, selects and textareas on mobile.", occurrence=cap.where(e, font_size_px=e["ifs"]))
    # safe areas: fixed bars at the bottom / top must keep their controls out of the home indicator / notch
    sb, st = safe.get("bottom", 0), safe.get("top", 0)
    fixed = [e for e in cap.els if e.get("vr") and e.get("pos") == "fixed"]
    bottom_bars = [e for e in fixed if e["r"][1] + e["r"][3] >= cap.vh - 2 and e["r"][2] > 0.5 * cap.vw]
    unsafe = []
    if sb:
        for e in cap.controls:
            if not (e.get("vr") or e.get("fixedbar")): continue
            bot = e["r"][1] + e["r"][3]
            tr = e.get("trect"); lab_bot = (tr[1] + tr[3]) if tr else bot
            if lab_bot > cap.vh - sb + 2 or (bot > cap.vh - sb and e["r"][3] - (bot - (cap.vh - sb)) < 30): unsafe.append((e, round(bot - (cap.vh - sb))))
    tops = []
    if st and "viewport-fit=cover" in meta:
        for e in cap.controls:
            if (e.get("vr") or e.get("fixedbar")) and e["r"][1] < st - 2: tops.append(e)
    n_fixed_ctrls = len([e for e in cap.controls if e.get("vr") or e.get("fixedbar")])
    if sb or st:
        C.metric("mobile", "mobile.safe_area", "fixed controls clear the notch and home indicator", 1 - min(1, (len(unsafe) + len(tops)) / max(1, n_fixed_ctrls)) if n_fixed_ctrls else 1.0, max(1, n_fixed_ctrls), screen=cap.screen, viewport=cap.viewport)
    for e, ov in unsafe[:3]:
        C.find("mobile.home_indicator", category="usability", area="mobile", title="Bottom controls sit under the home indicator", severity="major", evidence="measured", cost=1,
               explanation=f"With the iPhone's {sb}-px bottom safe area emulated, this fixed control extends {ov} px into the home-indicator zone, where swipes go to the system instead of the app.",
               recommendation="Pad fixed bottom bars with env(safe-area-inset-bottom): padding-bottom: calc(8px + env(safe-area-inset-bottom)).",
               occurrence=cap.where(e, safe_area_bottom_px=sb, overlap_px=ov))
    for e in tops[:2]:
        C.find("mobile.notch", category="usability", area="mobile", title="Top controls sit under the status bar / Dynamic Island", severity="major", evidence="measured", cost=1,
               explanation=f"The page uses viewport-fit=cover but this control starts at y={e['r'][1]} inside the {st}-px top safe area.",
               recommendation="Pad the top bar with env(safe-area-inset-top).", occurrence=cap.where(e, safe_area_top_px=st))
    # thumb reach: the main actions on a phone in portrait should not live only at the very top
    if cap.vh > cap.vw:
        prim = [e for e in cap.controls if e.get("bg") and e.get("st") and e.get("k") in ("button", "clickable", "link") and e["r"][2] >= 40 and _sat(e["bg"]) > 0.35 and e["r"][1] < cap.vh]
        if prim:
            top_only = [e for e in prim if (e["r"][1] + e["r"][3] / 2) < 0.22 * cap.vh]
            C.metric("mobile", "mobile.thumb_reach", "main actions within thumb reach", 1 - 0.5 * len(top_only) / len(prim), len(prim), screen=cap.screen, viewport=cap.viewport)
            for e in top_only[:2]:
                C.find("mobile.reach", category="usability", area="mobile", title="Main action is at the top of the phone screen", severity="minor", evidence="measured", cost=2,
                       explanation="The primary action sits in the top fifth of a tall phone screen, the hardest zone to reach one-handed.",
                       recommendation="Repeat or move the main action to the lower half (a bottom action bar or floating button).", occurrence=cap.where(e, centre_y_share=round((e["r"][1] + e["r"][3] / 2) / cap.vh, 2)))
    # fixed chrome eating the screen
    chrome = sum(e["r"][3] for e in fixed if e["r"][2] > 0.6 * cap.vw and e.get("p") is not None and not cap.els[e["p"]].get("vr")) + sum(e["r"][3] for e in cap.els if e.get("pos") == "sticky" and e["r"][2] > 0.6 * cap.vw and e["r"][1] <= 1)
    C.metric("mobile", "mobile.content_area", "fixed bars leave room for content", _clamp(1 - (chrome / cap.vh - 0.22) / 0.25), 1, screen=cap.screen, viewport=cap.viewport, detail={"fixed_height_px": chrome})
    if chrome / cap.vh > 0.35:
        C.find("mobile.chrome", category="usability", area="mobile", title="Fixed bars take too much of the screen", severity="major", evidence="measured", cost=2,
               explanation=f"Fixed or sticky bars cover {round(100 * chrome / cap.vh)}% of the phone screen height, leaving little room for content.",
               recommendation="Shrink or hide bars on scroll, or merge them.", occurrence={"screen": cap.screen, "viewport": cap.viewport, "measured": {"fixed_px": chrome, "viewport_px": cap.vh}})
    # browser toolbars: the first screen with the viewport shortened
    tb = cap.raw.get("toolbar")
    if tb and tb.get("dom"):
        th = tb["height"]; lost = [e for e in tb["dom"]["els"] if e.get("inter") and e.get("vr") and e.get("pos") == "fixed" and (e["r"][1] + e["r"][3] > th + 1 or e["r"][1] < 0)]
        C.metric("mobile", "mobile.toolbar", "works with the browser's toolbars showing", 0.0 if lost else 1.0, 1, screen=cap.screen, viewport=cap.viewport)
        for e in lost[:2]:
            C.find("mobile.toolbar", category="usability", area="mobile", title="A fixed control is pushed off-screen by the browser toolbars", severity="major", evidence="measured", cost=2,
                   explanation=f"With the viewport shortened to {th} px (Safari's toolbars showing), this fixed control is outside the visible area — typically 100vh used instead of 100dvh.",
                   recommendation="Size full-height layouts with 100dvh (or 100svh) and position fixed bars with bottom: 0, not top: 100vh.", occurrence=dict(cap.where(e, viewport_height_px=th), shot=tb.get("shot")))


def states(cap, C):
    s = cap.raw.get("states")
    if not s: return
    if s.get("hover"):
        ch = [h for h in s["hover"] if h["changed"]]
        C.metric("feedback", "states.hover", "controls react to hover", len(ch) / len(s["hover"]), len(s["hover"]), screen=cap.screen, viewport=cap.viewport)
        for h in [h for h in s["hover"] if not h["changed"]][:3]:
            C.find("states.no_hover", category="usability", area="feedback", title="No hover state", severity="minor", evidence="measured", cost=1,
                   explanation="The pointer over this control changes nothing (colour, shadow, underline), so it does not signal that it is clickable.",
                   recommendation="Add a hover style (tone shift, underline, elevation) for every interactive component variant.",
                   occurrence={"screen": cap.screen, "viewport": cap.viewport, "selector": h["sel"], "label": h.get("name"), "rect": cap.els[h["i"]]["r"] if h["i"] < len(cap.els) else None, "measured": {"style_changed_on_hover": False}})
    if s.get("pressed"):
        ch = [h for h in s["pressed"] if h["changed"]]
        C.metric("feedback", "states.pressed", "controls show a pressed state", len(ch) / len(s["pressed"]), len(s["pressed"]), screen=cap.screen, viewport=cap.viewport)
        for h in [h for h in s["pressed"] if not h["changed"]][:3]:
            C.find("states.no_pressed", category="usability", area="feedback", title="No pressed (active) state", severity="minor" if not cap.mobile else "major", evidence="measured", cost=1,
                   explanation="Pressing this control changes nothing visually until the action completes; on touch screens there is no hover, so this is the only immediate confirmation of a tap.",
                   recommendation="Add an :active style (darker tone, scale 0.97, or ripple) to every button and link variant.",
                   occurrence={"screen": cap.screen, "viewport": cap.viewport, "selector": h["sel"], "label": h.get("name"), "rect": cap.els[h["i"]]["r"] if h["i"] < len(cap.els) else None, "measured": {"style_changed_when_pressed": False}})
    if s.get("disabled"):
        enabled = [e for e in cap.controls if not e.get("dis")]
        same = []
        for dct in s["disabled"]:
            peers = [e for e in enabled if e.get("k") == dct["k"]]
            el = cap.els[dct["i"]] if dct["i"] < len(cap.els) else {}
            legible = el.get("col") and el.get("ebg") and contrast(el["col"], el["ebg"]) >= 4.5 and (el["col"][3] if len(el["col"]) > 3 else 1) > 0.9
            if dct.get("op", 1) >= 0.95 and (any(e.get("sig") == dct.get("sig") for e in peers) or legible): same.append(dct)
        C.metric("feedback", "states.disabled", "disabled controls look disabled", 1 - len(same) / len(s["disabled"]), len(s["disabled"]), screen=cap.screen, viewport=cap.viewport)
        for dct in same[:2]:
            C.find("states.disabled_lookalike", category="usability", area="feedback", title="Disabled control looks enabled", severity="major", evidence="measured", cost=1,
                   explanation="This disabled control has exactly the same colours and opacity as enabled controls of its kind; users tap it and nothing happens.",
                   recommendation="Give disabled controls a distinct style (reduced contrast/opacity, no shadow) and cursor: not-allowed.",
                   occurrence={"screen": cap.screen, "viewport": cap.viewport, "selector": dct["sel"], "label": dct.get("name"), "rect": cap.els[dct["i"]]["r"] if dct["i"] < len(cap.els) else None, "measured": {"opacity": dct.get("op", 1)}})
    if s.get("focus") is not None and "tab_stops" in s:
        foc = s["focus"]
        ctrls = [e for e in cap.controls if not e.get("dis") and e.get("k") not in ("label", "clickable", "region")]
        vis = [f for f in foc if f["visible"]]
        if foc: C.metric("accessibility", "keyboard.focus_visible", "keyboard focus is visible", len(vis) / len(foc), len(foc), screen=cap.screen, viewport=cap.viewport)
        if ctrls: C.metric("accessibility", "keyboard.reachable", "controls reachable with Tab", _clamp(len(foc) / len(ctrls)), len(ctrls), screen=cap.screen, viewport=cap.viewport, detail={"tab_stops": len(foc), "controls": len(ctrls)})
        for f in [f for f in foc if not f["visible"]][:3]:
            C.find("keyboard.no_focus", category="usability", area="accessibility", title="Keyboard focus is invisible", severity="major", evidence="measured", cost=1,
                   explanation="Tabbing to this control changes nothing on screen (outline removed, no replacement), so keyboard users cannot see where they are (WCAG 2.4.7).",
                   recommendation="Never remove outlines without a replacement: use :focus-visible { outline: 2px solid <brand>; outline-offset: 2px }.",
                   occurrence={"screen": cap.screen, "viewport": cap.viewport, "selector": f.get("sel"), "label": f.get("name"), "rect": cap.els[f["i"]]["r"] if f.get("i") is not None and f["i"] < len(cap.els) else None, "measured": {"focus_style_change": False}})
        unreach = [e for e in ctrls if e.get("k") == "clickable"]
        for e in [e for e in cap.controls if e.get("k") == "clickable" and not e.get("dis")][:2]:
            C.find("keyboard.div_button", category="usability", area="accessibility", title="Clickable element is not a real control", severity="major", evidence="measured", cost=1,
                   explanation="This element responds to clicks (pointer cursor) but is not a button or link, so keyboard and screen-reader users cannot use it.",
                   recommendation="Use <button> (or <a href>) instead of a clickable <div>/<span>.", occurrence=cap.where(e))


def accessibility(cap, C):
    ax = cap.raw.get("axe")
    if not ax or ax.get("error"): return
    w = {"critical": 0.3, "serious": 0.18, "moderate": 0.07, "minor": 0.02}
    pen = sum(w.get(v["impact"], 0.05) * min(3, 1 + math.log2(max(1, v["count"]))) / 2 for v in ax["violations"])
    C.metric("accessibility", "a11y.axe", "axe-core WCAG 2.2 AA checks", 1 - min(1, pen), ax.get("passes", 0) + len(ax["violations"]), evidence="accessibility", screen=cap.screen, viewport=cap.viewport,
             detail={v["id"]: v["count"] for v in ax["violations"]})
    sev = {"critical": "critical", "serious": "major", "moderate": "minor", "minor": "cosmetic"}
    for v in ax["violations"]:
        f = C.find(f"axe.{v['id']}", category="usability", area="accessibility", title=f"Accessibility: {v['help']}", severity=sev.get(v["impact"], "minor"), evidence="accessibility", cost=1,
                   explanation=f"axe-core rule {v['id']} ({', '.join(v['tags']) or 'best practice'}): {v['help']}.", recommendation=f"See {v['url']} — " + (v["nodes"][0]["summary"].replace("\n", " ")[:200] if v["nodes"] else ""))
        for n in v["nodes"][:3]:
            el = next((e for e in cap.els if e.get("sel") and (e["sel"] == n["target"] or n["target"].endswith(e["sel"].split(" > ")[-1]))), None)
            f["occurrences"].append({"screen": cap.screen, "viewport": cap.viewport, "selector": n["target"], "rect": n.get("rect") or (el["r"] if el else None), "measured": {"axe": n["summary"][:160], "nodes_on_screen": v["count"]}})


# ------------------------------------------------------------------ JOURNEYS / NAVIGATION
def journeys(js, screens, C):
    if not js: return
    for j in js:
        ctx = {"journey": j["name"], "viewport": j["viewport"]}
        if not j["ok"]:
            bad = next((s for s in j["steps"] if not s["ok"]), {})
            C.metric("efficiency", "journey.completes", "journeys complete", 0.0, 1, **ctx)
            C.find("journey.fails", category="usability", area="efficiency", title="A user journey cannot be completed", severity="critical", evidence="measured", cost=2,
                   explanation=f"Journey '{j['name']}' stopped: {bad.get('error') or 'an expected result did not appear'}.",
                   recommendation="Make the control discoverable under the expected label, or fix the flow.",
                   occurrence={"screen": j["name"], "viewport": j["viewport"], "selector": str(bad.get("step"))[:120], "rect": None, "measured": {"step": bad.get("step"), "error": bad.get("error")}, "shot": j.get("shot")})
            continue
        C.metric("efficiency", "journey.completes", "journeys complete", 1.0, 1, **ctx)
        if j.get("expected_taps"):
            extra = j["taps"] - j["expected_taps"]
            C.metric("efficiency", "journey.taps", "taps match the task's minimum", _clamp(1 - max(0, extra) / max(2, j["expected_taps"])), 1, **ctx, detail={"taps": j["taps"], "expected": j["expected_taps"]})
            if extra > 1:
                C.find("journey.too_many_taps", category="usability", area="efficiency", title="A task takes more taps than it should", severity="major", evidence="measured", cost=3,
                       explanation=f"'{j['name']}' took {j['taps']} taps; the task needs {j['expected_taps']}.", recommendation="Remove intermediate screens or confirmations, or add a shortcut where the task starts.",
                       occurrence={"screen": j["name"], "viewport": j["viewport"], "measured": {"taps": j["taps"], "expected": j["expected_taps"]}, "shot": j.get("shot")})
        dead = [s for s in j["steps"] if s.get("tap") and s["ok"] and not s.get("url_changed") and not s.get("mutations") and not s.get("dialog")]
        taps = [s for s in j["steps"] if s.get("tap")]
        if taps:
            C.metric("feedback", "journey.feedback", "every tap produces visible feedback", 1 - len(dead) / len(taps), len(taps), **ctx)
            slow = [s for s in taps if s.get("feedback_ms") is not None and s["feedback_ms"] > 400]
            C.metric("feedback", "journey.feedback_speed", "feedback within 400 ms", 1 - len(slow) / len(taps), len(taps), **ctx)
            for s in dead[:2]:
                C.find("journey.no_feedback", category="usability", area="feedback", title="A tap produces no visible response", severity="major", evidence="measured", cost=2,
                       explanation=f"In '{j['name']}', tapping {s['step']} changed nothing on the page within {s['step'].get('settle_ms', 700)} ms.",
                       recommendation="Acknowledge every tap immediately (pressed state, spinner, toast) even when the result takes time.",
                       occurrence={"screen": j["name"], "viewport": j["viewport"], "selector": str(s["step"])[:100], "rect": None, "measured": {"mutations": 0, "url_changed": False}, "shot": j.get("shot")})
        destructive = [s for s in j["steps"] if s.get("tap") and re.search(r"delete|remove|discard|sign out|log out", str(s["step"]), re.I)]
        if j.get("confirmations", 0) >= 2 or (j.get("confirmations", 0) >= 1 and not destructive):
            C.metric("efficiency", "journey.confirmations", "no unnecessary confirmation steps", 0.3, 1, **ctx)
            C.find("journey.confirmations", category="usability", area="efficiency", title="Unnecessary confirmation steps", severity="major" if j["confirmations"] >= 2 else "minor", evidence="measured", cost=2,
                   explanation=f"'{j['name']}' asked for confirmation {j['confirmations']} time(s)" + (" for one action" if j["confirmations"] >= 2 else " for a non-destructive action") + ": friction that trains users to click through.",
                   recommendation="Confirm once at most — better, act immediately and offer Undo (a snackbar for 5-8 s).",
                   occurrence={"screen": j["name"], "viewport": j["viewport"], "measured": {"confirmations": j["confirmations"]}, "shot": j.get("shot")})
        elif j.get("confirmations") is not None:
            C.metric("efficiency", "journey.confirmations", "no unnecessary confirmation steps", 1.0, 1, **ctx)
    # navigation depth: how many taps from the entry to each screen
    if screens:
        depths = [s.get("depth", 0) for s in screens if s.get("depth")]
        if depths: C.metric("navigation", "nav.depth", "every screen within 2 taps", sum(1.0 if d <= 2 else (0.5 if d == 3 else 0.0) for d in depths) / len(depths), len(depths), detail={"depths": depths})


def navigation(caps_by_vp, screens, C):
    for vp, caps in caps_by_vp.items():
        if len(caps) < 2: continue
        # persistent navigation: the same set of nav links on every top-level screen
        def navset(cap):
            return {(e.get("name") or "").lower() for e in cap.controls if e.get("k") in ("link", "tab", "button") and (e.get("vr") or e["r"][1] < 120) and e.get("name")}
        sets = [navset(c) for c in caps]
        common = set.intersection(*sets) if sets else set()
        C.metric("navigation", "nav.persistent", "navigation stays in the same place on every screen", 1.0 if len(common) >= 2 else (0.5 if common else 0.0), len(caps), viewport=vp, detail={"common_nav": sorted(common)[:8]})
        cur = [c for c in caps if any(e.get("cur") for e in c.controls)]
        C.metric("navigation", "nav.current", "the current location is indicated", len(cur) / len(caps), len(caps), viewport=vp)
        dead = []
        for c in caps:
            outs = [e for e in c.controls if e.get("k") in ("link", "tab") or re.search(r"back|home|close|cancel|done", e.get("name") or "", re.I)]
            if not outs: dead.append(c)
        C.metric("navigation", "nav.no_dead_ends", "no dead-end screens", 1 - len(dead) / len(caps), len(caps), viewport=vp)
        for c in dead[:2]:
            C.find("nav.dead_end", category="usability", area="navigation", title="Dead-end screen", severity="major", evidence="measured", cost=2,
                   explanation=f"Screen '{c.screen}' has no link, tab or back/close control: the only way out is the browser.",
                   recommendation="Give every screen persistent navigation or a visible back/close control.", occurrence={"screen": c.screen, "viewport": c.viewport, "measured": {"exits": 0}})
        if len(cur) < len(caps) and len(common) >= 2:
            c = next(c for c in caps if c not in cur)
            C.find("nav.no_current", category="usability", area="navigation", title="Navigation does not show where you are", severity="minor", evidence="measured", cost=1,
                   explanation=f"On '{c.screen}' no navigation item is marked current (aria-current, selected or an active style).", recommendation="Mark the current item with aria-current=\"page\" and a visible active style.",
                   occurrence={"screen": c.screen, "viewport": c.viewport, "measured": {"current_marked": False}})


# ------------------------------------------------------------------ CONSISTENCY
def _btn_variant(e):
    return (round(e["r"][3] / 4) * 4, round(e.get("rad", 0) / 2) * 2 if e.get("rad", 0) < 100 else 99, round(e.get("fs") or 0), tuple((e.get("bg") or [0, 0, 0, 0])[:3]) if e.get("bg") else None, bool(e.get("bw")))


def consistency(caps, C):
    by_vp = defaultdict(list)
    for c in caps: by_vp[c.viewport].append(c)
    for vp, cs in by_vp.items():
        # cross-screen: headers, heading sizes and font families stay the same
        if len(cs) >= 2:
            tops = []
            for c in cs:
                bar = next((e for e in c.els if e.get("pos") in ("fixed", "sticky") and e["r"][1] <= 1 and e["r"][2] > 0.6 * c.vw), None)
                tops.append(bar["r"][3] if bar else None)
            th = [t for t in tops if t]
            hs = defaultdict(set)
            for c in cs:
                for e in c.els:
                    if e.get("h") and e.get("fs"): hs[e["h"]].add(round(e["fs"]))
            incons = {k: sorted(v) for k, v in hs.items() if len(v) > 1}
            fams = [frozenset(e.get("ff") for e in c.els if e.get("ff")) for c in cs]
            score = 1.0 - (0.35 if th and (max(th) - min(th) > 2 or len(th) != len(tops)) else 0) - 0.15 * len(incons) - (0.2 if len(set(fams)) > 1 and len(set().union(*fams)) > 2 else 0)
            C.metric("cross_screen", "cross.structure", "headers, heading sizes and fonts match across screens", _clamp(score), len(cs), viewport=vp, detail={"header_heights": tops, "heading_sizes": {f"h{k}": v for k, v in hs.items()}})
            for lvl, v in list(incons.items())[:2]:
                C.find("cross.heading_sizes", category="consistency", area="cross_screen", title="The same heading level has different sizes on different screens", severity="minor", evidence="measured", cost=1,
                       explanation=f"h{lvl} is rendered at {', '.join(str(x) for x in v)} px depending on the screen.", recommendation="Style headings once, globally, from the type scale.",
                       occurrence={"screen": ", ".join(c.screen for c in cs), "viewport": vp, "measured": {f"h{lvl}_sizes_px": v}})
            # primary button style across screens
            prims = []
            for c in cs:
                for e in c.controls:
                    if e.get("bg") and _sat(e["bg"]) > 0.35 and e.get("k") in ("button", "clickable") and e["r"][2] >= 40: prims.append((c.screen, _btn_variant(e), e))
            pv = {v[:3] for _, v, _ in prims}
            if prims: C.metric("cross_screen", "cross.primary", "primary buttons look the same on every screen", _clamp(1 - (len(pv) - 1) * 0.25), len(prims), viewport=vp, detail={"variants": len(pv)})
        # component consistency: how many visual variants of buttons and inputs exist
        btns = [(c, e) for c in cs for e in c.controls if e.get("st") and e.get("k") in ("button",) and not e.get("dis")]
        if len(btns) >= 3:
            variants = Counter(_btn_variant(e)[:3] for _, e in btns)
            heights = sorted({v[0] for v in variants})
            C.metric("component", "component.buttons", "few button variants", _clamp(1 - (len(variants) - 4) * 0.12), len(btns), viewport=vp, detail={"variants": len(variants), "heights_px": heights})
            if len(variants) > 5:
                ex = {}
                for c, e in btns:
                    ex.setdefault(_btn_variant(e)[:3], (c, e))
                c0, e0 = next(iter(ex.values()))
                C.find("component.button_variants", category="consistency", area="component", title="Too many button variants", severity="major" if len(variants) > 8 else "minor", evidence="measured", cost=2,
                       explanation=f"{len(variants)} distinct button size/shape combinations (heights {', '.join(str(h) for h in heights)} px) at {vp}: buttons were styled one by one, not from a component.",
                       recommendation="Define 2-3 button sizes and 3 emphasis levels (primary, secondary, tertiary) as one component and use it everywhere.",
                       occurrence={"screen": "all", "viewport": vp, "selector": None, "rect": None, "measured": {"variants": len(variants), "heights_px": heights,
                                   "examples": [f"{c.screen}: {e.get('name')} ({e['r'][2]}×{e['r'][3]})" for c, e in list(ex.values())[:8]]}})
        inputs = [e for c in cs for e in c.controls if e.get("k") in ("input", "select") and e["r"][3] > 12]
        if len(inputs) >= 2:
            ih = {round(e["r"][3] / 2) * 2 for e in inputs}
            C.metric("component", "component.inputs", "inputs share one height", _clamp(1 - (len(ih) - 1) * 0.3), len(inputs), viewport=vp, detail={"heights_px": sorted(ih)})
        # design-system adherence over the whole viewport
        vals = [v for c in cs for e in c.els for v in (e.get("pad") or []) + ([e["gap"]] if e.get("gap") else []) if v > 0]
        if vals:
            on = sum(1 for v in vals if v <= 2 or min(v % 4, 4 - v % 4) <= 1) / len(vals)
            C.metric("design_system", "ds.spacing", "spacing tokens (4-px grid)", _clamp((on - 0.35) / 0.55), len(vals), viewport=vp, detail={"on_scale": round(on, 2)})
        cols = []
        for c in cs:
            for e in c.els:
                for k in ("col", "bg"):
                    v = e.get(k)
                    if v and (len(v) < 4 or v[3] > 0.5) and all(_dist(v, x) > 24 for x in cols): cols.append(v[:3])
        if cols: C.metric("design_system", "ds.palette", "a constrained colour palette", _clamp(1 - (len(cols) - 12) / 16), len(cols), viewport=vp, detail={"distinct_colours": len(cols)})
        sizes = {round(e["fs"]) for c in cs for e in c.els if e.get("fs") and e.get("t")}
        if sizes: C.metric("design_system", "ds.type_scale", "font sizes from a scale", _clamp(1 - (len(sizes) - 7) / 7), len(sizes), viewport=vp, detail={"sizes": sorted(sizes)})
        radii = {round(e["rad"] / 2) * 2 for c in cs for e in c.els if e.get("rad") and e.get("st") and e["rad"] < 100}
        if radii: C.metric("design_system", "ds.radii", "a small set of corner radii", _clamp(1 - (len(radii) - 4) / 5), len(radii), viewport=vp, detail={"radii": sorted(radii)})
        # state consistency
        hov = [h for c in cs for h in (c.raw.get("states") or {}).get("hover", [])]
        prs = [h for c in cs for h in (c.raw.get("states") or {}).get("pressed", [])]
        foc = [h for c in cs for h in (c.raw.get("states") or {}).get("focus", [])]
        for lst, nm in ((hov, "hover"), (prs, "pressed"), (foc, "focus")):
            if len(lst) >= 3:
                key = "changed" if nm != "focus" else "visible"
                share = sum(1 for h in lst if h[key]) / len(lst)
                C.metric("state", f"state.{nm}", f"{nm} treatment applied consistently", 1 - 2 * min(share, 1 - share) if 0 < share < 1 else (1.0 if share == 1 else 0.5), len(lst), viewport=vp, detail={"share_with_state": round(share, 2)})
    # responsive consistency: every screen renders at every viewport, without overflow, with the same content
    by_screen = defaultdict(dict)
    for c in caps: by_screen[c.screen][c.viewport] = c
    for s, vs in by_screen.items():
        words = {vp: set(re.findall(r"[a-z]{4,}", (c.dom.get("text") or "").lower())) for vp, c in vs.items()}
        allw = set().union(*words.values()) if words else set()
        if allw and len(words) >= 2:
            worst = min(len(w) / len(allw) for w in words.values())
            C.metric("responsive", "resp.content_parity", "the same content at every size", _clamp((worst - 0.6) / 0.35), len(words), screen=s, detail={vp: len(w) for vp, w in words.items()})
            if worst < 0.75:
                vp_missing = min(words, key=lambda v: len(words[v]))
                C.find("resp.content_missing", category="consistency", area="responsive", title="Content disappears at one screen size", severity="minor", evidence="measured", cost=2,
                       explanation=f"At {vp_missing}, '{s}' shows only {round(100 * worst)}% of the words other sizes show; hidden content on phones is a common source of 'where did it go?'.",
                       recommendation="Reflow content instead of hiding it; move secondary content behind a disclosure rather than display: none.",
                       occurrence={"screen": s, "viewport": vp_missing, "measured": {"word_share": round(worst, 2)}})
        over = [vp for vp, c in vs.items() if c.dom.get("sw", 0) - c.dom.get("cw", 0) > 1]
        C.metric("responsive", "resp.no_overflow", "fits every viewport", 1 - len(over) / max(1, len(vs)), len(vs), screen=s, detail={"overflow_at": over})


def analyse(probe, viewports, judgements=None):
    vpi = {v["name"]: v for v in viewports}
    caps = [Capture(c, vpi.get(c["viewport"], {})) for c in probe.get("captures", []) if c.get("dom")]
    C = Collector()
    for cap in caps:
        spacing(cap, C); layout(cap, C); typography(cap, C); controls(cap, C); visual_consistency(cap, C)
        mobile(cap, C, vpi.get(cap.viewport, {})); states(cap, C); accessibility(cap, C)
    journeys(probe.get("journeys"), probe.get("screens"), C)
    by_vp = defaultdict(list)
    for c in caps: by_vp[c.viewport].append(c)
    navigation(by_vp, probe.get("screens"), C)
    consistency(caps, C)
    for j in judgements or []:
        C.metric(j["area"], f"judgement.{j['area']}", j.get("title") or "visual judgement", j["score"], 1, evidence="screenshot", screen=j.get("screen"), viewport=j.get("viewport"), detail={"note": j.get("note"), "by": j.get("by")})
        if j["score"] < 0.6:
            C.find(f"judgement.{j['area']}.{len(C.findings)}", category=j.get("category") or "visual", area=j["area"], title=j.get("title") or "Visual judgement", severity=j.get("severity") or "minor",
                   evidence="screenshot", explanation=j.get("note") or "", recommendation=j.get("recommendation") or "", cost=j.get("cost", 2),
                   occurrence={"screen": j.get("screen"), "viewport": j.get("viewport"), "measured": {}, "shot": j.get("shot")})
    return caps, C
