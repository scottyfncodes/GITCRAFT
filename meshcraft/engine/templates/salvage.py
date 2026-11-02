"""Floating salvage (bobbing).

Lashed crate, barrel, chest and marker buoy on a driftwood raft; looping float_bob clip on the root.
Procedural builder: engine/procedural/builders.py (salvage); ported from ForgeCraft in the 3D
Department consolidation. Colours become palette roles (vertex colours, atlas, PBR bake).
"""
from .. import procedural
from ..procedural import builders

META = {"id": "salvage", "title": "Floating salvage (bobbing)", "category": "prop",
        "description": 'Lashed crate, barrel, chest and marker buoy on a driftwood raft; looping float_bob clip on the root.',
        "params": {"animate": {"type": "boolean", "default": True}, "seed": {"type": "integer", "default": 7}},
        "roles": [], "budget_tris": 6000}


def default_roles(params):
    return {}   # colours come from the builder's palette (PALETTE names / #hex in params)


def build(ctx):
    return procedural.build(ctx, builders.salvage, clips=['float_bob'], expect=None)
