"""Lighthouse on a rock.

Striped lighthouse tower with gallery, emissive lamp and cap on a rock base.
Procedural builder: engine/procedural/builders.py (lighthouse); ported from ForgeCraft in the 3D
Department consolidation. Colours become palette roles (vertex colours, atlas, PBR bake).
"""
from .. import procedural
from ..procedural import builders

META = {"id": "lighthouse", "title": "Lighthouse on a rock", "category": "environment",
        "description": 'Striped lighthouse tower with gallery, emissive lamp and cap on a rock base.',
        "params": {"seed": {"type": "integer", "default": 7}},
        "roles": [], "budget_tris": 8000}


def default_roles(params):
    return {}   # colours come from the builder's palette (PALETTE names / #hex in params)


def build(ctx):
    return procedural.build(ctx, builders.lighthouse, clips=None, expect=None)
