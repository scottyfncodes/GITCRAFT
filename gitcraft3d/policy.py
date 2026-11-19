"""What a sandboxed GITCRAFT tool may never write, because something outside the sandbox later runs or trusts it.

Standard library only. Used by scripts/mcp.sh (which roots may be granted at all), scripts/guard.py (path arguments
and the per-call tripwire) and MeshCraft's run_script (which folders a script may write). One list, three enforcers.

Landlock (scripts/sandbox.py) can only ALLOW paths: a writable root makes everything beneath it writable. So:

  1. Roots that would expose control files wholesale are refused outright (unsafe_root): /, $HOME or any folder
     holding it, GITCRAFT's own runtime, code, binaries, logs and network policy, and the home's credential and
     config folders (~/.ssh, ~/.claude, ~/.config ...). The kernel then makes those unreachable.
  2. Inside an allowed root (a repository), the control files are named here (protected) and defended by the guard:
     a tool call naming one is refused, and a tripwire snapshots them around every call and restores any change.
     run_script, which runs arbitrary Python, gets a second kernel layer that can write only folders holding none.

Control files are those something unsandboxed executes or obeys later: git hooks and config (core.hooksPath,
core.fsmonitor ...), Claude Code settings and hooks (.claude/, .mcp.json) and the scripts those hooks run, editor
auto-run tasks (.vscode/), hook managers (.husky/, .pre-commit-config.yaml, lefthook), direnv (.envrc), package
manager config (.npmrc, .yarnrc*) and shell start-up files.
"""
import json, os, re, shlex, stat

# folders that are control folders wherever they appear (a component of the path)
PROTECTED_DIRS = {".git", ".claude", ".husky", ".vscode", ".ssh", ".gnupg"}
# files that are control files wherever they appear (the basename)
PROTECTED_FILES = {".mcp.json", ".claude.json", ".envrc", ".npmrc", ".yarnrc", ".yarnrc.yml", ".pre-commit-config.yaml",
                   "lefthook.yml", ".lefthook.yml", ".gitconfig", ".bashrc", ".bash_profile", ".bash_login", ".profile",
                   ".zshrc", ".zprofile", ".zshenv", ".zlogin"}
# never a root, nor inside one: the home's credential, config and tool folders
HOME_CONTROL = (".ssh", ".gnupg", ".claude", ".config", ".aws", ".azure", ".kube", ".docker", ".local", ".cache", ".npm",
                ".cargo", ".rustup", ".pyenv", ".nvm", ".vscode", ".gitcraft-control")
# GITCRAFT's own code, binaries, venvs, logs and network policy (shared stores such as productions/, reports/,
# 3d-library/ and state/ are fine as roots: nothing outside the sandbox executes them)
GITCRAFT_CONTROL = ("runtime", "runtimes", "bin", "repo", "src", "target", "logs", "meshcraft", "studio", "forgecraft",
                    "allow-hosts", "status.json")
# exceptions inside those: ForgeCraft's model download cache (written by sandboxed tools, read only by sandboxed tools)
GITCRAFT_STORES = ("forgecraft/hf-cache",)

SNAP_FILE_MAX = 1 << 20       # a control file larger than this is watched by hash only (detected, not restorable)
SNAP_TOTAL_MAX = 16 << 20
SNAP_FILES_MAX = 4000


def _real(p):
    return os.path.realpath(os.path.expanduser(p))


def _under(p, d):
    return p == d or p.startswith(d.rstrip(os.sep) + os.sep)


def gitcraft_home(env=None):
    env = os.environ if env is None else env
    return _real(env.get("GITCRAFT_HOME") or os.path.join(env.get("HOME", "~"), ".gitcraft"))


def unsafe_root(path, env=None):
    """Why `path` may never be a writable root, or None when it may."""
    env = os.environ if env is None else env
    p, home = _real(path), _real(env.get("HOME") or "~")
    gh = gitcraft_home(env)
    if p == os.sep: return "it is the whole filesystem"
    if _under(home, p): return f"it is {'the home folder' if p == home else 'a folder that contains the home folder'} ({home}), which holds ~/.ssh, ~/.claude and shell start-up files"
    if _under(gh, p): return f"it contains GITCRAFT's own runtime and configuration ({gh})"
    for d in HOME_CONTROL:
        if _under(p, os.path.join(home, d)): return f"it is inside {os.path.join(home, d)} (credentials or tool configuration)"
    cfg = env.get("CLAUDE_CONFIG_DIR")
    if cfg and _under(p, _real(cfg)): return "it is inside Claude Code's configuration folder"
    for d in GITCRAFT_STORES:   # caches inside a control folder that nothing outside the sandbox executes
        if _under(p, os.path.join(gh, d)): return None
    for d in GITCRAFT_CONTROL:
        if _under(p, os.path.join(gh, d)): return f"it is inside GITCRAFT's {d} ({os.path.join(gh, d)}), which runs outside the sandbox or sets its policy"
    rt = os.path.join(gh, "runtime")
    if os.path.exists(rt) and _under(p, _real(rt)): return "it is inside the installed GITCRAFT runtime"
    return None


