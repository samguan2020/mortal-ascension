# Art Bible: Tingyu Inn

> **Status**: Draft for Review
> **Date**: 2026-10-04
> **Scope**: Cultivation-game visual foundation, beginning with Tingyu Inn
> **Target**: Desktop browser, Three.js WebGPU with WebGL 2 fallback, 60 FPS

## 1. Visual Identity Statement

### One-Line Rule

**Build the mortal world as a living three-dimensional scene painted inside
an unfolding Chinese landscape scroll; reveal cultivation as the moment ink,
paper, depth, and gravity stop obeying the same rules.**

Every visual decision must preserve the contrast between tangible everyday
life and scarce supernatural evidence. The inn remains fully navigable 3D,
but its materials, silhouettes, atmosphere, and UI share the same ink-and-
mineral-pigment visual grammar as the wider landscape.

### Supporting Principles

#### Crafted, Not Perfect

Wood bows, plaster stains, cloth creases, and objects sit slightly out of
alignment. Repetition is broken through controlled variation rather than
random noise.

**Serves:** Believable, persistent NPC lives.

**Design test:** When choosing between a pristine asset and one with a readable
history of use, choose the lived-in version unless it harms silhouette or
navigation.

#### Playable Ink Scroll

The camera sees the scene as a framed passage through a painted scroll.
Silhouettes are edged like confident brush marks; distant depth collapses into
layered ink washes, while interactive foreground objects retain enough 3D form
for navigation and animation.

**Serves:** Low-cost, always-on world.

**Design test:** If a detail does not strengthen silhouette, material rhythm,
spatial navigation, or story evidence at gameplay distance, merge it into a
painted texture or remove it.

#### Immortality Is a Visual Exception

The mortal world uses warm earth colors, soft reflections, and physically
plausible motion. Authentic cultivation phenomena introduce controlled cool
light, impossible suspension, unnaturally clean curves, or movement that
ignores wind and gravity.

**Serves:** Discovery and legible AI/world reasoning.

**Design test:** If every prop, costume, or effect looks magical, remove the
magic from ordinary objects so the true anomaly regains meaning.

### Not This Game

- Not photorealistic historical reconstruction.
- Not neon cyber-xianxia.
- Not a toy-like low-poly diorama with uniformly clean assets.
- Not constant particle spectacle.
- Not a collection of unmodified AI-generated models with conflicting proportions.

## 2. Mood & Atmosphere

| Game State | Emotional Target | Lighting | Atmosphere | Energy |
|---|---|---|---|---|
| Arrival in rain | Shelter after uncertainty | Cool exterior rain against warm interior lanterns; medium contrast | wet, inviting, unfamiliar, watchful | Measured |
| Free exploration | Quiet curiosity | Warm pools of light with darker rafters and corners | inhabited, layered, calm, slightly secretive | Contemplative |
| NPC conversation | Intimacy and attention | Subtle local lift on faces; background remains visible and subdued | personal, attentive, grounded | Low |
| Credible rumor revealed | A small pull toward adventure | Lantern warmth holds while one cool accent appears in UI or world detail | intriguing, uncertain, directional | Rising |
| AI waiting state | The world continues without the player | No global dim or freeze; NPC uses a thinking gesture and ambient motion continues | patient, alive, non-blocking | Low |
| Genuine immortal phenomenon | Awe through restraint | Narrow cool-white or blue-green light, high local contrast, minimal bloom | impossible, silent, precise, rare | Focused |
| Danger or deception | Mortal vulnerability | Warm light becomes uneven; red-brown shadows, occluded sightlines | tense, ambiguous, enclosed | Controlled |

### Atmosphere Carriers

- Rain against paper windows and eaves.
- Lantern sway that responds slightly to drafts.
- Steam from tea and the kitchen.
- Dust visible only inside strong light shafts.
- Quiet peripheral NPC motion.
- Rare supernatural elements that do not react like ordinary particles.

## 3. Shape Language

### World Geometry

- Mortal architecture is built from weight-bearing rectangles, thick beams,
  shallow curves, and visibly joined modules.
- Furniture uses broad tops and sturdy legs. Thin geometry is reserved for
  paper, tassels, chopsticks, and metal fittings.
- Structural elements may be slightly warped but must still communicate how
  the building stands.
