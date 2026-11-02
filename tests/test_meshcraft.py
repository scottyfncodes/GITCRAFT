#!/usr/bin/env python3
"""End-to-end MeshCraft test through scripts/mcp.sh (guard + Landlock sandbox).

  * every template runs the full pipeline (build → preview → validate → export →
    Khronos + round-trip) with no failed checks;
  * the chest GLB passes the Three.js engine check against its contract;
  * a hostile run_script cannot read ~/.claude.json, write outside the
    workspace, or open a network connection (the kernel sandbox stops it);
  * builds are reproducible: two fresh servers export identical GLB content;
  * web-pbr (baked texture maps) and stl-print exports validate and load;
  * Blockbench projects are written, inspected and imported (toon + PBR exports);
  * Mixamo: upload FBX has no rig; downloaded clips merge by bone name, clips from
    another skeleton are refused with a reason, and the merged clip plays in three.js.

    tests/test_meshcraft.py [template ...]
"""
import json, os, struct, sys, tempfile, shutil, time
sys.path.insert(0, os.path.dirname(__file__)); from mcp_client import Client
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
ws = os.environ.get("GITCRAFT_ROOT") or tempfile.mkdtemp(prefix="meshcraft-ws-")
os.makedirs(ws, exist_ok=True)
pal = os.path.join(ws, "palette.json")
json.dump({"Honey Timber": "#D9954F", "Timber": "#9A5A2E", "Deep Tide": "#0E3B66", "Midnight Swell": "#0A2142", "Doubloon Gold": "#F4C542",
           "Gold Deep": "#C98A12", "Sunlit Amber": "#FF9F2E", "Hibiscus": "#E0607E", "Sailcloth Cream": "#F6EAD0", "Palm Green": "#3FA55A",
           "Jungle Deep": "#1E6B4E", "Lagoon Teal": "#1FB5B0", "Shallows Aqua": "#7FE3D6", "Coral Flame": "#FF6B4A"}, open(pal, "w"))
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws)
res = []
def check(label, ok, detail=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + label + ("" if ok else f"  [{str(detail)[:400]}]"))

MCP = [os.path.join(REPO, "scripts", "mcp.sh"), "meshcraft"]
c = Client(MCP, env=env)
t0 = time.time(); ok, hw = c.call("hardware_probe"); dt = time.time() - t0
check("hardware_probe answers before Blender loads", ok and dt < 3 and hw["cpu"]["threads"] and "blender" in hw["capabilities"]
      and hw["network"].startswith("denied"), (round(dt, 2), str(hw)[:300]))
ok, st = c.call("meshcraft_status"); check("meshcraft starts sandboxed", ok and st.get("sandbox", "").startswith("landlock"), st)
templates = sys.argv[1:] or st["templates"]
CLIPS = {"chest": ("lid_open", "end"), "lantern": ("swing", "mid"), "flag": ("wave", "mid"), "sail": ("fill", "end"), "crab": ("wave", 14)}
for t in templates:
    clip = CLIPS.get(t)
    brief = {"asset_id": f"test_{t}", "template": t, "palette": pal, "out_dir": os.path.join(ws, t), "profiles": ["three-web-toon", "unity-fbx"],
             "preview": {"size": 256, "views": ["three_quarter"], "poses": [{"clip": clip[0], "at": clip[1]}] if clip else []}}
    ok, r = c.call("run_pipeline", {"brief": brief}, timeout=900)
    s = r["validation"]["summary"] if ok else {}
    check(f"{t}: pipeline with no failed checks", ok and s.get("fail") == 0, s if ok else r)
    if ok and t == "chest":
        glb = next(e["path"] for e in r["exports"] if e["format"] == "glb")
        ok2, e = c.call("engine_check", {"glb": glb, "clip": "lid_open", "time": 5, "contract": r["build"]["contract"], "size": 256}, timeout=300)
        check("chest: three@0.170 engine check passes its contract", ok2 and all(x["level"] == "pass" for x in e["checks"]), e if not ok2 else [x for x in e["checks"] if x["level"] != "pass"])

def glb_content(p):   # GLB minus the brief stored in the scene extras (it names the out_dir)
    b = open(p, "rb").read(); n = struct.unpack("<I", b[12:16])[0]; j = json.loads(b[20:20 + n])
    for sc in j.get("scenes", []): sc.pop("extras", None)
    return json.dumps(j, sort_keys=True).encode() + b[20 + n:]

def failed(r): return [x for x in r["validation"]["checks"] if x["level"] == "fail"]

