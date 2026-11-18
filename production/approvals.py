"""Approvals the acting agent cannot grant itself: deployment and infrastructure.

Every other approval (the app icon, the style and design picks, replacing assets, an escalated re-run) is a person's
choice relayed through production_approve. Deploying to production and creating infrastructure (a database, hosting)
are different: they change live systems with the session's credentials, so the session must not be able to say yes on
the person's behalf. For these two kinds:

  * production_approve, engine.approve and the blueprint's `authorisations` are refused (fail closed);
  * the only way through is approve_external(): a GitHub Actions run of the project's `gitcraft-approval.yml` workflow
    (production/kit/release/gitcraft-approval.yml) whose job uses a GitHub environment with REQUIRED REVIEWERS, which a
    person approved in GitHub (web or mobile). verify() checks that through GitHub's REST API: the run is that workflow
    in this project's repository, names this production and task, finished successfully, the environment requires
    reviewers, and a GitHub *user* (not an app or bot) approved this run for that environment;
  * anything it cannot verify (no network, a private repository without a token, a run that was not approved) is a
    refusal, never an approval.

What GitHub enforces is the independent part: the agent can start the workflow but cannot approve its own run, as long
as its GitHub credentials cannot review deployments (check the Claude GitHub App's permissions) and administrators may
not bypass the environment's protection (docs/security.md, "Approvals"). GITCRAFT's own records are not a security
boundary against code with shell access; they make sure GITCRAFT never treats the agent's word as the approval.
"""
import json, os, re, subprocess, urllib.error, urllib.request

EXTERNAL = {"deploy": "production", "infrastructure": "infrastructure"}   # approval kind -> required GitHub environment
WORKFLOW = ".github/workflows/gitcraft-approval.yml"
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kit", "release", "gitcraft-approval.yml")
API = "https://api.github.com"
RUN_URL = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/actions/runs/(\d+)(?:/attempts/\d+)?/?$")


class NotApproved(PermissionError):
    pass


def kind(task):
    return ((task or {}).get("work_order") or {}).get("approval")


def external(task):
    return kind(task) in EXTERNAL


def title(pid, task_id):
    """The run name the workflow gives itself (run-name), which verify() requires: ties the run to one decision."""
    return f"GITCRAFT approval: {pid} {task_id}"


def how(prod, task):
    env = EXTERNAL[kind(task)]
    return (f"{kind(task)} needs a person's approval in GitHub; the agent cannot grant it. 1) Once per repository: add {WORKFLOW} "
            f"(copy {os.path.relpath(TEMPLATE, os.path.dirname(os.path.dirname(TEMPLATE)))}) and create the GitHub environment '{env}' with "
            f"Required reviewers (the person) and administrators NOT allowed to bypass. 2) Run the workflow with production={prod['id']} "
            f"task={task['id']} environment={env}. 3) The person approves the run in GitHub. 4) Record it: "
            f"python3 -m production approve-external {prod['id']} {task['id']} --run <the run's URL> (verified against GitHub's API).")


REFUSAL = ("{kind} approval cannot be given through production_approve: the agent that would carry it out must not approve it. "
           "A person approves it in GitHub (an environment with required reviewers), then `python3 -m production approve-external` "
           "verifies that approval. A decline is accepted here.")


def project_repo(path):
    """owner/name of the project's GitHub remote (origin), or None."""
    if not path: return None
    try:
        url = subprocess.run(["git", "-C", path, "remote", "get-url", "origin"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return None
    m = re.search(r"github\.com[:/]+([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def _fetch(path, token=None):
    req = urllib.request.Request(API + path, headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                                                     "User-Agent": "gitcraft-approvals"})
    tok = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok: req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=20) as r:   # default TLS verification, never disabled
        return json.load(r)


def verify(run_url, pid, task_id, approval_kind, repo=None, fetch=None):
    """Evidence that a person approved this decision in GitHub, or NotApproved with the reason."""
    fetch = fetch or _fetch
    env = EXTERNAL.get(approval_kind)
    if not env: raise NotApproved(f"{approval_kind!r} is not an externally approved kind")
    m = RUN_URL.match(run_url or "")
    if not m: raise NotApproved("not a GitHub Actions run URL (https://github.com/<owner>/<repo>/actions/runs/<id>)")
    owner, name, rid = m.groups()
    slug = f"{owner}/{name}"
    if not repo: raise NotApproved("the project has no GitHub remote (origin), so the approval cannot be tied to it")
    if slug.lower() != repo.lower(): raise NotApproved(f"the run is in {slug}, not in this project's repository {repo}")
    try:
        run = fetch(f"/repos/{slug}/actions/runs/{rid}")
        approvals = fetch(f"/repos/{slug}/actions/runs/{rid}/approvals")
        envinfo = fetch(f"/repos/{slug}/environments/{env}")
    except urllib.error.HTTPError as e:
        raise NotApproved(f"UNVERIFIED: GitHub answered {e.code} ({'a private repository needs GITHUB_TOKEN' if e.code in (401, 403, 404) else 'error'})")
    except Exception as e:
        raise NotApproved(f"UNVERIFIED: GitHub's API could not be reached ({type(e).__name__}); nothing was approved")
    if (run.get("path") or "").split("@")[0] != WORKFLOW:
        raise NotApproved(f"the run is of {run.get('path')!r}, not {WORKFLOW}")
    if (run.get("display_title") or run.get("name")) != title(pid, task_id):
        raise NotApproved(f"the run is named {run.get('display_title')!r}, not {title(pid, task_id)!r} (it approves a different decision)")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise NotApproved(f"the run has not finished successfully (status {run.get('status')}, conclusion {run.get('conclusion')}): it is approved when its job ran")
    rules = envinfo.get("protection_rules") or []
    reviewers = [r for rule in rules if rule.get("type") == "required_reviewers" for r in (rule.get("reviewers") or [])]
    if not reviewers:
        raise NotApproved(f"the GitHub environment '{env}' has no required reviewers, so its runs are not a person's approval")
    ok = [a for a in approvals if isinstance(a, dict) and a.get("state") == "approved" and (a.get("user") or {}).get("type") == "User"
          and any((e or {}).get("name") == env for e in a.get("environments") or [])]
    if not ok:
        raise NotApproved(f"no GitHub user approved this run for the '{env}' environment")
    if envinfo.get("can_admins_bypass") is True:
        bypass = "administrators may bypass this environment's protection (turn that off: Settings > Environments)"
    else:
        bypass = None
    return {"run": run_url, "run_id": int(rid), "repository": slug, "environment": env, "head_sha": run.get("head_sha"),
            "approved_by": sorted({(a.get("user") or {}).get("login") for a in ok}), "comments": [a.get("comment") for a in ok if a.get("comment")],
            "triggered_by": (run.get("triggering_actor") or run.get("actor") or {}).get("login"),
            "required_reviewers": sorted({(r.get("reviewer") or {}).get("login") or (r.get("reviewer") or {}).get("slug") or "?" for r in reviewers}),
            "warning": bypass, "verified_via": "GitHub REST API"}
