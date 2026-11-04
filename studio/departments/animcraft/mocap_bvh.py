"""MediaPipe world landmarks → a humanoid BVH, and an independent BVH reader with forward kinematics (to check
what was written). Pure numpy; runs in the Studio venv.

Axes: BVH is Y up, the character faces +Z, its left is +X (MediaPipe x, -y, -z). Blender's BVH import
(axis_forward -Z, axis_up Y) turns that into Z up, facing -Y: the same rest frame as AnimCraft's rigs.

Solve: the rest skeleton is a T-pose built from the median bone lengths of the take. Hips and chest take a
full frame from the hip and shoulder lines; head from the ear line and nose; every limb bone takes the
smallest rotation (swing) that points it from its parent's frame at the observed child landmark, so no
twist is invented. Local rotations go out as Euler ZXY (R = Rz·Rx·Ry), the order most BVH tools read."""
import math
import numpy as np

# MediaPipe Pose landmark indices
NOSE, LEAR, REAR, LSH, RSH, LEL, REL, LWR, RWR, LPI, RPI, LIN, RIN = 0, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20
LHIP, RHIP, LKN, RKN, LAN, RAN, LHE, RHE, LFI, RFI = 23, 24, 25, 26, 27, 28, 29, 30, 31, 32

# limb segments checked against the landmarks: (BVH joint, landmark from, landmark to)
SEGMENTS = [("LeftArm", LSH, LEL), ("LeftForeArm", LEL, LWR), ("RightArm", RSH, REL), ("RightForeArm", REL, RWR),
            ("LeftUpLeg", LHIP, LKN), ("LeftLeg", LKN, LAN), ("RightUpLeg", RHIP, RKN), ("RightLeg", RKN, RAN)]


def _n(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True); return v / np.maximum(n, 1e-9)


def to_bvh_axes(world):
    """(F, 33, 3) MediaPipe world (x right, y down, z away) → BVH axes (Y up, facing +Z)."""
    return world * np.array([1.0, -1.0, -1.0])


def fill_and_smooth(frames, window=5):
    """frames: list of (33,4) arrays or None. Linear gap fill, then a centred moving average."""
    F = len(frames); idx = [i for i, f in enumerate(frames) if f is not None]
    if not idx: raise ValueError("no person was detected in any frame")
    A = np.full((F, 33, 4), np.nan)
    for i in idx: A[i] = frames[i]
    t = np.arange(F)
    for j in range(33):
        for c in range(4): A[:, j, c] = np.interp(t, idx, A[idx, j, c])
    if window > 1 and F > 2:
        w = min(window, F if F % 2 else F - 1); k = w // 2
        P = np.pad(A, ((k, k), (0, 0), (0, 0)), mode="edge")
        A = np.mean([P[i:i + F] for i in range(w)], axis=0)
    return A


def _frame(x, up):
    """Rotation whose columns are (x, y, z) built from a lateral axis and an approximate up axis."""
    x = _n(x); z = _n(np.cross(x, up)); y = np.cross(z, x)
    return np.stack([x, y, z], axis=-1)


def _swing(a, b):
    """Smallest rotation taking unit vector a to unit vector b (both (3,))."""
    a, b = _n(a), _n(b); v = np.cross(a, b); c = float(np.dot(a, b))
    if c < -0.999999:
        p = _n(np.cross(a, [1, 0, 0] if abs(a[0]) < 0.9 else [0, 1, 0])); return 2 * np.outer(p, p) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


def _quat(R):
    w = math.sqrt(max(0.0, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    x = math.copysign(math.sqrt(max(0.0, 1 + R[0, 0] - R[1, 1] - R[2, 2])) / 2, R[2, 1] - R[1, 2])
    y = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] + R[1, 1] - R[2, 2])) / 2, R[0, 2] - R[2, 0])
    z = math.copysign(math.sqrt(max(0.0, 1 - R[0, 0] - R[1, 1] + R[2, 2])) / 2, R[1, 0] - R[0, 1])
    q = np.array([w, x, y, z]); return q / np.linalg.norm(q)


