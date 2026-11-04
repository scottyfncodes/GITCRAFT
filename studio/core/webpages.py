"""Generated pages for the browser harness (core/web/harness.mjs): engine-side checks in three@0.170
(the version the GITCRAFT portfolio's games use) and Phaser 3. Each page renders, measures and
sets window.__report; the harness screenshots it."""
import json, os
from . import runners

IMPORTMAP = '<script type="importmap">{"imports":{"three":"http://gc.local/three/build/three.module.js","three/addons/":"http://gc.local/three/examples/jsm/"}}</script>'


def file_url(p): return "http://gc.local/files" + os.path.abspath(p)


def run(html, screenshot, size=(640, 480), timeout_ms=60000, shots=None):
    r = runners.node("harness.mjs", {"html": html, "screenshot": screenshot, "size": list(size), "timeout_ms": timeout_ms, "shots": shots or []},
                     timeout=timeout_ms / 1000 + 90)
    return r


def glb_view(glb, screenshot, size=(800, 600), camera=None, target=None, background="#cfe3ea", sky=True, fog=None, play=None, extra_js=""):
    """Load a GLB with three's GLTFLoader (like a game), frame it, render, report counts and bounds."""
    opts = {"glb": file_url(glb), "camera": camera, "target": target, "bg": background, "fog": fog, "play": play}
    html = f"""<!doctype html><html><head>{IMPORTMAP}</head><body style="margin:0;background:{background}">
<canvas id="c" width="{size[0]}" height="{size[1]}"></canvas>
<script type="module">
import * as THREE from 'three';
import {{ GLTFLoader }} from 'three/addons/loaders/GLTFLoader.js';
const o = {json.dumps(opts)};
const R = {{ ok: false }};
try {{
  const renderer = new THREE.WebGLRenderer({{ canvas: document.getElementById('c'), antialias: true, preserveDrawingBuffer: true }});
  renderer.setSize({size[0]}, {size[1]}, false); renderer.setClearColor(o.bg); renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xeef6ff, 0x5a6b4a, 1.6));
  const sun = new THREE.DirectionalLight(0xfff0d8, 2.4); sun.position.set(-0.5, 1, 0.35).multiplyScalar(100); scene.add(sun);
  const gltf = await new GLTFLoader().loadAsync(o.glb);
  scene.add(gltf.scene);
  let mixer = null;
  if (o.play && gltf.animations.length) {{ mixer = new THREE.AnimationMixer(gltf.scene); gltf.animations.forEach((a) => mixer.clipAction(a).play()); mixer.update(o.play); gltf.scene.updateMatrixWorld(true); }}
  const box = new THREE.Box3().setFromObject(gltf.scene); const size = box.getSize(new THREE.Vector3()); const c = box.getCenter(new THREE.Vector3());
  const r = Math.max(size.x, size.y, size.z);
  const cam = new THREE.PerspectiveCamera(45, {size[0]}/{size[1]}, Math.max(0.01, r / 1000), r * 20);
  if (o.camera) cam.position.fromArray(o.camera); else cam.position.set(c.x + r * 0.75, c.y + r * 0.55, c.z + r * 0.85);
  cam.lookAt(o.target ? new THREE.Vector3(...o.target) : c);
  if (o.fog) scene.fog = new THREE.Fog(o.bg, r * o.fog[0], r * o.fog[1]);
  let meshes = 0, tris = 0, colored = 0;
  gltf.scene.traverse((m) => {{ if (!m.isMesh) return; meshes++; const g = m.geometry; if (g.attributes.color) colored++;
    tris += (g.index ? g.index.count : g.attributes.position.count) / 3; }});
  {extra_js}
  renderer.render(scene, cam);
  const gl = renderer.getContext(); const px = new Uint8Array(4 * {size[0]} * {size[1]});
  gl.readPixels(0, 0, {size[0]}, {size[1]}, gl.RGBA, gl.UNSIGNED_BYTE, px);
  let distinct = new Set(); for (let i = 0; i < px.length; i += 4 * 7) distinct.add(px[i] >> 3 << 10 | px[i+1] >> 3 << 5 | px[i+2] >> 3);
  Object.assign(R, {{ ok: true, meshes, triangles: tris, vertex_colored_meshes: colored, clips: gltf.animations.map(a => [a.name, +a.duration.toFixed(3)]),
    bounds: {{ min: box.min.toArray().map(v => +v.toFixed(3)), max: box.max.toArray().map(v => +v.toFixed(3)) }}, centre_colours: distinct.size }});
}} catch (e) {{ R.error = String(e); }}
window.__report = R; window.__done = true;
</script></body></html>"""
    return run(html, screenshot, size)


def khronos(glb):
    """Khronos glTF-Validator report for a GLB: {errors, warnings, infos, messages}."""
    return runners.node("gltf_validate.mjs", {"glb": os.path.abspath(glb)}, timeout=120)


def glb_checks(glb, screenshot, label="GLB", **view):
    """The standard engine-side verification of a GLB deliverable: Khronos validator with no errors,
    then a three.js r170 load + render that shows something (not a blank frame)."""
    k = khronos(glb); v = glb_view(glb, screenshot, **view); rep = v.get("report") or {}
    checks = [{"name": f"{label}: Khronos glTF-Validator, 0 errors", "ok": k.get("errors") == 0, "detail": {"errors": k.get("errors"), "warnings": k.get("warnings"), "first": k.get("messages", [])[:3]}},
              {"name": f"{label}: loads and renders in three.js r170", "ok": bool(rep.get("ok")) and rep.get("centre_colours", 0) > 3 and not v.get("errors"),
               "detail": {"meshes": rep.get("meshes"), "triangles": rep.get("triangles"), "errors": (v.get("errors") or [])[:3] or rep.get("error")}}]
    return checks, k, rep
