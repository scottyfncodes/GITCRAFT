#!/usr/bin/env python3
"""Cross-repository check, run by tests/test_global.sh: use GITCRAFT from ANOTHER project.

    python3 global_project_check.py <project_dir> <gitcraft_checkout> <report.json>

Starts each server exactly as Claude Code does: the command and args registered at user scope
in ~/.claude.json, with the other project as the working directory and none of GITCRAFT's
variables set. Then makes a small brand kit for that project with three tools handing files to
each other (vectorcraft → photocraft → designcraft), in the project's own palette, and checks
where everything landed. Exits 1 on any failure."""
import hashlib, json, os, re, struct, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_client import Client

proj, checkout, report_path = (os.path.abspath(a) for a in sys.argv[1:4])
cfg_path = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~")), ".claude.json")
servers = json.load(open(cfg_path)).get("mcpServers", {})
env = {k: v for k, v in os.environ.items() if not k.startswith(("GITCRAFT_", "FORGECRAFT_"))}
env.pop("CLAUDE_PROJECT_DIR", None)
results, report = [], {"project": proj, "checks": [], "files": {}}
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()


def check(label, ok, detail=""):
    results.append(bool(ok)); report["checks"].append({"check": label, "ok": bool(ok), "detail": str(detail)[:400]})
    print(("PASS " if ok else "FAIL ") + label + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)


def start(name):
    s = servers[name]
    return Client([s["command"], *s.get("args", [])], env=dict(env, **(s.get("env") or {})), cwd=proj,
                  log=os.path.join(proj, ".gitcraft-work", f"{name}.stderr.log"))


def png_size(p):
    with open(p, "rb") as f: h = f.read(24)
    return struct.unpack(">II", h[16:24]) if h[:8] == b"\x89PNG\r\n\x1a\n" else None


os.makedirs(os.path.join(proj, ".gitcraft-work"), exist_ok=True)
palette = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", open(os.path.join(proj, "src", "theme.css")).read()))
existing = os.path.join(proj, "assets", "brand", "logo-old.svg"); existing_sha = sha(existing)
before_checkout = subprocess.run(["git", "-C", checkout, "status", "--porcelain"], capture_output=True, text=True).stdout

# --- discovery: every registered server answers from the other project, none of them launched from a checkout
names = sorted(n for n, s in servers.items() if str(s.get("command", "")).endswith("/scripts/mcp.sh"))
check("ten GITCRAFT servers registered at user scope", set(names) >= {"photocraft", "vectorcraft", "designcraft", "pdfcraft", "lightcraft", "filmcraft",
                                                                     "effectcraft", "meshcraft", "forgecraft", "studiocraft"}, names)
check("registered commands live in ~/.gitcraft/runtime, not in a GITCRAFT checkout",
      all("/.gitcraft/runtime/" in servers[n]["command"] and not servers[n]["command"].startswith(checkout + "/") for n in names),
      {n: servers[n]["command"] for n in names})
tools_count = {}
for n in names:
    try:
        c = start(n); tools_count[n] = len(c.tools()); c.p.terminate()
    except Exception as e: tools_count[n] = f"error: {e}"
check("every server starts from the other project and lists its tools", all(isinstance(v, int) and v > 0 for v in tools_count.values()), tools_count)
report["tools"] = tools_count

brand = os.path.join(proj, "assets", "brand"); mkt = os.path.join(proj, "marketing"); work = os.path.join(proj, ".gitcraft-work")
logo_svg, logo_png = os.path.join(brand, "logo.svg"), os.path.join(work, "logo-1024.png")
icon = os.path.join(brand, "app-icon-512.png"); poster_png, poster_pdf = os.path.join(mkt, "launch-poster.png"), os.path.join(mkt, "launch-poster.pdf")
for d in (brand, mkt, os.path.join(proj, "assets", "3d")): os.makedirs(d, exist_ok=True)   # as Claude would, following the project's layout

# --- 1. vectorcraft: logo in the project's palette → SVG (asset) + PNG (hand-off)
vc = start("vectorcraft")
ok1, _ = vc.call("draw_shape", {"shape": "ellipse", "x": 156, "y": 246, "width": 300, "height": 300, "fill": palette["brand-primary"], "stroke": "none"})
ok2, _ = vc.call("draw_shape", {"shape": "star", "cx": 306, "cy": 396, "radius1": 120, "radius2": 52, "points": 5, "fill": palette["brand-accent"], "stroke": "none"})
ok3, _ = vc.call("add_text", {"text": "ORBIT", "x": 206, "y": 600, "size": 72, "color": palette["brand-ink"]})
ok4, r4 = vc.call("export", {"path": logo_svg, "format": "svg"})
# PNG export options come from the installed binary (document.formats), not from memory: an option VectorCraft
# does not offer is refused by current builds and was silently ignored by older ones (`resolution` was never one).
okf, rf = vc.call("command_run", {"id": "document.formats", "params": {}})
png_opts = next((f.get("options", {}) for f in (rf.get("formats", []) if okf and isinstance(rf, dict) else []) if f.get("id") == "png"), {})
check("vectorcraft: the installed binary describes its PNG export options, including ppi (document.formats)", "ppi" in png_opts,
      f"PNG options offered: {sorted(png_opts) or rf}")