def _mat(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def slerp(A, B, t):
    qa, qb = _quat(A), _quat(B)
    if np.dot(qa, qb) < 0: qb = -qb
    d = min(1.0, float(np.dot(qa, qb))); th = math.acos(d)
    if th < 1e-6: return A
    return _mat((math.sin((1 - t) * th) * qa + math.sin(t * th) * qb) / math.sin(th))


def euler_zxy(R):
    """R = Rz(a)·Rx(b)·Ry(c) → (a, b, c) in degrees."""
    b = math.asin(max(-1.0, min(1.0, R[2, 1])))
    a = math.atan2(-R[0, 1], R[1, 1]); c = math.atan2(-R[2, 0], R[2, 2])
    return math.degrees(a), math.degrees(b), math.degrees(c)


def rot_zxy(a, b, c):
    a, b, c = map(math.radians, (a, b, c))
    Rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]])
    Ry = np.array([[math.cos(c), 0, math.sin(c)], [0, 1, 0], [-math.sin(c), 0, math.cos(c)]])
    return Rz @ Rx @ Ry


def skeleton(P):
    """Rest skeleton (T-pose, metres) from median bone lengths of the take. Returns [(joint, parent, offset)] and end sites."""
    d = lambda a, b: float(np.median(np.linalg.norm(a - b, axis=-1)))
    mid = lambda i, j: (P[:, i] + P[:, j]) / 2
    hip, sh, ear = mid(LHIP, RHIP), mid(LSH, RSH), mid(LEAR, REAR)
    T = d(sh, hip); hw = d(P[:, LHIP], P[:, RHIP]); sw = d(P[:, LSH], P[:, RSH]); neck = d(ear, sh)
    up = (d(P[:, LSH], P[:, LEL]) + d(P[:, RSH], P[:, REL])) / 2; fo = (d(P[:, LEL], P[:, LWR]) + d(P[:, REL], P[:, RWR])) / 2
    hand = (d(P[:, LWR], mid(LIN, LPI)) + d(P[:, RWR], mid(RIN, RPI))) / 2
    th = (d(P[:, LHIP], P[:, LKN]) + d(P[:, RHIP], P[:, RKN])) / 2; sn = (d(P[:, LKN], P[:, LAN]) + d(P[:, RKN], P[:, RAN])) / 2
    ft = (d(P[:, LAN], P[:, LFI]) + d(P[:, RAN], P[:, RFI])) / 2
    hh = th + sn + 0.45 * ft   # rest hip height: the toe tip (lowest rest point) on the ground
    J = [("Hips", None, (0.0, hh, 0.0)), ("Spine", "Hips", (0, 0.25 * T, 0)), ("Chest", "Spine", (0, 0.35 * T, 0)),
         ("Neck", "Chest", (0, 0.4 * T, 0)), ("Head", "Neck", (0, neck, 0))]
    for s, sx in (("Left", 1), ("Right", -1)):
        J += [(f"{s}Shoulder", "Chest", (sx * 0.02, 0.4 * T, 0)), (f"{s}Arm", f"{s}Shoulder", (sx * (sw / 2 - 0.02), 0, 0)),
              (f"{s}ForeArm", f"{s}Arm", (sx * up, 0, 0)), (f"{s}Hand", f"{s}ForeArm", (sx * fo, 0, 0)),
              (f"{s}UpLeg", "Hips", (sx * hw / 2, 0, 0)), (f"{s}Leg", f"{s}UpLeg", (0, -th, 0)), (f"{s}Foot", f"{s}Leg", (0, -sn, 0)),
              (f"{s}ToeBase", f"{s}Foot", tuple(ft * np.array([0, -0.45, 0.89])))]
    ends = {"Head": (0, 0.18, 0), "LeftHand": (hand, 0, 0), "RightHand": (-hand, 0, 0), "LeftToeBase": (0, 0, 0.05), "RightToeBase": (0, 0, 0.05)}
    return J, ends, {"torso": T, "hip_width": hw, "shoulder_width": sw, "upper_arm": up, "forearm": fo, "thigh": th, "shin": sn, "foot": ft, "neck": neck, "hip_height": hh}


