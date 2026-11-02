"""MeshCraft templates as a ForgeCraft backend.

MeshCraft (meshcraft/, its own MCP server) builds hand-tuned Pebble & Sail assets from a
brief: chest, Biscuit the teacup crab, flag, lantern, sail, sun figurehead. ForgeCraft calls
its `engine.core.run_pipeline` in Blender's Python (the same bpy venv), takes MeshCraft's
own validated export and adds it to the ForgeCraft library. MeshCraft's geometry, rigs and
clips are used as-is: ForgeCraft does not re-process them."""
import json, os, subprocess, time
import hardware

PROFILE = "three-web-atlas"   # single atlas texture + COLOR_0: works in any glTF engine; clips kept

SCRIPT = r'''
import sys, json, contextlib
sys.path.insert(0, sys.argv[1])
with contextlib.redirect_stdout(sys.stderr):
    from engine import core
    rep = core.run_pipeline(json.load(open(sys.argv[2])))
print(json.dumps({"report": rep["report"]}))
'''


def templates():
    d = os.path.join(hardware.MESHCRAFT_DIR, "engine", "templates")
    return sorted(f[:-3] for f in os.listdir(d) if f.endswith(".py") and not f.startswith("_")) if os.path.isdir(d) else []


def palette():
    """Palette for MeshCraft's colour roles: $FORGECRAFT_PALETTE, else the TIDEBREAKERS brand palette
    bundled in forgecraft/palettes/ (readable inside the sandbox, unlike other repos' checkouts)."""
    p = os.environ.get("FORGECRAFT_PALETTE")
    if p and os.path.exists(p): return p
    bundled = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "palettes", "tidebreakers-palette.json")
    return bundled if os.path.exists(bundled) else None


def run(template, params, slug, work, log, timeout=1200):
    st = hardware.meshcraft()
    if not st["available"]: raise RuntimeError("MeshCraft unavailable: " + st["reason"])
    if template not in st["templates"]: raise RuntimeError(f"MeshCraft has no template `{template}` (has {', '.join(st['templates'])})")
    out = os.path.join(work, "meshcraft"); os.makedirs(out, exist_ok=True)
    brief = {"asset_id": slug, "template": template, "params": params or {}, "out_dir": out, "profiles": [PROFILE],
             "preview": {"size": 512}}
    if palette(): brief["palette"] = palette()
    bf = os.path.join(work, "meshcraft_brief.json"); json.dump(brief, open(bf, "w"), indent=1)
    t0 = time.time()
    with open(log, "a") as lf:
        lf.write(f"$ meshcraft run_pipeline {bf}\n"); lf.flush()
        r = subprocess.run([hardware.BLENDER_PY, "-c", SCRIPT, hardware.MESHCRAFT_DIR, bf], stdout=subprocess.PIPE, stderr=lf, text=True, timeout=timeout)
    try:
        report_path = json.loads(r.stdout.strip().splitlines()[-1])["report"]; rep = json.load(open(report_path))
    except Exception: raise RuntimeError(f"MeshCraft run_pipeline failed (exit {r.returncode}); see {log}")
    summ = rep["validation"]["summary"]
    glb = next((e["path"] for e in rep["exports"] if e["format"] == "glb"), None)
    if not glb or summ.get("fail"):
        raise RuntimeError(f"MeshCraft export failed its own validation: {summ}")
    views = [p["path"] if isinstance(p, dict) else p for p in rep.get("previews", [])]
    return {"glb": glb, "blend": rep["build"]["blend"]["path"], "previews": [v for v in views if v.endswith(".png")],
            "clips": rep["build"].get("actions", []), "meshcraft_validation": summ, "seconds": round(time.time() - t0, 1),
            "template": template, "params": params, "palette": brief.get("palette"), "report": report_path}
