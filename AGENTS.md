# Mortal Ascension - Shared Project Instructions

This is the standalone cultivation game at `D:\Repos\mortal-ascension`.
It is not the studio template and is no longer a submodule. Do not select another
game or copy unconfigured studio defaults over this project's settings.

## Active project surfaces

- `web/`: current Three.js / TypeScript / Vite browser client.
- `cloud/`: protected FastAPI / HelloAgents runtime for the browser client.
- `backend/`: shared NPC prompt and deterministic affinity rules only.
- `assets/source/`: editable character and motion sources.
- `tools/asset-pipeline/`: character generation and validation tools.

**Mortal Ascension** is the project name. **Tingyu Inn** remains the
opening location. Keep NPC personalities and Chinese dialogue intact unless a
design change is requested. Existing Azure names are compatibility identifiers,
not instructions to provision another deployment.

## Assistant runtime

- GitHub Copilot: read [.github/copilot-instructions.md](.github/copilot-instructions.md).
  The 49 roles and 73 skills live locally under `.github/`.
- Read referenced documents explicitly; `@file` is not a Copilot import.

## Standards and approvals

Read the relevant context and applicable `.github/instructions/` rules before edits:

- [Technical preferences](.github/docs/technical-preferences.md)
- [Directory layout](.github/docs/directory-structure.md)
- [Coding standards](.github/docs/coding-standards.md)
- [Coordination](.github/docs/coordination-rules.md)
- [Collaborative design](docs/COLLABORATIVE-DESIGN-PRINCIPLE.md)
- [Private browser boundary](docs/architecture/adr-private-browser-preview.md)

Preserve Question -> Options -> Decision -> Draft -> Approval. Show the affected
paths and obtain approval before writes. Never commit, push, deploy, delete
resources or generate paid assets without user authorization.

Keep editable asset source out of production imports. Preserve accepted binary
art and editable sources. Do not copy virtualenvs or generated caches between checkouts.
Never expose `.env` values, credentials or authenticated cloud secret output.

## Validation

Use [README.md](README.md) for installation and exact commands.
Run the smallest tests/builds relevant to the changed surface. Browser UI changes
need screenshots or a walkthrough; mock AI except for explicitly approved live
verification. Stop temporary servers after verification.

The repository currently has no configured Git remote.
