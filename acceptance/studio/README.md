# GITCRAFT Studio acceptance package

Made by `tests/acceptance_studio.py` with fixed seeds: **69/69 runs ok**, 253 checks. Each folder holds selected outputs and the run's `.studio.json` record (tools, licences, hashes, checks).

## animcraft

| Run | Status | Checks | Files |
|---|---|---|---|
| demo humanoid mesh | ok | 2/2 | [hero_mesh.glb](animcraft/hero_mesh/hero_mesh.glb) |
| auto-rig (heat weights) | ok | 5/5 | [hero_rig.glb](animcraft/hero_rig/hero_rig.glb), [hero_rig_engine.png](animcraft/hero_rig/hero_rig_engine.png) |
| 5 clips, each verified moving in three.js | ok | 7/7 | [hero_anim.glb](animcraft/hero_anim/hero_anim.glb), [hero_anim_clips.png](animcraft/hero_anim/hero_anim_clips.png) |
| 1.2 m demo humanoid | ok | 2/2 | [kid_mesh.glb](animcraft/kid_mesh/kid_mesh.glb) |
| Mixamo-named rig | ok | 5/5 | [kid_mixamo.glb](animcraft/kid_mixamo/kid_mixamo.glb) |
| walk retargeted 1.8 m → 1.2 m across bone naming schemes | ok | 3/3 | [kid_walk.glb](animcraft/kid_walk/kid_walk.glb), [kid_walk_clips.png](animcraft/kid_walk/kid_walk_clips.png) |
| 4-direction walk sprite sheets | ok | 8/8 | [hero_walk_dir0.png](animcraft/hero/hero_walk_dir0.png), [hero_walk_dir0.json](animcraft/hero/hero_walk_dir0.json), [hero_walk_dir0.gif](animcraft/hero/hero_walk_dir0.gif), [hero_walk_dir1.png](animcraft/hero/hero_walk_dir1.png), [hero_walk_dir1.json](animcraft/hero/hero_walk_dir1.json), [hero_walk_dir1.gif](animcraft/hero/hero_walk_dir1.gif) |
| demo quadruped | ok | 2/2 | [dog_mesh.glb](animcraft/dog_mesh/dog_mesh.glb) |
| quadruped rig | ok | 5/5 | [dog_rig.glb](animcraft/dog_rig/dog_rig.glb) |
| quadruped walk + idle | ok | 4/4 | [dog_anim.glb](animcraft/dog_anim/dog_anim.glb), [dog_anim_clips.png](animcraft/dog_anim/dog_anim_clips.png) |
| rigid-body drop | ok | 3/3 | [drop.glb](animcraft/drop/drop.glb), [drop_engine.png](animcraft/drop/drop_engine.png) |

## assetcraft

| Run | Status | Checks | Files |
|---|---|---|---|
| catalogue every acceptance output | ok | 2/2 | [scan.json](assetcraft/scan/scan.json) |
| licence inventory + ATTRIBUTION.md | ok | 2/2 | [licenses.json](assetcraft/licenses/licenses.json), [ATTRIBUTION.md](assetcraft/licenses/ATTRIBUTION.md) |
| browsable HTML catalogue | ok | 1/1 | [catalog.html](assetcraft/catalog/catalog.html) |

## audiocraft

