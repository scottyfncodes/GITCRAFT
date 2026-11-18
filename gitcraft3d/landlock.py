"""Narrow the writes of THIS process with one more Landlock layer (standard library only).

A process that is already inside GITCRAFT's sandbox (scripts/sandbox.py) can add a layer but never remove one: the
kernel enforces the intersection. narrow_writes() keeps reading and executing as the outer layer allows and lets this
process (and its children) write only beneath the given folders. MeshCraft's run_script uses it so that an
arbitrary Blender script can write its declared outputs and nothing else in the workspace.
"""
import ctypes, os

SYS_create_ruleset, SYS_add_rule, SYS_restrict_self = 444, 445, 446
PR_SET_NO_NEW_PRIVS = 38
RULE_PATH_BENEATH = 1
EXECUTE, WRITE_FILE, READ_FILE, READ_DIR = 1 << 0, 1 << 1, 1 << 2, 1 << 3
REMOVE_DIR, REMOVE_FILE, MAKE_CHAR, MAKE_DIR = 1 << 4, 1 << 5, 1 << 6, 1 << 7
MAKE_REG, MAKE_SOCK, MAKE_FIFO, MAKE_BLOCK, MAKE_SYM = 1 << 8, 1 << 9, 1 << 10, 1 << 11, 1 << 12
REFER, TRUNCATE, IOCTL_DEV = 1 << 13, 1 << 14, 1 << 15
FILE_ONLY = EXECUTE | WRITE_FILE | READ_FILE | TRUNCATE | IOCTL_DEV


class _Attr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64), ("handled_access_net", ctypes.c_uint64), ("scoped", ctypes.c_uint64)]


class _Beneath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


class Unavailable(RuntimeError):
    pass


def abi():
    libc = ctypes.CDLL(None, use_errno=True); libc.syscall.restype = ctypes.c_long
    return libc.syscall(SYS_create_ruleset, None, ctypes.c_size_t(0), ctypes.c_uint32(1))


def narrow_writes(writable):
    """After this, the process may write only beneath `writable` (folders or files); reads and execution are
    unchanged. Raises Unavailable when the kernel has no Landlock. Irrevocable for this process and its children."""
    libc = ctypes.CDLL(None, use_errno=True); libc.syscall.restype = ctypes.c_long
    v = libc.syscall(SYS_create_ruleset, None, ctypes.c_size_t(0), ctypes.c_uint32(1))
    if v < 0: raise Unavailable("Landlock is not available on this kernel")
    handled = EXECUTE | WRITE_FILE | READ_FILE | READ_DIR | REMOVE_DIR | REMOVE_FILE | MAKE_CHAR | MAKE_DIR | MAKE_REG \
        | MAKE_SOCK | MAKE_FIFO | MAKE_BLOCK | MAKE_SYM
    if v >= 2: handled |= REFER
    if v >= 3: handled |= TRUNCATE
    if v >= 5: handled |= IOCTL_DEV
    attr = _Attr(handled, 0, 0)
    fd = libc.syscall(SYS_create_ruleset, ctypes.byref(attr), ctypes.c_size_t(8), ctypes.c_uint32(0))
    if fd < 0: raise OSError(ctypes.get_errno(), "landlock_create_ruleset: " + os.strerror(ctypes.get_errno()))

    def add(path, rights):
        try: pfd = os.open(path, os.O_PATH | os.O_CLOEXEC)
        except FileNotFoundError: return
        try:
            if not os.path.isdir(path): rights &= FILE_ONLY
            rule = _Beneath(rights & handled, pfd)
            if libc.syscall(SYS_add_rule, ctypes.c_int(fd), ctypes.c_int(RULE_PATH_BENEATH), ctypes.byref(rule), ctypes.c_uint32(0)) < 0:
                raise OSError(ctypes.get_errno(), f"landlock_add_rule {path}: " + os.strerror(ctypes.get_errno()))
        finally:
            os.close(pfd)

    try:
        add("/", READ_FILE | READ_DIR | EXECUTE | (IOCTL_DEV if v >= 5 else 0))   # reads: whatever the outer layer allows
        for p in writable: add(p, handled)
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0: raise OSError(ctypes.get_errno(), "prctl(NO_NEW_PRIVS)")
        if libc.syscall(SYS_restrict_self, ctypes.c_int(fd), ctypes.c_uint32(0)) < 0:
            raise OSError(ctypes.get_errno(), "landlock_restrict_self: " + os.strerror(ctypes.get_errno()))
    finally:
        os.close(fd)
    return v