def solve(P):
    """P: (F,33,3) BVH-axes landmarks. Returns global rotations {joint: (F,3,3)} and root positions (F,3)."""
    F = len(P); J, _, L = skeleton(P); off = {j: np.array(o, float) for j, _, o in J}; par = {j: p for j, p, _ in J}
    mid = lambda i, k: (P[:, i] + P[:, k]) / 2
    hip, sh, ear = mid(LHIP, RHIP), mid(LSH, RSH), mid(LEAR, REAR)
    up = _n(sh - hip)
    G = {"Hips": _frame(P[:, LHIP] - P[:, RHIP], up), "Chest": _frame(P[:, LSH] - P[:, RSH], up)}
    G["Spine"] = np.stack([slerp(G["Hips"][f], G["Chest"][f], 0.5) for f in range(F)])
    head_x = P[:, LEAR] - P[:, REAR]; fwd = P[:, NOSE] - ear
    head_up = _n(np.cross(_n(fwd - np.sum(fwd * _n(head_x), -1, keepdims=True) * _n(head_x)), _n(head_x)))
    G["Head"] = _frame(head_x, head_up)
    targets = {"Neck": (sh, ear), "LeftShoulder": (sh, P[:, LSH]), "RightShoulder": (sh, P[:, RSH]),
               "LeftArm": (P[:, LSH], P[:, LEL]), "LeftForeArm": (P[:, LEL], P[:, LWR]), "LeftHand": (P[:, LWR], mid(LIN, LPI)),
               "RightArm": (P[:, RSH], P[:, REL]), "RightForeArm": (P[:, REL], P[:, RWR]), "RightHand": (P[:, RWR], mid(RIN, RPI)),
               "LeftUpLeg": (P[:, LHIP], P[:, LKN]), "LeftLeg": (P[:, LKN], P[:, LAN]), "LeftFoot": (P[:, LAN], P[:, LFI]),
               "RightUpLeg": (P[:, RHIP], P[:, RKN]), "RightLeg": (P[:, RKN], P[:, RAN]), "RightFoot": (P[:, RAN], P[:, RFI])}
    child = {}
    for j, p, _ in J:
        if p and p not in child: child[p] = j
    child.update({"Chest": "Neck", "Hips": "Spine"})
    _, ends, _ = skeleton(P)
    rest_dir = lambda j: off[child[j]] if j in child and j not in ("LeftHand", "RightHand") else np.array(ends.get(j, (0, 1, 0)), float)
    for j, p, _ in J:
        if j in G: continue
        if j == "Head" or j not in targets: G[j] = G[p]; continue
        a, b = targets[j]; rd = rest_dir(j)
        G[j] = np.stack([_swing(G[p][f] @ rd, b[f] - a[f]) @ G[p][f] for f in range(F)])
    # ToeBase: no landmark beyond the toe tip, keep the foot's rotation
    for s in ("Left", "Right"): G[f"{s}ToeBase"] = G[f"{s}Foot"]
    feet = P[:, [LHE, RHE, LFI, RFI, LAN, RAN], 1].min(axis=1)
    root = np.stack([np.zeros(F), -feet, np.zeros(F)], axis=1)   # hip-centred landmarks: keep the lowest foot point on the ground (absolute)
    return J, ends, L, G, root


def write(path, P, fps, hold=None):
    """Write a BVH from (F,33,3) BVH-axes landmarks. hold=N: a single pose eased in from the rest pose over N frames."""
    J, ends, L, G, root = solve(P)
    par = {j: p for j, p, _ in J}; F = len(P)
    local = {j: np.stack([(G[par[j]][f].T @ G[j][f]) if par[j] else G[j][f] for f in range(F)]) for j, _, _ in J}
    if hold and F == 1:
        F = hold; ease = [0.5 - 0.5 * math.cos(math.pi * min(1.0, i / max(1, hold * 0.6))) for i in range(hold)]
        local = {j: np.stack([slerp(np.eye(3), R[0], t) for t in ease]) for j, R in local.items()}
        rest_h = L["hip_height"]
        root = np.stack([np.array([0, rest_h + (root[0, 1] - rest_h) * t, 0]) for t in ease])
    kids = {}
    for j, p, _ in J: kids.setdefault(p, []).append(j)
    off = {j: o for j, _, o in J}; lines = ["HIERARCHY"]
    def emit(j, depth):
        ind = "  " * depth
        lines.append(f"{ind}{'ROOT' if depth == 0 else 'JOINT'} {j}"); lines.append(ind + "{")
        lines.append(f"{ind}  OFFSET {off[j][0]:.5f} {off[j][1]:.5f} {off[j][2]:.5f}")
        lines.append(f"{ind}  CHANNELS " + ("6 Xposition Yposition Zposition Zrotation Xrotation Yrotation" if depth == 0 else "3 Zrotation Xrotation Yrotation"))
        for k in kids.get(j, []): emit(k, depth + 1)
        if j in ends:
            e = ends[j]; lines.append(f"{ind}  End Site"); lines.append(ind + "  {"); lines.append(f"{ind}    OFFSET {e[0]:.5f} {e[1]:.5f} {e[2]:.5f}"); lines.append(ind + "  }")
        lines.append(ind + "}")
    emit("Hips", 0)
    order = []
    def walk(j):
        order.append(j)
        for k in kids.get(j, []): walk(k)
    walk("Hips")
    lines += ["MOTION", f"Frames: {F}", f"Frame Time: {1.0 / fps:.6f}"]
    for f in range(F):
        vals = list(root[f])
        for j in order: vals += euler_zxy(local[j][f])
        lines.append(" ".join(f"{v:.4f}" for v in vals))
    open(path, "w").write("\n".join(lines) + "\n")
    return {"joints": len(J), "frames": F, "fps": fps, "bone_lengths_m": {k: round(v, 3) for k, v in L.items()}}


