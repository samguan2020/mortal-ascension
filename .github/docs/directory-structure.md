# Directory Structure

Mortal Ascension is a standalone browser game. The production stack is
`web/` plus `cloud/`; no preserved engine client or runnable prototype remains.

```text
/
├── AGENTS.md
├── .github/                     # Copilot roles, skills, rules and CI
│   └── docs/                    # Shared Copilot standards and templates
├── web/                         # Three.js / TypeScript / Vite client
│   ├── public/characters/       # Final runtime GLB assets
│   └── src/                     # Game code and Node tests
├── cloud/                       # FastAPI runtime, Dockerfile and Python tests
├── backend/                     # Shared pure-Python NPC modules
│   ├── npc_roles.py
│   └── relationship_manager.py
├── assets/source/
│   ├── characters/              # Editable Blender files
│   └── motions/                 # Reusable source animation GLBs
├── cinematics/blender/          # Offline Eevee cinematic scenes and build scripts
├── tools/
│   ├── asset-pipeline/          # Character build/validation tools
│   ├── deploy_azure.py
│   ├── test_deploy_azure.py
│   └── verify_azure.py
├── design/                      # Current visual, UX and opening specifications
└── docs/                        # Current architecture and deployment docs
```

## Source routing

| Location | Responsibility |
|---|---|
| `web/src/**/*.ts` | Browser gameplay, rendering and UI |
| `cloud/**/*.py` | Protected API, sessions and integration tests |
| `backend/*.py` | Shared NPC prompt and deterministic relationship logic |
| `tools/asset-pipeline/**/*.py` | Offline asset generation and validation |
| `assets/source/**` | Editable source assets; never imported at runtime |
| `cinematics/blender/**` | Editable offline cinematic scenes; renders are ignored |

## Cinematic visual test

The Blender 3.6 Eevee path is the current lightweight visual test and remains
independent of the browser game.
`cinematics/blender/build_first_shot.py` builds `FirstShot_BronzeJade.blend` from the
existing traveler source without overwriting it. Run it using Blender's
`--factory-startup -b --python-exit-code 1 --python` options. Append
`-- --preview` for a 10-second, 24 fps, 960x540 H.264 camera study in addition
to the 1920x1080 PNG still. Both render outputs live under the ignored
`cinematics/blender/renders/` directory.

The current cinematic-only direction uses blue-green mountains, weathered
bronze, carved jade and warm sunlight, rather than ink-wash rendering.
The default still is `renders/bronze_jade_1080.png`; the optional video is
`renders/bronze_jade_preview.mp4`. The original `FirstShot.blend` and its
`first_shot_*` renders are preserved as the initial composition blockout.

After approving the base scene, use `-- --final` instead of `-- --preview`
to load (not rebuild) `FirstShot_BronzeJade.blend`, add slow cloud-texture
flow and bounded jade-emission animation, and output a separate
`FirstShot_BronzeJade_Final.blend`. This mode renders
`renders/bronze_jade_final_1080.png` and a 10-second 1920x1080, 24 fps H.264
`renders/bronze_jade_final.mp4`, using 48 Eevee samples per video frame.
It leaves the accepted base scene, still and preview untouched.
The saved final scene retains the animation and HD video-output settings.
Here "final" distinguishes the HD render from the low-resolution preview;
it is not a claim of finished trailer art. Audio and titles are not included.

To package this HD shot, run
`python cinematics\blender\package_first_shot.py` with Pillow and
imageio-ffmpeg available (validated with versions 11.1.0 and 0.6.0).
This separate Windows tool uses installed Georgia and Microsoft YaHei fonts,
generates its own stereo wind/chime audio without external samples, and
outputs `renders/bronze_jade_teaser.mp4`: a 12-second, 1080p/24 fps H.264/AAC
edit with introductory titles, a two-second final-frame hold, and an end card.
The approved branding is **凡骨登仙** (short name **登仙**) /
**Mortal Ascension**, with the tagline **凡骨入道，一念登仙**.
Use these titles for the film, not the working scene label.
The faded mix uses two-pass loudness normalization targeting -23 LUFS with
a -2 dBTP ceiling. Fonts are rasterized, not copied.
Generated title PNGs and the editable PCM WAV stay in the ignored render
folder for reuse. The source video and Blender scenes are not modified.
Rerunning the packaging tool replaces only its own packaging outputs.

For the cinematic-only costume refinement, run Blender 3.6 with
`--factory-startup -b --python-exit-code 1 --python
cinematics\blender\refine_traveler_costume.py`.
It reuses the existing offline garment builders and traveler skin-weight
rules to add layered robes, a shoulder mantle, embroidered borders, belt,
charms and travel-gear details. It loads the approved final scene and writes
`FirstShot_Costume.blend`, plus `renders/traveler_costume_scene.png` and
front/rear wardrobe portraits. The saved scene retains its original camera
and ambient animation; portrait staging is temporary and is not saved.
Neither the accepted source character nor existing videos are overwritten.

