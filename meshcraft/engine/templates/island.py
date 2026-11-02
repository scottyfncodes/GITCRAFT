"""Small tropical island.

Noise heightfield (sand, grass, jungle, rock by height and slope), palms, rocks, stilt hut, dock and summit flag; socket_dock and socket_spawn empties. Sea level is z = 0.
Procedural builder: engine/procedural/builders.py (island); ported from ForgeCraft in the 3D
Department consolidation. Colours become palette roles (vertex colours, atlas, PBR bake).
"""
from .. import procedural
from ..procedural import builders

META = {"id": "island", "title": "Small tropical island", "category": "environment",
        "description": 'Noise heightfield (sand, grass, jungle, rock by height and slope), palms, rocks, stilt hut, dock and summit flag; socket_dock and socket_spawn empties. Sea level is z = 0.',
        "params": {"radius": {"type": "number", "default": 22}, "peak": {"type": "number", "default": 6.5}, "palms": {"type": "integer", "default": 7}, "resolution": {"type": "integer", "default": 72}, "seed": {"type": "integer", "default": 7}},
        "roles": [], "budget_tris": 40000}


def default_roles(params):
    return {}   # colours come from the builder's palette (PALETTE names / #hex in params)


def build(ctx):
    return procedural.build(ctx, builders.island, clips=None, expect=None)
