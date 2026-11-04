#!/usr/bin/env python3
"""Run a command inside a Landlock filesystem (and optional network) sandbox.

    sandbox.py [--rw DIR]... [--ro DIR]... [--rx DIR]... [--no-net [--allow-connect PORT]...] [--require] -- CMD ARGS...

Landlock is a Linux security module (kernel 5.13+) that lets an unprivileged
process give up access to everything except the paths it names. The rules are
inherited by every child process and can never be widened again, so a tool
(and anything it spawns, including scripts it runs) cannot read or write
outside the listed directories, whatever its own settings say.

--rw   read + write (+ create/delete) beneath DIR
--ro   read beneath DIR
--rx   read + execute beneath DIR
--no-net  deny all TCP bind/connect (Landlock ABI >= 4)
--allow-connect PORT  with --no-net: still allow TCP connect to this port (e.g. the local netgate proxy that
          lets through only the hosts in GITCRAFT_ALLOW_HOSTS; Landlock cannot filter by host itself)
--require fail instead of running unsandboxed when Landlock is unavailable

Paths that don't exist are skipped. Exit code 126 means the sandbox could not
be set up and --require was given.
"""
import ctypes, errno, os, sys

SYS_create_ruleset, SYS_add_rule, SYS_restrict_self = 444, 445, 446  # x86_64 + aarch64 share these numbers
PR_SET_NO_NEW_PRIVS = 38
RULE_PATH_BENEATH, RULE_NET_PORT = 1, 2

EXECUTE, WRITE_FILE, READ_FILE, READ_DIR = 1 << 0, 1 << 1, 1 << 2, 1 << 3
REMOVE_DIR, REMOVE_FILE, MAKE_CHAR, MAKE_DIR = 1 << 4, 1 << 5, 1 << 6, 1 << 7
MAKE_REG, MAKE_SOCK, MAKE_FIFO, MAKE_BLOCK, MAKE_SYM = 1 << 8, 1 << 9, 1 << 10, 1 << 11, 1 << 12
REFER, TRUNCATE, IOCTL_DEV = 1 << 13, 1 << 14, 1 << 15
NET_BIND_TCP, NET_CONNECT_TCP = 1 << 0, 1 << 1

FILE_ONLY = EXECUTE | WRITE_FILE | READ_FILE | TRUNCATE | IOCTL_DEV


class RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64), ("handled_access_net", ctypes.c_uint64),
                ("scoped", ctypes.c_uint64)]


class NetPort(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("port", ctypes.c_uint64)]


class PathBeneath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def log(msg):
    print(f"gitcraft-sandbox: {msg}", file=sys.stderr)


def fs_rights(abi):
    r = EXECUTE | WRITE_FILE | READ_FILE | READ_DIR | REMOVE_DIR | REMOVE_FILE | MAKE_CHAR | MAKE_DIR \
        | MAKE_REG | MAKE_SOCK | MAKE_FIFO | MAKE_BLOCK | MAKE_SYM
    if abi >= 2: r |= REFER
    if abi >= 3: r |= TRUNCATE
    if abi >= 5: r |= IOCTL_DEV
    return r


def main(argv):
    rw, ro, rx, no_net, require, ports = [], [], [], False, False, []
    i = 0
    while i < len(argv) and argv[i] != "--":
        a = argv[i]
        if a in ("--rw", "--ro", "--rx"):
            {"--rw": rw, "--ro": ro, "--rx": rx}[a].append(argv[i + 1]); i += 2; continue
        if a == "--allow-connect": ports.append(int(argv[i + 1])); i += 2; continue
        if a == "--no-net": no_net = True
        elif a == "--require": require = True
        else: log(f"unknown option {a}"); return 2
        i += 1
    cmd = argv[i + 1:]
    if not cmd: log("no command"); return 2

    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    abi = libc.syscall(SYS_create_ruleset, None, ctypes.c_size_t(0), ctypes.c_uint32(1))
    if abi < 0:
        if require:
            log("Landlock is not available on this kernel; refusing to run unsandboxed (--require)."); return 126
        log("Landlock unavailable: running WITHOUT the filesystem sandbox.")
        os.execvp(cmd[0], cmd)

    handled = fs_rights(abi)
    attr = RulesetAttr(handled, (NET_BIND_TCP | NET_CONNECT_TCP) if (no_net and abi >= 4) else 0, 0)
    size = ctypes.sizeof(RulesetAttr) if abi >= 6 else (16 if abi >= 4 else 8)
    fd = libc.syscall(SYS_create_ruleset, ctypes.byref(attr), ctypes.c_size_t(size), ctypes.c_uint32(0))
    if fd < 0:
        log(f"landlock_create_ruleset failed: {os.strerror(ctypes.get_errno())}"); return 126

    read = READ_FILE | READ_DIR
    write = handled & ~EXECUTE  # everything but execute
    def add(path, rights):
        try:
            pfd = os.open(path, os.O_PATH | os.O_CLOEXEC)
        except FileNotFoundError:
            return
        try:
            if not os.path.isdir(path): rights &= FILE_ONLY
            rule = PathBeneath(rights & handled, pfd)
            if libc.syscall(SYS_add_rule, ctypes.c_int(fd), ctypes.c_int(RULE_PATH_BENEATH), ctypes.byref(rule), ctypes.c_uint32(0)) < 0:
                log(f"could not add rule for {path}: {os.strerror(ctypes.get_errno())}")
        finally:
            os.close(pfd)

    for p in ro: add(p, read)
    for p in rx: add(p, read | EXECUTE)
    for p in rw: add(p, write | read)
    if no_net and abi >= 4:
        for port in ports:
            rule = NetPort(NET_CONNECT_TCP, port)
            if libc.syscall(SYS_add_rule, ctypes.c_int(fd), ctypes.c_int(RULE_NET_PORT), ctypes.byref(rule), ctypes.c_uint32(0)) < 0:
                log(f"could not allow connect to port {port}: {os.strerror(ctypes.get_errno())}"); return 126

    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        log("prctl(NO_NEW_PRIVS) failed"); return 126
    if libc.syscall(SYS_restrict_self, ctypes.c_int(fd), ctypes.c_uint32(0)) < 0:
        log(f"landlock_restrict_self failed: {os.strerror(ctypes.get_errno())}"); return 126
    os.close(fd)
    os.environ["GITCRAFT_SANDBOX"] = f"landlock-abi{abi}" + ("+nonet" if no_net and abi >= 4 else "") + ("+netgate" if ports and no_net and abi >= 4 else "")
    try:
        os.execvp(cmd[0], cmd)
    except OSError as e:
        log(f"cannot start {cmd[0]}: {e}"); return 127


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