def read(path):
    """Minimal BVH reader: joints (name, parent, offset, channels), frames (F, C), frame time."""
    tok = open(path).read().split(); i = 0; J = []; stack = []; chans = []
    while tok[i] != "MOTION":
        t = tok[i]
        if t in ("ROOT", "JOINT"):
            J.append({"name": tok[i + 1], "parent": stack[-1] if stack else None}); i += 2; continue
        if t == "End": J.append({"name": None, "parent": stack[-1], "end": True}); i += 2; continue
        if t == "{": stack.append(len(J) - 1)
        elif t == "}": stack.pop()
        elif t == "OFFSET": J[-1]["offset"] = np.array(list(map(float, tok[i + 1:i + 4]))); i += 4; continue
        elif t == "CHANNELS":
            n = int(tok[i + 1]); J[-1]["channels"] = tok[i + 2:i + 2 + n]; chans += [(len(J) - 1, c) for c in J[-1]["channels"]]; i += 2 + n; continue
        i += 1
    F = int(tok[i + 2]); dt = float(tok[i + 5]); data = np.array(list(map(float, tok[i + 6:i + 6 + F * len(chans)]))).reshape(F, len(chans))
    return J, chans, data, dt


def fk(path):
    """World joint positions per frame: {name: (F,3)} (End Sites as '<parent>_end')."""
    J, chans, data, dt = read(path); F = len(data); out = {}
    col = {}
    for c, (ji, ch) in enumerate(chans): col.setdefault(ji, {})[ch] = c
    Gs = [None] * len(J); Ps = [None] * len(J)
    for ji, j in enumerate(J):
        p = j["parent"]; R = np.zeros((F, 3, 3)); pos = np.zeros((F, 3))
        c = col.get(ji, {})
        for f in range(F):
            Rl = rot_zxy(*(data[f, c[k]] if k in c else 0.0 for k in ("Zrotation", "Xrotation", "Yrotation"))) if c else np.eye(3)
            # position channels are absolute (they replace the OFFSET), as Blender's importer and most tools read them
            o = np.array([data[f, c[k]] for k in ("Xposition", "Yposition", "Zposition")]) if "Xposition" in c else j["offset"]
            if p is None: R[f], pos[f] = Rl, o
            else: R[f], pos[f] = Gs[p][f] @ Rl, Ps[p][f] + Gs[p][f] @ o
        Gs[ji], Ps[ji] = R, pos
        out[j["name"] or (J[p]["name"] + "_end")] = pos
    return out, F, dt


def segment_errors(path, P):
    """Angle (degrees) between each written limb bone and the landmark segment it should follow, per frame."""
    pos, F, _ = fk(path); err = {}
    child = {"LeftArm": "LeftForeArm", "LeftForeArm": "LeftHand", "RightArm": "RightForeArm", "RightForeArm": "RightHand",
             "LeftUpLeg": "LeftLeg", "LeftLeg": "LeftFoot", "RightUpLeg": "RightLeg", "RightLeg": "RightFoot"}
    for j, a, b in SEGMENTS:
        u = _n(pos[child[j]] - pos[j]); v = _n(P[:, b] - P[:, a])
        err[j] = np.degrees(np.arccos(np.clip(np.sum(u * v, -1), -1, 1)))
    return err
