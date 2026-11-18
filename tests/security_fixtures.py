"""Recorded GitHub API answers for the deployment/infrastructure approval tests (production/approvals.py).

Nothing here contacts GitHub: github() returns a fetch function that answers the three requests verify() makes
(the run, its approvals, the environment) from the arguments, so each refusal can be produced on purpose."""
import os, subprocess, urllib.error

RUN_URL = "https://github.com/{repo}/actions/runs/424242"


def add_origin(path, repo):
    if not os.path.isdir(os.path.join(path, ".git")):
        subprocess.run(["git", "-C", path, "init", "-q"], check=True)
    subprocess.run(["git", "-C", path, "remote", "remove", "origin"], capture_output=True)
    subprocess.run(["git", "-C", path, "remote", "add", "origin", f"https://github.com/{repo}.git"], check=True)


def github(pid, task, repo, env="production", approved=True, user_type="User", reviewers=True, status="completed",
           conclusion="success", title=None, workflow=".github/workflows/gitcraft-approval.yml", approval_env=None, fail=None):
    run = {"id": 424242, "path": workflow, "display_title": title or f"GITCRAFT approval: {pid} {task}", "status": status,
           "conclusion": conclusion, "head_sha": "a" * 40, "triggering_actor": {"login": "owner"}, "actor": {"login": "owner"}}
    approvals = [{"state": "approved" if approved else "rejected", "comment": "ship it",
                  "user": {"login": "owner" if user_type == "User" else "claude[bot]", "type": user_type},
                  "environments": [{"name": approval_env or env}]}] if approved is not None else []
    envinfo = {"name": env, "can_admins_bypass": False,
               "protection_rules": [{"type": "required_reviewers", "reviewers": [{"type": "User", "reviewer": {"login": "owner"}}]}] if reviewers else []}

    def fetch(path, token=None):
        if fail == "network": raise OSError("no route to host")
        if fail == "404": raise urllib.error.HTTPError(path, 404, "Not Found", {}, None)
        if path == f"/repos/{repo}/actions/runs/424242": return run
        if path == f"/repos/{repo}/actions/runs/424242/approvals": return approvals
        if path == f"/repos/{repo}/environments/{env}": return envinfo
        raise urllib.error.HTTPError(path, 404, "Not Found", {}, None)
    return fetch
