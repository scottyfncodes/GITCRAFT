"""Small environment prop.

Barrel (hooped, bulged), crate, rock or palm tree.
Procedural builder: engine/procedural/builders.py (prop); ported from ForgeCraft in the 3D
Department consolidation. Colours become palette roles (vertex colours, atlas, PBR bake).
"""
from .. import procedural
from ..procedural import builders

META = {"id": "prop", "title": "Small environment prop", "category": "prop",
        "description": 'Barrel (hooped, bulged), crate, rock or palm tree.',
        "params": {"prop": {"type": "string", "enum": ["barrel", "crate", "rock", "palm"], "default": "barrel"}, "seed": {"type": "integer", "default": 1}},
        "roles": [], "budget_tris": 4000}


def default_roles(params):
    return {}   # colours come from the builder's palette (PALETTE names / #hex in params)


def build(ctx):
    return procedural.build(ctx, builders.prop, clips=None, expect=None)
