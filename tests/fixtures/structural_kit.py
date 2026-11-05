"""run_script fixture for tests/test_meshcraft_structural.py: builds one of each structural helper and
prints their bounds and triangle counts as JSON."""
import json
K = kit  # noqa: F821
K.reset()
pal = Palette.from_file(args["palette"])  # noqa: F821
mats = K.Materials(pal, {"log": "#7D6150", "shade": "#6F5547", "grain": "#A48A74", "snow": "#F2F5F8", "steel": "#8C9298"})
M = mats.__getitem__
def info(objs):
    import bpy
    bpy.context.view_layer.update()
    xs, ys, zs, tris = [], [], [], 0
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            xs.append(w.x); ys.append(w.y); zs.append(w.z)
        tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return {"min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)], "tris": tris, "objects": len(objs)}
wall = K.log_wall("wall", 6.0, 3.1, (0, 0, 0), "X", mats=(M("log"), M("shade")), grain=M("grain"), openings=[(-0.6, 0.6, 0.0, 2.2)])
def crosses_door(o):
    xs = [(o.matrix_world @ v.co).x for v in o.data.vertices]
    zs = [(o.matrix_world @ v.co).z for v in o.data.vertices]
    return min(xs) < 0.55 and max(xs) > -0.55 and min(zs) < 2.2
gap = [o for o in wall if crosses_door(o)]
drift = K.mound("drift", 4.0, 0.6, 2.0, (1, 2, 0), M("snow"))
brace = K.beam("brace", (0, 0, 0), (0, 2, 2), 0.1, M("steel"))
print(json.dumps({"wall": info(wall), "logs_in_door": len(gap), "drift": info([drift]), "brace": info([brace]),
                  "brace_len": round((brace.dimensions.z), 4)}))
