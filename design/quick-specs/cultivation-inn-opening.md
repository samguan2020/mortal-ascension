# Quick Design Spec: Tingyu Inn Opening

> **Status**: Prototype Validated
> **Date**: 2026-10-04
> **Scope**: First playable location

## Premise

The player begins as an ordinary traveler with no cultivation knowledge. A
rainstorm brings them to Tingyu Inn in Qingshi Town, where merchants,
storytellers, wanderers, and occasional cultivators exchange incomplete and
contradictory information.

The player's first goal is not to gain power immediately. It is to learn that
cultivation is real, discover one plausible path toward it, and decide which
rumor is worth pursuing.

## Tone

Classical low fantasy. Immortal cultivators exist but are rarely seen by
ordinary people. Genuine opportunities, misunderstandings, superstition, and
fraud coexist. NPCs distinguish personal observation from reliable reports and
hearsay.

## First NPC: Innkeeper Liu

- **Role**: Keeper of Tingyu Inn.
- **Public manner**: Polite, cautious, worldly, and reluctant to guarantee any rumor.
- **Knowledge**: Local roads, travelers, nearby sect rumors, unusual incidents.
- **Conversation rule**: Reveal at most one or two new clues per reply and invite follow-up.
- **AI behavior**: Maintain character, remember prior conversations when memory service is available, and adapt affinity through the existing relationship system.

## Initial Inquiry Paths

1. **How to Cultivate** — Learn about spiritual roots and the difficulty of entering the immortal path.
2. **Nearby Sects** — Hear that cultivators test spiritual roots near Qixia Mountain around the spring equinox.
3. **Wandering Tales** — Hear uncertain stories about blue light at the northern ruined temple or a wounded woman carrying a cloud-patterned bronze token.

## Seed Clues

- Qixia Mountain lies thirty li east of town.
- Cultivators are rumored to test young people's spiritual roots at its foot around the spring equinox.
- Blue light has appeared around the northern ruined temple; explanations range from a sword immortal's relic to a mountain demon.
- A wounded woman in green stayed in room Tian-2 three days ago and left half of a cloud-patterned bronze token.

No clue is automatically confirmed as truth. Later locations and NPCs determine
which reports are accurate.

## MVP Acceptance Criteria

- [x] The first location visually reads as an inn rather than an office.
- [x] The player can move through the inn and approach the keeper.
- [x] The dialogue UI offers the three initial inquiry paths.
- [x] The keeper responds through the live AI Agent rather than a fixed dialogue tree.
- [x] The response stays in the cultivation setting and supplies a follow-up hook.
- [x] The world remains interactive while the AI request is pending.
- [ ] NPC memory persists once Qdrant connectivity is restored.