# reproducible builds: the same brief in two fresh server processes gives the same GLB
digests = []
for i in range(2):
    ci = Client(MCP, env=env)
    b = {"asset_id": "repro_lantern", "template": "lantern", "palette": pal, "out_dir": os.path.join(ws, f"repro{i}")}
    ok, r = ci.call("build_asset", {"brief": b}, timeout=600)
    ok2, e = ci.call("export_asset", {"blend": r["blend"]["path"], "profiles": ["three-web-toon"]}, timeout=600) if ok else (False, r)
    digests.append(glb_content(e[0]["path"]) if ok2 else None); ci.close()
check("builds are reproducible across server processes (identical GLB content)", digests[0] is not None and digests[0] == digests[1])

# web-pbr + stl-print on the chest
brief = {"asset_id": "pbr_chest", "template": "chest", "palette": pal, "out_dir": os.path.join(ws, "pbr_chest"), "profiles": ["web-pbr", "stl-print"],
         "preview": {"size": 128, "views": ["three_quarter"]}}
ok, r = c.call("run_pipeline", {"brief": brief}, timeout=900)
check("web-pbr + stl-print: pipeline with no failed checks", ok and not failed(r), failed(r) if ok else r)
if ok:
    pbr = next(e for e in r["exports"] if e["profile"] == "web-pbr"); stl = next(e for e in r["exports"] if e["profile"] == "stl-print")
    maps = pbr.get("bake", {}).get("maps", {})
    check("web-pbr: basecolor + metallic-roughness maps baked", {"basecolor", "orm"} <= set(maps) and all(os.path.getsize(p) > 1000 for p in maps.values()), pbr.get("bake"))
    ok2, e = c.call("engine_check", {"glb": pbr["path"], "material": "authored", "size": 256, "out": os.path.join(ws, "pbr_chest", "engine.png")}, timeout=300)
    check("web-pbr: loads in three@0.170 with base colour maps", ok2 and all(x["level"] == "pass" for x in e["checks"]) and any(x["check"] == "engine_basecolor_maps" for x in e["checks"]), e)
    check("stl-print: re-imports with the same triangle count", stl.get("roundtrip", {}).get("triangles") == pbr["roundtrip"]["triangles"],
          (stl.get("roundtrip"), pbr.get("roundtrip", {}).get("triangles")))

# Blockbench
bbdir = os.path.join(ws, "blockbench")
for t in ("crate", "chest", "crab", "lantern", "boat"):
    ok, r = c.call("blockbench_build", {"template": t, "out": os.path.join(bbdir, f"{t}.bbmodel"), "palette": pal, "roles": {"gold": "Doubloon Gold"} if t == "chest" else {}})
    ok2, i = c.call("blockbench_inspect", {"path": os.path.join(bbdir, f"{t}.bbmodel")})
    check(f"blockbench {t}: .bbmodel format 5.0 with an embedded texture", ok and ok2 and i["format_version"] == "5.0" and i["textures"][0]["embedded"] and not i["problems"], (r, i))
ok, r = c.call("blockbench_import", {"path": os.path.join(bbdir, "chest.bbmodel"), "out_dir": os.path.join(bbdir, "bb_chest"), "asset_id": "bb_chest",
                                     "profiles": ["three-web-toon", "web-pbr"]}, timeout=900)
check("blockbench import: .bbmodel → .blend → toon + PBR GLBs with no failed checks", ok and r["objects"] == 5 and not failed(r), failed(r) if ok else r)
if ok:
    toon = next(e for e in r["exports"] if e["profile"] == "three-web-toon")
    ok2, e = c.call("engine_check", {"glb": toon["path"], "size": 256, "out": os.path.join(bbdir, "bb_chest", "engine.png")}, timeout=300)
    check("blockbench import: toon GLB loads with COLOR_0 in three@0.170", ok2 and all(x["level"] == "pass" for x in e["checks"]), e)
ok, r = c.call("blockbench_inspect", {"path": pal})
check("blockbench_inspect explains a file that is not a project", not ok and "Blockbench" in str(r), r)

# Mixamo (fixtures stand in for mixamo.com downloads, which need a person with an Adobe ID)
fx = os.path.join(ws, "mixamo"); fixture = os.path.join(ws, "mixamo_fixture.py")
shutil.copy(os.path.join(HERE, "fixtures", "mixamo_fixture.py"), fixture)
for a in ({"kind": "character"}, {"kind": "clip"}, {"kind": "clip", "prefix": "mixamorig1:", "clip_name": "Run_Small.fbx", "scale": 0.5},
          {"kind": "foreign"}, {"kind": "apose"}):
    ok, r = c.call("run_script", {"path": fixture, "args": dict(a, out=fx)}, timeout=300)
    if not ok: check(f"mixamo fixture {a['kind']}", False, r)