logo_png_1x = os.path.join(work, "logo-72ppi.png")
ok5a, r5a = vc.call("export", {"path": logo_png_1x, "format": "png", "options": {"ppi": 72}}) if "ppi" in png_opts else (False, "no ppi option")
ok5, r5 = vc.call("export", {"path": logo_png, "format": "png", "options": {"ppi": 144}}) if "ppi" in png_opts else (False, "no ppi option")
ok6, r6 = vc.call("export", {"path": os.path.join(checkout, "gitcraft-xrepo-should-not-exist.svg"), "format": "svg"})
vc.close() if hasattr(vc, "close") else vc.p.terminate()
check("vectorcraft: logo drawn in the project's palette and exported as SVG into the project", ok1 and ok2 and ok3 and ok4 and os.path.getsize(logo_svg) > 200
      and palette["brand-primary"].lower() in open(logo_svg).read().lower(), (ok1, ok2, ok3, r4))
s1, s2 = (png_size(p) if os.path.exists(p) else None for p in (logo_png_1x, logo_png))
check("vectorcraft: PNG hand-off file written to the project's work folder", ok5 and s2, r5)
check("vectorcraft: ppi takes effect (144 ppi is exactly twice the pixels of 72 ppi, not silently ignored)",
      ok5a and ok5 and s1 and s2 and s2 == (2 * s1[0], 2 * s1[1]), (s1, s2, r5a, r5))
check("isolation: writing into the GITCRAFT checkout from another project is refused",
      not ok6 and not os.path.exists(os.path.join(checkout, "gitcraft-xrepo-should-not-exist.svg")), r6)

# --- 2. photocraft: open vectorcraft's PNG, make a square app icon with a shadow
pc = start("photocraft")
ok1, r1 = pc.call("doc_open", {"path": logo_png})
ok2, r2 = pc.call("command_run", {"id": "image.imageSize", "params": {"width": 400, "height": int(400 * png_size(logo_png)[1] / png_size(logo_png)[0])}})
ok3, r3 = pc.call("command_run", {"id": "layer.layerStyle.dropShadow", "params": {"color": palette["brand-ink"], "opacity": 45, "distance": 6, "size": 12}})
ok4, r4 = pc.call("command_run", {"id": "image.canvasSize", "params": {"width": 512, "height": 512, "anchor": "center", "extensionColor": palette["brand-bg"]}})
ok5, r5 = pc.call("doc_save", {"path": icon})
pc.p.terminate()
check("photocraft: opened vectorcraft's PNG and saved a 512×512 app icon into the project", all([ok1, ok2, ok3, ok4, ok5]) and png_size(icon) == (512, 512),
      [r1, r2, r3, r4, r5])

# --- 3. designcraft: launch poster from photocraft's icon → PNG + PDF
dc = start("designcraft")
ok1, r1 = dc.call("new_document", {"width": 612, "height": 792, "pages": 1, "title": "Orbit launch poster", "margins": 36, "facingPages": False})
ok2, r2 = dc.call("place_image", {"path": icon, "x": 156, "y": 120, "width": 300})
ok3, r3 = dc.call("execute", {"command": "frame.create", "params": {"rect": [72, 470, 540, 560], "content": "text", "text": "Orbit is here. Launching this spring."}})
ok4, r4 = dc.call("export_png", {"page": 0, "path": poster_png, "scale": 1})
ok5, r5 = dc.call("execute", {"command": "file.exportPdf", "params": {"path": poster_pdf}})
dc.p.terminate()
check("designcraft: placed photocraft's icon in a poster and exported PNG + PDF into the project",
      all([ok1, ok2, ok3, ok4, ok5]) and png_size(poster_png) and open(poster_pdf, "rb").read(5) == b"%PDF-", [r1, r2, r3, r4, r5])

# --- 4. 3D: ForgeCraft routes, MeshCraft builds, the asset is handed off into this project
fc = start("forgecraft")
okp, p = fc.call("generate", {"brief": "low-poly wooden crate prop for the Orbit landing page", "name": "Orbit Crate", "profiles": ["three-web-toon"],
                             "handoff_dir": os.path.join(proj, "assets", "3d")}, timeout=1800)
fc.p.terminate()
glb = [os.path.join(r, f) for r, _, fs in os.walk(os.path.join(proj, "assets", "3d")) for f in fs if f.endswith(".glb")]
check("forgecraft + meshcraft: 3D asset built, engine-checked and handed off into the project", okp and p.get("status") == "done" and glb
      and open(glb[0], "rb").read(4) == b"glTF", p if not okp else (p.get("status"), p.get("error"), glb))

# --- hand-offs and placement, from the audit log
audit = os.path.join(os.environ.get("GITCRAFT_HOME", os.path.expanduser("~/.gitcraft")), "logs", "audit.jsonl")
ents = [json.loads(l) for l in open(audit)] if os.path.exists(audit) else []
txt = json.dumps(ents)
check("hand-offs are hashed in the audit log (vectorcraft PNG → photocraft, photocraft icon → designcraft)",
      sha(logo_png) in txt and sha(icon) in txt, f"{len(ents)} audit entries")
new = []
for root, _, fs in os.walk(proj):
    if "/.git" in root: continue
    new += [os.path.relpath(os.path.join(root, f), proj) for f in fs]
report["files"] = {f: sha(os.path.join(proj, f)) for f in sorted(new) if not f.startswith(".gitcraft-work/") or f.endswith(".png")}
check("deliverables landed in the project's asset folders", all(os.path.exists(p) for p in (logo_svg, icon, poster_png, poster_pdf)) and bool(glb))
check("the project's existing asset was not overwritten", sha(existing) == existing_sha)
after_checkout = subprocess.run(["git", "-C", checkout, "status", "--porcelain"], capture_output=True, text=True).stdout
check("the GITCRAFT checkout is unchanged by work in the other project", before_checkout == after_checkout)
json.dump(report, open(report_path, "w"), indent=1)
print(f"\n{sum(results)}/{len(results)} project checks passed")
sys.exit(0 if all(results) else 1)
