# What GITCRAFT costs: free audit and watch list

Goal: every tool GITCRAFT installs or calls is free to use. Audited 4 November 2026 against the code on `main`
(installers, workflows, every network call) and the licence of every dependency. Re-check the **watch list**
when a vendor changes its terms.

## Result

Everything GITCRAFT installs and runs by default costs nothing and has a licence that allows commercial use
of what you make. Nothing in the code calls a paid API. Tencent's paid Hunyuan 3D API is deliberately not wired
in, and there are no keys for OpenAI, ElevenLabs, Meshy, Tripo, Stability or similar services.

| Area | Components | Licence | Cost |
|---|---|---|---|
| 2D apps (ArtCraft) | photocraft, vectorcraft, designcraft, pdfcraft (printcraft), lightcraft, filmcraft, effectcraft | MIT OR Apache-2.0 | free; prebuilt by this repo's own workflow |
| 3D | Blender 5.2 (bpy), pygltflib, three.js, Khronos glTF-Validator, Blockbench format | GPL (software only, not your models), MIT, Apache-2.0 | free |
| 3D, opt-in | TripoSR, Meshroom | MIT, MPL-2.0 | free (big downloads; fast only with a GPU) |
| Studio | numpy, Pillow, FFmpeg, Phaser, Playwright/Chromium, SQLite, three.quarks, LDtk schema, jsonschema | BSD/MIT/Apache/LGPL-GPL/public domain | free |
| Studio models | Kokoro-82M voice, MediaPipe Pose, ACE-Step 1.5 (opt-in), UniRig (opt-in) | Apache-2.0, Apache-2.0, MIT, MIT | free downloads (GitHub releases, Google's public bucket, Hugging Face) |
| CI | GitHub Actions (tests, weekly builds, weekly later-setup check) | — | free: the repo is **public**, and standard runners are free for public repos |

## Watch list: where free could become not free

| # | What | How it could cost money | What GITCRAFT does about it |
|---|---|---|---|
| 1 | **GitHub Actions** | Free because the repo is public. Made private, the Free plan includes 2,000 minutes a month; each PR run of `tests.yml` takes 7–16 minutes, plus the two weekly workflows | With GitHub's default $0 spending limit, jobs stop instead of billing. Keep the repo public, or keep the $0 limit |
| 2 | **later-setup.yml with `ANTHROPIC_API_KEY`** | A real Claude Code session in CI is billed per token to the API key | Now runs only when a person starts the workflow by hand and ticks `claude_session`; never on the schedule or a push, even if the secret exists. No such secret is set today |
| 3 | **Vercel project `meshcraft`** (team HaveAnApp) | Publishes the 3D library viewer demo from this repo. Hobby is free but for non-commercial personal use; commercial use needs Pro (paid per seat). Usage beyond Hobby limits pauses the project | Pushes to the `bin` branch (prebuilt binaries) no longer build there (Ignored Build Step), so builds and bandwidth go to the demo only. Check the team's plan (below) |
| 4 | **Hunyuan3D-2** (opt-in, ForgeCraft) | Free of charge but not an open licence: not licensed in the EU, UK or South Korea, and more than 1M monthly active users needs a paid Tencent licence. Its public Hugging Face Space has a free GPU quota; heavier use needs a paid HF plan | Off unless `FORGECRAFT_HUNYUAN_LICENSE=accepted`; remote mode also needs `GITCRAFT_ALLOW_NET=1`. TripoSR (MIT) is the free alternative |
| 5 | **GPU-only tools** (UniRig, Hunyuan3D local, fast ACE-Step/TripoSR, dense Meshroom) | Free software, but needs an NVIDIA GPU: free if you own one, paid if you rent cloud GPUs | Every one is opt-in and reports `blocked` without a GPU; the CPU path stays the default |
| 6 | **Hugging Face downloads** (ACE-Step, UniRig, TripoSR, Hunyuan3D weights) | Free today, including anonymous downloads; HF could rate-limit anonymous use (a free account token fixes that) | Downloads happen once at install; nothing calls HF at run time unless you allow it per host (netgate) |
| 7 | **Mixamo** (Adobe) | Free with an Adobe ID; Adobe sets the terms and could change them | Nothing contacts mixamo.com: MeshCraft only prepares and merges files. `animcraft_mocap` + `retarget` is the fully free path |
| 8 | **H.264/AAC video** (FFmpeg, CinematicCraft and TestCraft MP4s) | Encoding and free internet video are royalty-free under the patent pools' terms; selling encoded video as a paid product can owe codec royalties | Gameplay capture also writes WebM. If you sell video, ask for VP9/AV1 + Opus output (royalty-free) |
| 9 | **Copyleft runtimes** (espeak-ng/phonemizer GPL-3.0 in the voice venv, Blender GPL, FFmpeg GPL build) | Not a cost, but shipping a product that *bundles* them brings GPL obligations | They are separate runtimes, never committed or linked; outputs (speech, models, video) carry no obligation |
| 10 | **Claude Code itself** | Your Claude plan is the one paid part of the workflow; GITCRAFT adds no usage of its own | — |

## Keeping it free

- New dependencies must be recorded here, in `docs/studio-acquisition.md` or `docs/3d-licensing.md`, with their
  licence and cost. Reject anything with a non-commercial, revenue-capped or paid-tier licence as a default.
- Paid or restricted options stay opt-in behind an explicit switch and report `blocked` otherwise.
