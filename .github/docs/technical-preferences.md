# Technical Preferences

## Current Browser Game

- **Project**: Mortal Ascension, standalone at `D:\Repos\mortal-ascension`
- **Client**: `web/`, Three.js 0.180, TypeScript 5.9, Vite 7, Node.js 24
- **Rendering**: WebGPU with WebGL 2 fallback
- **Runtime**: `cloud/`, FastAPI + HelloAgents, same-origin protected API
- **Shared Python**: `backend/npc_roles.py` and
  `backend/relationship_manager.py`
- **Asset Sources**: `assets/source/`; runtime uses only final assets copied to
  `web/public/characters/`
- **Validation**: Node tests, TypeScript/Vite build, network-free Python tests,
  deployment-tool tests and mocked Playwright walkthrough

## Input and Platform

- **Target**: Desktop browser
- **Primary Input**: Keyboard and mouse
- **Additional Input**: Gamepad
- **Touch**: Not supported
- **Target Framerate**: 60 fps
- **Frame Budget**: 16.6 ms

## Naming

- TypeScript classes and types: PascalCase
- TypeScript functions and variables: camelCase
- Python classes: PascalCase
- Python functions and variables: snake_case
- Constants: UPPER_SNAKE_CASE
- Files: existing surface convention (`main.ts`, `test_server.py`)

## Security and Runtime Boundaries

- Model credentials remain server-side.
- Browser and API share one authenticated HTTPS origin.
- Sessions, dialogue logs and affinity are ephemeral and bounded.
- Provider calls are mocked in automated tests.
- Editable assets and asset-generation tools are never production imports.
- No prototype, vector database or autonomous NPC runtime is supported.

## File Routing

| File type | Reviewer |
|---|---|
| TypeScript / Three.js | General web or gameplay programmer |
| FastAPI / Python | General-purpose Python reviewer |
| Browser UI / CSS | UI programmer or UX reviewer |
| Blender / GLB pipeline | Technical artist |
| Deployment / CI | DevOps engineer |
