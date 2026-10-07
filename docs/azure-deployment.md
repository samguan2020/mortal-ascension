# Mortal Ascension: Private Azure Preview

The project is located at `D:\Repos\mortal-ascension`. The Azure resources below
belong to the existing private preview. Local renaming and repository cleanup did
not redeploy, disable, or rename those resources. The hosted page will retain its
current deployed version until a new deployment is explicitly approved.

## Components and Boundaries

- [web/](../web/) is the independent Three.js, TypeScript, and Vite browser
  client. It prefers WebGPU and falls back to WebGL through Three.js.
- [cloud/](../cloud/) is the reduced FastAPI and HelloAgents runtime that serves
  the page and AI dialogue.
- [deploy_azure.py](../tools/deploy_azure.py) packages only allowlisted files,
  starts an ACR remote build, and injects server secrets through in-memory ARM
  HTTPS requests.
- [Private browser preview ADR](architecture/adr-private-browser-preview.md)
  defines authentication, resource, and session boundaries.

Editable asset sources and offline generation tools are not production
dependencies. The deployment reuses only the two approved final skinned GLB
files. Model-provider credentials are never included in the browser.

## Existing Resources

| Item | Value |
|---|---|
| Subscription | Visual Studio Enterprise Subscription |
| Subscription ID | `fd6715f9-cb85-43c6-ae95-7a01434bb7d6` |
| Resource group | `rg-ai-town` |
| App | `tingyu-inn` |
| Environment | `ai-town-env-eastus2` / East US 2 |
| Registry | `aitownfd6715.azurecr.io` / East US / Basic |
| Pull identity | `ai-town-image-pull`, with `AcrPull` on this registry only |
| Replicas | 0-1, Consumption |
| Container | 0.5 vCPU / 1 GiB, non-root, one worker |
| Ingress | HTTPS, target port 8000 |
| Log Analytics | No new workspace |

Creating the environment in East US returned `AKSCapacityHeavyUsage`, so the
preview uses East US 2. Do not modify resource groups belonging to other games.

## Access

URL:
<https://tingyu-inn.victoriousground-3395f0d2.eastus2.azurecontainerapps.io>

The browser displays an authentication prompt:

- Username: `player`
- Password: the Container App `site-password` secret.

On a local machine with an authenticated Azure CLI session, the following
command copies the password to the clipboard without writing it to a file or
printing it directly:

```powershell
az containerapp secret list `
  --name tingyu-inn `
  --resource-group rg-ai-town `
  --subscription fd6715f9-cb85-43c6-ae95-7a01434bb7d6 `
  --show-values `
  --query "[?name=='site-password'].value | [0]" --output tsv |
  Set-Clipboard
