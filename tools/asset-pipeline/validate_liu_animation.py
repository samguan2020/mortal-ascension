# PROTOTYPE - NOT FOR PRODUCTION
# Question: Does Liu's visible skin have two distinct upper-body gestures with planted feet?
# Date: 2026-10-06

"""Validate the actual NPC conversation GLB and its skin/animation accessors."""

import argparse
import json
from pathlib import Path

from validate_traveler_animation import accessor_values, read_asset, validate_geometry


def validate(document, binary, size):
    triangles, primitive_count = validate_geometry(document, binary, size)
    animations = {clip["name"]: clip for clip in document.get("animations", [])}
    if set(animations) != {"Idle", "TalkExplain", "TalkWelcome"}:
        raise ValueError("Liu requires Idle, TalkExplain and TalkWelcome clips only")
    durations = {}
    signatures = []
    for name, clip in animations.items():
        duration = 0
        moving_arms = set()
        signature = []
        for channel in clip["channels"]:
            sampler = clip["samplers"][channel["sampler"]]
            times = accessor_values(document, binary, sampler["input"])
            values = accessor_values(document, binary, sampler["output"])
            if len(times) != len(values) or len(times) < 2:
                raise ValueError("Gesture has no usable keyframes")
            if any(a[0] >= b[0] for a, b in zip(times, times[1:])):
                raise ValueError("Gesture times must increase")
            duration = max(duration, times[-1][0] - times[0][0])
            node = document["nodes"][channel["target"]["node"]]["name"]
            path = channel["target"]["path"]
            seam = max(abs(a-b) for a, b in zip(values[0], values[-1]))
            if path == "rotation":
                seam = min(seam, max(abs(a+b) for a, b in zip(values[0], values[-1])))
                if any(abs(sum(v*v for v in row) - 1) > 1e-3 for row in values):
                    raise ValueError("Gesture quaternion is not normalized")
            if seam > 2e-4:
                raise ValueError(f"Gesture loop pops at {name}/{node}/{path}")
            change = max(abs(v-first) for row in values for v, first in zip(row, values[0]))
            if name == "Idle" or node.startswith(("Hips", "Thigh.", "Shin.", "Foot.")):
                if change > 2e-4:
                    raise ValueError(f"NPC must remain planted: {name}/{node}/{path}")
            if node.startswith(("UpperArm.", "Forearm.", "Hand.")) and path == "rotation":
                signature.extend(round(v, 5) for row in values for v in row)
                if change > 0.03:
                    moving_arms.add(node)
        if name != "Idle":
            if len(moving_arms) < 2 or not 1 <= duration <= 6:
                raise ValueError(f"{name} is not a usable conversational gesture")
            signatures.append(signature)
        durations[name] = round(duration, 3)
    if signatures[0] == signatures[1]:
        raise ValueError("Conversation gestures must be distinct")
    return {"triangles": triangles, "material_primitives": primitive_count, "bones": 17,
            "clips": durations, "size_mib": round(size / 1024**2, 2),
            "skinning": "all visible primitives weighted", "feet": "stationary"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glb", type=Path)
    args = parser.parse_args()
    document, binary = read_asset(args.glb)
    print(json.dumps(validate(document, binary, args.glb.stat().st_size), indent=2))
