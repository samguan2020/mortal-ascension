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
