"""Modular boat upgrade (fits the boat template's sockets).

One of the five TIDEBREAKERS upgrade slots, modelled at its socket origin: canvas mainsail (socket_sail), lashed cargo crates (socket_storage), brass compass binnacle (socket_navigation), ship's wheel and ash rudder (socket_steering), copper sheathing (socket_hull).
Procedural builder: engine/procedural/builders.py (upgrade); ported from ForgeCraft in the 3D
Department consolidation. Colours become palette roles (vertex colours, atlas, PBR bake).
"""
from .. import procedural
from ..procedural import builders

META = {"id": "boat_upgrade", "title": "Modular boat upgrade (fits the boat template's sockets)", "category": "ship component",
        "description": "One of the five TIDEBREAKERS upgrade slots, modelled at its socket origin: canvas mainsail (socket_sail), lashed cargo crates (socket_storage), brass compass binnacle (socket_navigation), ship's wheel and ash rudder (socket_steering), copper sheathing (socket_hull).",
        "params": {"upgrade": {"type": "string", "enum": ["sail_canvas", "cargo_crate", "compass_brass", "rudder_ash", "hull_copper"], "default": "cargo_crate"}, "color": {"type": "string", "default": "cream"}, "seed": {"type": "integer", "default": 7}},
        "roles": [], "budget_tris": 6000}


def default_roles(params):
    return {}   # colours come from the builder's palette (PALETTE names / #hex in params)


def build(ctx):
    return procedural.build(ctx, builders.upgrade, clips=None, expect=None)
