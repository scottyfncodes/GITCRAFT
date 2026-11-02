"""Load colour palettes from GITCRAFT brand packages.

Accepts the formats VectorCraft exports: .json ({"Name": "#hex"}), .css (custom
properties), .gpl (GIMP palette) and .ase (Adobe swatch exchange, RGB only).
Returns {name: "#RRGGBB"} with names normalised so "Deep Tide", "deep-tide"
and "deep_tide" all resolve.
"""
import json, os, re, struct


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _hex(r, g, b):
    return "#%02X%02X%02X" % (round(r), round(g), round(b))


def load(path: str) -> dict:
    ext = os.path.splitext(path)[1].lower()
    out = {}
    if ext == ".json":
        data = json.load(open(path))
        if isinstance(data, dict) and "colors" in data and isinstance(data["colors"], dict): data = data["colors"]
        for k, v in data.items():
            if isinstance(v, str) and re.fullmatch(r"#?[0-9a-fA-F]{6}", v): out[k] = "#" + v.lstrip("#").upper()
    elif ext == ".css":
        for name, val in re.findall(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})", open(path).read()):
            out[name.replace("-", " ").title()] = val.upper()
    elif ext == ".gpl":
        for line in open(path):
            m = re.match(r"\s*(\d+)\s+(\d+)\s+(\d+)\s+(.*)$", line)
            if m: out[m.group(4).strip() or f"color{len(out)}"] = _hex(*map(int, m.group(1, 2, 3)))
    elif ext == ".ase":
        data = open(path, "rb").read()
        if data[:4] != b"ASEF": raise ValueError("not an ASE file")
        n = struct.unpack(">I", data[8:12])[0]; i = 12
        for _ in range(n):
            btype, blen = struct.unpack(">HI", data[i:i + 6]); body = data[i + 6:i + 6 + blen]; i += 6 + blen
            if btype != 0x0001: continue
            nlen = struct.unpack(">H", body[:2])[0]
            name = body[2:2 + nlen * 2].decode("utf-16-be").rstrip("\x00"); j = 2 + nlen * 2
            model = body[j:j + 4]; j += 4
            if model == b"RGB ":
                r, g, b = struct.unpack(">fff", body[j:j + 12]); out[name] = _hex(r * 255, g * 255, b * 255)
    else:
        raise ValueError(f"unsupported palette format {ext} (json, css, gpl, ase)")
    if not out: raise ValueError(f"no colours found in {path}")
    return out


class Palette:
    def __init__(self, colors: dict):
        self.colors = dict(colors)
        self._idx = {norm(k): v for k, v in colors.items()}

    @classmethod
    def from_file(cls, path):
        return cls(load(path))

    def get(self, ref: str) -> str:
        """`ref` is a palette name ("Deep Tide") or a literal hex."""
        if re.fullmatch(r"#?[0-9a-fA-F]{6}", ref or ""): return "#" + ref.lstrip("#").upper()
        k = norm(ref)
        if k not in self._idx: raise KeyError(f"palette has no colour named {ref!r}; available: {', '.join(self.colors)}")
        return self._idx[k]


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear(h: str):
    h = h.lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
