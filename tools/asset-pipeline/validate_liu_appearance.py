# PROTOTYPE - NOT FOR PRODUCTION
# Question: Does the static appearance export satisfy its browser asset contract?
# Date: 2026-10-05

"""Validate a local Liu v2 GLB without Blender, browser, or remote APIs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct


def read_glb(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError("Truncated GLB header")
    magic, version, length = struct.unpack_from("<III", data)
    if magic != 0x46546C67 or version != 2 or length != len(data):
        raise ValueError("Invalid GLB magic, version, or declared length")
    size, kind = struct.unpack_from("<II", data, 12)
    if kind != 0x4E4F534A or size + 20 > len(data):
        raise ValueError("Invalid GLB JSON chunk")
    return json.loads(data[20:20 + size])


def validate(document: dict, byte_length: int) -> dict:
    if byte_length > 8 * 1024 * 1024:
        raise ValueError("Static character exceeds 8 MiB prototype budget")
    if document.get("animations") or document.get("skins"):
        raise ValueError("Appearance-only export must not claim animation or skinning")
    meshes = document.get("meshes", [])
    if len(meshes) != 1:
        raise ValueError("Visible static meshes must be joined for export")
    primitives = meshes[0]["primitives"]
    if not 1 <= len(primitives) <= 20:
        raise ValueError("Character exceeds 20 material primitives")
    triangles = 0
    textured = 0
    accessors = document["accessors"]
    materials = document["materials"]
    for primitive in primitives:
        if primitive.get("mode", 4) != 4:
            raise ValueError("Expected triangle geometry")
        positions = accessors[primitive["attributes"]["POSITION"]]
        if positions["count"] <= 0:
            raise ValueError("Empty geometry")
        count = accessors[primitive["indices"]]["count"] if "indices" in primitive else positions["count"]
        if count % 3:
            raise ValueError("Incomplete triangles")
        triangles += count // 3
        material = materials[primitive["material"]]
        if "baseColorTexture" in material.get("pbrMetallicRoughness", {}):
            if "TEXCOORD_0" not in primitive["attributes"]:
                raise ValueError("Textured garment has no UV coordinates")
            textured += 1
    if not 1000 <= triangles <= 100000:
        raise ValueError(f"Triangle count outside static prototype budget: {triangles}")
    images = document.get("images", [])
    if len(images) < 3 or textured < 3:
        raise ValueError("Expected three woven garment textures")
    if any("uri" in image or "bufferView" not in image for image in images):
        raise ValueError("Textures must be embedded for self-contained loading")
    return {
        "triangles": triangles,
        "material_primitives": len(primitives),
        "embedded_images": len(images),
        "textured_primitives": textured,
        "size_mib": round(byte_length / 1048576, 2),
        "animation": "none (static appearance)",
        "skinning": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glb", type=Path)
    args = parser.parse_args()
    try:
        result = validate(read_glb(args.glb), args.glb.stat().st_size)
    except (ValueError, OSError, KeyError, IndexError, TypeError) as error:
        parser.exit(1, f"Appearance validation failed: {error}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
