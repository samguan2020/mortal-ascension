# UX Spec: Project Showcase

> **Status**: Approved for Implementation
> **Author**: User + UX Designer
> **Last Updated**: 2026-10-06
> **Journey Phase(s)**: Project Discovery, Technical Evaluation
> **Template**: UX Spec

---

## Purpose & Player Need

The showcase introduces Mortal Ascension to prospective players, collaborators,
and technical reviewers. A visitor arrives wanting to understand what the game
feels like, see it running, and learn what makes its AI-driven NPC interaction
different from a stateless chatbot.

The page must communicate the playable experience before implementation detail.
It should then explain the three key AI features and the full stack without
requiring the visitor to read the repository documentation.

---

## Player Context on Arrival

Visitors may arrive from the GitHub repository, a shared Pages link, or a
portfolio. They are assumed to be curious but unfamiliar with the project. The
page should establish the cultivation setting and working demo within the first
viewport, then support deeper technical evaluation below.

---

## Navigation Position

```text
External link or repository
  -> Project Showcase
      |-- Watch demo
      |-- Explore AI features
      |-- Review architecture and stack
      `-- View source on GitHub
```

The showcase is independent from the protected playable client and does not
load game runtime code or contact the AI backend.

---

## Entry & Exit Points

| Entry Source | Trigger | Visitor Context |
|---|---|---|
| GitHub repository | Showcase link | Technical or project interest |
| Shared Pages URL | Direct navigation | General discovery |
| Portfolio | Project link | Comparative evaluation |

| Exit Destination | Trigger | Notes |
|---|---|---|
| GitHub repository | View Source link | Opens in the same tab |
| README | Run Locally link | Opens source documentation |
| External page | Browser navigation | No state is persisted |

---

## Layout Specification

### Information Hierarchy

1. Project identity and playable premise.
2. Real demo video.
3. Session memory, hidden affinity, and recoverable dialogue log.
4. End-to-end architecture flow.
5. Complete technology stack.
6. Source and local-run calls to action.

### Layout Zones

- Sticky compact navigation with section links and a source action.
- Cinematic two-column hero with project statement and technical proof points.
- Wide 16:9 demo stage immediately below the hero.
- Three equal feature cards with player value and implementation boundary.
- Horizontal architecture flow that wraps into a vertical flow on narrow screens.
- Five-category technology grid.
- Closing source and local-run call to action.

### Component Inventory

| Zone | Component | Interactive | Notes |
|---|---|---:|---|
| Navigation | Anchor links | Yes | Keyboard focus remains visible |
| Hero | Primary and secondary actions | Yes | No animated background |
| Demo | Native HTML video | Yes | Controls enabled; no autoplay |
| AI features | Three semantic articles | No | Numbered with text, not color alone |
| Architecture | Ordered process diagram | No | Preserves reading order |
| Technology | Category cards | No | Full names accompany abbreviations |
| Closing | Source and README links | Yes | Clear destination labels |

### ASCII Wireframe

```text
+---------------------------------------------------------------+
| BRAND          AI FEATURES  TECH STACK            VIEW SOURCE |
+---------------------------------------------------------------+
| PROJECT STATEMENT                 | RUNTIME PROOF POINTS       |
| [WATCH DEMO] [VIEW SOURCE]        | 8 TURNS / 30 MIN / 0 CALLS |
+---------------------------------------------------------------+
|                       DEMO VIDEO                            |
+---------------------------------------------------------------+
| SESSION MEMORY | HIDDEN AFFINITY | RECOVERABLE DIALOGUE LOG |
+---------------------------------------------------------------+
| BROWSER -> GAME CLIENT -> API -> AGENT -> MODEL PROVIDER      |
|                    EPHEMERAL SESSION STATE                    |
+---------------------------------------------------------------+
| FRONTEND | RENDERING | AI/RUNTIME | SECURITY | DELIVERY      |
+---------------------------------------------------------------+
| EXPLORE SOURCE                         RUN LOCALLY             |
+---------------------------------------------------------------+
```

---

## States & Variants

| State / Variant | Trigger | What Changes |
|---|---|---|
| Default | Page loads | Hero, video metadata, and content display |
| Video loading | Visitor presses play | Native browser loading feedback |
| Video unavailable | Media cannot load | Download link remains available |
| Narrow viewport | Width below 760 px | Columns stack and architecture becomes vertical |
| Reduced motion | OS preference enabled | Smooth scrolling and decorative transitions are disabled |

---

## Interaction Map

| Action | Input | Immediate Feedback | Outcome |
|---|---|---|---|
| Navigate to section | Click, Enter, Space | Visible focus and anchor movement | Requested section is focused visually |
| Play or seek demo | Native video controls | Browser-native state feedback | Local video playback |
| View source | Click or keyboard activation | Link state and focus | Opens GitHub repository |
| Run locally | Click or keyboard activation | Link state and focus | Opens README instructions |

---

## Events Fired

No analytics or game-state events are fired. The page is static and contains no
tracking scripts.

---

## Transitions & Animations

Section links use native smooth scrolling when motion is allowed. Feature cards
may use a short border and shadow transition on hover. Reduced-motion mode
removes smooth scrolling and all nonessential transitions.

---

## Data Requirements

| Data | Source | Read / Write | Notes |
|---|---|---|---|
| Project copy | Static HTML | Read | No runtime fetch |
| Demo video | Local MP4 asset | Read | Preload metadata only |
| Source links | Static URLs | Read | Public repository |
| AI feature details | Current runtime documentation | Read | Must match implementation |

---

## Accessibility

- Semantic landmarks and heading order support screen-reader navigation.
- Every interactive element is keyboard reachable with a visible focus ring.
- Text and controls target WCAG 2.2 AA contrast.
- Meaning is never communicated through color alone.
- Body text remains at least 16 px, with long-form copy near 18 px.
- Native video controls are retained; video does not autoplay.
- Reduced-motion preferences disable smooth scrolling and decorative transitions.

---

## Localization Considerations

The initial showcase is English. Tingyu Inn and Innkeeper Liu remain proper
names. Cards and navigation permit wrapping and tolerate at least 40% text
expansion. No layout-critical text is embedded in images.

---

## Acceptance Criteria

- [ ] The page displays its hero and video frame without loading game runtime code.
- [ ] The demo requires an explicit play action and exposes native playback controls.
- [ ] All three AI features state both player value and implementation boundary.
- [ ] The architecture and technology sections cover the browser, rendering, API,
      agent, provider, state, security, testing, and deployment layers.
- [ ] Navigation and calls to action work using keyboard-only input with visible focus.
- [ ] At 360 px width, content remains readable without horizontal page scrolling.
- [ ] Reduced-motion mode disables smooth scrolling and decorative transitions.
- [ ] Missing video playback does not prevent access to the page or source links.
- [ ] GitHub Pages publishes only the contents of `showcase/`.

---

## Open Questions

- A formal player journey map has not been created.
- A project-wide accessibility tier has not been defined; this page adopts
  WCAG 2.2 AA as its implementation baseline.
