// Khronos glTF-Validator: node validate.mjs file.glb  -> JSON report on stdout
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import validator from 'gltf-validator';
const file = process.argv[2];
const data = new Uint8Array(await readFile(file));
const report = await validator.validateBytes(data, {
  uri: path.basename(file), maxIssues: 50,
  externalResourceFunction: (uri) => readFile(path.join(path.dirname(file), decodeURIComponent(uri))).then((b) => new Uint8Array(b)),
});
process.stdout.write(JSON.stringify(report));
