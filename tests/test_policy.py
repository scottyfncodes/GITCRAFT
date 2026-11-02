#!/usr/bin/env python3
"""End-to-end policy test for every installed GITCRAFT tool.

For each tool: start it through scripts/mcp.sh (guard + sandbox), do one real
operation inside a scratch workspace, and confirm a path outside the workspace
is refused. FilmCraft and LightCraft (no native file fence) are also run under
the sandbox *without* the guard, to prove the kernel layer stops them alone.

    GITCRAFT_ROOT=/some/workspace tests/test_policy.py [tool ...]
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import Client

HERE = os.path.dirname(os.path.abspath(__file__)); MCP = os.path.join(HERE, "..", "scripts", "mcp.sh")
ws = os.environ.get("GITCRAFT_ROOT") or tempfile.mkdtemp(prefix="gitcraft-ws-")
os.makedirs(ws, exist_ok=True)
SECRET = os.path.expanduser("~/.gitcraft-policy-secret.txt")   # outside the workspace
open(SECRET, "w").write("top secret")
# own LightCraft library: the session's LightCraft server keeps the shared one locked
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_LIGHTCRAFT_LIBRARY=os.path.join(ws, "lightcraft-library"),
           GITCRAFT_3D_LIBRARY=os.path.join(ws, "3d-library"))
results = []

def check(label, cond, detail=""):
    results.append((label, bool(cond), detail)); print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail and not cond else ""))

def png(path):  # tiny valid PNG made without third-party deps
    import zlib, struct
    raw = b"".join(b"\x00" + b"\x1f\xb5\xb0\xff" * 8 for _ in range(8))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

src = os.path.join(ws, "in.png"); png(src)
TESTS = {
 "vectorcraft": (lambda c: (c.call("command_run", {"id": "file.new", "params": {"width": 64, "height": 64}}), c.call("export", {"path": f"{ws}/vc.svg"}))[-1],
                 lambda c: c.call("export", {"path": SECRET + ".svg"})),
 "photocraft":  (lambda c: (c.call("doc_open", {"path": src}), c.call("doc_save", {"path": f"{ws}/pc.png"}))[-1],
                 lambda c: c.call("doc_open", {"path": SECRET})),
 "designcraft": (lambda c: (c.call("new_document", {"width": 100, "height": 100}), c.call("save_document", {"path": f"{ws}/dc.designcraft"}))[-1],
                 lambda c: c.call("open_document", {"path": SECRET})),
 "pdfcraft":    (lambda c: c.call("doc_combine", {"paths": [src, src], "out": f"{ws}/pdf.pdf"}),
                 lambda c: c.call("doc_open", {"path": SECRET})),
 "effectcraft": (lambda c: (c.call("open_project", {"new": True}), c.call("save_project", {"path": f"{ws}/ec.ecproj"}))[-1],
                 lambda c: c.call("open_project", {"path": SECRET})),
 "filmcraft":   (lambda c: c.call("media_import", {"paths": [src]}),
                 lambda c: c.call("media_import", {"paths": [SECRET]})),
 "lightcraft":  (lambda c: c.call("import", {"paths": [src]}),
                 lambda c: c.call("import", {"paths": [SECRET]})),
 "meshcraft":   (lambda c: c.call("inspect_palette", {"path": pal}),
                 lambda c: c.call("inspect_palette", {"path": SECRET})),
 "forgecraft":  (lambda c: c.call("blockbench_build", {"template": "crate", "name": "policy", "out": f"{ws}/policy.bbmodel"}),
                 lambda c: c.call("blockbench_inspect", {"path": SECRET})),
}
pal = os.path.join(ws, "palette.json"); json.dump({"Honey Timber": "#D9954F", "Timber": "#9A5A2E", "Deep Tide": "#0E3B66", "Midnight Swell": "#0A2142",
                                                "Doubloon Gold": "#F4C542", "Gold Deep": "#C98A12", "Sunlit Amber": "#FF9F2E", "Sailcloth Cream": "#F6EAD0"}, open(pal, "w"))
if not os.path.exists(os.path.join(os.path.expanduser(os.environ.get("GITCRAFT_HOME", "~/.gitcraft")), "meshcraft", "venv", "bin", "python")):
    TESTS.pop("meshcraft"); TESTS.pop("forgecraft")   # optional tools (GITCRAFT_MESHCRAFT=0); forgecraft drives MeshCraft's Blender
want = sys.argv[1:] or list(TESTS)
for name in want:
    good, bad = TESTS[name]
    try:
        c = Client([MCP, name], env=env)
        ok, val = good(c); check(f"{name}: works inside the workspace", ok, str(val)[:200])
        ok, val = bad(c);  check(f"{name}: path outside the workspace refused", not ok and "GITCRAFT policy" in str(val), str(val)[:200])
        c.close()
    except Exception as e:
        check(f"{name}: server starts under guard + sandbox", False, str(e)[:300])

# ForgeCraft (the 3D orchestrator) answers at once too, and what it hands to MeshCraft stays fenced:
# a mesh outside the roots is refused before any Blender work starts.
if "forgecraft" in want:
    try:
        import time
        t0 = time.time(); c = Client([MCP, "forgecraft"], env=env); dt = time.time() - t0
        check("forgecraft: answers initialize within 2 s", dt < 2.0, f"{dt:.2f} s")
        names = [t["name"] for t in c.tools()]
        check("forgecraft: keeps its 1.0 tool names", {"generate", "route", "process_mesh", "photogrammetry", "compose_scene", "blockbench_build",
              "mixamo_apply", "library_search", "job_retry"} <= set(names), names)
        ok, val = c.call("process_mesh", {"input": SECRET + ".glb", "name": "escape"})
        check("forgecraft: a mesh outside the workspace is refused before MeshCraft runs", not ok and "GITCRAFT policy" in str(val), str(val)[:200])
        ok, val = c.call("hardware_probe")
        check("forgecraft: probe reports one shared library and every 3D backend", ok and {"meshcraft", "blockbench", "mixamo", "meshroom", "triposr", "hunyuan3d"} <= set(val["backends"]), str(val)[:200])
        c.close()
    except Exception as e:
        check("forgecraft: handshake and delegation fence", False, str(e)[:300])

# MeshCraft must answer the MCP handshake at once (Blender loads afterwards): Claude Code gives a
# server 30 s to connect, and a cold Blender import at session start used to take longer (#10).
import time
if "meshcraft" in want:
    try:
        t0 = time.time(); c = Client([MCP, "meshcraft"], env=env); dt = time.time() - t0
        check("meshcraft: answers initialize within 2 s, before Blender has loaded", dt < 2.0, f"{dt:.2f} s")
        names = [t["name"] for t in c.tools()]
        check("meshcraft: lists its tools without loading Blender", "run_pipeline" in names and time.time() - t0 < 3.0, names)
        # the guard records files a tool names only in its result (renders written into an out_dir)
        lantern = {"asset_id": "policy_lantern", "template": "lantern", "palette": pal, "out_dir": os.path.join(ws, "policy_lantern")}
        ok, b = c.call("build_asset", {"brief": lantern}, timeout=600)
        ok2, r = c.call("render_preview", {"blend": b["blend"]["path"] if ok else "", "out_dir": os.path.join(ws, "policy_lantern", "previews"),
                                           "size": 64, "views": ["front"]}, timeout=600)
        c.close()
        pngs = sorted({os.path.realpath(p) for p in __import__("re").findall(r"/[^\s\"']+\.png", json.dumps(r))}) if ok2 else []
        log = os.path.join(os.path.expanduser(os.environ.get("GITCRAFT_HOME", "~/.gitcraft")), "logs", "audit.jsonl")
        rec = next((json.loads(l) for l in reversed(open(log).readlines()) if '"render_preview"' in l and "policy_lantern" in l), {})
        logged = {o["path"]: o["sha256"] for o in rec.get("outputs", [])}
        import hashlib
        match = bool(pngs) and all(logged.get(p) == hashlib.sha256(open(p, "rb").read()).hexdigest() for p in pngs)
        check("guard: hashes files named only in a tool's result (audit `outputs`)", match, f"renders {pngs[:2]} logged {list(logged)[:3]}")
    except Exception as e:
        check("meshcraft: startup and audit checks", False, str(e)[:300])

# Fonts: the per-tool XDG folders must still expose the user's fonts inside the sandbox.
# Render the same text with a user-installed font sandboxed and unsandboxed; the pixels must match.
ufont_dir = next((d for d in (os.path.expanduser("~/.local/share/fonts"), os.path.expanduser("~/.fonts")) if os.path.isdir(d) and os.listdir(d)), None)
if ufont_dir and "designcraft" in want:
    def render(sandbox):
        e = dict(env, GITCRAFT_SANDBOX="landlock" if sandbox else "off")
        c = Client([MCP, "designcraft"], env=e)
        c.call("new_document", {"width": 600, "height": 200, "pages": 1, "intent": "web", "margins": 0})
        ok, r = c.call("execute", {"command": "frame.create", "params": {"rect": [10, 10, 590, 190], "content": "text", "text": "Fontcheck Gg"}})
        c.call("execute", {"command": "selection.set", "params": {"ids": [r["id"]]}})
        fam = os.environ.get("GITCRAFT_TEST_FONT", "Fraunces 144pt")
        c.call("execute", {"command": "type.char", "params": {"attrs": {"fontFamily": fam, "size": 80}}})
        out = f"{ws}/fontcheck_{'sb' if sandbox else 'open'}.png"
        c.call("export_png", {"page": 0, "path": out, "scale": 1}); c.close()
        return open(out, "rb").read()
    check("designcraft: user fonts render identically inside the sandbox", render(True) == render(False),
          "sandboxed render differs: user fonts not visible (set GITCRAFT_TEST_FONT to a family installed in " + ufont_dir + ")")

# Kernel layer alone (no guard): the two tools without a native fence.
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
gh = os.path.expanduser(os.environ.get("GITCRAFT_HOME", "~/.gitcraft"))
base = ["python3", os.path.join(HERE, "..", "scripts", "sandbox.py"), "--rx", "/usr", "--rx", "/lib", "--rx", "/lib64", "--rx", "/bin",
        "--rx", f"{gh}/bin", "--ro", "/etc", "--ro", "/proc", "--ro", "/sys", "--rw", "/dev", "--rw", ws, "--rw", f"{gh}/state", "--no-net", "--require", "--"]
FC_DIR = os.path.join(HERE, "..", "forgecraft")
# ForgeCraft writes hand-offs itself (library_export): give its kernel-only run one library asset and
# ask it to export into the home folder, which only the kernel layer can stop here.
if "forgecraft" in want:
    os.environ["GITCRAFT_3D_LIBRARY"] = f"{ws}/3d-lib"; sys.path.insert(0, os.path.join(HERE, ".."))
    from gitcraft3d import library as _lib
    _lib.ROOT = f"{ws}/3d-lib"; open(f"{ws}/policy_asset.glb", "wb").write(b"glTF")
    _lib.add_version("policy_asset", {"exports": [{"path": f"{ws}/policy_asset.glb"}]}, {"tool": "test_policy"})
for name, cmd, bad in (("forgecraft", ["python3", os.path.join(FC_DIR, "server.py")], ("library_export", {"asset": "policy_asset", "dest": os.path.expanduser("~/gitcraft-policy-escape")})),
                       ("filmcraft", [f"{gh}/bin/filmcraft-cli", "mcp"], ("media_import", {"paths": [SECRET]})),
                       ("lightcraft", [f"{gh}/bin/lightcraft-cli", "mcp", "--compact", "--library", f"{ws}/lc-lib"], ("import", {"paths": [SECRET]}))):
    if name not in want: continue
    try:
        extra = ["--rx", FC_DIR, "--rx", os.path.join(HERE, "..", "gitcraft3d"), "--rx", f"{gh}/forgecraft", "--rx", f"{gh}/meshcraft",
                 "--rx", os.path.join(HERE, "..", "meshcraft")] if name == "forgecraft" else []
        c = Client(base[:-1] + extra + ["--"] + cmd, env=dict(env, TMPDIR=ws, XDG_CONFIG_HOME=f"{gh}/state", XDG_CACHE_HOME=f"{gh}/state", GITCRAFT_3D_LIBRARY=f"{ws}/3d-lib"))
        ok, val = c.call(*bad)
        if name == "forgecraft": leaked = ok
        else: leaked = ok and ("imported" in str(val) and "[]" not in str(val).split("imported")[1][:8] or "items" in str(val) and "[]" not in str(val).split("items")[1][:8])
        print("   kernel-only response:", str(val)[:240]); check(f"{name}: sandbox alone blocks reading outside the workspace", not leaked, str(val)[:300])
        c.close()
    except Exception as e:
        check(f"{name}: sandbox-only run", False, str(e)[:300])

os.remove(SECRET)
failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
