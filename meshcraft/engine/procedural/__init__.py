"""Procedural templates: the bridge between MeshCraft's template contract (META, build(ctx))
and the procedural builders in builders.py.

build(ctx, fn) seeds randomness from the brief (deterministic builds), routes every material
the builders ask for to a palette role on ctx.mats (so core.build paints vertex colours and the
export profiles atlas/bake them like any other template), runs the builder and returns the
template result (contract + expect)."""
import random, re
from .. import kit
from . import geo


def _role_factory(mats):
    def material(hexcol, kind, rough, metal, emit):
        hx = hexcol if str(hexcol).startswith("#") else geo.PALETTE.get(hexcol, "#CCCCCC")
        role = f"{kind}_{hx.lstrip('#').lower()}" + (f"_e{int(emit)}" if emit else "") + (f"_m{int(metal * 10)}" if metal else "")
        if role not in mats.mats:
            mats.add(role, hx.upper(), rough=rough, metal=metal, emit=emit)
        return mats[role]
    return material


def build(ctx, fn, params=None, clips=None, expect=None):
    p = dict(ctx.params, **(params or {}))
    p["slug"] = re.sub(r"[^a-z0-9_]+", "_", ctx.brief["asset_id"].lower())
    random.seed(int(p.get("seed", 7)))                 # builders may use the module-level RNG
    geo.MATERIALS = _role_factory(ctx.mats)
    try:
        root = fn(p)
    finally:
        geo.MATERIALS = None
    # boats, islands, salvage and kit parts float or mount: only assets with a base_z sit on the ground (engine check)
    res = {"root": root.name if hasattr(root, "name") else root[0].name, "contract": {"root": p["slug"], "ground": "base_z" in (expect or {})},
           "expect": dict(expect or {})}
    if clips: res["contract"]["clips"] = list(clips)
    return res
