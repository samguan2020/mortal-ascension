"""Retarget the accepted SayMotion walk onto the CastSmith xianxia youth."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_traveler_animation import choose_cycle, source_sample


TARGET_DIRECTIONS = {
    "Spine": "mixamorig:Spine",
    "Chest": "mixamorig:Spine1",
    "Neck": "mixamorig:Neck",
    "UpperArm.L": "mixamorig:LeftArm",
    "UpperArm.R": "mixamorig:RightArm",
    "Thigh.L": "mixamorig:LeftUpLeg",
    "Shin.L": "mixamorig:LeftLeg",
    "Thigh.R": "mixamorig:RightUpLeg",
    "Shin.R": "mixamorig:RightLeg",
}
TARGET_ROTATIONS = {
    "Hips": "mixamorig:Hips",
    "Head": "mixamorig:Head",
    "Foot.L": "mixamorig:LeftFoot",
    "Foot.R": "mixamorig:RightFoot",
}
ARM_SWING_SCALE = {
    "mixamorig:LeftArm": 0.18,
    "mixamorig:RightArm": 0.18,
}
ARM_BASE_DIRECTIONS = {
    "mixamorig:LeftArm": Vector((0.18, 0, -0.98)).normalized(),
    "mixamorig:RightArm": Vector((-0.18, 0, -0.98)).normalized(),
}
ARM_BONES = {
    "mixamorig:LeftShoulder",
    "mixamorig:LeftArm",
    "mixamorig:LeftForeArm",
    "mixamorig:LeftHand",
    "mixamorig:RightShoulder",
    "mixamorig:RightArm",
    "mixamorig:RightForeArm",
    "mixamorig:RightHand",
}


def find_armature(objects, required_bone):
    matches = [
        obj for obj in objects
        if obj.type == "ARMATURE" and required_bone in obj.pose.bones
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one armature containing {required_bone}, found {len(matches)}"
        )
    return matches[0]


def mirror_bone_name(name):
    if "Left" in name:
        return name.replace("Left", "Right")
    if "Right" in name:
        return name.replace("Right", "Left")
    return name


def repair_arm_weights(objects):
    meshes = [obj for obj in objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(f"Expected one character mesh, found {len(meshes)}")
    mesh = meshes[0]
    groups_by_index = {group.index: group.name for group in mesh.vertex_groups}
    groups_by_name = {group.name: group for group in mesh.vertex_groups}
    missing = ARM_BONES - groups_by_name.keys()
    if missing:
        raise RuntimeError(f"Character skin is missing arm groups: {sorted(missing)}")

    left_vertices = [vertex for vertex in mesh.data.vertices if vertex.co.x > 0.02]
    tree = KDTree(len(left_vertices))
    for index, vertex in enumerate(left_vertices):
        tree.insert(vertex.co, index)
    tree.balance()

    repaired = 0
    max_distance = 0.0
    for vertex in mesh.data.vertices:
        if vertex.co.x >= -0.02:
            continue
        arm_weight = sum(
            element.weight
            for element in vertex.groups
            if groups_by_index[element.group] in ARM_BONES
        )
        if arm_weight <= 0.001:
            continue
        _, source_index, distance = tree.find(
            Vector((-vertex.co.x, vertex.co.y, vertex.co.z))
        )
        if distance > 0.025:
            continue
        source = left_vertices[source_index]
        source_weights = {
            mirror_bone_name(groups_by_index[element.group]): element.weight
            for element in source.groups
        }
        for element in list(vertex.groups):
            mesh.vertex_groups[groups_by_index[element.group]].remove([vertex.index])
        for name, weight in source_weights.items():
            groups_by_name[name].add([vertex.index], weight, "REPLACE")
        repaired += 1
        max_distance = max(max_distance, distance)
    if repaired < 1000:
        raise RuntimeError(f"Too few right-arm vertices repaired: {repaired}")
    hand_group = groups_by_name["mixamorig:RightHand"]
    forearm_group = groups_by_name["mixamorig:RightForeArm"]
    cleaned = 0
    for vertex in mesh.data.vertices:
        if vertex.co.x >= -0.02 or vertex.co.z >= 0.95:
            continue
        hand_weight = next(
            (
                element.weight
                for element in vertex.groups
                if element.group == hand_group.index
            ),
            0.0,
        )
        if hand_weight <= 0.001:
            continue
        forearm_weight = next(
            (
                element.weight
                for element in vertex.groups
                if element.group == forearm_group.index
            ),
            0.0,
        )
        hand_group.remove([vertex.index])
        forearm_group.add(
            [vertex.index], forearm_weight + hand_weight, "REPLACE"
        )
        cleaned += 1
    print(
        f"ARM_WEIGHT_REPAIR={{'vertices': {repaired}, "
        f"'max_mirror_distance': {max_distance:.6f}, "
        f"'low_sleeve_hand_weights_removed': {cleaned}}}"
    )


def target_pose(rig, directions, rotations, arm_swing_centers, idle=False):
    for bone in rig.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    direction_by_bone = {} if idle else {
        target: directions[source] for source, target in TARGET_DIRECTIONS.items()
    }
    rotation_by_bone = {} if idle else {
        target: rotations[source] for source, target in TARGET_ROTATIONS.items()
    }
    for bone in rig.pose.bones:
        rest = bone.bone
        direction = direction_by_bone.get(bone.name)
        arm_base = ARM_BASE_DIRECTIONS.get(bone.name)
        if arm_base is not None:
            if idle:
                direction = arm_base
            else:
                source_name = next(
                    source
                    for source, target in TARGET_DIRECTIONS.items()
                    if target == bone.name
                )
                direction = Vector((
                    arm_base.x,
                    (
                        direction.y - arm_swing_centers[source_name]
                    ) * ARM_SWING_SCALE[bone.name],
                    arm_base.z,
                )).normalized()
        if direction is not None:
            current_direction = bone.vector.normalized()
            rotation = (
                current_direction.rotation_difference(direction)
                @ bone.matrix.to_quaternion()
            )
        elif bone.name in rotation_by_bone:
            delta = rotation_by_bone[bone.name]
            rotation = delta @ rest.matrix_local.to_quaternion()
        else:
            continue
        position = bone.head.copy()
        bone.matrix = Matrix.LocRotScale(position, rotation, Vector((1, 1, 1)))


def key_pose(rig, frame):
    for bone in rig.pose.bones:
        bone.rotation_mode = "QUATERNION"
        bone.keyframe_insert("location", frame=frame, group=bone.name)
        bone.keyframe_insert("rotation_quaternion", frame=frame, group=bone.name)
        bone.keyframe_insert("scale", frame=frame, group=bone.name)


def make_actions(target, source, source_action):
    samples = []
    first = round(source_action.frame_range[0])
    last = round(source_action.frame_range[1])
    for frame in range(first, last + 1):
        bpy.context.scene.frame_set(frame)
        samples.append(source_sample(source))
    start, end = choose_cycle(samples)
    arm_swing_centers = {
        name: (
            min(samples[index][0][name].y for index in range(start, end + 1))
            + max(samples[index][0][name].y for index in range(start, end + 1))
        ) / 2
        for name in ("UpperArm.L", "UpperArm.R")
    }

    target.animation_data_create()
    idle = bpy.data.actions.new("Idle")
    target.animation_data.action = idle
    target_pose(
        target, *samples[start], arm_swing_centers, idle=True
    )
    key_pose(target, 1)
    key_pose(target, end - start + 1)

    walk = bpy.data.actions.new("Walk")
    target.animation_data.action = walk
    for output_frame, sample_index in enumerate(range(start, end + 1), 1):
        sample = samples[start] if sample_index == end else samples[sample_index]
        target_pose(target, *sample, arm_swing_centers)
        key_pose(target, output_frame)

    target.animation_data.action = None
    for action in (idle, walk):
        track = target.animation_data.nla_tracks.new()
        track.name = action.name
        strip = track.strips.new(action.name, 1, action)
        strip.name = action.name
        track.mute = False
    return idle, walk


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--character", type=Path, required=True)
    parser.add_argument("--motion", type=Path, required=True)
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--glb", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.character))
    target_objects = set(bpy.context.scene.objects)
    target = find_armature(target_objects, "mixamorig:Hips")
    repair_arm_weights(target_objects)

    bpy.ops.import_scene.gltf(filepath=str(args.motion))
    source_objects = set(bpy.context.scene.objects) - target_objects
    source = find_armature(source_objects, "hips_JNT")
    source_action = source.animation_data.action if source.animation_data else None
    if not source_action:
        raise RuntimeError("Walk source has no active animation")

    idle, walk = make_actions(target, source, source_action)
    for obj in source_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for action in list(bpy.data.actions):
        if action not in (idle, walk):
            bpy.data.actions.remove(action)

    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = round(
        bpy.data.actions["Walk"].frame_range[1]
    )
    bpy.context.scene.frame_set(1)
    args.blend.parent.mkdir(parents=True, exist_ok=True)
    args.glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.blend))

    bpy.ops.object.select_all(action="DESELECT")
    export_objects = [target, *[obj for obj in target_objects if obj.type == "MESH"]]
    for obj in export_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.export_scene.gltf(
        filepath=str(args.glb),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_skins=True,
        export_morph=False,
        export_apply=False,
        export_nla_strips=True,
        export_force_sampling=True,
        export_frame_range=False,
        export_materials="EXPORT",
    )
    print(f"ANIMATED_GLB={args.glb}")


if __name__ == "__main__":
    main()
