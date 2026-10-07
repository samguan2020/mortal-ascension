# UX Spec: Browser Experience Framework

> **Status**: In Design
> **Author**: User + UX Designer
> **Last Updated**: 2026-10-04
> **Journey Phase(s)**: First Launch, World Exploration, NPC Interaction, AI Observation, Settings
> **Template**: UX Spec

---

## Purpose & Player Need

The browser experience invites players into the warm, miniature Tingyu Inn where
residents have distinct personalities, memories, and relationship states.
Through ongoing conversations, the player builds relationships that feel
personal and continuous. The player arrives wanting to discover whether the
residents remember them and how those relationships will develop, rather than
to operate a generic chat tool or debugging dashboard.

The interface must protect the continuity of the relationship experience.
Each NPC's identity, mood, current activity, familiarity with the player, and
shared history should emerge naturally through world presentation and
conversation. The AI insight layer explains memory, goals, and generation
status only when the player chooses to reveal it.

AI replies, TTS narration, music, image, and video generation must not block
movement, observation, or unrelated interactions for extended periods. Every
high-latency generation flow must acknowledge the request immediately, keep
the world active, provide progressive status feedback, allow the player to
leave, and notify them through an in-world cue when the result is ready.
Failures must preserve the current experience and offer a clear recovery
action rather than trapping the player in a waiting state.

Design principles:

- Relationships take priority over technology demonstrations.
- NPCs must feel like residents living in the world, not stationary chat entry points.
- The AI insight layer builds understanding and trust but remains opt-in.
- AI generation must never freeze the core world experience.
- Multimedia generation must serve a relationship or world event rather than appear as a disconnected tool.

---

## Player Context on Arrival

Players arrive in a low-pressure state of warm curiosity. They want to see
what the town looks like today, what its residents are doing, and whether a
familiar NPC remembers their previous interactions. Entering the experience
should feel like approaching a place that continues to exist, not like
starting an AI tool.

### First Visit

- Present a brief world-waking sequence using a town vista, ambient sound, and light narrative framing.
- Detect WebGPU support during the sequence and automatically select the WebGL fallback when required.
- Preload the core scene, first-visible NPCs, essential animation, and interface assets in parallel.
- Check dialogue, memory, TTS, and generation service availability without exposing technical logs.
- Move into the town through a continuous camera transition as soon as the minimum playable set is ready; stream secondary assets in the background.
- Show a concise, actionable message only when a missing capability materially affects play.

### Return Visit

- Restore the player's last position, most recent conversation partner, and relationship context first.
- Use only a short world-waking animation to cover synchronization and first-frame preparation.
- Allow the animation to be skipped when restoration is already complete.
- Let an NPC acknowledge the returning player through movement, eye contact, or a short greeting without forcing dialogue open.
- Connect slower AI and multimedia services in the background instead of delaying world entry.

### Intended Emotional State

- Warm rather than technically cold.
- Curious rather than task-pressured.
- Increasingly familiar across visits, so returning feels like coming back to see the residents.
- Loading, capability checks, and degradation should be expressed through world presentation whenever practical.

---

## Navigation Position

The browser experience uses world-centered navigation. The town is both the
home destination and the persistent navigation root. Once the player reaches
the interactive world, dialogue, Agent observation, and settings do not
require leaving it.

```text
Browser Entry
  -> World Wake / Capability Check
  -> Tingyu Inn
      |-- Nearby NPC -> Dialogue Overlay
      |-- Insight Toggle -> AI Insight Layer
      |-- Resident Focus -> Relationship and Memory Summary
      |-- Generation Notice -> Result Preview Overlay
      `-- Escape / Menu Button -> Settings and Session Menu
```

Navigation constraints:

- The world remains the visual and stateful foundation; full-page routes must not unload it.
- The dialogue overlay keeps the NPC and surrounding scene visible so conversation remains spatial.
- The AI insight layer is a world display mode, not a separate administration dashboard.
- Settings appear as a pause-style overlay. If continuous or multiplayer simulation is added later, the overlay may suspend local input but must not assume the world has stopped.
- Resident memory and relationship information begins as a compact summary and may expand on demand without losing world context.
- TTS, music, image, and video results enter through non-blocking notifications and never take focus automatically.
- Mobile devices that do not meet the desktop play target receive a compatibility layer with basic project information instead of entering the full interactive world.
- Browser Back closes the topmost overlay first. With no overlay open, it requests confirmation before leaving the session.

---

## Entry & Exit Points

[To be designed]

---

## Layout Specification

### Information Hierarchy

[To be designed]

### Layout Zones

[To be designed]

### Component Inventory

[To be designed]

### ASCII Wireframe

[To be designed]

---

## States & Variants

[To be designed]

---

## Interaction Map

[To be designed]

---

## Events Fired

[To be designed]

---

## Transitions & Animations

[To be designed]

---

## Data Requirements

[To be designed]

---

## Accessibility

[To be designed]

---

## Localization Considerations

[To be designed]

---

## Acceptance Criteria

[To be designed]

---

## Open Questions

[To be designed]