| Run | Status | Checks | Files |
|---|---|---|---|
| coin pickup ×3 variations | ok | 3/3 | [coin_01.ogg](audiocraft/coin/coin_01.ogg), [coin_01_waveform.png](audiocraft/coin/coin_01_waveform.png), [coin_02.ogg](audiocraft/coin/coin_02.ogg), [coin_02_waveform.png](audiocraft/coin/coin_02_waveform.png), [coin_03.ogg](audiocraft/coin/coin_03.ogg), [coin_03_waveform.png](audiocraft/coin/coin_03_waveform.png) |
| explosion SFX | ok | 1/1 | [explosion.ogg](audiocraft/explosion/explosion.ogg), [explosion_waveform.png](audiocraft/explosion/explosion_waveform.png) |
| laser SFX | ok | 1/1 | [laser.ogg](audiocraft/laser/laser.ogg), [laser_waveform.png](audiocraft/laser/laser_waveform.png) |
| jump SFX | ok | 1/1 | [jump.ogg](audiocraft/jump/jump.ogg), [jump_waveform.png](audiocraft/jump/jump_waveform.png) |
| footstep SFX | ok | 1/1 | [footstep.ogg](audiocraft/footstep/footstep.ogg), [footstep_waveform.png](audiocraft/footstep/footstep_waveform.png) |
| splash SFX | ok | 1/1 | [splash.ogg](audiocraft/splash/splash.ogg), [splash_waveform.png](audiocraft/splash/splash_waveform.png) |
| magic SFX | ok | 1/1 | [magic.ogg](audiocraft/magic/magic.ogg), [magic_waveform.png](audiocraft/magic/magic_waveform.png) |
| 12 s seamless ocean loop (OGG LOOPSTART/LOOPLENGTH) | ok | 2/2 | [ocean_loop.ogg](audiocraft/ocean_loop/ocean_loop.ogg), [ocean_loop_waveform.png](audiocraft/ocean_loop/ocean_loop_waveform.png) |
| 12 s seamless forest loop | ok | 2/2 | [forest_loop.ogg](audiocraft/forest_loop/forest_loop.ogg) |
| adventure theme: mix, MIDI, adaptive layers manifest | ok | 3/3 | [adventure_theme.ogg](audiocraft/adventure_theme/adventure_theme.ogg), [adventure_theme_waveform.png](audiocraft/adventure_theme/adventure_theme_waveform.png), [adventure_theme.mid](audiocraft/adventure_theme/adventure_theme.mid), [adventure_theme.layers.json](audiocraft/adventure_theme/adventure_theme.layers.json) |
| three voiced lines (Kokoro-82M, CPU) | ok | 3/3 | [captain_01.ogg](audiocraft/harbour_scene/captain_01.ogg), [parrot_01.ogg](audiocraft/harbour_scene/parrot_01.ogg), [narrator_01.ogg](audiocraft/harbour_scene/narrator_01.ogg), [harbour_scene.dialogue.json](audiocraft/harbour_scene/harbour_scene.dialogue.json) |
| loop point recovered from audio with a 1.3 s intro | ok | 2/2 | [theme_with_intro_marked.ogg](audiocraft/theme_with_intro/theme_with_intro_marked.ogg), [theme_with_intro.loop.json](audiocraft/theme_with_intro/theme_with_intro.loop.json) |
| EBU R128 normalised to −16 LUFS | ok | 2/2 | [theme_-16LUFS.ogg](audiocraft/theme_-16LUFS/theme_-16LUFS.ogg) |

## cinematiccraft

| Run | Status | Checks | Files |
|---|---|---|---|
| animated title card | ok | 2/2 | [title.mp4](cinematiccraft/title/title.mp4), [title.png](cinematiccraft/title/title.png) |
| golden-hour island orbit (Cycles) + camera path | ok | 4/4 | [island_orbit.mp4](cinematiccraft/island_orbit/island_orbit.mp4), [island_orbit.camera.json](cinematiccraft/island_orbit/island_orbit.camera.json), [island_orbit_contact.png](cinematiccraft/island_orbit/island_orbit_contact.png) |
| storyboard sheet | ok | 2/2 | [storyboard.png](cinematiccraft/storyboard/storyboard.png), [storyboard.pdf](cinematiccraft/storyboard/storyboard.pdf) |
| teaser: title → orbit → map, music bed | ok | 3/3 | [teaser.mp4](cinematiccraft/teaser/teaser.mp4), [teaser_poster.png](cinematiccraft/teaser/teaser_poster.png) |
| gameplay capture of the fixture game | ok | 2/2 | [gameplay.mp4](cinematiccraft/gameplay/gameplay.mp4) |

## fxcraft

