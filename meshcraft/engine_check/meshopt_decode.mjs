// Decode an EXT_meshopt_compression GLB into a plain GLB that Blender can import (the bpy wheel has no meshopt
// bridge). Uses the decoder that ships with three (no extra dependency). KHR_mesh_quantization stays: Blender reads it.
//   node meshopt_decode.mjs <in.glb> <out.glb>
import { readFileSync, writeFileSync } from 'node:fs';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';

const [src, dst] = process.argv.slice(2);
const buf = readFileSync(src);
if (buf.readUInt32LE(0) !== 0x46546c67) throw new Error('not a GLB');
const jsonLen = buf.readUInt32LE(12);
const json = JSON.parse(buf.subarray(20, 20 + jsonLen).toString('utf8'));
let bin = null;
for (let off = 20 + jsonLen; off < buf.length;) {
  const len = buf.readUInt32LE(off), type = buf.readUInt32LE(off + 4);
  if (type === 0x004e4942) bin = buf.subarray(off + 8, off + 8 + len);
  off += 8 + len;
}
await MeshoptDecoder.ready;
const glbBuffer = json.buffers.findIndex((b) => !b.uri && !b.extensions?.EXT_meshopt_compression?.fallback);
const chunks = [];
let total = 0;
for (const bv of json.bufferViews) {
  const ext = bv.extensions?.EXT_meshopt_compression;
  let bytes;
  if (ext) {
    const source = new Uint8Array(bin.buffer, bin.byteOffset + (ext.byteOffset || 0), ext.byteLength);
    bytes = new Uint8Array(ext.count * ext.byteStride);
    MeshoptDecoder.decodeGltfBuffer(bytes, ext.count, ext.byteStride, source, ext.mode, ext.filter || 'NONE');
    if (ext.byteStride && bv.target === 34962) bv.byteStride = ext.byteStride;
    delete bv.extensions.EXT_meshopt_compression;
    if (!Object.keys(bv.extensions).length) delete bv.extensions;
  } else {
    if (bv.buffer !== glbBuffer) throw new Error(`bufferView on external buffer ${bv.buffer}`);
    bytes = new Uint8Array(bin.buffer, bin.byteOffset + (bv.byteOffset || 0), bv.byteLength);
  }
  const pad = (4 - (total % 4)) % 4;
  if (pad) { chunks.push(new Uint8Array(pad)); total += pad; }
  bv.buffer = 0; bv.byteOffset = total; bv.byteLength = bytes.length;
  chunks.push(bytes); total += bytes.length;
}
const pad = (4 - (total % 4)) % 4;
if (pad) { chunks.push(new Uint8Array(pad)); total += pad; }
json.buffers = [{ byteLength: total }];
for (const k of ['extensionsUsed', 'extensionsRequired']) {
  if (json[k]) { json[k] = json[k].filter((e) => e !== 'EXT_meshopt_compression'); if (!json[k].length) delete json[k]; }
}
let js = Buffer.from(JSON.stringify(json), 'utf8');
js = Buffer.concat([js, Buffer.alloc((4 - (js.length % 4)) % 4, 0x20)]);
const out = Buffer.alloc(12 + 8 + js.length + 8 + total);
out.writeUInt32LE(0x46546c67, 0); out.writeUInt32LE(2, 4); out.writeUInt32LE(out.length, 8);
out.writeUInt32LE(js.length, 12); out.writeUInt32LE(0x4e4f534a, 16); js.copy(out, 20);
let o = 20 + js.length;
out.writeUInt32LE(total, o); out.writeUInt32LE(0x004e4942, o + 4); o += 8;
for (const c of chunks) { Buffer.from(c.buffer, c.byteOffset, c.byteLength).copy(out, o); o += c.byteLength; }
writeFileSync(dst, out);
console.log(JSON.stringify({ src, dst, bytes: out.length }));
