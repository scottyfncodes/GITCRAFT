# 3D tools: licences, hardware and cost

What MeshCraft uses or works with, what each licence allows, and what it costs to run. Checked 2 November 2026; re-check vendor terms before relying on them commercially.

| Tool | How MeshCraft uses it | Licence | Commercial use of what you make | Hardware | Cost |
|---|---|---|---|---|---|
| Blender 5.2 LTS (`bpy` wheel) | runs headless inside the sandbox | GPL-2.0-or-later (wheel GPL-3.0); Cycles Apache-2.0 | unrestricted: the GPL covers the software, not models, renders or `.blend` content | CPU is enough; Cycles can use CUDA/OptiX | none (~400 MB install) |
| Blockbench | file format only (`.bbmodel` read/write); the app is never run | GPL-3.0-or-later | unrestricted for projects and exports you author | none | none |
| Mixamo (Adobe) | manual workflow: MeshCraft prepares the upload FBX and merges downloaded clips; it never contacts mixamo.com | Adobe General Terms (free with an Adobe ID) | characters and animations are royalty-free in personal, commercial and non-profit projects. Do not redistribute the raw Mixamo files on their own, bulk-download, or use them to train AI models | none locally (Adobe hosts it) | free; needs a person to use the site |
| three.js 0.170, Khronos glTF-Validator | engine check and validation | MIT, Apache-2.0 | unrestricted | headless Chromium (CPU) | none |

## Not integrated yet (roadmap)

| Tool | Licence | Hardware | Cost | Phase |
|---|---|---|---|---|
| Meshroom / AliceVision (photogrammetry) | MPL-2.0 | CPU: draft meshing only; dense reconstruction needs an NVIDIA CUDA GPU | none; ~2 GB install; minutes per object on CPU | P3 |
| TripoSR (image → mesh) | MIT (code and weights) | CPU: minutes per image; ~6 GB VRAM: about a second | none locally; ~5 GB PyTorch + 1.7 GB weights from Hugging Face | P5 |
| Hunyuan3D-2 (text/image → textured mesh) | Tencent Hunyuan 3D Community Licence: **not licensed in the EU, UK or South Korea**; more than 1M monthly active users needs a separate licence; outputs must be labelled AI-generated | NVIDIA GPU, ≥6 GB VRAM for shape, ≥16 GB with texture | local GPU time; the public Hugging Face Space has free quotas; Tencent's hosted API is paid per generation | P5, opt-in with approval |

Model weights and large runtimes are never committed to git; they install into `~/.gitcraft/meshcraft`.
