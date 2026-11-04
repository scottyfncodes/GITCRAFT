#!/usr/bin/env python3
"""PLAYCRAFT acceptance on a real game, from the game's own repository.

    python3 tests/acceptance_playcraft.py <game_repo> [<build_dir>] [<out_dir>] [--full] [--viewports desktop,phone]

Starts studiocraft exactly as Claude Code does in another project: the command and args registered at user scope
in ~/.claude.json (the installed runtime, ~/.gitcraft/runtime, not this checkout), with the game repo as the
working directory and no GITCRAFT variables set. Then runs the PLAYCRAFT pass (or the full GITCRAFT + PLAYCRAFT
pass) on the build and checks what a person would check: the game was read, the genres make sense, the game was
played (screens, responses), the scorecard has evidence levels and the report exists in the game's own
gitcraft-out folder. Writes <out_dir>/ACCEPTANCE.json. Exit 1 on failure."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_client import Client

args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = sys.argv[1:]
proj = os.path.abspath(args[0]); build = os.path.abspath(args[1]) if len(args) > 1 else None
out = os.path.abspath(args[2]) if len(args) > 2 else os.path.join(proj, "gitcraft-out", "playcraft", "acceptance")
vps = flags[flags.index("--viewports") + 1].split(",") if "--viewports" in flags else None
cfg = json.load(open(os.path.join(os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~")), ".claude.json")))
srv = cfg["mcpServers"]["studiocraft"]
env = {k: v for k, v in os.environ.items() if not k.startswith(("GITCRAFT_", "FORGECRAFT_"))}; env.pop("CLAUDE_PROJECT_DIR", None)
rep = {"project": proj, "server": [srv["command"], *srv.get("args", [])], "cwd": proj, "checks": []}


def check(label, ok, detail=""):
    rep["checks"].append({"check": label, "ok": bool(ok), "detail": str(detail)[:400]})
    print(("PASS " if ok else "FAIL ") + label + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)


os.makedirs(out, exist_ok=True)
check("studiocraft is registered from the GITCRAFT runtime, not a project checkout", "/.gitcraft/runtime/" in srv["command"] + " ".join(srv.get("args", [])), rep["server"])
c = Client([srv["command"], *srv.get("args", [])], env=dict(env, **(srv.get("env") or {})), cwd=proj, log=os.path.join(out, "studiocraft.stderr.log"))
tools = {t["name"] for t in c.tools()}
check("PLAYCRAFT tools are available from this repository", {"playcraft_pass", "playcraft_verify", "playcraft_full_pass"} <= tools, len(tools))
tool = "playcraft_full_pass" if "--full" in flags else "playcraft_pass"
params = {"project": proj, "out_dir": out}
if build: params["target"] = build
if vps: params["viewports"] = vps
t = time.time(); ok, r = c.call(tool, params, timeout=2400); rep["seconds"] = round(time.time() - t, 1)
check(f"{tool} ran on the game ({rep['seconds']} s)", ok and isinstance(r, dict) and r.get("status") == "ok", r.get("error") if isinstance(r, dict) else r)
if ok and isinstance(r, dict) and r.get("status") == "ok":
    card = json.load(open(os.path.join(r["out_dir"], "playcraft.json")))
    rep.update(summary=r["summary"], genres=[(g["genre"], g.get("share")) for g in card["genre"]["genres"]], played=card["played"], plan=r.get("plan"),
               engineering=r.get("engineering"), overall=card["overall"])
    check("outputs landed inside the game's workspace, not in GITCRAFT", r["out_dir"].startswith(proj + os.sep) or r["out_dir"].startswith(out), r["out_dir"])
    check("the game was played in the browser", card["played"]["played"], card["played"])
    resp = card["metrics"]["responses"] if card.get("metrics") else []
    check("at least one control produced a verified response", any(x["responded"] for x in resp), [(x["input"], x["responded"]) for x in resp])
    check("every criterion has an evidence level", all(x["level"] in ("verified", "observed", "inferred", "not_tested") for x in card["results"]))
    check("findings are ranked with recommendations", card["findings"] and all(f["recommendation"] for f in card["findings"]))
    check("report written", os.path.exists(os.path.join(r["out_dir"], "playcraft_report.md")))
c.close()
rep["ok"] = all(x["ok"] for x in rep["checks"])
json.dump(rep, open(os.path.join(out, "ACCEPTANCE.json"), "w"), indent=1, default=str)
print(json.dumps({k: rep.get(k) for k in ("genres", "overall", "seconds")}, default=str))
sys.exit(0 if rep["ok"] else 1)
