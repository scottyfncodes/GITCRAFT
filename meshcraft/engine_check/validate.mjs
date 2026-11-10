// Khronos glTF-Validator: node validate.mjs file.glb  -> JSON report on stdout
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
// gltf-validator from MESHCRAFT_NODE_MODULES (set by MeshCraft, meshcraft/engine/nodemods.py) or a local `npm ci`
const base = process.env.MESHCRAFT_NODE_MODULES ? path.join(process.env.MESHCRAFT_NODE_MODULES, '..', 'x.js') : import.meta.url;
const validator = createRequire(base)('gltf-validator');
const file = process.argv[2];
const data = new Uint8Array(await readFile(file));
const report = await validator.validateBytes(data, {
  uri: path.basename(file), maxIssues: 50,
  externalResourceFunction: (uri) => readFile(path.join(path.dirname(file), decodeURIComponent(uri))).then((b) => new Uint8Array(b)),
});
process.stdout.write(JSON.stringify(report));
