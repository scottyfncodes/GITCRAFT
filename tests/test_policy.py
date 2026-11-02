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
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws)
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
 "forgecraft":  (lambda c: c.call("blockbench_build", {"template": "crate", "name": "policy", "out": f"{ws}/policy.bbmodel"}),
                 lambda c: c.call("blockbench_inspect", {"path": SECRET})),
}
mesh_ok = os.access(os.path.expanduser(os.environ.get("GITCRAFT_HOME", "~/.gitcraft") + "/meshcraft/venv/bin/python"), os.X_OK)
want = sys.argv[1:] or [n for n in TESTS if n != "forgecraft" or mesh_ok]   # forgecraft needs MeshCraft's Blender installed
for name in want:
    good, bad = TESTS[name]
    try:
        c = Client([MCP, name], env=env)
        ok, val = good(c); check(f"{name}: works inside the workspace", ok, str(val)[:200])
        ok, val = bad(c);  check(f"{name}: path outside the workspace refused", not ok and "GITCRAFT policy" in str(val), str(val)[:200])
        c.close()
    except Exception as e:
        check(f"{name}: server starts under guard + sandbox", False, str(e)[:300])

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
for name, cmd, bad in (("forgecraft", ["python3", os.path.join(FC_DIR, "server.py")], ("blockbench_inspect", {"path": SECRET})),
                       ("filmcraft", [f"{gh}/bin/filmcraft-cli", "mcp"], ("media_import", {"paths": [SECRET]})),
                       ("lightcraft", [f"{gh}/bin/lightcraft-cli", "mcp", "--compact", "--library", f"{ws}/lc-lib"], ("import", {"paths": [SECRET]}))):
    if name not in want: continue
    try:
        extra = ["--rx", FC_DIR, "--rx", f"{gh}/forgecraft", "--rx", f"{gh}/meshcraft"] if name == "forgecraft" else []
        c = Client(base[:-1] + extra + ["--"] + cmd, env=dict(env, TMPDIR=ws, XDG_CONFIG_HOME=f"{gh}/state", XDG_CACHE_HOME=f"{gh}/state", FORGECRAFT_LIBRARY=f"{ws}/fc-lib"))
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
