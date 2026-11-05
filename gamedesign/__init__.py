"""DESIGNCRAFT: game-design intelligence for the Craft ecosystem (package `gamedesign`).

Inspects a game repository read-only, builds a game model, runs five analysis departments (LEVELCRAFT,
MISSIONCRAFT, STORYCRAFT, PROGRESSIONCRAFT, EXPERIENCECRAFT), writes three design alternatives per significant
finding, scores the design out of 100 with evidence and confidence, keeps a history and publishes a web app.
The product name is DESIGNCRAFT; the package is `gamedesign` so it never collides with GITCRAFT's
`designcraft` page-layout MCP server. See docs/designcraft.md."""
import hashlib, os

VERSION = "1.0.0"
HERE = os.path.dirname(os.path.abspath(__file__))


def method_hash():
    """Hash of the analysis code: assessments compare as 'measured change' only under the same method."""
    h = hashlib.sha256()
    for d, _, fs in sorted(os.walk(HERE)):
        if "web" in d.split(os.sep) or "__pycache__" in d: continue
        for f in sorted(fs):
            if f.endswith(".py") and f not in ("site.py", "cli.py", "__main__.py", "history.py", "report.py", "lab.py"):
                h.update(f.encode()); h.update(open(os.path.join(d, f), "rb").read())
    return h.hexdigest()[:12]