| Run | Status | Checks | Files |
|---|---|---|---|
| fire flipbook | ok | 3/3 | [fire_flipbook.png](fxcraft/fire/fire_flipbook.png), [fire_flipbook.json](fxcraft/fire/fire_flipbook.json), [fire_preview.gif](fxcraft/fire/fire_preview.gif) |
| smoke flipbook | ok | 3/3 | [smoke_flipbook.png](fxcraft/smoke/smoke_flipbook.png), [smoke_flipbook.json](fxcraft/smoke/smoke_flipbook.json), [smoke_preview.gif](fxcraft/smoke/smoke_preview.gif) |
| magic flipbook | ok | 3/3 | [magic_flipbook.png](fxcraft/magic/magic_flipbook.png), [magic_flipbook.json](fxcraft/magic/magic_flipbook.json), [magic_preview.gif](fxcraft/magic/magic_preview.gif) |
| energy flipbook | ok | 3/3 | [energy_flipbook.png](fxcraft/energy/energy_flipbook.png), [energy_flipbook.json](fxcraft/energy/energy_flipbook.json), [energy_preview.gif](fxcraft/energy/energy_preview.gif) |
| explosion flipbook | ok | 3/3 | [explosion_flipbook.png](fxcraft/explosion/explosion_flipbook.png), [explosion_flipbook.json](fxcraft/explosion/explosion_flipbook.json), [explosion_preview.gif](fxcraft/explosion/explosion_preview.gif) |
| sparks flipbook | ok | 3/3 | [sparks_flipbook.png](fxcraft/sparks/sparks_flipbook.png), [sparks_flipbook.json](fxcraft/sparks/sparks_flipbook.json), [sparks_preview.gif](fxcraft/sparks/sparks_preview.gif) |
| dust flipbook | ok | 3/3 | [dust_flipbook.png](fxcraft/dust/dust_flipbook.png), [dust_flipbook.json](fxcraft/dust/dust_flipbook.json), [dust_preview.gif](fxcraft/dust/dust_preview.gif) |
| splash flipbook | ok | 3/3 | [splash_flipbook.png](fxcraft/splash/splash_flipbook.png), [splash_flipbook.json](fxcraft/splash/splash_flipbook.json), [splash_preview.gif](fxcraft/splash/splash_preview.gif) |
| lightning flipbook | ok | 3/3 | [lightning_flipbook.png](fxcraft/lightning/lightning_flipbook.png), [lightning_flipbook.json](fxcraft/lightning/lightning_flipbook.json), [lightning_preview.gif](fxcraft/lightning/lightning_preview.gif) |
| snow flipbook | ok | 3/3 | [snow_flipbook.png](fxcraft/snow/snow_flipbook.png), [snow_flipbook.json](fxcraft/snow/snow_flipbook.json), [snow_preview.gif](fxcraft/snow/snow_preview.gif) |
| torch emitter played in three.js | ok | 4/4 | [torch_flipbook.png](fxcraft/torch/torch_flipbook.png), [torch.fx.json](fxcraft/torch/torch.fx.json), [fxcraft-particles.js](fxcraft/torch/fxcraft-particles.js), [torch_engine.png](fxcraft/torch/torch_engine.png) |
| crate Voronoi destruction with physics | ok | 5/5 | [crate_shatter.glb](fxcraft/crate_shatter/crate_shatter.glb), [crate_shatter_contact.png](fxcraft/crate_shatter/crate_shatter_contact.png), [crate_shatter_engine.png](fxcraft/crate_shatter/crate_shatter_engine.png) |

## levelcraft