- Hero lines guide the eye from the entrance to the counter, then toward
  stairs, notice boards, or story clues.

### Character Silhouettes

- Characters use stylized human proportions: approximately 5.5 to 6 heads tall.
- Hands, sleeves, headwear, belts, and carried objects are enlarged enough to
  read from the gameplay camera.
- Each important NPC receives one dominant silhouette feature and one secondary
  movement feature.
- Cultivators are not identified by excessive ornaments. Their distinction
  comes from controlled posture, clean garment rhythm, and one impossible detail.

### Archetype Grammar

| Archetype | Dominant Shapes | Meaning |
|---|---|---|
| Innkeeper / merchant | Stable rectangles, layered waist silhouette | Reliability, rootedness, guarded information |
| Traveler / jianghu wanderer | Diagonals, asymmetry, wrapped bundles | Motion, incomplete stories |
| Scholar / storyteller | Vertical folds, circular fan or scroll | Interpretation, memory, performance |
| Cultivator | Long uninterrupted curves, narrow triangular accents | Discipline, direction, separation from ordinary life |
| Deceiver / threat | Broken symmetry, concealed hands, inward shapes | Withheld intent |

### UI Shape Grammar

- Panels echo dark wood frames and layered paper rather than literal parchment scrolls.
- Corners are softly chamfered, not modern pill shapes everywhere.
- Important choices use seal-like square or vertical markers.
- The AI insight layer may use cleaner geometric overlays, but it must remain
  opt-in and visually distinct from the diegetic world.

## 4. Color System

### Primary Palette

| Name | Hex | Role |
|---|---|---|
| Smoked Timber | `#2B2119` | Deep background, beams, dialogue foundations |
| Aged Walnut | `#5B3A29` | Primary architecture and furniture |
| Tea Paper | `#E8D7B5` | Readable text, paper, warm highlights |
| Lantern Amber | `#D99B4A` | Safety, hospitality, active interaction |
| Clay Red | `#9C4A35` | Fabric, seals, social importance |
| Rain Slate | `#53636B` | Exterior weather, uncertainty, distance |
| Spirit Jade | `#79C7B7` | Verified supernatural presence only |

### Semantic Rules

- **Amber:** shelter, available interaction, ordinary human warmth.
- **Clay red:** authored importance, warning through human convention, seals and vows.
- **Rain slate:** unknown information, distance, rumor, unconfirmed paths.
- **Spirit jade:** genuine or strongly evidenced cultivation phenomena. Never use
  it for ordinary decoration.
- **Gold:** earned status or sacred institutional authority, not generic loot rarity.
- **White:** spiritual clarity, mourning, or absence depending on context; pair with shape and sound.

### Area Temperature

- Tingyu Inn interior: warm 2600–3400 K impression.
- Rain exterior: cool 6000–7500 K impression with reduced saturation.
- Qixia Mountain mortal paths: neutral daylight with moss and stone.
- Confirmed spiritual sites: neutral world palette interrupted by narrow jade-white accents.

### UI Palette

- Main UI uses Smoked Timber, Tea Paper, and Lantern Amber.
- Unconfirmed rumor cards use Rain Slate plus a question-mark or broken-line icon.
- Confirmed journal facts use Tea Paper plus a solid seal icon.
- Spirit Jade cannot be the only indicator of magical authenticity.

### Colorblind Safety

- Status meaning always includes icon shape and text.
- Unconfirmed/confirmed information uses broken/solid border patterns.
- Hostile/beneficial effects combine color with directional motion and audio.
- Never encode relationship level using a red-to-green gradient alone.

## 5. Character Design Direction

### Overall Style

- Ink-outlined, hand-painted stylized 3D with restrained PBR response.
- Broad forms and garment flow carry the character; brush-shaped value groups
  support rather than obscure anatomy.
- Faces use simplified planes, readable brows, eyes, and mouth, with restrained
  normal detail.
- Faces are illustrated through clean planes, selective ink accents, and
  restrained mineral color rather than plastic smoothness or realistic skin.

### Player Character

- Starts visually ordinary: practical travel clothes, rain cape, cloth shoes,
  modest pack, no glowing weapon or sect insignia.
