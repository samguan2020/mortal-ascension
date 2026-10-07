# PROTOTYPE - NOT FOR PRODUCTION
# Question: Can a free MPFB/Blender character replace the geometric innkeeper?
# Date: 2026-10-05

"""Build an MPFB-based Innkeeper Liu appearance prototype and export GLB."""

from __future__ import annotations

import argparse
import bmesh
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--glb", type=Path, required=True)
    return parser.parse_args(args)


def create_material(
    name: str,
    color: tuple[float, float, float, float],
    roughness: float,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = roughness
    return material


def smooth(object_: bpy.types.Object) -> None:
    if object_.type != "MESH":
        return
    for polygon in object_.data.polygons:
        polygon.use_smooth = True


def add_uv_sphere(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    material: bpy.types.Material,
    segments: int = 24,
    rings: int = 16,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        location=location,
    )
    object_ = bpy.context.object
    object_.name = name
    object_.scale = scale
    object_.data.materials.append(material)
    smooth(object_)
    return object_


def add_tapered_cylinder(
    name: str,
    location: tuple[float, float, float],
    radius_top: float,
    radius_bottom: float,
    depth: float,
    material: bpy.types.Material,
    vertices: int = 32,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius_bottom,
        radius2=radius_top,
        depth=depth,
        location=location,
    )
    object_ = bpy.context.object
    object_.name = name
    object_.data.materials.append(material)
    bevel = object_.modifiers.new("Soft cloth edges", "BEVEL")
    bevel.width = 0.018
    bevel.segments = 2
    smooth(object_)
    return object_


def add_sleeve(
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    material: bpy.types.Material,
) -> bpy.types.Object:
    start_vector = Vector(start)
    end_vector = Vector(end)
    direction = end_vector - start_vector
    midpoint = (start_vector + end_vector) * 0.5
    bpy.ops.mesh.primitive_cone_add(
        vertices=24,
        radius1=radius * 0.78,
        radius2=radius,
        depth=direction.length,
        location=midpoint,
    )
    sleeve = bpy.context.object
    sleeve.name = name
    sleeve.data.materials.append(material)
    sleeve.rotation_mode = "QUATERNION"
    sleeve.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(direction.normalized())
    bevel = sleeve.modifiers.new("Sleeve softness", "BEVEL")
    bevel.width = 0.02
    bevel.segments = 2
    smooth(sleeve)
    return sleeve


def add_box(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    rotation: tuple[float, float, float],
    material: bpy.types.Material,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    object_ = bpy.context.object
    object_.name = name
    object_.scale = scale
    object_.data.materials.append(material)
    bevel = object_.modifiers.new("Fabric edge", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 2
    return object_


def configure_human(human: bpy.types.Object, skin: bpy.types.Material) -> None:
    human.name = "Liu_Innkeeper_Body"
    human.data.materials.clear()
    human.data.materials.append(skin)
    smooth(human)

    keys = human.data.shape_keys.key_blocks if human.data.shape_keys else []
    for key in keys:
        if key.name == "Basis":
            continue
        lowered = key.name.lower()
        if "$fe-" in lowered:
            key.value = 0.0
        elif "$as-$ma-" in lowered and "cauc" not in lowered:
            key.value = 0.48
        elif "universal-$ma-" in lowered:
            key.value = 0.52
        elif "$ma-" in lowered:
            key.value = 0.12
        else:
            key.value = 0.0


def pose_human(human: bpy.types.Object) -> bpy.types.Object:
    bpy.context.view_layer.objects.active = human
    human.select_set(True)
    result = bpy.ops.mpfb.add_standard_rig()
    if "FINISHED" not in result:
        raise RuntimeError(f"MPFB standard rig creation failed: {result}")
    rig = next(object_ for object_ in bpy.context.scene.objects if object_.type == "ARMATURE")
    rig.name = "Liu_Innkeeper_Rig"
    return rig


def create_head_preview(
    human: bpy.types.Object,
    skin: bpy.types.Material,
) -> bpy.types.Object:
    evaluated = human.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = bpy.data.meshes.new_from_object(evaluated)
    head = bpy.data.objects.new("Liu_Innkeeper_Head", mesh)
    bpy.context.collection.objects.link(head)

    editable = bmesh.new()
    editable.from_mesh(mesh)
    editable.verts.ensure_lookup_table()
    bmesh.ops.delete(
        editable,
        geom=[vertex for vertex in editable.verts if vertex.co.z < 1.34],
        context="VERTS",
    )
    editable.to_mesh(mesh)
    editable.free()

    mesh.materials.clear()
    mesh.materials.append(skin)
    smooth(head)
    human.hide_render = True
    human.hide_set(True)
    return head


def create_costume(
    rig: bpy.types.Object,
    skin: bpy.types.Material,
    robe: bpy.types.Material,
    robe_dark: bpy.types.Material,
    sash: bpy.types.Material,
    hair: bpy.types.Material,
) -> list[bpy.types.Object]:
    costume = [
        add_tapered_cylinder("Outer_Robe_Lower", (0, 0, 0.62), 0.29, 0.47, 1.12, robe_dark),
        add_tapered_cylinder("Outer_Robe_Torso", (0, 0, 1.095), 0.23, 0.35, 0.55, robe),
        add_tapered_cylinder("Sash", (0, 0, 0.88), 0.355, 0.355, 0.12, sash),
        add_sleeve("Sleeve_L", (0.23, 0, 1.28), (0.45, -0.01, 0.98), 0.14, robe),
        add_sleeve("Sleeve_R", (-0.23, 0, 1.28), (-0.45, -0.01, 0.98), 0.14, robe),
        add_box(
            "Collar_L",
            (0.065, -0.242, 1.20),
            (0.038, 0.018, 0.18),
            (math.radians(-5), math.radians(-18), math.radians(-16)),
            robe_dark,
        ),
        add_box(
            "Collar_R",
            (-0.065, -0.242, 1.20),
            (0.038, 0.018, 0.18),
            (math.radians(-5), math.radians(18), math.radians(16)),
            robe_dark,
        ),
        add_uv_sphere("Hair_Cap", (0, 0.015, 1.655), (0.10, 0.105, 0.055), hair),
        add_uv_sphere("Hair_Knot", (0, 0.025, 1.745), (0.045, 0.045, 0.05), hair, 20, 12),
        add_uv_sphere("Short_Beard", (0, -0.135, 1.465), (0.06, 0.018, 0.033), hair, 20, 12),
        add_uv_sphere("Hand_L", (0.47, -0.02, 0.94), (0.065, 0.055, 0.105), skin, 20, 12),
        add_uv_sphere("Hand_R", (-0.47, -0.02, 0.94), (0.065, 0.055, 0.105), skin, 20, 12),
    ]

    for side, x in (("L", 0.115), ("R", -0.115)):
        shoe = add_uv_sphere(f"Cloth_Shoe_{side}", (x, -0.07, 0.055), (0.13, 0.22, 0.07), robe_dark)
        costume.append(shoe)

    for object_ in costume:
        object_.parent = rig
    return costume


def validate_neck_clearance(head: bpy.types.Object) -> None:
    bpy.context.view_layer.update()

    def vertical_bounds(name: str) -> tuple[float, float]:
        object_ = bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get())
        heights = [(object_.matrix_world @ Vector(corner)).z for corner in object_.bound_box]
        return min(heights), max(heights)

    beard_bottom, _ = vertical_bounds("Short_Beard")
    for name in ("Outer_Robe_Torso", "Collar_L", "Collar_R", "Sleeve_L", "Sleeve_R"):
        _, top = vertical_bounds(name)
        if beard_bottom - top < 0.04:
            raise RuntimeError(f"{name} must leave at least 4 cm of neck below the beard")
    neck_bottom, _ = vertical_bounds(head.name)
    _, torso_top = vertical_bounds("Outer_Robe_Torso")
    if neck_bottom >= torso_top:
        raise RuntimeError("Neck must overlap the robe rather than float above it")


def main() -> None:
    args = parse_args()
    args.blend.parent.mkdir(parents=True, exist_ok=True)
    args.glb.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    bpy.ops.mpfb.create_human()
    human = bpy.context.active_object

    skin = create_material("Warm_Olive_Skin", (0.39, 0.23, 0.15, 1.0), 0.82)
    robe = create_material("Tea_Brown_Robe", (0.24, 0.13, 0.08, 1.0), 0.9)
    robe_dark = create_material("Ink_Green_Robe", (0.075, 0.12, 0.095, 1.0), 0.94)
    sash = create_material("Cinnabar_Sash", (0.35, 0.075, 0.045, 1.0), 0.86)
    hair = create_material("Ink_Black_Hair", (0.018, 0.012, 0.009, 1.0), 0.72)

    configure_human(human, skin)
    rig = pose_human(human)
    head = create_head_preview(human, skin)
    costume = create_costume(rig, skin, robe, robe_dark, sash, hair)
    validate_neck_clearance(head)

    human["prototype_role"] = "Innkeeper Liu appearance blockout"
    human["pipeline"] = "MPFB 2.0.2 + Blender 3.6"
    rig["animation_status"] = "Awaiting SayMotion retargeting"

    bpy.ops.wm.save_as_mainfile(filepath=str(args.blend))

    bpy.ops.object.select_all(action="DESELECT")
    export_objects = [head, rig, *costume]
    for object_ in export_objects:
        object_.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(
        filepath=str(args.glb),
        export_format="GLB",
        use_selection=True,
        export_animations=False,
        export_apply=False,
        export_skins=True,
        export_morph=True,
        export_materials="EXPORT",
    )

    print(f"BLEND_OUTPUT={args.blend}")
    print(f"GLB_OUTPUT={args.glb}")
    print(f"OBJECT_COUNT={len(export_objects)}")
    print(f"BONE_COUNT={len(rig.data.bones)}")


if __name__ == "__main__":
    main()
