// FXCraft particle runtime for three.js (r150+). Part of GITCRAFT; copy it into a game freely.
// Plays an FXCraft emitter preset (.fx.json) with its flipbook atlas as one THREE.Points draw call.
//
//   import { FXEmitter } from './fxcraft-particles.js';
//   const fx = await FXEmitter.load(THREE, 'fire.fx.json');   // resolves the atlas next to the preset
//   scene.add(fx.object); fx.object.position.set(0, 0, 0);
//   // each frame: fx.update(dt, camera)     one-shots: fx.burst()     stop emitting: fx.emitting = false
export class FXEmitter {
  static async load(THREE, url) {
    const preset = await (await fetch(url)).json();
    const tex = await new THREE.TextureLoader().loadAsync(new URL(preset.flipbook.image, new URL(url, location.href)).href);
    tex.colorSpace = THREE.SRGBColorSpace;
    return new FXEmitter(THREE, preset, tex);
  }

  constructor(THREE, preset, texture) {
    this.THREE = THREE; this.p = preset; const e = preset.emitter, fb = preset.flipbook;
    this.max = preset.max_particles || 256; this.emitting = true; this.acc = 0; this.t = 0; this.alive = 0;
    const n = this.max, g = new THREE.BufferGeometry();
    this.pos = new Float32Array(n * 3); this.vel = new Float32Array(n * 3); this.age = new Float32Array(n); this.life = new Float32Array(n);
    this.attr = { size: new Float32Array(n), alpha: new Float32Array(n), frame: new Float32Array(n), spin: new Float32Array(n) };
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));
    for (const k of Object.keys(this.attr)) g.setAttribute(k, new THREE.BufferAttribute(this.attr[k], 1));
    this.mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: preset.blending === 'additive' ? THREE.AdditiveBlending : THREE.NormalBlending,
      uniforms: { map: { value: texture }, grid: { value: new THREE.Vector2(fb.cols, fb.rows) }, scale: { value: 1 } },
      vertexShader: `attribute float size; attribute float alpha; attribute float frame; attribute float spin;
        varying float vA; varying float vF; varying float vS; uniform float scale;
        void main() { vA = alpha; vF = frame; vS = spin; vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = size * scale / -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform sampler2D map; uniform vec2 grid; varying float vA; varying float vF; varying float vS;
        void main() { vec2 pc = gl_PointCoord - 0.5; float c = cos(vS), s = sin(vS); pc = vec2(c * pc.x - s * pc.y, s * pc.x + c * pc.y) + 0.5;
          if (pc.x < 0.0 || pc.x > 1.0 || pc.y < 0.0 || pc.y > 1.0) discard;
          float f = floor(vF); vec2 cell = vec2(mod(f, grid.x), floor(f / grid.x));
          vec4 t = texture2D(map, (cell + vec2(pc.x, pc.y)) / grid); gl_FragColor = vec4(t.rgb, t.a * vA); if (gl_FragColor.a < 0.004) discard; }`,
    });
    this.object = new THREE.Points(g, this.mat); this.object.frustumCulled = false; this.geom = g;
    if (e.burst) this.burst();
  }

  rnd(a) { return Array.isArray(a) ? a[0] + Math.random() * (a[1] - a[0]) : a; }

  spawn(k) {
    const e = this.p.emitter; let i = -1;
    for (let j = 0; j < this.max; j++) if (this.age[j] >= this.life[j]) { i = j; break; }
    if (i < 0) return;
    const ar = e.area || [0, 0, 0];
    this.pos[i * 3] = (Math.random() - 0.5) * ar[0]; this.pos[i * 3 + 1] = (Math.random() - 0.5) * ar[1]; this.pos[i * 3 + 2] = (Math.random() - 0.5) * ar[2];
    const d = e.direction || [0, 1, 0], spread = (e.spread_deg || 0) * Math.PI / 180, sp = this.rnd(e.speed || 1);
    const th = Math.random() * 2 * Math.PI, ph = Math.random() * spread;
    // a random direction within `spread` of d
    const up = Math.abs(d[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0];
    const a = [d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2], d[0] * up[1] - d[1] * up[0]]; const la = Math.hypot(...a); a.forEach((v, q) => a[q] = v / la);
    const b = [d[1] * a[2] - d[2] * a[1], d[2] * a[0] - d[0] * a[2], d[0] * a[1] - d[1] * a[0]];
    for (let q = 0; q < 3; q++) this.vel[i * 3 + q] = sp * (Math.cos(ph) * d[q] + Math.sin(ph) * (Math.cos(th) * a[q] + Math.sin(th) * b[q]));
    this.age[i] = 0; this.life[i] = this.rnd(e.lifetime || 1); this.attr.spin[i] = e.random_rotation ? Math.random() * 6.283 : 0;
  }

  burst(n) { for (let k = 0; k < (n || this.p.emitter.burst || 0); k++) this.spawn(); }

  update(dt, camera) {
    const e = this.p.emitter, fb = this.p.flipbook, gr = e.gravity || [0, 0, 0], drag = e.drag || 0;
    this.t += dt;
    if (this.emitting && e.rate) { this.acc += e.rate * dt; while (this.acc >= 1) { this.spawn(); this.acc -= 1; } }
    if (camera && camera.isPerspectiveCamera) this.mat.uniforms.scale.value = window.innerHeight / (2 * Math.tan(camera.fov * Math.PI / 360));
    let alive = 0;
    for (let i = 0; i < this.max; i++) {
      if (this.age[i] >= this.life[i]) { this.attr.alpha[i] = 0; this.attr.size[i] = 0; continue; }
      alive++; this.age[i] += dt; const t = Math.min(1, this.age[i] / this.life[i]);
      for (let q = 0; q < 3; q++) { this.vel[i * 3 + q] = this.vel[i * 3 + q] * (1 - drag * dt) + gr[q] * dt; this.pos[i * 3 + q] += this.vel[i * 3 + q] * dt; }
      const s = e.size || [1, 1]; this.attr.size[i] = s[0] + (s[1] - s[0]) * t;
      const al = e.alpha || [1, 1, 0]; this.attr.alpha[i] = t < 0.5 ? al[0] + (al[1] - al[0]) * t * 2 : al[1] + (al[2] - al[1]) * (t - 0.5) * 2;
      this.attr.frame[i] = fb.loop ? Math.floor((this.age[i] * fb.fps) % fb.frames) : Math.min(fb.frames - 1, Math.floor(t * fb.frames));
    }
    this.alive = alive;
    for (const k of ['position', 'size', 'alpha', 'frame', 'spin']) this.geom.attributes[k].needsUpdate = true;
  }
}