```

The secret can also be viewed in Azure Portal under Container App > Secrets.
Never paste the password or `llm-api-key` into chat, screenshots, source code,
issues, or logs. Browsers may cache Basic credentials; close all private windows
before leaving a shared machine. Future deployments preserve the existing site
password instead of rotating it silently.

The first visit may wait for a cold start. After the character assets load, use
WASD, arrow keys, or the gamepad left stick to move. Approach Innkeeper Liu and
press E or gamepad A to speak; use Escape or gamepad B to return. The current
client does not provide a mobile virtual stick.

## Security and Usage Limits

- The page, models, and `/api/*` require authentication. Only `/healthz` is an
  anonymous liveness endpoint.
- `POST /api/chat` enforces the configured origin and a 500-character input
  limit.
- Each browser is isolated through a secure `HttpOnly` session cookie.
- At most 2 generations run concurrently. Limits are 6 requests per session per
  minute, 30 requests per process per minute, and 500 requests per process per
  day. Each response is capped at 256 output tokens.
- Each NPC retains at most 8 dialogue turns and expires after 30 minutes idle.
- The application returns an error after a 25-second wait; provider requests
  default to a 20-second timeout. The frontend timeout is 40 seconds and never
  fabricates a successful reply.
- A restart, update, or scale-to-zero clears sessions and rate counters. This is
  **not persistent storage or an unbypassable daily spending limit**.
- There is no ambient generation, scheduled NPC model traffic, Qdrant, or Torch
  service.
- `/api/health` validates configuration but does not prove that the provider has
  completed a successful model request.

## Updating the Deployment

Run from the repository root. Azure CLI must already be authenticated, and the
operator must have permission to update the Container App and run ACR builds in
the existing environment and registry.

```powershell
Set-Location D:\Repos\mortal-ascension
.\.venv\Scripts\python.exe tools\deploy_azure.py `
  --subscription fd6715f9-cb85-43c6-ae95-7a01434bb7d6
```

The tool reads only `LLM_API_KEY`, `LLM_MODEL_ID`, and `LLM_BASE_URL` from the
local `backend/.env`; it never uploads that file. The URL must use HTTPS. The
build context is created from an explicit allowlist and deleted after success or
failure. Image tags contain UTC timestamps for version tracing.

To reuse a verified image, such as for an application-code rollback:

```powershell
.\.venv\Scripts\python.exe tools\deploy_azure.py `
  --subscription fd6715f9-cb85-43c6-ae95-7a01434bb7d6 `
  --image tingyu-inn:<verified-image-tag>
```

This reinjects the current local model configuration; it does not restore a full
snapshot of older secrets. Never replace the image tag with an unreviewed
third-party image.

## Local Validation

```powershell
Set-Location D:\Repos\mortal-ascension
.\.venv\Scripts\python.exe -m unittest `
  cloud.test_relationship_manager `
  cloud.test_server `
  tools.test_deploy_azure -v

Push-Location web
npm ci
npm test
npm run build
npm run dev -- --port 5174 --strictPort
```

In another terminal, run the browser test from the repository root. Python
Playwright and Chromium must already be installed. The test intercepts API
requests and **does not incur model charges**.

```powershell
python web\test_browser.py --base-url http://127.0.0.1:5174
```

The Vite development server has no cloud authentication and does not proxy a
local API. It is only for isolated UI development and mocked validation. The
complete private runtime serves the built `web/dist`. Production acceptance must
use HTTPS because the secure cloud cookie is not equivalent over local HTTP.

## Recorded Deployment Validation

On 2026-10-06:

- Image `aitownfd6715.azurecr.io/tingyu-inn:20261006-055209` and ready revision
  `tingyu-inn--14nxt9f` completed remote build and deployment successfully.
- Network-free cloud and deployment tests passed.
- Web tests, TypeScript checks, and the Vite production build passed. The
  Three.js bundle exceeded Vite's 500 kB advisory threshold; this was a warning,
  not a failure.
- The mocked browser walkthrough passed keyboard movement, Idle/Walk switching,
  both speaking gestures, dialogue close/timeout behavior, error UI, responsive
  framing, and visible skinned-hand deformation.
- Anonymous access to the hosted page, API, and models returned 401; the health
  probe returned 200; foreign-origin chat returned 403; environment-file paths
  returned 404. Both hosted GLB files matched the approved local SHA-256 values.
- One explicitly approved live conversation returned a valid response. Secure
  session-cookie flags were correct and the browser reported no JavaScript
  errors. The automated renderer used the WebGL fallback, so this was not treated
  as WebGPU hardware acceptance.
- The empty environment created during the initial capacity failure was removed.
  No Azure resources belonging to other games were changed.

Rerun hosted checks without sending a real model request:

```powershell
python -m tools.verify_azure `
  --subscription fd6715f9-cb85-43c6-ae95-7a01434bb7d6 `
  --origin https://tingyu-inn.victoriousground-3395f0d2.eastus2.azurecontainerapps.io
```

Only `--live-chat` sends one real question and validates its reply. It requires
an authenticated Azure CLI session, Python Playwright/Chromium, and
python-dotenv. The site password is read in memory and is never printed or
written.

## Cost and Shutdown

- Container Apps bill for actual usage and scale to zero when idle; cold starts
  are the corresponding tradeoff.
- **ACR Basic has a fixed cost even when nobody visits the game.** Image storage,
  builds, bandwidth, and the configured model provider may also incur charges.
  No fixed monthly cost or free operation is promised.
- No additional Log Analytics workspace was created, so do not rely on
  long-term platform log retention.
- Create a budget alert for `rg-ai-town` in Azure Cost Management. Budget alerts
  generally do not enforce a hard automatic shutdown.
- Pausing the app does not eliminate ACR charges. When the private preview is no
  longer needed, the dedicated `rg-ai-town` resource group may be deleted in
  Azure Portal; this also deletes its images and related resources. Confirm that
  no additional workloads were added before deletion.

Do not automatically delete cloud resources, rotate secrets, commit code, or
push the repository.
