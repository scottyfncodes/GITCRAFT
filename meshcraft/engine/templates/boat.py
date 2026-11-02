"""Coastal sloop or dinghy (TIDEBREAKERS player boat).

Lofted hull ported from TIDEBREAKERS shipModel.ts, deck, cabin, mast, boom, striped mainsail, jib, rails, tiller, lantern, flag; socket_* empties for the five upgrade slots (sail, storage, navigation, steering, hull) and the flag. Bow at +Z (glTF).
Procedural builder: engine/procedural/builders.py (boat); ported from ForgeCraft in the 3D
Department consolidation. Colours become palette roles (vertex colours, atlas, PBR bake).
"""
from .. import procedural
from ..procedural import builders

META = {"id": "boat", "title": "Coastal sloop or dinghy (TIDEBREAKERS player boat)", "category": "ship",
        "description": 'Lofted hull ported from TIDEBREAKERS shipModel.ts, deck, cabin, mast, boom, striped mainsail, jib, rails, tiller, lantern, flag; socket_* empties for the five upgrade slots (sail, storage, navigation, steering, hull) and the flag. Bow at +Z (glTF).',
        "params": {"vessel": {"type": "string", "enum": ["sloop", "dinghy"], "default": "sloop"}, "paint": {"type": "array", "default": ["#4FB39A", "#F2EAD8"], "description": "[hull, trim] colours"}, "sail_colors": {"type": "array", "default": ["#F1E6CC", "#C0392B"], "description": "[sail, stripe] colours"}, "seed": {"type": "integer", "default": 7}},
        "roles": [], "budget_tris": 12000}


def default_roles(params):
    return {}   # colours come from the builder's palette (PALETTE names / #hex in params)


def build(ctx):
    return procedural.build(ctx, builders.boat, clips=None, expect=None)