| Run | Status | Checks | Files |
|---|---|---|---|
| dungeon level (Tiled + Phaser check + blockout) | ok | 7/7 | [dungeon.tmj](levelcraft/dungeon/dungeon.tmj), [dungeon_tileset.png](levelcraft/dungeon/dungeon_tileset.png), [dungeon_preview.png](levelcraft/dungeon/dungeon_preview.png), [dungeon_phaser.png](levelcraft/dungeon/dungeon_phaser.png), [dungeon_blockout.png](levelcraft/dungeon/dungeon_blockout.png) |
| cave level (Tiled + Phaser check + blockout) | ok | 7/7 | [cave.tmj](levelcraft/cave/cave.tmj), [cave_tileset.png](levelcraft/cave/cave_tileset.png), [cave_preview.png](levelcraft/cave/cave_preview.png), [cave_phaser.png](levelcraft/cave/cave_phaser.png), [cave_blockout.png](levelcraft/cave/cave_blockout.png) |
| platformer level (Tiled + Phaser check + blockout) | ok | 6/6 | [platformer.tmj](levelcraft/platformer/platformer.tmj), [platformer_tileset.png](levelcraft/platformer/platformer_tileset.png), [platformer_preview.png](levelcraft/platformer/platformer_preview.png), [platformer_phaser.png](levelcraft/platformer/platformer_phaser.png), [platformer_blockout.png](levelcraft/platformer/platformer_blockout.png) |
| overworld level (Tiled + Phaser check + blockout) | ok | 6/6 | [overworld.tmj](levelcraft/overworld/overworld.tmj), [overworld_tileset.png](levelcraft/overworld/overworld_tileset.png), [overworld_preview.png](levelcraft/overworld/overworld_preview.png), [overworld_phaser.png](levelcraft/overworld/overworld_phaser.png), [overworld_blockout.png](levelcraft/overworld/overworld_blockout.png) |
| settlement level (Tiled + Phaser check + blockout) | ok | 5/5 | [settlement.tmj](levelcraft/settlement/settlement.tmj), [settlement_tileset.png](levelcraft/settlement/settlement_tileset.png), [settlement_preview.png](levelcraft/settlement/settlement_preview.png), [settlement_phaser.png](levelcraft/settlement/settlement_phaser.png), [settlement_blockout.png](levelcraft/settlement/settlement_blockout.png) |

## materialcraft

| Run | Status | Checks | Files |
|---|---|---|---|
| cobblestone PBR material | ok | 5/5 | [cobblestone_tiled2x2.png](materialcraft/cobblestone/cobblestone_tiled2x2.png), [cobblestone.material.json](materialcraft/cobblestone/cobblestone.material.json), [cobblestone_render.png](materialcraft/cobblestone/cobblestone_render.png) |
| rust PBR material | ok | 5/5 | [rust_tiled2x2.png](materialcraft/rust/rust_tiled2x2.png), [rust.material.json](materialcraft/rust/rust.material.json), [rust_render.png](materialcraft/rust/rust_render.png) |
| planks PBR material | ok | 5/5 | [planks_tiled2x2.png](materialcraft/planks/planks_tiled2x2.png), [planks.material.json](materialcraft/planks/planks.material.json), [planks_render.png](materialcraft/planks/planks_render.png) |
| lava PBR material | ok | 5/5 | [lava_tiled2x2.png](materialcraft/lava/lava_tiled2x2.png), [lava.material.json](materialcraft/lava/lava.material.json), [lava_render.png](materialcraft/lava/lava_render.png) |
| brick PBR material | ok | 5/5 | [brick_tiled2x2.png](materialcraft/brick/brick_tiled2x2.png), [brick.material.json](materialcraft/brick/brick.material.json), [brick_render.png](materialcraft/brick/brick_render.png) |
| ice PBR material | ok | 5/5 | [ice_tiled2x2.png](materialcraft/ice/ice_tiled2x2.png), [ice.material.json](materialcraft/ice/ice.material.json), [ice_render.png](materialcraft/ice/ice_render.png) |
| all 21 materials | ok | 1/1 | [swatches.png](materialcraft/swatches/swatches.png) |

## testcraft

