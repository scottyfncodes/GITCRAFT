"""Evaluator dependency health: can the evaluators the Production Report depends on actually run here?

Checked by doing the work, never by looking for a file: the Studio runtime must start and answer, and the browser the
measuring departments share (PLAYCRAFT, PIXELCRAFT, TestCraft) must launch, render a page and run its script. A Chromium
that exists on disk but cannot start is the failure this exists to catch.

  python3 -m production evaluators        prints the checks; exit code 1 when a required one fails

A failed check is a failure of GITCRAFT's own tooling. It is reported as that, with the reason, and is never turned
into a score or a finding about a project (production/scoring.py: validity)."""
import json, os, subprocess
from . import REPO

BROWSER_DEPARTMENTS = ("playcraft", "pixelcraft", "testcraft")
PROBE = ("import json, sys; sys.path.insert(0, sys.argv[1]); from core import runners; "
         "r = runners.node('harness.mjs', {'html': '<!doctype html><canvas id=c width=8 height=8></canvas><script>"
         "document.getElementById(\\'c\\').getContext(\\'2d\\').fillRect(0,0,8,8);window.__report={sum:1+1};window.__done=true</script>', "
         "'size': [64, 64], 'timeout_ms': 15000}, 60); print(json.dumps(r, default=str))")


def studio_python():
    home = os.environ.get("GITCRAFT_STUDIO_HOME") or os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "studio")
    return os.path.join(home, "venv", "bin", "python")


def _last(text):
    lines = [x.strip() for x in (text or "").strip().splitlines() if x.strip()]
    said = next((x for x in lines if "Error" in x and not x.startswith(("Traceback", "File ", "raise "))), None)   # the error itself, not the last stack frame
    return (said or (lines[-1] if lines else ""))[:400]


def check(timeout=90):
    """{ok, checks: [{id, title, ok, detail, needed_by}]}. ok is False when any check failed."""
    py = studio_python(); out = []
    have = os.path.exists(py)
    out.append({"id": "studio-runtime", "title": "Studio runtime (the departments' Python environment)", "ok": have, "needed_by": ["playcraft", "pixelcraft", "testcraft", "assetcraft"],
                "detail": py if have else f"not installed ({py}); install it with scripts/install-studio.sh"})
    if have:
        try:
            r = subprocess.run([py, os.path.join(REPO, "studio", "cli.py"), "--call", "studio_status", "{}"], capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
            st = json.loads((r.stdout or "").strip().splitlines()[-1]) if r.returncode == 0 and (r.stdout or "").strip() else None
        except (subprocess.TimeoutExpired, ValueError, OSError) as e:
            r, st = None, None; err = f"{type(e).__name__}: {e}"[:300]
        ok = isinstance(st, dict) and not st.get("state")
        out.append({"id": "studio-answers", "title": "Studio departments answer", "ok": ok, "needed_by": ["playcraft", "pixelcraft", "testcraft", "assetcraft"],
                    "detail": "studio_status answered" if ok else (str(st.get("state")) if isinstance(st, dict) else (_last(r.stderr) if r is not None else err) or "no answer")})
        try:
            r = subprocess.run([py, "-c", PROBE, os.path.join(REPO, "studio")], capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
            res = json.loads((r.stdout or "").strip().splitlines()[-1]) if r.returncode == 0 and (r.stdout or "").strip() else None
            why = None if res else _last(r.stderr) or f"exit code {r.returncode}"
        except subprocess.TimeoutExpired:
            res, why = None, f"the browser did not answer within {timeout} s"
        except (ValueError, OSError) as e:
            res, why = None, f"{type(e).__name__}: {e}"[:300]
        ran = isinstance(res, dict) and ((res.get("report") or {}).get("sum") == 2 or res.get("sum") == 2)
        out.append({"id": "browser", "title": "Browser (Chromium through Playwright) launches, renders a page and runs its script", "ok": bool(ran), "needed_by": list(BROWSER_DEPARTMENTS),
                    "detail": "launched, rendered and ran a script" if ran else (why or f"the page did not report back: {json.dumps(res, default=str)[:300]}")})
    return {"ok": all(c["ok"] for c in out), "checks": out}


def text(H):
    L = ["Evaluator dependency health: " + ("OK" if H["ok"] else "FAILED")]
    for c in H["checks"]:
        L.append(f"  [{'ok' if c['ok'] else 'FAILED'}] {c['title']}: {c['detail']}" + ("" if c["ok"] else f" (needed by {', '.join(c['needed_by'])})"))
    return "\n".join(L)
