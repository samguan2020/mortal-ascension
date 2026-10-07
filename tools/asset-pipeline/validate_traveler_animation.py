# PROTOTYPE - NOT FOR PRODUCTION
# Question: Does the actual player GLB contain normalized skinning and a looping walk?
# Date: 2026-10-06

"""Validate exported GLB binary data, not just the presence of a skin definition."""

import argparse
import json
import math
from pathlib import Path
import struct

from validate_liu_appearance import read_glb


def read_asset(path):
    document = read_glb(path)
    data = path.read_bytes()
    json_size = struct.unpack_from("<I", data, 12)[0]
    offset = 20 + json_size
    binary_size, chunk_type = struct.unpack_from("<II", data, offset)
    if chunk_type != 0x004E4942:
        raise ValueError("GLB has no binary chunk")
    binary = data[offset + 8:offset + 8 + binary_size]
    if len(binary) != binary_size:
        raise ValueError("GLB binary chunk is truncated")
    return document, binary


def accessor_values(document, binary, index):
    accessor = document["accessors"][index]
    if "sparse" in accessor:
        raise ValueError("Sparse accessors are not supported by this asset contract")
    view = document["bufferViews"][accessor["bufferView"]]
    components = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[accessor["type"]]
    code = {5121: "B", 5123: "H", 5125: "I", 5126: "f"}[accessor["componentType"]]
    format_ = "<" + code * components
    size = struct.calcsize(format_)
    stride = view.get("byteStride", size)
    offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    values = [struct.unpack_from(format_, binary, offset + stride * row)
              for row in range(accessor["count"])]
    if not all(math.isfinite(v) for row in values for v in row):
        raise ValueError("Non-finite accessor values")
    return values


def validate_skin_rows(weights, joints, joint_count):
    if not weights or len(weights) != len(joints):
        raise ValueError("Skin attribute counts do not match")
    for weight_row, joint_row in zip(weights, joints):
        if len(weight_row) != 4 or len(joint_row) != 4:
            raise ValueError("Expected four skin influences")
        if not all(math.isfinite(w) and 0 <= w <= 1 for w in weight_row):
            raise ValueError("Skin weight outside [0,1]")
        if abs(sum(weight_row) - 1) > 1e-4:
            raise ValueError("Skin weights are not normalized")
        if not all(isinstance(j, int) and 0 <= j < joint_count for j in joint_row):
            raise ValueError("Skin joint index is out of range")


def validate_geometry(document, binary, size):
    if size > 8 * 1024 * 1024:
        raise ValueError("Animated character exceeds 8 MiB")
    skins = document.get("skins", [])
    if len(skins) != 1 or len(skins[0]["joints"]) != 17:
        raise ValueError("Expected one fitted 17-bone character skin")
    skinned_nodes = [node for node in document["nodes"] if "mesh" in node and "skin" in node]
    if len(skinned_nodes) != 1 or skinned_nodes[0]["skin"] != 0 or len(document["meshes"]) != 1:
        raise ValueError("The visible player mesh must be skinned")
    primitives = document["meshes"][0]["primitives"]
    triangles = 0
    for primitive in primitives:
        attributes = primitive["attributes"]
        if not {"POSITION", "JOINTS_0", "WEIGHTS_0", "TEXCOORD_0"} <= attributes.keys():
            raise ValueError("Every visible material primitive must have skin weights and UVs")
        weights = accessor_values(document, binary, attributes["WEIGHTS_0"])
        joints = accessor_values(document, binary, attributes["JOINTS_0"])
        positions = accessor_values(document, binary, attributes["POSITION"])
        if len(positions) != len(weights):
            raise ValueError("Some visible vertices have no weights")
        validate_skin_rows(weights, joints, len(skins[0]["joints"]))
        triangles += document["accessors"][primitive["indices"]]["count"] // 3
    if not 1000 <= triangles <= 100000 or len(primitives) > 20:
        raise ValueError("Animated geometry exceeds the appearance budget")
    images = document.get("images", [])
    if len(images) < 3 or any("bufferView" not in image for image in images):
        raise ValueError("Missing embedded garment textures")
    return triangles, len(primitives)


def validate(document, binary, size):
    triangles, primitive_count = validate_geometry(document, binary, size)
    animations = {clip["name"]: clip for clip in document.get("animations", [])}
    if set(animations) != {"Idle", "Walk"}:
        raise ValueError("Expected only the player's Idle and Walk clips")
    duration = 0
    animated_legs = set()
    for name, animation in animations.items():
        for channel in animation["channels"]:
            sampler = animation["samplers"][channel["sampler"]]
            times = accessor_values(document, binary, sampler["input"])
            values = accessor_values(document, binary, sampler["output"])
            if len(times) != len(values) or len(times) < 2:
                raise ValueError("Animation sampler has no usable keyframes")
            if any(a[0] >= b[0] for a, b in zip(times, times[1:])):
                raise ValueError("Animation keyframe times must increase")
            node = document["nodes"][channel["target"]["node"]]["name"]
            path = channel["target"]["path"]
            seam = max(abs(a - b) for a, b in zip(values[0], values[-1]))
            if path == "rotation":
                seam = min(seam, max(abs(a + b) for a, b in zip(values[0], values[-1])))
                if any(abs(sum(v*v for v in row) - 1) > 1e-3 for row in values):
                    raise ValueError("Animation quaternion is not normalized")
            if seam > 2e-4:
                raise ValueError(f"{name} has a discontinuous loop at {node}")
            change = max(abs(value - initial) for row in values for value, initial in zip(row, values[0]))
            if name == "Idle" and change > 2e-4:
                raise ValueError("Idle must remain a stable standing pose")
            if name == "Walk":
                duration = max(duration, times[-1][0] - times[0][0])
                if node in ("Thigh.L", "Thigh.R", "Shin.L", "Shin.R") and path == "rotation" and change > 0.1:
                    animated_legs.add(node)
                if node == "Hips" and path == "translation":
                    if any(abs(row[i] - values[0][i]) > 1e-4 for row in values for i in (0, 2)):
                        raise ValueError("Walk must not translate the character horizontally")
    if len(animated_legs) != 4 or not 0.6 <= duration <= 2:
        raise ValueError("Walk requires both knees and thighs moving through a full stride")
    return {"triangles": triangles, "material_primitives": primitive_count, "bones": 17,
            "clips": sorted(animations), "walk_seconds": round(duration, 3),
            "size_mib": round(size / 1024**2, 2), "skinning": "all visible primitives weighted",
            "loop": "continuous endpoints; no horizontal root motion"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glb", type=Path)
    args = parser.parse_args()
    document, binary = read_asset(args.glb)
    print(json.dumps(validate(document, binary, args.glb.stat().st_size), indent=2))
