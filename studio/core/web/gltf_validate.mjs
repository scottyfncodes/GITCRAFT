// Khronos glTF-Validator (Apache-2.0) on one file: node gltf_validate.mjs request.json
// request: { glb, _result }  →  result: { errors, warnings, infos, messages: [...first 20] }
import { readFileSync, writeFileSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
const req = JSON.parse(readFileSync(process.argv[2], 'utf8'));
try {
  const require = createRequire(path.join(process.env.STUDIO_NODE_MODULES, 'x.js'));
  const validator = require('gltf-validator');
  const report = await validator.validateBytes(new Uint8Array(readFileSync(req.glb)), {
    uri: path.basename(req.glb), maxIssues: 50,
    externalResourceFunction: (uri) => readFile(path.join(path.dirname(req.glb), decodeURIComponent(uri))).then((b) => new Uint8Array(b)) });
  const i = report.issues;
  writeFileSync(req._result, JSON.stringify({ errors: i.numErrors, warnings: i.numWarnings, infos: i.numInfos, version: report.validatorVersion,
    messages: i.messages.slice(0, 20).map((m) => `${['ERROR', 'WARNING', 'INFO', 'HINT'][m.severity]} ${m.code}: ${m.message} @ ${m.pointer || ''}`) }));
} catch (e) { writeFileSync(req._result, JSON.stringify({ error: String(e) })); }