For the separate narrated costume edit, run
`python -B cinematics\blender\narrate_first_shot.py --prepare`.
This offline Windows pipeline uses Pillow/imageio-ffmpeg and the installed
**Microsoft Kangkang** zh-CN male synthetic voice through PowerShell 7
(`pwsh.exe`) and `System.Speech` (the legacy Windows PowerShell host does not
expose this installed voice);
missing voices fail explicitly, without substitution or execution-policy changes.
It needs no source video, network, samples, paid services or Blender process.
The three short Chinese sentences are a cinematic draft, not new game lore.
Speech is synthesized at rate -1 into separate uncut 48 kHz PCM takes.
Measured sentence durations drive subtitles and the edit: a 0.75-second lead-in,
0.45-second inter-sentence gaps, the final tagline on the end card, and at least
1.5 seconds after speech. Duration is rounded up to 24 fps, bounded to 12-20 seconds.

Preparation creates only `renders/narrated_*` assets: UTF-8 sentence text/SRT,
readable backed subtitle PNGs, branded title PNGs, sentence WAVs, editable stereo
voice/music/ducked-music/raw-mix/normalized-mix WAVs, and `narrated_timing.json`.
The original synthesized D-major pentatonic melody uses soft plucked harmonics
and a warm airy sustained layer. Smooth music ducking preserves at least 14 dB
sentence-level voice/music RMS separation. Two-pass normalization targets
-18 LUFS with a -2 dBTP delivery ceiling (normalizing to -2.5 dBTP reserves
headroom for AAC overshoot); both PCM and a temporary AAC encode are measured.
The timing report includes actual durations, frame count, note events, hashes,
loudness readings and exact assembly commands. These are numerical checks,
not a claim of listening review. Preparation stages assets before atomic
per-file publication; the manifest is published last and verified at assembly.
Rerunning preparation replaces only its own named assets.

After the parent renders the silent 10-second 1920x1080/24 fps
`renders/bronze_jade_costume.mp4` from `FirstShot_Costume.blend`, run
`python -B cinematics\blender\narrate_first_shot.py --assemble`.
Assembly preserves the full native-rate shot, clones its last frame only under
the closing title, burns in the synchronized subtitles, and fades the entire
composite to six final black frames. The separate output is
`renders/mortal_ascension_narrated.mp4` (H.264 yuv420p, AAC 48 kHz stereo,
faststart). It validates source/output frames, audio loudness and final black
frames before atomic publication, and refuses to overwrite an existing narrated
film. Prior videos, scene files and editable character sources remain untouched.

For the separately approved Clipchamp recording, use the same mixer, score,
graphics and assembler with a distinct variant:

```powershell
python -B cinematics\blender\narrate_first_shot.py --prepare --variant clipchamp --narration-audio "C:\Users\xingu\Downloads\Video Project 4.m4a" --cuts 4.46 7.24
python -B cinematics\blender\narrate_first_shot.py --assemble --variant clipchamp
python -B -m unittest discover -s cinematics\blender -p narration_import_test.py -v
```

Import requires an existing local M4A/WAV (at most 64 MiB), and exactly two
finite, increasing cuts strictly inside the measured decoded duration. Cuts
are rounded to 48 kHz sample boundaries and must leave three nonempty takes.
All decoded stereo PCM16 frames are retained, including source silence, without
truncation or speed changes. A byte-identical input copy, the complete decoded
WAV and its three uncut slices are stored as `renders/clipchamp_*`, alongside
the distinct stems, title/subtitle graphics, SRT and `clipchamp_timing.json`.
The report records original/decoded SHA256, encoder metadata, original path,
sample counts, explicit cuts and source-to-film timing. The closing title moves
later if necessary to finish the second sentence before the title transition;
the final sentence starts after the title is fully visible. The same 12-20 second
film bound applies, with explicit failure rather than truncation or substitution.

The approved cuts at 4.46 and 7.24 seconds were inferred from pauses and the
supplied text, **not confirmed by listening or ASR**. The user identified a male
Clipchamp source; its encoder metadata establishes the provider, not the voice
preset. The fixed captions are the approved cinematic draft, not a transcript
verification. Import never falls back to Windows speech.
Assembly needs only the verified prepared assets and silent costume source,
not the mutable Downloads original or a speech service. It writes
`renders/mortal_ascension_clipchamp.mp4` and refuses to overwrite it.
The default commands still use Microsoft Kangkang and `narrated_*`; this variant
does not replace those assets or `mortal_ascension_narrated.mp4`.

The base render is a silent cinematic material study; even the packaged
version is not final trailer art or game footage, and neither changes the
game's art bible.
Regeneration overwrites the new generated scene and renders; save manual
scene edits under a different filename. Existing source characters and the
browser/cloud runtime are not modified by the cinematic build.

