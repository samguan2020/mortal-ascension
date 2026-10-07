# Editable Asset Sources

Runtime character assets live in `web/public/characters/`. This directory keeps
the editable sources required to revise or rebuild them:

- `source/characters/`: Blender appearance and rig files.
- `source/motions/`: reusable source animation GLBs.

Offline builders and validators live in `tools/asset-pipeline/`. These files are
not copied into the browser bundle or cloud container.

Asset generation can invoke external or paid services. Do not run generation
tools without explicit approval, and keep tool credentials in
`assets/source/.env`, which is gitignored by the repository-wide `.env` rule.
