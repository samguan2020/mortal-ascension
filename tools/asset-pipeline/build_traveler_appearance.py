# PROTOTYPE - NOT FOR PRODUCTION
# Question: Can the player's traveler share Liu's appearance quality without losing identity?
# Date: 2026-10-06

"""Create an original clean-shaven traveler using the same local MPFB pipeline."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_liu_appearance import (
    ASSETS, build_character, cloth_material, export_appearance, loft, mesh_object,
    ribbon, sphere, stage_preview, stroke, validate_character,
)


def replace_material(old_name, material):
    for obj in ASSETS:
        for slot in obj.material_slots:
            if slot.material and slot.material.name == old_name:
                slot.material = material


def remove_part(obj):
    ASSETS.remove(obj)
    bpy.data.objects.remove(obj, do_unlink=True)


def crop_hem(name, old_bottom, new_bottom, waist):
    obj = bpy.data.objects[name]
    for vertex in obj.data.vertices:
        if vertex.co.z < waist:
            fraction = (vertex.co.z - old_bottom) / (waist - old_bottom)
            vertex.co.z = new_bottom + fraction * (waist - new_bottom)
            vertex.co.x *= 0.86 + 0.14 * fraction
            vertex.co.y *= 0.90 + 0.10 * fraction
    obj.data.update()


def build_traveler():
    head = build_character()
    for obj in list(ASSETS):
        if obj.name.startswith(("Moustache_", "Beard_lock_", "Temple_silver_", "Purse_cord")):
            remove_part(obj)
        elif obj.name == "Merchant_purse":
            remove_part(obj)
        elif obj.name.startswith("Swept_hair_") and int(obj.name.rsplit("_", 1)[1]) % 2:
            remove_part(obj)

    inner = cloth_material("Traveler_cloud_linen", (0.48, 0.50, 0.43), (0.70, 0.65, 0.47))
    outer = cloth_material("Traveler_slate_blue_coat", (0.19, 0.31, 0.36), (0.45, 0.58, 0.56))
    sash = cloth_material("Traveler_ochre_sash", (0.43, 0.29, 0.14), (0.65, 0.53, 0.32))
    replace_material("Ink_teal_woven_robe", inner)
    replace_material("Walnut_woven_surcoat", outer)
    replace_material("Clay_red_sash", sash)
    hair = bpy.data.materials["Ink_brown_hair"]
    trim = bpy.data.materials["Aged_brass_and_ochre"]
    linen = bpy.data.materials["Undyed_linen"]

    crop_hem("Continuous_underrobe", 0.12, 0.54, 0.89)
    crop_hem("Split_outer_coat", 0.24, 0.65, 0.88)
    reduction = bpy.data.objects["Continuous_underrobe"].modifiers.new("Hidden cloth simplification", "DECIMATE")
    reduction.ratio = 0.6
    tail = bpy.data.objects["Sash_hanging_end"]
    for vertex in tail.data.vertices:
        if vertex.co.z < 0.92:
            vertex.co.z = 0.92 - (0.92 - vertex.co.z) * 0.68
    for side in (-1, 1):
        leg = loft(f"Traveler_trouser_{side}", [
            (0.12, 0.064, 0.067), (0.20, 0.066, 0.069),
            (0.36, 0.079, 0.085), (0.53, 0.092, 0.090), (0.70, 0.098, 0.095),
        ], outer, folds=0.003, segments=32)
        leg.location.x = side * 0.105
        leg.modifiers["Tailored surface"].levels = 0
        boot = loft(f"Traveler_boot_upper_{side}", [
            (0.075, 0.072, 0.079), (0.09, 0.074, 0.083),
            (0.23, 0.072, 0.073), (0.25, 0.070, 0.071),
        ], hair, folds=0.001, segments=32)
        boot.location.x = side * 0.105
        boot.modifiers["Tailored surface"].levels = 0
        for row in range(3):
            z = 0.16 + row * 0.024
            stroke(f"Boot_binding_{side}_{row}", [
                (side * 0.105 + math.sin(i / 24 * math.tau) * 0.076,
                 -math.cos(i / 24 * math.tau) * 0.079, z)
                for i in range(25)
            ], 0.0025, trim)

    # Back-facing gear makes the player readable from the follow camera.
    pack = sphere("Traveler_cloth_pack", (0, 0.223, 1.13), (0.156, 0.084, 0.185), sash)
    pack.rotation_euler.y = -0.12
    bedroll = sphere("Traveler_bedroll", (0, 0.257, 1.315), (0.204, 0.057, 0.060), inner)
    bedroll.rotation_euler.y = -0.10
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    support_surfaces = [bpy.data.objects[name].evaluated_get(depsgraph) for name in (
        "Continuous_underrobe", "Split_outer_coat", "Tailored_shoulder_yoke",
    )]
    for side in (-1, 1):
        x = side * 0.145
        path = [
            (-0.19, 1.02), (-0.19, 1.08), (-0.195, 1.22), (-0.182, 1.32),
            (-0.135, 1.389), (-0.07, 1.422), (0.02, 1.425), (0.11, 1.400),
            (0.175, 1.36), (0.205, 1.31), (0.262, 1.27), (0.286, 1.25),
        ]
        vertices = [(x + offset, y, z) for y, z in path for offset in (-0.014, 0.014)]
        for index, vertex in enumerate(vertices):
            if vertex[1] > 0.18:
                continue
            point = Vector(vertex)
            hits = []
            for surface in support_surfaces:
                found, position, normal, _ = surface.closest_point_on_mesh(point)
                if found:
                    hits.append(((point - position).length_squared, position, normal))
            if not hits:
                raise RuntimeError("Cannot fit pack strap to clothing")
            _, position, normal = min(hits, key=lambda hit: hit[0])
            vertices[index] = position + normal * 0.012
        faces = [(i * 2, i * 2 + 1, i * 2 + 3, i * 2 + 2) for i in range(len(path) - 1)]
        uvs = [(u, i / (len(path) - 1)) for i in range(len(path)) for u in (0, 1)]
        strap = mesh_object(f"Travel_pack_strap_{side}", vertices, faces, sash, uvs)
        strap.modifiers.new("Strap thickness", "SOLIDIFY").thickness = 0.006
        strap.modifiers.new("Soft strap", "SUBSURF").levels = 1
    for x in (-0.11, 0.11):
        stroke(f"Bedroll_binding_{x}", [
            (x, 0.257 + math.cos(i / 24 * math.tau) * 0.060,
             1.315 + math.sin(i / 24 * math.tau) * 0.064)
            for i in range(25)
        ], 0.004, trim)
    stroke("Pack_cross_tie", [(-0.115, 0.27, 1.25), (0, 0.312, 1.13),
                              (0.105, 0.277, 0.99)], 0.004, linen)
    stroke("Pack_cross_tie_other", [(0.115, 0.27, 1.25), (0, 0.314, 1.13),
                                    (-0.105, 0.277, 0.99)], 0.004, linen)
    sphere("Pack_tie_knot", (0, 0.316, 1.13), (0.014, 0.009, 0.017), linen)
    ribbon("Traveler_hair_tie", [(0.020, 0.064, 1.732), (0.034, 0.085, 1.676),
                                (0.030, 0.102, 1.608)], [0.012, 0.015, 0.010], outer)
    head["prototype_role"] = "Player traveler static appearance"
    bpy.data.objects["Liu_Innkeeper_Body"]["prototype_role"] = "Hidden MPFB reference only"
    return head


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--previews", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.source.resolve() in (args.blend.resolve(), args.glb.resolve()):
        raise RuntimeError("Keep the original MPFB source unchanged")
    bpy.ops.wm.open_mainfile(filepath=str(args.source))
    ASSETS.clear()
    head = build_traveler()
    validate_character(head)
    for path in (args.blend, args.glb):
        path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.blend))
    if args.previews:
        stage_preview(args.previews, prefix="traveler")
    export_appearance(head, args.glb, "Traveler_Static_Appearance")


if __name__ == "__main__":
    main()
