# ADR: Private browser preview on Azure Container Apps

- Status: Accepted for private preview
- Date: 2026-10-06
- Scope: `web/`, `cloud/`, shared NPC definitions, Azure deployment tooling
- Authorization: user approved preparation and deployment to their Azure account.

## Context

The game needs animated, skinned characters and AI conversation in a vivid
cultivation-themed inn without exposing model credentials or editable assets.
Editable character and motion sources must remain outside production imports.

## Decision

Implement an independent typed Three.js/Vite client in `web/` and an isolated
FastAPI runtime in `cloud/`. Reuse the accepted final binary character assets, not
editable source. Keep Blender and motion sources outside production imports.

Keep the Innkeeper Liu registry and prompt builder in `backend/npc_roles.py` and
deterministic relationship rules in `backend/relationship_manager.py`. Cloud
sessions use those shared modules with HelloAgents core and do not include vector
storage or autonomous background generators.

Package the client and API into one nonroot container. Serve both on the same
HTTPS origin through Azure Container Apps. A managed identity has only `AcrPull`
on the dedicated private registry. Registry admin passwords are disabled.

## Trust boundary

- All pages, character assets and `/api/*` require HTTP Basic authentication.
  Username is `player`; the generated high-entropy password is an Azure secret.
- Only `GET /healthz` is public, for liveness/readiness probes.
- LLM credentials remain server-side. They are sent to ARM in memory, not
  committed, placed in a browser bundle, passed in CLI arguments or saved in
  intermediate deployment JSON.
- Chat requires the exact configured HTTPS origin and a valid authenticated
  browser request. The runtime issues Secure, HttpOnly, SameSite=Strict session
  cookies and keeps each browser's NPC history separate.
- Message length, output token count, session count, retained turns, execution
  time, concurrency and request rates are bounded. Errors return non-2xx
  responses, never fabricated NPC replies.
- A physical allowlisted build staging directory prevents uploading local
  `.env`, repository metadata, Blender sources or prototype source to ACR.

Local development is an explicit exception to the deployed transport boundary,
not a weaker production configuration. The dedicated launcher binds FastAPI to
`127.0.0.1`, accepts unauthenticated requests only from a loopback peer, and
allows state-changing requests only from the exact Vite origin
`http://127.0.0.1:5174`. It reads only the three required provider values from
the private local dotenv file. Local sessions use a non-Secure development
cookie because HTTP cannot set the production `__Host-` cookie; HttpOnly and
SameSite=Strict remain enabled. Production defaults still require HTTPS, Basic
authentication, Secure cookies and a built static client.

## Operating envelope

Use one worker, at most one Consumption replica, 0.5 vCPU and 1 GiB. Scale to zero
when idle. Local process memory holds dialogue and request budgets: they reset
on revision replacement, restart or scale-to-zero. Session history is bounded to
eight turns per NPC; idle sessions expire after 30 minutes.

The defaults allow two simultaneous generations, six calls/session/minute,
30 calls/process/minute and 500 calls/process/day, with 256 output tokens/call.
These are protective limits, **not a durable billing cap**. For broader access,
replace the shared password with per-user authentication and move budgets and
session state to a durable shared service before increasing replicas.

`/api/health` reports configured capabilities without spending an LLM request.
A live authenticated chat is required to verify actual provider connectivity.

## Alternatives

- **Publish the original prototype/backend:** rejected because it violates the
  prototype boundary and would expose unprotected AI quota/background generation.
- **Static hosting plus a separate public API:** viable later, but adds cross-origin
  auth and deployment coordination without benefiting this private preview.
- **Persistent vector memory immediately:** deferred; increases operational
  dependencies and cost beyond this deployment request.

## Consequences

The deployment has one origin, a small dependency set, explicit access control and
no periodic LLM charges. The browser still supports WebGPU with WebGL fallback.
The Azure image is built remotely because this machine has no Docker executable.
The ACR Basic registry incurs standing cost even when the app has zero replicas.
East US lacked hosting capacity during setup, so the app environment uses East
US 2; the dedicated registry remains in East US.

Automated unit and mocked browser integration tests cover motion, dialogue and
failure behavior. This is a private preview, not a declaration of public-launch
readiness, persistent save support, facial animation or mobile touch controls.
