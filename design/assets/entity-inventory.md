# Visual Entity and Asset Inventory: Tingyu Inn

> **Status**: Draft
> **Date**: 2026-10-04
> **Governing document**: `design/art/art-bible.md`
> **MVP area**: Qingshi Town - Tingyu Inn

## Priority Definitions

- **P0**: Required to replace the current geometric prototype.
- **P1**: Required for a convincing first public slice.
- **P2**: Adds variation after the core scene is stable.

## Characters

| ID | Asset | Priority | Source Strategy | Notes |
|---|---|---:|---|---|
| CHR-PLAYER-001 | Mortal player base | P0 | Blender base mesh; generated concept reference allowed | Shared humanoid rig, neutral travel clothes |
| CHR-LIU-001 | Innkeeper Liu | P0 | Blender hero character; Tripo only as blockout | Full dialogue LOD0 and expressive hands |
| CHR-PATRON-001 | Traveling merchant | P1 | Shared body + modular clothing | Background ambient behavior |
| CHR-PATRON-002 | Old storyteller | P1 | Shared rig, unique silhouette | Future legend source |
| CHR-PATRON-003 | Quiet wanderer | P1 | Shared rig, asymmetric cloak | Possible sect clue |
| CHR-PATRON-VAR | Patron variants | P2 | Modular heads, hair, hats, clothing colors | Instanced/background LOD |

## Character Animation

| ID | Animation Set | Priority | Notes |
|---|---|---:|---|
| ANIM-HUM-LOC | Idle, walk, turn | P0 | Shared by all humanoids |
| ANIM-LIU-WORK | Abacus, wipe counter, pour tea | P0 | Loops during normal state |
| ANIM-LIU-TALK | Calm talk, cautious aside, rumor emphasis | P0 | Must support AI latency loops |
| ANIM-PLAYER-INT | Listen, nod, receive item | P1 | Conversation feedback |
| ANIM-PATRON | Drink, eat, listen, quiet talk | P1 | Ambient variety |

## Architecture Modules

| ID | Asset | Priority | Source Strategy |
|---|---|---:|---|
| ENV-INN-FLOOR | Modular timber floor | P0 | Blender |
| ENV-INN-WALL | Timber-and-plaster wall set | P0 | Blender |
| ENV-INN-BEAM | Beam and post kit | P0 | Blender |
| ENV-INN-WINDOW | Paper window, open/closed variants | P0 | Blender |
| ENV-INN-DOOR | Main rain-facing entrance | P0 | Blender |
| ENV-INN-COUNTER | Hero counter and shelving | P0 | Blender hero asset |
| ENV-INN-STAIRS | Stair/lodging transition | P1 | Blender |
| ENV-INN-KITCHEN | Kitchen doorway and stove glimpse | P1 | Blender |
| ENV-INN-EXTERIOR | Visible eaves and rainy street slice | P1 | Blender modular kit |

## Furniture and Props

| ID | Asset | Priority | Suggested Source |
|---|---|---:|---|
| PROP-TABLE | Square guest table set | P0 | Blender or CC0 rebuild |
| PROP-STOOL | Stool and bench variants | P0 | Blender |
| PROP-LANTERN | Hanging paper lantern | P0 | Blender |
| PROP-LEDGER | Room ledger | P0 | Blender |
| PROP-ABACUS | Working abacus hero prop | P0 | Blender |
| PROP-TEA | Teapot, cups, steam source | P0 | Blender / CC0 rebuild |
| PROP-JAR | Wine and food storage jars | P0 | Blender / Tripo blockout |
| PROP-SHELF | Storage shelf modules | P0 | Blender |
| PROP-SIGN | Inn signboard | P1 | Blender + authored texture |
| PROP-CLOTH | Counter cloth, curtains, table runner | P1 | Blender cloth bake |
| PROP-FOOD | Bowls and simple dishes | P1 | CC0 rebuild / Blender |
| PROP-TRAVEL | Packs, umbrellas, hats, crates | P1 | Tripo blockout + Blender cleanup |
| PROP-TOKEN | Half cloud-pattern bronze token | P1 | Blender hero clue |
| PROP-RAIN-GEAR | Wet capes and straw rain hats | P2 | Modular set |

## Materials

| ID | Material Family | Priority |
|---|---|---:|
| MAT-WOOD | Walnut, dark beam, wet threshold, worn counter | P0 |
| MAT-PLASTER | Warm aged wall plaster | P0 |
| MAT-PAPER | Window paper, ledger, topic slips | P0 |
| MAT-CLOTH | Hemp, cotton, rain-darkened cloth | P0 |
| MAT-CERAMIC | Glazed and unglazed pottery | P0 |
| MAT-METAL | Bronze, iron fittings, token | P1 |
| MAT-JADE | Reserved supernatural material | P2 |

## VFX and Atmosphere

| ID | Effect | Priority | Implementation |
|---|---|---:|---|
| VFX-RAIN-EXT | Exterior rainfall | P0 | TSL/GPU particles; simplified WebGL path |
| VFX-WINDOW-RAIN | Rain streak silhouettes on windows | P0 | Animated material |
| VFX-LANTERN | Lantern flame and light variation | P0 | Low-cost emissive + point-light modulation |
| VFX-TEA-STEAM | Tea and kitchen steam | P0 | Billboard particles |
| VFX-DUST | Sparse light-shaft dust | P1 | Instanced particles |
| VFX-DRIP | Eave and threshold drips | P1 | Timed particles |
| VFX-SPIRIT-JADE | Genuine cultivation anomaly language | P2 | TSL material + restrained particles |

## UI Assets

| ID | Asset | Priority |
|---|---|---:|
| UI-FRAME-DIALOGUE | Wood-and-paper dialogue frame | P0 |
| UI-TOPIC-SLIP | Quick inquiry topic slip | P0 |
| UI-QUEST-MARKER | Current objective seal | P0 |
| UI-RUMOR-STATE | Hearsay/corroborated/confirmed icon set | P1 |
| UI-RELATIONSHIP | Relationship state icon family | P1 |
| UI-CONTROLLER | Keyboard and gamepad glyph set | P1 |

## First Production Batch

The first asset batch should contain only:

1. Player base character.
2. Innkeeper Liu.
3. Shared humanoid rig and P0 animations.
4. Inn floor, wall, beam, window, entrance, and counter modules.
5. Table, stool, lantern, abacus, ledger, tea set, jar, and shelf.
6. P0 material families.
7. Rain, lantern, and tea-steam effects.
8. Dialogue frame, topic slip, and objective seal.

No P1 or P2 asset begins until this batch is assembled in Three.js and meets
the browser delivery and frame-rate budgets.