ok, g = c.call("mixamo_guide"); check("mixamo_guide lists the manual steps and core bones", ok and len(g["steps"]) >= 6 and "Hips" in g["core_bones"], g)
ok, r = c.call("mixamo_prepare_upload", {"input": os.path.join(fx, "character.fbx"), "out": os.path.join(fx, "upload", "character_upload.fbx")}, timeout=300)
ok2, i = c.call("inspect_file", {"path": os.path.join(fx, "upload", "character_upload.fbx")}) if ok else (False, r)
check("mixamo_prepare_upload: mesh-only FBX (no armature) for the auto-rigger", ok and ok2 and i["armatures"] == 0 and i["triangles"] > 0, (r, i))
anims = [os.path.join(fx, f) for f in ("Walking.fbx", "Run_Small.fbx", "Foreign_Walk.fbx", "APose_Walk.fbx")]
ok, r = c.call("mixamo_apply", {"character": os.path.join(fx, "character.fbx"), "animations": anims, "out_dir": os.path.join(fx, "hero"),
                                "asset_id": "mx_hero", "profiles": ["godot-glb"]}, timeout=900)
clips = {x["clip"]: x for x in r.get("clips", [])} if ok else {}
check("mixamo_apply: clips merged by bone name (mixamorig: and mixamorig1:)", ok and set(clips) == {"Walking", "Run_Small"} and not failed(r), r if not ok else failed(r))
check("mixamo_apply: hip motion rescaled for a different-size skeleton", ok and abs(clips.get("Run_Small", {}).get("hip_scale", 0) - 2.0) < 0.01, clips)
rej = {os.path.basename(x["file"]): x["reason"] for x in r.get("rejected", [])} if ok else {}
check("mixamo_apply: a non-Mixamo skeleton is refused with a reason", "core bones" in rej.get("Foreign_Walk.fbx", ""), rej)
check("mixamo_apply: a clip whose rest pose differs is refused with a reason", "rest poses differ" in rej.get("APose_Walk.fbx", ""), rej)
if ok:
    glb = next(e["path"] for e in r["exports"] if e["format"] == "glb")
    ok2, e = c.call("engine_check", {"glb": glb, "material": "authored", "clip": "Walking", "time": 0.25, "size": 256,
                                     "contract": {"clips": ["Walking", "Run_Small"]}, "out": os.path.join(fx, "engine_walk.png")}, timeout=300)
    check("mixamo_apply: merged clips play in three@0.170", ok2 and all(x["level"] == "pass" for x in e["checks"]), e)
ok, r = c.call("mixamo_apply", {"character": os.path.join(fx, "character.fbx"), "animations": [anims[2]], "out_dir": os.path.join(fx, "bad"), "asset_id": "mx_bad"})
check("mixamo_apply: nothing applicable → error that names the reason", not ok and "core bones" in str(r), r)

hostile = os.path.join(ws, "hostile.py")
open(hostile, "w").write('''
import os, socket
out = {}
try: open(os.path.expanduser("~/.claude.json")).read(10); out["read_home"] = "LEAKED"
except Exception as e: out["read_home"] = type(e).__name__
try: open("/tmp/meshcraft_escape.txt", "w").write("x"); out["write_tmp"] = "ESCAPED"
except Exception as e: out["write_tmp"] = type(e).__name__
try: socket.create_connection(("151.101.0.223", 443), timeout=5); out["net"] = "CONNECTED"
except Exception as e: out["net"] = type(e).__name__
print(out)
''')
ok, r = c.call("run_script", {"path": hostile})
out = r.get("stdout", "") if ok else str(r)
check("run_script cannot read outside the workspace", "PermissionError" in out.split("read_home")[1][:30] if "read_home" in out else False, out)
check("run_script cannot write outside the workspace", "'write_tmp': 'PermissionError'" in out, out)
check("run_script has no network", "'net': 'PermissionError'" in out, out)
ok, r = c.call("inspect_palette", {"path": os.path.expanduser("~/.claude.json")})
check("guard refuses paths outside the workspace", not ok and "GITCRAFT policy" in str(r), r)
c.close()
print(f"\n{sum(res)}/{len(res)} checks passed"); sys.exit(0 if all(res) else 1)
