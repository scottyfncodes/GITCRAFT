"""Deckhand: a low-poly humanoid on a Mixamo-named skeleton, with game clips.

22 bones named mixamorig:Hips … mixamorig:RightToeBase (Mixamo's skeleton), so clips
downloaded from mixamo.com apply by name with mixamo_apply. Rigid skinning (one bone per part).
Clips: Idle, Walk, Run (loops), Jump, Interact (wave), Attack (cutlass slash). Faces -Y in
Blender (+Z glTF), feet on z = 0. Ported from ForgeCraft in the 3D Department consolidation.
"""
from .. import procedural
from ..procedural import builders

CLIPS = ["Idle", "Walk", "Run", "Jump", "Interact", "Attack"]
META = {"id": "deckhand", "title": "Deckhand (humanoid, Mixamo skeleton, rigged)", "category": "character",
        "description": "Low-poly pirate deckhand: bandana, vest, cutlass; 22-bone Mixamo-named rig; Idle/Walk/Run/Jump/Interact/Attack clips.",
        "params": {"colors": {"type": "object", "default": {}, "description": "{skin, shirt, vest, pants, bandana}: palette names or #hex"},
                   "weapon": {"type": "boolean", "default": True}, "clips": {"type": "array", "default": CLIPS},
                   "seed": {"type": "integer", "default": 7}},
        "roles": [], "budget_tris": 6000}


def default_roles(params):
    return {}


def _rigged(p):
    root, body = builders.character(p)
    builders.rig_character(root, body, tuple(p.get("clips") or CLIPS))
    return root


def build(ctx):
    clips = list(ctx.params.get("clips") or CLIPS)
    return procedural.build(ctx, _rigged, clips=clips, expect={"base_z": 0.0})