# ------------------------------------------------------------------ control files inside a repository
_HOOK_VAR = re.compile(r"\$\{?CLAUDE_PROJECT_DIR\}?")


def hook_targets(repo):
    """Files and folders in `repo` that its Claude Code hooks run (the command's script and, unless that is the repo
    root, the folder it lives in, since such scripts source their neighbours), plus git's core.hooksPath."""
    out = set()
    for name in ("settings.json", "settings.local.json"):
        try: cfg = json.load(open(os.path.join(repo, ".claude", name)))
        except Exception: continue
        for groups in (cfg.get("hooks") or {}).values() if isinstance(cfg, dict) else ():
            for g in groups if isinstance(groups, list) else ():
                for h in (g.get("hooks") or []) if isinstance(g, dict) else ():
                    cmd = h.get("command") if isinstance(h, dict) else None
                    if not isinstance(cmd, str): continue
                    try: toks = shlex.split(_HOOK_VAR.sub(repo, cmd))
                    except ValueError: toks = cmd.split()
                    for t in toks:
                        if t.startswith("-") or "/" not in t: continue
                        f = _real(t if os.path.isabs(t) else os.path.join(repo, t))
                        if _under(f, _real(repo)) and os.path.exists(f):
                            out.add(f)
                            d = os.path.dirname(f)
                            if d != _real(repo): out.add(d)
    try:
        m = re.search(r"^\s*hookspath\s*=\s*(.+?)\s*$", open(os.path.join(repo, ".git", "config")).read(), re.I | re.M)
        if m:
            d = _real(os.path.join(repo, m.group(1).strip().strip('"')))
            if _under(d, _real(repo)) and d != _real(repo): out.add(d)
    except OSError:
        pass
    return out


def _repo_of(p, roots):
    """The nearest folder at or above p (within a root) that is a repository or has Claude settings."""
    d = p if os.path.isdir(p) else os.path.dirname(p)
    tops = [_real(r) for r in roots]
    while True:
        if os.path.isdir(os.path.join(d, ".git")) or os.path.isdir(os.path.join(d, ".claude")): return d
        if d in tops or d == os.sep or not any(_under(d, t) for t in tops): return None
        d = os.path.dirname(d)


def protected(path, roots=()):
    """Why `path` is a control file a tool may not touch, or None."""
    p = _real(path)
    tops = sorted((_real(r) for r in roots), key=len, reverse=True)
    base = next((t for t in tops if _under(p, t)), None)
    rel = os.path.relpath(p, base) if base else p.lstrip(os.sep)
    parts = [x for x in rel.split(os.sep) if x not in ("", ".")]
    for x in parts:
        if x in PROTECTED_DIRS: return f"{x}/ holds control files (hooks, settings) that run outside the sandbox"
    if parts and parts[-1] in PROTECTED_FILES: return f"{parts[-1]} is a control file read or run outside the sandbox"
    repo = _repo_of(p, roots) if roots else None
    if repo:
        for t in hook_targets(repo):
            if _under(p, t): return f"{os.path.relpath(t, repo)} is run by the repository's hooks"
    return None


def dir_has_protected(d, roots=(), limit=20000):
    """Why a folder may not be handed to a script as writable (it holds, or is inside, control files), or None."""
    d = _real(d)
    why = protected(d, roots)
    if why: return why
    repo = _repo_of(d, roots) if roots else None
    if repo:
        for t in hook_targets(repo):
            if _under(t, d): return f"it contains {os.path.relpath(t, repo)}, which the repository's hooks run"
    n = 0
    for cur, dirs, files in os.walk(d):
        n += len(dirs) + len(files)
        if n > limit: return f"it holds more than {limit} entries: pass a narrower output folder"
        hit = next((x for x in dirs if x in PROTECTED_DIRS), None) or next((x for x in files if x in PROTECTED_FILES), None)
        if hit: return f"it contains {os.path.relpath(os.path.join(cur, hit), d)} (a control file)"
        for x in list(dirs):
            if os.path.isdir(os.path.join(cur, x, ".claude")):
                for t in hook_targets(os.path.join(cur, x)):
                    if _under(t, d): return f"it contains {os.path.relpath(t, d)}, which a repository's hooks run"
    return None


