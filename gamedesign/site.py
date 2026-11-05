"""Publish the DESIGNCRAFT web app (static, standard library only, so the Vercel build runs it).

  publish(archive, dist)   archive = history/designcraft (recorded assessments, append-only)
                           dist    = output folder, e.g. forgecraft/ui/dist/designcraft
Writes index.html + app.js + app.css (gamedesign/web), data/index.json (every game, latest scores, trend) and
per game data/<id>.json (latest assessment + run summaries + comparison) and data/<id>.report.md."""
import json, os, shutil
from . import history, report

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def publish(archive, dist):
    if os.path.isdir(dist): shutil.rmtree(dist)
    os.makedirs(os.path.join(dist, "data"))
    for f in os.listdir(WEB):
        shutil.copy(os.path.join(WEB, f), os.path.join(dist, f))
    games = []
    if os.path.isdir(archive):
        for gid in sorted(os.listdir(archive)):
            if not os.path.isdir(os.path.join(archive, gid)): continue
            runs = history.runs(gid, archive)
            if not runs: continue
            A = runs[-1]
            A["history"] = [history.summary(r) for r in runs]
            with open(os.path.join(dist, "data", gid + ".json"), "w") as fh: json.dump(A, fh, separators=(",", ":"), default=str)
            with open(os.path.join(dist, "data", gid + ".report.md"), "w") as fh: fh.write(report.assessment_md(A))
            s = history.summary(A)
            games.append({"id": gid, "title": A["game"]["title"], "pitch": A["game"].get("pitch"), "genres": A["game"].get("genres"), "engine": A["game"].get("engine"),
                          "remote": A["game"].get("remote"), "latest": s, "runs": len(runs), "trend": [r["overall"] for r in A["history"]],
                          "top": [{"title": f["title"], "severity": f["severity"], "dept": f["dept"]} for f in A["findings"][:3]]})
    games.sort(key=lambda g: -g["latest"]["coverage"])
    with open(os.path.join(dist, "data", "index.json"), "w") as fh:
        json.dump({"games": games, "generated_from": "history/designcraft"}, fh, separators=(",", ":"))
    return len(games)
