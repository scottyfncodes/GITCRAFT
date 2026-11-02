"""Which MeshCraft path fits a request. Advice only: it never builds anything. Standard library only.

It answers from what MeshCraft can do on this machine (hardware.probe) and never offers a
different method as if it were the one asked for: when a request needs a capability that is not
available (photogrammetry, image-to-3D), the answer says so, and any alternative is labelled as
not derived from the photos or concept art.
Adapted from the routing rules of the 3D Department proposal (GITCRAFT PR #9).
"""
import re
from . import hardware

TEMPLATE_WORDS = {
    "chest": ["chest", "treasure", "loot box", "coffer"], "lantern": ["lantern", "lamp"],
    "flag": ["flag", "banner", "pennant"], "sail": ["sail", "canvas sail"],
    "sun_figurehead": ["figurehead", "bow ornament"], "crab": ["crab", "biscuit"],
}
VOXEL = ["voxel", "blocky", "minecraft", "cube-built", "cubes", "pixel art", "boxy", "blockbench"]
HUMANOID = ["character", "humanoid", "human", "pirate", "sailor", "captain", "deckhand", "npc", "person", "villager", "crew"]
ANIMATED = ["animated", "animation", "walk", "run", "idle", "jump", "rigged", "mixamo"]
SCAN = ["photogrammetry", "scan", "reconstruct", "real-world", "real world", "captured"]
IMAGE3D = ["concept art to 3d", "from the concept", "from this image", "from a photo", "image to 3d", "image-to-3d", "from the drawing"]


def _has(text, words): return [w for w in words if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text)]


def route(request, images=0):
    t = (request or "").lower()
    caps = hardware.probe()["capabilities"]
    out = {"request": request, "advice_only": True}
    if images >= 8 or _has(t, SCAN):
        c = caps["photogrammetry"]
        return dict(out, route="photogrammetry", available=c["available"], reason=c.get("reason"),
                    alternatives=[{"route": "template or run_script", "note": "modelled by hand from the photos as reference: NOT reconstructed from them"}])
    if images >= 1 and (_has(t, IMAGE3D) or not _has(t, sum(TEMPLATE_WORDS.values(), []) + VOXEL)):
        c = caps["image_to_3d"]
        return dict(out, route="image_to_3d", available=c["available"], reason=c.get("reason"),
                    alternatives=[{"route": "template / Blockbench with the image as a reference", "note": "NOT derived from the image: the image only guides proportions and colour"}])
    if _has(t, VOXEL):
        return dict(out, route="blockbench", available=True,
                    tools=["blockbench_build", "(edit in Blockbench)", "blockbench_import"], why=f"matched {_has(t, VOXEL)}")
    hits = {k: _has(t, w) for k, w in TEMPLATE_WORDS.items()}; hits = {k: v for k, v in hits.items() if v}
    if hits:
        tmpl = max(hits, key=lambda k: len(hits[k]))
        return dict(out, route="template", template=tmpl, available=caps["blender"]["available"], tools=["run_pipeline"],
                    why=f"matched {hits[tmpl]}")
    if _has(t, HUMANOID):
        anim = _has(t, ANIMATED)
        return dict(out, route="mixamo" if anim else "run_script", available=True,
                    tools=(["run_script (model the character)", "mixamo_prepare_upload", "(mixamo.com)", "mixamo_apply"] if anim
                           else ["run_script (model the character)", "mixamo_prepare_upload"]),
                    why="humanoid characters have no MeshCraft template; Mixamo rigs and animates them" + (f" (matched {anim})" if anim else ""))
    return dict(out, route="run_script", available=caps["blender"]["available"], tools=["run_script", "export_asset", "engine_check"],
                why="no template matches: model it with a Blender script in the workspace (assisted modelling), or extend a template")