- Silhouette must leave room for visible progression through garments, posture,
  accessories, and eventually cultivation phenomena.
- Base costume uses neutral earth tones so future faction colors remain readable.

### Innkeeper Liu

- Dominant silhouette: stable layered torso with rolled sleeves and a broad waist sash.
- Secondary feature: one hand frequently rests near the abacus or tea cloth.
- Face: middle-aged, observant eyes, restrained smile, readable brow movement.
- Costume: worn walnut-brown outer vest, tea-paper inner shirt, clay-red accounting pouch.
- No overt magical ornament.

### Expression and Pose

- Conversation animation is measured and asymmetrical.
- NPCs look toward tasks and nearby people instead of staring at the player continuously.
- Emotion is carried first by posture, then hands, then face.
- Gestures must have a clear rest pose so AI response latency can loop gracefully.

### Runtime LOD

| LOD | Use | Preserve |
|---|---|---|
| LOD0 | Conversation and close camera | Face planes, hands, major garment layers |
| LOD1 | Normal gameplay | Silhouette, headwear, carried object, primary colors |
| LOD2 | Background patrons | Body mass, dominant costume color, motion archetype |

## 6. Environment Design Language

### Architecture

- Northern market-town timber construction with heavy beams, plaster infill,
  tiled eaves, paper windows, and practical repairs.
- The inn layout must communicate business operations: entrance, counter,
  kitchen access, guest tables, stair or lodging access, storage.
- Construction modules remain reusable, but visible seams are covered by beams,
  trim, cloth, or believable repair work.

### Texture Philosophy

- Low-frequency ink wash and mineral-pigment variation layered over restrained PBR.
- Roughness variation matters more than high-resolution normal noise.
- Wood grain follows geometry and scale; no universal procedural wood texture.
- Edge wear appears at contact points, never uniformly along every edge.
- Dirt accumulates by use: wet entrance, counter hand zone, stove smoke, chair legs.
- Distant exterior scenery uses layered painted cards or low-detail geometry so
  mountains, roofs, mist, and rain read like parallax sections of a handscroll.

### Prop Density

- Navigation lanes stay visually quiet.
- Social clusters contain 3–7 meaningful props that explain activity.
- Hero clue areas use one dominant object plus two supporting details.
- Background shelves rely on grouped silhouettes and texture atlases rather than
  dozens of unique draw calls.

### Environmental Storytelling

- A rain-darkened threshold shows recent arrivals.
- Abacus, room ledger, tea stains, and patched counter explain the keeper's routine.
- Travelers leave regional objects that hint at places beyond the inn.
- Rumors appear through physical traces before journal exposition whenever possible.
- The half cloud-pattern token receives a controlled material and silhouette,
  not a large quest glow.

## 7. UI/HUD Visual Direction

### Structure

- HTML/CSS screen-space UI remains primary for accessibility and text input.
- The 3D world stays visible during dialogue.
- Dialogue panels resemble dark ink blocks laid over warm paper, with sparse
  vermilion seal accents and irregular brush-edge masks.
- Quick questions resemble annotations or stamped topic slips, not modern app chips.

### Typography

- Display headings: a legible Song/Ming-style Chinese serif with restrained brush character.
- Body and dialogue: highly legible CJK serif or humanist sans at a minimum 18 px desktop size.
- English fallback uses a serif with similar contrast and proportion.
- Never use decorative calligraphy for body text or controls.

### Iconography

- Simple filled or two-tone silhouettes inspired by seals and carved signage.
- Icons must remain legible at 20–24 px.
- Rumor reliability uses border grammar:
  - dotted/broken: hearsay;
  - mixed: corroborated;
  - solid seal: witnessed or confirmed.

### Motion

- Panels settle like a placed object: 140–220 ms ease-out with minimal scale.
- Topic slips shift or stamp into place.
- Reduced-motion mode replaces movement with opacity transitions.
- Waiting feedback appears on the NPC and status line; no blocking full-screen spinner.

## 8. Asset Standards

### Runtime Formats

- Models and skeletal animation: glTF 2.0 binary (`.glb`).
- Textures: KTX2/Basis Universal for production; PNG only for source or UI where necessary.
- Geometry compression: Meshopt preferred; Draco allowed only when decode cost is measured.
- Audio: compressed browser-supported assets with loop metadata documented.
- Source files: `.blend` retained beside export metadata but never shipped to clients.