### Isolated traveler character study

Before any further animation rerender, build the separate character study from
the repository root:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 3.6\blender.exe' `
  --factory-startup -b --python-exit-code 1 `
  --python cinematics\blender\refine_traveler_portrait.py
```

The generator reads `FirstShot_Costume.blend` and writes only
`cinematics/blender/FirstShot_TravelerStudy.blend` and
`cinematics/blender/renders/traveler_study_*` outputs. The saved file retains
the original cinematic scene and adds an independent editable portrait studio.
It renders `traveler_study_half.png` (1200x1500), `traveler_study_full.png`
and `traveler_study_rear.png` (1080x1500), using Eevee at 128 samples.
The comparison sheet's columns are old full, study full, old half, study half;
the old costume uses identical studio cameras and lighting.

The study prioritizes slimmer garment forms, restrained ornaments, cloth folds,
smaller footwear, fitted backpack straps, finer hair and subtle skin variation.
Soft key/fill/rim lighting and an earthy contact-shadow stage are preview-only
changes, not changes to the film's environment or the game's art direction.
`traveler_study_evidence.json` records preserved-input hashes, finite geometry,
full-body framing, original skin-weight checks and a saved-scene reload render
comparison; `traveler_study_reload_half.png` is the reload proof.

This remains a stylized procedural study with source facial anatomy, simplified
hair/cloth transitions and a **baked static pose, not an animation-ready rig**.
The folds are not cloth simulation. Inspect the actual stills before approving
further film work. Regeneration replaces this study's generated outputs, so save
manual edits elsewhere. Original character sources, scenes, images, movies,
audio variants and browser assets are not replaced.

#### Richer costume alternative

Append `-- --ornate` to the same Blender command to load the accepted
`FirstShot_TravelerStudy.blend` rather than rebuilding it. This variant keeps
the corrected connected shoulders, anatomy, collar and hair, and adds fitted
asymmetric mantle layers, muted madder/indigo bands, flat flax embroidery,
an aged-bronze belt fastening, pouch, secured scroll cases and a short hair ribbon.
It reuses the accepted studio lights, cameras, world and exposure.

Outputs are exclusively `FirstShot_TravelerOrnate.blend` and
`renders/traveler_ornate_*`: half/full/rear portraits, a closer `craft.png`
view, contact sheet, reload proof and JSON evidence. The comparison columns
are accepted simple full, ornate full, accepted simple half, ornate half.
The generator checks the approved input fingerprints, preserves all existing
study renders and scenes, and validates geometry, original weights, camera
margins and a saved-scene rerender. Running without `--ornate` retains the
original simple-study workflow; do not run that default mode to refresh an
accepted study unintentionally. Both alternatives remain static baked-pose
studies, not animation-ready costumes or final hero art. Neither mode rerenders
a film or changes narration.

#### Reference-inspired face without glasses

Use the same command with `-- --ornate --reference-face` to load the saved ornate
alternative and create `FirstShot_TravelerPortrait.blend` plus only
`renders/traveler_portrait_*`. Both prior alternatives and all their renders
remain unchanged. The face is an approximate stylized interpretation of a
user-provided frontal illustration: broader jaw/cheek planes, a fuller nose,
coordinated eyes/lids, defined brows, short moustache/goatee, and swept-back
black hair tied above an exposed forehead. No glasses are created.

The generator uses deterministic authored sculpt parameters, not an image pasted
on the face. It neither archives nor embeds the reference bitmap, and reruns do
not depend on its temporary location. Optional `--reference-proof <local image>`
checks the approved image hash before and after generation without modifying it.
No reference path or bitmap is published into runtime assets.

Outputs include `front.png` and `threequarter.png` face close-ups, half/full/rear
views, a prior-ornate versus reference-face contact sheet, reload proof and JSON
evidence, all with the `traveler_portrait_` prefix. The half view is 1200x1500;
the other portraits are 1080x1500. Facial alignment, finite geometry, the
preserved garment topology, input hashes and a saved-scene rerender are checked.
One small frontal illustration cannot determine concealed eyes or a unique
side profile: this is not an exact likeness, photoreal reconstruction, identity
recognition or facial-animation-ready asset.

The focused facial correction uses broader, less peaked brows, skin-only
upper-lid hooding without vertically flattening ocular components, fuller lower lids,
localized bridge/alar/philtrum edits, Cupid-shaped upper-lip and fuller lower-lip
geometry with restrained lip shading. Short irregularly distributed fibers
replace the earlier row-like facial hair. Costume, studio lights and scalp groom
are unchanged. Add `--face-preview` to the reference-face command to render and
inspect only frontal/three-quarter views before running the complete command.
The source's generic socket, cheek and mouth topology still limits likeness:
these edits improve characterization, not a faithful reconstruction.
