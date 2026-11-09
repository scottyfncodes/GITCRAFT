#!/usr/bin/env python3
"""Department linkage: the hand-offs between departments and the readings that pick them, end to end without
running a department. Each check names the defect it guards against; each was failing before its fix.

    python3 tests/test_linkage.py      (seconds; the PLAYCRAFT refusal runs through the Studio CLI when its runtime is installed)"""
import json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO); sys.path.insert(0, os.path.join(REPO, "studio"))
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-linkage-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws)
from production import intake, planner, gates, engine, builtins, maturity, entry, lifecycle, standards, project_report, executors, discovery
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)


def write(root, files):
    for rel, text in files.items():
        p = os.path.join(root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f: f.write(text)
    return root


# ---------------------------------------------------------------- what kind of project it is (BookNd: an e-book reader scored as a game)
reader = write(os.path.join(ws, "reader"), {
    "package.json": json.dumps({"scripts": {"dev": "next dev"}, "dependencies": {"next": "16.4.5", "react": "19.3.1", "react-dom": "19.3.1", "dexie": "4.4.7", "epubjs": "0.3.93"}}),
    "README.md": "# Booknd\n\nRead your EPUB library offline, with a page-turn animation.\n",
    "app/page.tsx": "export default function Page() { return <main><form onSubmit={add}><input/></form></main>; }\n",
    "lib/ink.ts": "export function runInk(canvas) {\n  const ctx = canvas.getContext('2d');\n  ctx.fillRect(0, 0, 10, 10);\n}\n",
    "components/Reader.tsx": "// Typography lives in a <style> we own inside each chapter document.\nexport const Reader = () => null;\n",
    "app/globals.css": ".a { font-weight: 600; } /* heading level */\n.b { z-index: 2; } /* level two */\n"})
canvas_game = write(os.path.join(ws, "dodge"), {
    "README.md": "# Dodge\n\nAn arcade game: dodge the rocks.\n", "index.html": "<canvas id=c></canvas><script src=game.js></script>",
    "game.js": "const cx = c.getContext('2d'); let player = {x: 0, lives: 3}, score = 0;\naddEventListener('keydown', e => player.x++);\n"
               "function loop() { score++; requestAnimationFrame(loop); }\nloop();\n"})
godot = write(os.path.join(ws, "godot"), {"project.godot": "[application]\n", "level1.tscn": "[gd_scene]\n", "README.md": "# Keep\n"})
K = {n: maturity.kind(p) for n, p in (("reader", reader), ("game", canvas_game), ("godot", godot))}
check("kind: a Next.js reader with one canvas animation, 'lives' in a comment and 'level' in CSS is an app, high confidence",
      K["reader"]["kind"] == "app" and K["reader"]["confidence"] == "high", K["reader"])
check("kind: ...and a 2D canvas without a game loop is not counted as an engine", any("not counted" in e for e in K["reader"]["evidence"]), K["reader"]["evidence"])
check("kind: a canvas game with a loop and input is a game", K["game"]["kind"] == "game", K["game"])
check("kind: Godot scenes make a game without any game words", K["godot"]["kind"] == "game" and "godot" in K["godot"]["engines"], K["godot"])
A = maturity.assess(reader)
check("assess: the kind has its own confidence and evidence (the old 'high' was the maturity's)", A["kind"] == "app" and A.get("kind_confidence") and A.get("kind_evidence"), A.get("kind_evidence"))
check("entry: the kind the person names beats the heuristic", entry._stated_kind("Run GITCRAFT on my e-reader app") == "app"
      and entry._stated_kind("polish this game") == "game" and entry._stated_kind("Run GITCRAFT") is None)

spec_ex = intake.parse("Update this existing project: tidy the settings screen", project=reader)
decs = lifecycle.decisions(spec_ex, {"project": {"exists": True}})
kd = next((d for d in decs if d["id"] == "kind"), None)
check("Decision Room: an existing project's kind is shown with its evidence and can be corrected", kd and kd["recommended"] == "app"
      and {"game", "app", "site"} == {o["value"] for o in kd["options"]} and kd["sets"]["game"]["deliverable"] == "game", kd)
weak = dict(spec_ex, mode=dict(spec_ex["mode"], kind_confidence="low"))
kw = next(d for d in lifecycle.decisions(weak, {"project": {"exists": True}}) if d["id"] == "kind")
check("Decision Room: a low-confidence kind is an essential question (approval waits for it)", kw["kind"] == "question" and "essential" in kw["why"], kw)

# ---------------------------------------------------------------- planning: requests that were dropped or made the plan unapprovable
def plan(prompt, path):
    s = intake.parse(prompt); s["project"]["path"] = os.path.join(ws, path)
    d = discovery.run(s); return s, d, planner.build(s, d)

s, d, pl = plan("Build a polished mobile pirate adventure game with voice lines, music, sound effects, a trailer and a 3D ocean island with a 3D model of a pirate captain, animated", "pirate")
T = pl["tasks"]
check("plan: voice lines no longer make the plan unapprovable (a required input handed on by $from)", not [p for p in planner.validate(pl, d) if "voice" in p], planner.validate(pl, d))
check("plan: the whole voice/trailer/ocean/animation plan validates", planner.validate(pl, d) == [], planner.validate(pl, d))
check("plan: a trailer schedules CinematicCraft (title card + gameplay capture + assembly with the music)",
      {"trailer.title", "trailer.capture", "trailer.assemble"} <= set(T) and "audio.music" in T["trailer.assemble"]["depends_on"]
      and "asset_trailer" in {c["id"] for c in s["acceptance"]}, sorted(t for t in T if t.startswith("trailer")))
check("plan: an ocean schedules WorldCraft's ocean (it used to become only an ambience sound)", "world.ocean" in T and T["world.ocean"]["action"] == "ocean", sorted(T))
check("plan: an animated character goes 3D model → AnimCraft rig → AnimCraft clips → TestCraft playback",
      T.get("anim.1.rig", {}).get("depends_on") == ["models.1"] and T["anim.1.clips"]["depends_on"] == ["anim.1.rig"]
      and T["anim.1.check"]["department"] == "testcraft" and T["anim.1.check"]["action"] == "animation"
      and T["anim.1.rig"]["params"]["input"]["$from"] == "models.1", {k: T[k]["depends_on"] for k in T if k.startswith("anim.")})
check("plan: the animated GLB ships into the project and integration waits for it", T["anim.1.clips"]["ship"]["roles"] == ["animated_mesh"]
      and "anim.1.clips" in T["integrate.assets"]["depends_on"])
check("plan: built-in tasks are gated (integration and scaffold used to pass a partial failure)", T["integrate.assets"]["gate"] and T["foundation.scaffold"]["gate"])
check("plan: DESIGNCRAFT and PLAYCRAFT stay in the parallel QA wave", T["qa.playcraft"]["depends_on"] == ["build"] and T["qa.designcraft"]["depends_on"] == ["build"])
s2, d2, pl2 = plan("Build a 3D low-poly island game with a 3D model of a lighthouse, animated", "lighthouse")
check("plan: a prop is never auto-rigged (autorig replaces an armature)", not any(t.startswith("anim.") for t in pl2["tasks"]) and any("animation asked" in a for a in s2["assumptions"]))

# ---------------------------------------------------------------- the 3D hand-off
fake = {"job": "j", "status": "ok", "asset": {"id": "pirate_captain", "version": 2}, "handoff": os.path.join(ws, "h"),
        "files": {"exports/pirate_captain.glb": "/lib/pirate_captain/v2/exports/pirate_captain.glb", "source/pirate_captain.blend": "/lib/x.blend"}}
os.makedirs(os.path.join(ws, "h", "exports"), exist_ok=True); open(os.path.join(ws, "h", "exports", "pirate_captain.glb"), "wb").write(b"glTF")
fo = engine._forge_outputs(dict(fake))
check("3D: a ForgeCraft result becomes outputs (the model, from the task's hand-off copy) and names its library asset",
      fo["asset_id"] == "pirate_captain" and any(o["role"] == "model" and o["format"] == "glb" and o["path"].startswith(os.path.join(ws, "h")) for o in fo["outputs"]), fo["outputs"])
proj = os.path.join(ws, "proj"); os.makedirs(proj)
exported = os.path.join(proj, "assets/models/pirate_captain_v2"); os.makedirs(os.path.join(exported, "exports"))
glb = os.path.join(exported, "exports/pirate_captain.glb"); open(glb, "wb").write(b"glTF-binary")
json.dump({"license": {"asset": "Owned by the project"}}, open(os.path.join(exported, "asset.json"), "w"))
calls = []
def fake_call(tool, args, timeout=0):
    calls.append((tool, args)); return {"asset": args["asset"], "version": 2, "dir": exported, "verified": True,
                                       "files": [{"path": glb, "sha256": builtins.sha256(glb)}, {"path": os.path.join(exported, "asset.json"), "sha256": "x"}]}
executors.forgecraft_call, real = fake_call, executors.forgecraft_call
up = [{"id": "models.1", "state": "passed", "ship": {"dest": "$project/assets/models", "library": True}, "outputs": fo["outputs"], "result": engine._slim(fo)}]
ctx = {"prod": {"id": "p"}, "project": proj, "upstream": up, "auth": {}, "approved": False, "out_dir": ws, "previous_manifest": None}
r = builtins.integrate(ctx)
check("3D: integration reads ForgeCraft's asset id and exports it (it read asset_id/library.asset, which ForgeCraft never sets)",
      calls and calls[0][1]["asset"] == "pirate_captain", calls)
man = {m["dest_rel"]: m for m in r.get("integrated", [])}
check("3D: the exported GLB is in the integration manifest the build is handed (it was left out)", any(k.endswith("pirate_captain.glb") and v["role"] == "model" for k, v in man.items())
      and os.path.isfile(glb + ".license.json"), man)
check("3D: the model's record files are source, not 'unreferenced assets'", all(v["role"] == "model_source" for k, v in man.items() if k.endswith("asset.json")) and "model_source" in gates.SOURCE_ROLES)
ctx["upstream"] = [dict(up[0], result={"status": "ok"})]
r2 = builtins.integrate(ctx)
check("3D: a passed 3D task with no library asset fails integration as a hand-off (it was skipped silently)", r2["status"] == "failed" and r2["failure"] == "handoff", r2)
executors.forgecraft_call = real
g = gates.evaluate(T["integrate.assets"], {"status": "failed", "checks": [{"name": "3D asset exported", "ok": False}]}, {"project": proj})
check("gate: a partially failed integration no longer passes", g and not all(x["ok"] for x in g), g)

# ---------------------------------------------------------------- findings into fix work orders
px = {"title": "Touch target is too small", "severity": "major", "frequency": "3 screens", "evidence": {"min_px": 28, "selector": "#save"}, "fix": "make it ≥ 44 px"}
items = gates.remediation({"department": "pixelcraft"}, {"summary": {"top_findings": [px]}}, [])
check("work order: a PIXELCRAFT finding is one readable instruction (it was a Python dict)", items and "{'" not in items[0] and "Touch target is too small" in items[0]
      and "44 px" in items[0], items)
items = gates.remediation({"department": "playcraft"}, {"summary": {}}, [], design=[{"id": "m1", "title": "Give each mission its own structure", "priority": "P1"}])
check("work order: DESIGNCRAFT's proposals reach the agent through the gameplay fix (they were recorded only)", any("DESIGNCRAFT proposal (P1)" in i for i in items), items)

# ---------------------------------------------------------------- the department lists agree
from core import routing
fc = open(os.path.join(REPO, "forgecraft", "server.py")).read()
check("lists: ForgeCraft's departments tool names PIXELCRAFT", re.search(r'"departments": \("Every GITCRAFT Studio department \([^)]*pixelcraft', fc))
rr = routing.route("a game design review of my missions and pacing")
check("lists: the Studio router points game-design briefs at DESIGNCRAFT", (rr.get("game_design") or {}).get("use", "").startswith("DESIGNCRAFT"), rr)

# ---------------------------------------------------------------- report and standards readings
D = {"status": "current", "age_days": 1, "notes": []}
project_report._stale(D, {"project": {"head": None}}, "2f70374")
check("report: a score whose commit cannot be compared (no checkout) is unverified, never current", D["status"] == "unverified", D)
tools = write(os.path.join(ws, "toolrepo"), {"vercel.json": json.dumps({"buildCommand": "python3 build.py", "outputDirectory": "site/dist"}), "build.py": "print(1)\n",
                                           "kit/starters/app/index.html": '<link rel="apple-touch-icon" href="assets/icons/apple-touch-icon.png">'})
check("standards: an entry page generated by the build is a review item, not a failure", next(c for c in standards.check(tools)["checks"] if c["id"] == "entry")["status"] == "review")
check("maturity: placeholders in starter templates are not the project's missing files", not maturity.assess(tools)["inventory"]["defects"], maturity.assess(tools)["inventory"]["defects"])

# ---------------------------------------------------------------- registration: two hooks at once
race = os.path.join(ws, "race"); os.makedirs(os.path.join(race, "bin")); os.makedirs(os.path.join(race, "reg")); os.makedirs(os.path.join(race, "home", "bin"))
open(os.path.join(race, "bin", "claude"), "w").write("""#!/usr/bin/env bash
R="$FAKE_REG"; case "$2" in
 remove) sleep 0.05; rm -f "$R/$5";; add) sleep 0.05; [ -e "$R/$5" ] && exit 1; echo "${@: -2:1}" > "$R/$5";;
 get) [ -e "$R/$3" ] && { echo "  Command: $(cat "$R/$3")"; exit 0; }; exit 1;; esac
""")
os.chmod(os.path.join(race, "bin", "claude"), 0o755)
env = dict(os.environ, PATH=os.path.join(race, "bin") + ":" + os.environ["PATH"], FAKE_REG=os.path.join(race, "reg"), HOME=os.path.join(race, "home"),
           GITCRAFT_HOME=os.path.join(race, "home", ".gitcraft"), GITCRAFT_BIN=os.path.join(race, "home", "bin"), GITCRAFT_MESHCRAFT="1", GITCRAFT_STUDIO="1")
ps = [subprocess.Popen(["bash", os.path.join(REPO, "scripts", "register.sh")], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for _ in range(2)]
outs = [p.communicate(timeout=120)[0] for p in ps]
check("register: two runs at once report no false 'couldn't register'", not any("couldn't register" in o for o in outs) and len(os.listdir(os.path.join(race, "reg"))) == 3, outs)

# ---------------------------------------------------------------- PLAYCRAFT refuses to score an app (through the Studio CLI)
py = executors.studio_python()
if py:
    r = subprocess.run([py, os.path.join(REPO, "studio", "cli.py"), "--call", "run", json.dumps({"department": "playcraft", "action": "assess",
                        "params": {"project": reader, "play": False, "out_dir": os.path.join(ws, "pc")}})], capture_output=True, text=True, timeout=300)
    res = json.loads(r.stdout or "{}")
    check("PLAYCRAFT: an app is refused with the reason, not given a gameplay scorecard", res.get("status") == "failed" and "not a game" in (res.get("error") or ""), res.get("error"))
    r = subprocess.run([py, os.path.join(REPO, "studio", "cli.py"), "--call", "run", json.dumps({"department": "playcraft", "action": "assess",
                        "params": {"project": reader, "play": False, "treat_as_game": True, "out_dir": os.path.join(ws, "pc2")}})], capture_output=True, text=True, timeout=300)
    check("PLAYCRAFT: ...unless the caller says it is a game", json.loads(r.stdout or "{}").get("status") == "ok", r.stdout[-300:])
else:
    print("SKIP PLAYCRAFT refusal: the Studio runtime is not installed (scripts/install-studio.sh)")

bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
shutil.rmtree(ws, ignore_errors=True)
sys.exit(1 if bad else 0)
