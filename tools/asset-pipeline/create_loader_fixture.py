# PROTOTYPE - NOT FOR PRODUCTION
# Question: Can Three.js replace the fallback NPC with an animated GLB?
# Date: 2026-10-05

"""Create a tiny animated humanoid-shaped GLB for loader validation only."""

import argparse
from pathlib import Path

import bpy


def add_part(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> None:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, location=location)
    part = bpy.context.object
    part.name = name
    part.scale = scale
    part.data.materials.append(material)
    part.parent = parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(__import__("sys").argv[__import__("sys").argv.index("--") + 1 :])

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    root = bpy.data.objects.new("LoaderFixtureRoot", None)
    bpy.context.collection.objects.link(root)

    robe = bpy.data.materials.new("Robe")
    robe.diffuse_color = (0.24, 0.32, 0.26, 1.0)
    skin = bpy.data.materials.new("Skin")
    skin.diffuse_color = (0.55, 0.34, 0.24, 1.0)
    hair = bpy.data.materials.new("Hair")
    hair.diffuse_color = (0.025, 0.018, 0.015, 1.0)

    add_part("Torso", (0, 0, 1.35), (0.42, 0.25, 0.66), robe, root)
    add_part("Head", (0, 0, 2.15), (0.28, 0.25, 0.34), skin, root)
    add_part("Hair", (0, 0, 2.35), (0.29, 0.26, 0.18), hair, root)
    add_part("LeftArm", (-0.5, 0, 1.38), (0.14, 0.14, 0.58), robe, root)
    add_part("RightArm", (0.5, 0, 1.38), (0.14, 0.14, 0.58), robe, root)
    add_part("LowerRobe", (0, 0, 0.62), (0.55, 0.32, 0.72), robe, root)

    root.rotation_euler.z = -0.03
    root.keyframe_insert(data_path="rotation_euler", frame=1)
    root.rotation_euler.z = 0.03
    root.keyframe_insert(data_path="rotation_euler", frame=24)
    root.rotation_euler.z = -0.03
    root.keyframe_insert(data_path="rotation_euler", frame=48)
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 48

    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(args.output),
        export_format="GLB",
        export_animations=True,
    )


if __name__ == "__main__":
    main()