# ------------------------------------------------------------------ the tripwire: snapshot, compare, restore
def _repos(roots):
    seen = []
    for r in roots:
        r = _real(r)
        for c in [r] + [os.path.join(r, x) for x in (sorted(os.listdir(r)) if os.path.isdir(r) else [])]:
            if os.path.isdir(c) and (os.path.isdir(os.path.join(c, ".git")) or os.path.isdir(os.path.join(c, ".claude"))) and c not in seen:
                seen.append(c)
    return seen


def _watch(repo):
    """The control files of one repository (existing ones, and the folders where new ones would appear)."""
    files, dirs = [], []
    for rel in (".git/config", ".mcp.json", ".envrc", ".npmrc", ".yarnrc", ".yarnrc.yml", ".pre-commit-config.yaml", "lefthook.yml", ".lefthook.yml"):
        files.append(os.path.join(repo, rel))
    for rel, depth in ((".git/hooks", 1), (".claude", 3), (".husky", 2), (".vscode", 1)):
        dirs.append((os.path.join(repo, rel), depth))
    for t in hook_targets(repo):
        (dirs.append((t, 2)) if os.path.isdir(t) else files.append(t))
    out = set(f for f in files)
    for d, depth in dirs:
        if not os.path.isdir(d): continue
        base = d.count(os.sep)
        for cur, sub, fs in os.walk(d):
            if cur.count(os.sep) - base >= depth: sub[:] = []
            for f in fs: out.add(os.path.join(cur, f))
    return out, [d for d, _ in dirs]


def snapshot(roots):
    """{path: (mode, bytes or None, sha)} for every control file under the roots, plus the watched folders."""
    import hashlib
    snap, total, watched = {}, 0, []
    for repo in _repos(roots):
        files, dirs = _watch(repo)
        watched += dirs
        for f in sorted(files):
            if len(snap) >= SNAP_FILES_MAX: break
            try:
                st = os.lstat(f)
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode):
                snap[f] = (st.st_mode, None, "link:" + os.readlink(f)); continue
            if not stat.S_ISREG(st.st_mode): continue
            try: data = open(f, "rb").read() if st.st_size <= SNAP_FILE_MAX and total + st.st_size <= SNAP_TOTAL_MAX else None
            except OSError: continue
            total += len(data or b"")
            h = hashlib.sha256(data if data is not None else open(f, "rb").read()).hexdigest()
            snap[f] = (st.st_mode, data, h)
    return {"files": snap, "watched": watched, "repos": _repos(roots)}


def compare_and_restore(before, roots, stamp):
    """Changes to control files since `before`; each one is undone (new or changed content moved aside to
    <file>.gitcraft-quarantine-<stamp>, the original content and mode put back, deleted files restored).
    Returns [{path, change, restored, quarantine}]."""
    after = snapshot(roots)
    out = []
    old, new = before["files"], after["files"]
    for f in sorted(set(old) | set(new)):
        a, b = old.get(f), new.get(f)
        if a and b and a[2] == b[2] and stat.S_IMODE(a[0]) == stat.S_IMODE(b[0]): continue
        change = "created" if not a else "deleted" if not b else "modified"
        rec = {"path": f, "change": change, "restored": False, "quarantine": None}
        try:
            if b:
                q = f"{f}.gitcraft-quarantine-{stamp}"
                os.rename(f, q); os.chmod(q, 0o600); rec["quarantine"] = q
            if a and a[1] is not None:
                os.makedirs(os.path.dirname(f), exist_ok=True)
                fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as fh: fh.write(a[1])
                os.chmod(f, stat.S_IMODE(a[0])); rec["restored"] = True
            elif a and a[2].startswith("link:"):
                os.symlink(a[2][5:], f); rec["restored"] = True
            elif not a:
                rec["restored"] = True   # it did not exist before: moving it aside is the restore
        except OSError as e:
            rec["error"] = f"{type(e).__name__}: {e}"
        out.append(rec)
    return out


if __name__ == "__main__":   # python3 policy.py check-roots DIR... (scripts/mcp.sh): exit 1 with the reason on stdout
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "check-roots":
        for r in sys.argv[2:]:
            if not r: continue
            why = unsafe_root(r)
            if why: print(f"the root {r} is refused because {why}"); sys.exit(1)
        sys.exit(0)
    print("usage: policy.py check-roots DIR...", file=sys.stderr); sys.exit(2)