### Coordinate and Export Rules

- Units: meters.
- Up axis: Y.
- Forward axis: document per exporter and validate in Three.js.
- Object origins placed at the logical ground/contact point.
- Apply transforms before export.
- Human characters use a shared humanoid skeleton and consistent rest pose.
- Animation names use `category_action_variant`, for example `social_talk_calm_01`.

### Geometry Budgets

| Asset | LOD0 | LOD1 | LOD2 | Material Slots |
|---|---:|---:|---:|---:|
| Hero NPC | 30k–40k triangles | 12k–18k | 3k–6k | 4 max |
| Background NPC | 15k–22k | 6k–10k | 2k–4k | 2 max |
| Hero architecture module | 15k–25k | 6k–10k | 2k–4k | 3 max |
| Large prop | 4k–10k | 1.5k–4k | 500–1.5k | 2 max |
| Small prop | 500–3k | 200–1k | optional | 1 max |

Budgets are ceilings, not targets.

### Texture Budgets

| Category | Maximum | Preferred |
|---|---:|---:|
| Hero character | 2K per set | Shared packed maps where practical |
| Background character | 1K | Atlas by archetype |
| Architecture hero module | 2K | Tiling material plus masks |
| Large prop | 1K | Reuse material families |
| Small prop | 512 | Shared atlas |
| UI illustration | 2K source | Responsive production sizes |

### Browser Delivery Budgets

- Initial playable download target: 15 MB compressed or less.
- Tingyu Inn complete area target: 35 MB compressed or less.
- Initial visible hero character: 5 MB compressed or less.
- Maintain 60 FPS at 1080p on the agreed minimum desktop target.
- WebGL fallback removes expensive particles, high-cost post effects, and distant
  secondary patrons before reducing core material readability.
- Prefer instancing, atlases, and shared materials over increasing draw calls.

### AIGC and External Asset Intake

Every Tripo or external model must pass through Blender and satisfy:

1. Source and license recorded.
2. Scale, orientation, and origin normalized.
3. Topology inspected; hidden and duplicate geometry removed.
4. UV density normalized.
5. Materials rebuilt into approved families.
6. Texture colors shifted into the approved palette.
7. Silhouette checked at gameplay camera distance.
8. LODs and collision representation created where needed.
9. Browser download and GPU memory cost measured.

Unmodified generated assets do not enter the game.

### Naming

```text
env_inn_beam_a.glb
env_inn_counter_hero.glb
prop_ceramic_wine_jar_a.glb
chr_liu_innkeeper_lod0.glb
chr_player_mortal_base_lod0.glb
vfx_rain_window_sheet.ts
mat_wood_walnut_aged.ktx2
```

## 9. Reference Direction and Style Prohibitions

### References

#### Gujian 3

**Take:** believable Chinese timber architecture, material hierarchy, and the
sense that domestic spaces support real routines.

**Avoid:** cinematic realism, dense texture detail, and asset cost unsuitable
for a browser miniature.

#### Chinese Landscape Handscrolls

**Take:** layered depth, intentional empty space, mountain-and-cloud rhythm,
mineral color accents, and compositions that guide the eye horizontally.

**Avoid:** treating the world as a flat background image with no playable depth.

#### Ink-Outlined Stylized 3D Characters

**Take:** readable garment masses, selective linework, controlled proportions,
painted value grouping, and animation-friendly forms.

**Avoid:** generic faceless capsules, plastic toy shading, and mismatched
AI-generated anatomy.

#### Chinese Ink and Mineral Pigment Painting

**Take:** controlled empty space, restrained atmospheric gradients, and selective
jade, clay-red, and mineral-blue accents.

**Avoid:** applying paper grain or ink outlines uniformly to every surface.

### Style Prohibitions

- No neon outlines for ordinary interactable objects.
- No generic golden quest beams.
- No excessive bloom.
- No uniform edge wear.
- No photorealistic humans beside stylized architecture.
- No more than one dominant magical color in an ordinary scene.
- No modern glassmorphism as the primary UI language.
- No unreadable calligraphy for functional text.
- No generated asset is accepted solely because it looks attractive in isolation.
