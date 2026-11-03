"""Standard MIDI File (type 1) writer, stdlib only: the editable source of a generated piece
(opens in any DAW or notation program: LMMS, Ardour, MuseScore, Reaper...)."""
import struct

PROGRAMS = {"pad": 89, "bass": 33, "lead": 80, "arp": 46, "drums": 0}   # GM: warm pad, fingered bass, square lead, harp


def _vlq(n):
    b = [n & 0x7F]; n >>= 7
    while n: b.append(0x80 | (n & 0x7F)); n >>= 7
    return bytes(reversed(b))


def write(path, notes, tempo, ppq=480):
    """notes: {layer: [(start_seconds, dur_seconds, midi_note, velocity 0..1)]}"""
    spb = 60.0 / tempo; tick = lambda s: int(round(s / spb * ppq))
    tracks = [b"\x00\xff\x51\x03" + struct.pack(">I", int(spb * 1e6))[1:] + b"\x00\xff\x58\x04\x04\x02\x18\x08" + b"\x00\xff\x2f\x00"]
    for ch, (layer, ns) in enumerate(notes.items()):
        chan = 9 if layer == "drums" else min(ch, 8)
        ev = []
        for s, d, m, v in ns:
            vel = max(1, min(127, int(v * 127 / 0.9 if layer == "drums" else v * 127 / 0.5)))
            ev.append((tick(s), 1, bytes([0x90 | chan, m, vel]))); ev.append((tick(s + d), 0, bytes([0x80 | chan, m, 0])))
        ev.sort(key=lambda e: (e[0], e[1]))
        name = layer.encode()
        body = b"\x00\xff\x03" + _vlq(len(name)) + name
        if layer != "drums": body += b"\x00" + bytes([0xC0 | chan, PROGRAMS.get(layer, 0)])
        last = 0
        for t, _, msg in ev: body += _vlq(t - last) + msg; last = t
        body += b"\x00\xff\x2f\x00"; tracks.append(body)
    out = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), ppq) + b"".join(b"MTrk" + struct.pack(">I", len(t)) + t for t in tracks)
    open(path, "wb").write(out); return path
