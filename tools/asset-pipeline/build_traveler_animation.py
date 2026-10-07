# PROTOTYPE - NOT FOR PRODUCTION
# Question: Can SayMotion drive the accepted traveler's own skinned appearance?
# Date: 2026-10-06

"""Fit a deform rig, skin the saved traveler, and retarget a SayMotion walk."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from traveler_skinning import weights_for_part
from validate_traveler_animation import read_asset, validate

FPS = 30
ROOT_HEIGHT = 0.88
FLOOR = 0.008
SOURCE_PAIRS = {
    "Spine": ("spine_JNT", "spine1_JNT"),
    "Chest": ("spine1_JNT", "neck_JNT"),
    "Neck": ("neck_JNT", "head_JNT"),
}
for side, prefix in (("L", "l"), ("R", "r")):
    SOURCE_PAIRS.update({
        f"UpperArm.{side}": (f"{prefix}_arm_JNT", f"{prefix}_forearm_JNT"),
        f"Forearm.{side}": (f"{prefix}_forearm_JNT", f"{prefix}_hand_JNT"),
        f"Hand.{side}": (f"{prefix}_hand_JNT", f"{prefix}_handMiddle1_JNT"),
        f"Thigh.{side}": (f"{prefix}_upleg_JNT", f"{prefix}_leg_JNT"),
        f"Shin.{side}": (f"{prefix}_leg_JNT", f"{prefix}_foot_JNT"),
    })
SOURCE_ROTATIONS = {"Hips": "hips_JNT", "Head": "head_JNT",
                    "Foot.L": "l_foot_JNT", "Foot.R": "r_foot_JNT"}


def create_rig(name="Traveler"):
    data = bpy.data.armatures.new(f"{name}_Deform")
    rig = bpy.data.objects.new(f"{name}_Rig", data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    specifications = [
        ("Hips", (0, 0, ROOT_HEIGHT), (0, 0, 1.00), None),
        ("Spine", (0, 0, 1.00), (0, 0, 1.15), "Hips"),
        ("Chest", (0, 0, 1.15), (0, 0, 1.40), "Spine"),
        ("Neck", (0, 0, 1.40), (0, -0.025, 1.49), "Chest"),
        ("Head", (0, -0.025, 1.49), (0, -0.025, 1.76), "Neck"),
    ]
    for side, sign in (("L", 1), ("R", -1)):
        specifications.extend([
            (f"UpperArm.{side}", (sign * 0.20, 0, 1.31), (sign * 0.295, -0.025, 1.155), "Chest"),
            (f"Forearm.{side}", (sign * 0.295, -0.025, 1.155), (sign * 0.358, -0.052, 0.982), f"UpperArm.{side}"),
            (f"Hand.{side}", (sign * 0.358, -0.052, 0.982), (sign * 0.419, -0.063, 0.890), f"Forearm.{side}"),
            (f"Thigh.{side}", (sign * 0.105, 0, ROOT_HEIGHT), (sign * 0.105, -0.008, 0.47), "Hips"),
            (f"Shin.{side}", (sign * 0.105, -0.008, 0.47), (sign * 0.105, 0, 0.10), f"Thigh.{side}"),
            (f"Foot.{side}", (sign * 0.105, 0, 0.10), (sign * 0.105, -0.17, 0.07), f"Shin.{side}"),
        ])
    for name, head, tail, parent in specifications:
        bone = data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        if parent:
            bone.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    for bone in rig.pose.bones:
        bone.rotation_mode = "QUATERNION"
    return rig


def skin_appearance(parts, rig, weight_function=weights_for_part):
    shoe_points = {}
    for obj in parts:
        bpy.ops.object.select_all(action="DESELECT")
        obj.hide_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.convert(target="MESH")
        obj = bpy.context.object
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        if obj.data.uv_layers.active:
            obj.data.uv_layers.active.name = "CharacterUV"
        obj.vertex_groups.clear()
        groups = {bone.name: obj.vertex_groups.new(name=bone.name) for bone in rig.data.bones}
        for vertex in obj.data.vertices:
            for name, weight in weight_function(obj.name, vertex.co).items():
                groups[name].add([vertex.index], weight, "REPLACE")
        modifier = obj.modifiers.new("Traveler skin", "ARMATURE")
        modifier.object = rig
        obj.parent = rig
        if obj.name.startswith("Cloth_shoe_"):
            side = "L" if obj.name.endswith("_1") else "R"
            shoe_points[side] = [v.co.copy() for v in obj.data.vertices]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    mesh = bpy.context.object
    mesh.name = rig.name.removesuffix("_Rig") + "_Skinned_Appearance"
    if set(shoe_points) != {"L", "R"}:
        raise RuntimeError("Missing shoes for floor contact calibration")
    return mesh, shoe_points


def source_sample(source):
    bones = source.pose.bones
    hips = bones["hips_JNT"]
    hip_delta = hips.matrix.to_quaternion() @ source.data.bones["hips_JNT"].matrix_local.to_quaternion().inverted()
    forward = hip_delta @ Vector((0, -1, 0))
    yaw = math.atan2(forward.x, -forward.y)
    heading = Quaternion((0, 0, 1), -yaw)
    directions = {
        name: (heading @ (bones[end].head - bones[start].head)).normalized()
        for name, (start, end) in SOURCE_PAIRS.items()
    }
    rotations = {
        name: heading @ (bones[source_name].matrix.to_quaternion()
                         @ source.data.bones[source_name].matrix_local.to_quaternion().inverted())
        for name, source_name in SOURCE_ROTATIONS.items()
    }
    return directions, rotations


def choose_cycle(samples):
    leg_names = ("Thigh.L", "Shin.L", "Thigh.R", "Shin.R")
    candidates = []
    for start in range(FPS, len(samples) - FPS * 2):
        for length in range(24, 49):
            end = start + length
            if end + 1 >= len(samples):
                continue
            amplitude = max(samples[i][0]["Thigh.L"].y for i in range(start, end)) - min(
                samples[i][0]["Thigh.L"].y for i in range(start, end))
            if amplitude < 0.25:
                continue
            pose_cost = sum((samples[start][0][name] - samples[end][0][name]).length_squared
                            for name in SOURCE_PAIRS)
            velocity_cost = sum(((samples[start + 1][0][name] - samples[start - 1][0][name])
                                 - (samples[end + 1][0][name] - samples[end - 1][0][name])).length_squared
                                for name in leg_names)
            candidates.append((pose_cost + velocity_cost * 4, start, end))
    if not candidates:
        raise RuntimeError("SayMotion source has no measurable walk cycle")
    cost, start, end = min(candidates)
    print(f"CYCLE={json.dumps({'source_start': start, 'source_end': end, 'seconds': (end-start)/FPS, 'seam_cost': cost})}")
    return start, end


def set_pose(rig, directions, rotations, shoes, idle=False):
    for bone in rig.pose.bones:
        rest = bone.bone
        rest_rotation = rest.matrix_local.to_quaternion()
        direction = directions.get(bone.name)
        if idle and bone.name.startswith(("Thigh.", "Shin.")):
            direction = (rest.tail_local - rest.head_local).normalized()
        if direction is not None:
            direction = direction.copy()
            # The roomy sleeves need more lateral clearance than the stock unclothed source.
            if bone.name.startswith(("UpperArm.", "Forearm.", "Hand.")):
                side = 1 if bone.name.endswith(".L") else -1
                minimum = 0.38 if bone.name.startswith("UpperArm.") else 0.24
                direction.x = side * max(minimum, side * direction.x)
                direction.normalize()
            original = (rest.tail_local - rest.head_local).normalized()
            rotation = original.rotation_difference(direction) @ rest_rotation
        else:
            delta = Quaternion() if idle and bone.name.startswith("Foot.") else rotations[bone.name]
            rotation = delta @ rest_rotation
        position = rest.head_local.copy()
        if bone.parent:
            position = bone.parent.matrix @ bone.parent.bone.matrix_local.inverted() @ position
        bone.matrix = Matrix.LocRotScale(position, rotation, Vector((1, 1, 1)))
        bpy.context.view_layer.update()
    bottom = min((rig.pose.bones[f"Foot.{side}"].matrix
                  @ rig.data.bones[f"Foot.{side}"].matrix_local.inverted() @ point).z
                 for side, points in shoes.items() for point in points)
    rig.pose.bones["Hips"].location.y += FLOOR - bottom
    bpy.context.view_layer.update()


def key_pose(rig, frame):
    for bone in rig.pose.bones:
        bone.keyframe_insert("location", frame=frame, group=bone.name)
        bone.keyframe_insert("rotation_quaternion", frame=frame, group=bone.name)


def make_actions(rig, samples, start, end, shoes):
    rig.animation_data_create()
    walk = bpy.data.actions.new("Walk")
    rig.animation_data.action = walk
    first_directions, first_rotations = samples[start]
    for offset, source_frame in enumerate(range(start, end + 1)):
        directions, rotations = samples[source_frame]
        remaining = end - source_frame
        if remaining < 5:
            blend = (1 - remaining / 5) ** 2
            directions = {name: direction.lerp(first_directions[name], blend).normalized()
                          for name, direction in directions.items()}
            rotations = {name: rotation.slerp(first_rotations[name], blend)
                         for name, rotation in rotations.items()}
        set_pose(rig, directions, rotations, shoes)
        key_pose(rig, offset + 1)
    idle = bpy.data.actions.new("Idle")
    rig.animation_data.action = idle
    directions = {name: sum((samples[f][0][name] for f in range(start, end)), Vector()).normalized()
                  for name in SOURCE_PAIRS}
    rotations = {name: Quaternion() for name in SOURCE_ROTATIONS}
    set_pose(rig, directions, rotations, shoes, idle=True)
    key_pose(rig, 1)
    key_pose(rig, FPS + 1)
    for action in (walk, idle):
        for curve in action.fcurves:
            for key in curve.keyframe_points:
                key.interpolation = "LINEAR"
    rig.animation_data.action = None
    for action in (idle, walk):
        track = rig.animation_data.nla_tracks.new()
        track.name = action.name
        strip = track.strips.new(action.name, 1, action)
        strip.name = action.name
        track.mute = True
    return idle, walk


def preview(rig, walk, directory):
    from build_liu_appearance import stage_preview
    directory.mkdir(parents=True, exist_ok=True)
    rig.animation_data.action = walk
    bpy.context.scene.frame_set(1)
    stage_preview(directory, "traveler-walk")
    scene = bpy.context.scene
    camera = scene.camera
    camera.location = (2.7, -5, 2.1)
    camera.rotation_euler = (Vector((0, 0, 0.91)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = 2.03
    for index in range(4):
        frame = 1 + round(index * (walk.frame_range[1] - 1) / 4)
        scene.frame_set(frame)
        scene.render.filepath = str(directory / f"walk-phase-{index}.png")
        bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--motion", type=Path, required=True)
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--previews", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if len({p.resolve() for p in (args.source, args.motion, args.blend, args.glb)}) != 4:
        raise RuntimeError("Animated output must not overwrite appearance or motion sources")
    bpy.ops.wm.open_mainfile(filepath=str(args.source))
    parts = [o for o in bpy.context.scene.objects if not o.hide_render and o.type in ("MESH", "CURVE")]
    for obj in list(bpy.context.scene.objects):
        if obj not in parts:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    rig = create_rig()
    mesh, shoes = skin_appearance(parts, rig)
    bpy.context.scene.render.fps = FPS
    existing = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.motion))
    imported = [o for o in bpy.data.objects if o not in existing]
    source = next(o for o in imported if o.type == "ARMATURE")
    action = source.animation_data.action
    if not action:
        raise RuntimeError("SayMotion GLB contains no source animation")
    required = {name for pair in SOURCE_PAIRS.values() for name in pair} | set(SOURCE_ROTATIONS.values())
    missing = required - set(source.pose.bones.keys())
    if missing:
        raise RuntimeError(f"Unexpected SayMotion Adult Male rig: missing {sorted(missing)}")
    samples = []
    for frame in range(math.floor(action.frame_range[0]), math.floor(action.frame_range[1]) + 1):
        bpy.context.scene.frame_set(frame)
        samples.append(source_sample(source))
    start, end = choose_cycle(samples)
    idle, walk = make_actions(rig, samples, start, end, shoes)
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
    for unused in list(bpy.data.actions):
        if unused not in (idle, walk):
            bpy.data.actions.remove(unused)
    rig["motion_source"] = args.motion.name
    rig["source_cycle_frames"] = [start, end]
    rig.animation_data.action = idle
    bpy.context.scene.frame_set(1)
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = end - start + 1
    for path in (args.blend, args.glb):
        path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.blend))
    if args.previews:
        preview(rig, walk, args.previews)
    rig.animation_data.action = None
    for track in rig.animation_data.nla_tracks:
        track.mute = False
    bpy.context.scene.frame_set(1)
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(
        filepath=str(args.glb), export_format="GLB", use_selection=True,
        export_animations=True, export_skins=True, export_morph=False, export_apply=False,
        export_nla_strips=True, export_force_sampling=True, export_frame_range=False,
        export_materials="EXPORT",
    )
    document, binary = read_asset(args.glb)
    print(f"ANIMATION_VALIDATION={json.dumps(validate(document, binary, args.glb.stat().st_size))}")
    print(f"ANIMATED_GLB={args.glb}")


if __name__ == "__main__":
    main()