| Run | Status | Checks | Files |
|---|---|---|---|
| smoke test on desktop, phone, tablet | ok | 18/18 | [desktop_loaded.png](testcraft/smoke/desktop_loaded.png), [phone_loaded.png](testcraft/smoke/phone_loaded.png), [tablet_loaded.png](testcraft/smoke/tablet_loaded.png), [smoke_report.html](testcraft/smoke/smoke_report.html) |
| scripted gameplay with state assertions | ok | 4/4 | [desktop_after_move.png](testcraft/play/desktop_after_move.png), [play_report.html](testcraft/play/play_report.html) |
| FPS / frame-time profile | ok | 3/3 | [perf_report.html](testcraft/perf/perf_report.html) |
| asset integrity of every WorldCraft output | ok | 1/1 | [world_assets_report.html](testcraft/world_assets/world_assets_report.html) |

## worldcraft

| Run | Status | Checks | Files |
|---|---|---|---|
| island terrain (tropical) | ok | 6/6 | [island_height16.png](worldcraft/island/island_height16.png), [island_splat.png](worldcraft/island/island_splat.png), [island_preview.png](worldcraft/island/island_preview.png), [island_scatter.json](worldcraft/island/island_scatter.json), [island_coastline.json](worldcraft/island/island_coastline.json), [island.glb](worldcraft/island/island.glb) |
| archipelago terrain (tropical) | ok | 6/6 | [archipelago_height16.png](worldcraft/archipelago/archipelago_height16.png), [archipelago_splat.png](worldcraft/archipelago/archipelago_splat.png), [archipelago_preview.png](worldcraft/archipelago/archipelago_preview.png), [archipelago.terrain.json](worldcraft/archipelago/archipelago.terrain.json), [archipelago_engine.png](worldcraft/archipelago/archipelago_engine.png) |
| mountains terrain (cold) | ok | 5/5 | [mountains_height16.png](worldcraft/mountains/mountains_height16.png), [mountains_splat.png](worldcraft/mountains/mountains_splat.png), [mountains_preview.png](worldcraft/mountains/mountains_preview.png), [mountains.terrain.json](worldcraft/mountains/mountains.terrain.json), [mountains_engine.png](worldcraft/mountains/mountains_engine.png) |
| canyon terrain (arid) | ok | 5/5 | [canyon_height16.png](worldcraft/canyon/canyon_height16.png), [canyon_splat.png](worldcraft/canyon/canyon_splat.png), [canyon_preview.png](worldcraft/canyon/canyon_preview.png), [canyon.terrain.json](worldcraft/canyon/canyon.terrain.json), [canyon_engine.png](worldcraft/canyon/canyon_engine.png) |
| cave system (closed surface-nets mesh) | ok | 3/3 | [cave.glb](worldcraft/cave/cave.glb), [cave_engine.png](worldcraft/cave/cave_engine.png), [cave_slices.png](worldcraft/cave/cave_slices.png) |
| sunset sky (Blender Nishita) + cubemap | ok | 3/3 | [sky_sunset_equirect.png](worldcraft/sky_sunset/sky_sunset_equirect.png), [sky_sunset_cubemap_sheet.png](worldcraft/sky_sunset/sky_sunset_cubemap_sheet.png), [sky_sunset.sky.json](worldcraft/sky_sunset/sky_sunset.sky.json) |
| noon sky (Blender Nishita) + cubemap | ok | 3/3 | [sky_noon_equirect.png](worldcraft/sky_noon/sky_noon_equirect.png), [sky_noon_cubemap_sheet.png](worldcraft/sky_noon/sky_noon_cubemap_sheet.png), [sky_noon.sky.json](worldcraft/sky_noon/sky_noon.sky.json) |
| night sky (Blender Nishita) + cubemap | ok | 3/3 | [sky_night_equirect.png](worldcraft/sky_night/sky_night_equirect.png), [sky_night_cubemap_sheet.png](worldcraft/sky_night/sky_night_cubemap_sheet.png), [sky_night.sky.json](worldcraft/sky_night/sky_night.sky.json) |
| FFT ocean (loops in time and space) | ok | 5/5 | [ocean_normal_flipbook.png](worldcraft/ocean/ocean_normal_flipbook.png), [ocean.ocean.json](worldcraft/ocean/ocean.ocean.json), [ocean_engine.png](worldcraft/ocean/ocean_engine.png) |

