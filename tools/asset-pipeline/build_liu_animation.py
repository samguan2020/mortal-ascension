# PROTOTYPE - NOT FOR PRODUCTION
# Question: Can the accepted innkeeper gesture during replies without changing appearance?
# Date: 2026-10-06

"""Skin Innkeeper Liu and retarget two restrained SayMotion conversation excerpts."""

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_traveler_animation import (
    FPS, SOURCE_PAIRS, SOURCE_ROTATIONS, create_rig, key_pose, set_pose,
    skin_appearance, source_sample,
)
from build_liu_appearance import stage_preview
from traveler_skinning import weights_for_liu
from validate_liu_animation import read_asset, validate


def make_gestures(rig, samples, shoes):
    rig.animation_data_create()
    idle = bpy.data.actions.new("Idle")
    rig.animation_data.action = idle
    directions = {name: (rig.data.bones[name].tail_local - rig.data.bones[name].head_local).normalized()
                  for name in SOURCE_PAIRS}
    rotations = {name: Quaternion() for name in SOURCE_ROTATIONS}
    set_pose(rig, directions, rotations, shoes, idle=True)
    key_pose(rig, 1)
    key_pose(rig, FPS + 1)
    actions = [idle]
    for name, low, high in (("TalkExplain", 0.10, 0.45), ("TalkWelcome", 0.50, 0.85)):
        start, end = round((len(samples)-1)*low), round((len(samples)-1)*high)
        print(f"GESTURE_SOURCE={name}:{start}-{end}")
        action = bpy.data.actions.new(name)
        rig.animation_data.action = action
        first_directions, first_rotations = samples[start]
        for offset, frame in enumerate(range(start, end + 1)):
            directions, rotations = samples[frame]
            remaining = end - frame
            if remaining < 10:
                blend = (1 - remaining/10) ** 2
                directions = {bone: direction.lerp(first_directions[bone], blend).normalized()
                              for bone, direction in directions.items()}
                rotations = {bone: rotation.slerp(first_rotations[bone], blend)
                             for bone, rotation in rotations.items()}
            if name == "TalkWelcome":
                mirrored_directions = {}
                for bone, direction in directions.items():
                    target = bone[:-1] + ("R" if bone.endswith(".L") else "L") if bone.endswith((".L", ".R")) else bone
                    mirrored_directions[target] = Vector((-direction.x, direction.y, direction.z))
                directions = mirrored_directions
                rotations = {bone: Quaternion((rotation.w, rotation.x, -rotation.y, -rotation.z))
                             for bone, rotation in rotations.items()}
            rotations = {**rotations, "Hips": Quaternion()}
            set_pose(rig, directions, rotations, shoes, idle=True)
            key_pose(rig, offset + 1)
        actions.append(action)
    for action in actions:
        for curve in action.fcurves:
            for key in curve.keyframe_points:
                key.interpolation = "LINEAR"
    rig.animation_data.action = None
    for action in actions:
        track = rig.animation_data.nla_tracks.new()
        track.name = action.name
        track.strips.new(action.name, 1, action)
        track.mute = True
    return actions


def preview(rig, actions, directory):
    scene = bpy.context.scene
    rig.animation_data.action = actions[1]
    scene.frame_set(round(actions[1].frame_range[1] / 2))
    stage_preview(directory, "liu-talk")
    camera = scene.camera
    camera.location = (2.7, -5, 2.1)
    camera.rotation_euler = (Vector((0, 0, 0.91)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = 2.03
    for action in actions[1:]:
        rig.animation_data.action = action
        for index, fraction in enumerate((0.0, 0.35, 0.65)):
            scene.frame_set(1 + round((action.frame_range[1]-1)*fraction))
            scene.render.filepath = str(directory / f"{action.name}-{index}.png")
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
        raise RuntimeError("Keep appearance, motion and output files separate")
    bpy.ops.wm.open_mainfile(filepath=str(args.source))
    parts = [o for o in bpy.context.scene.objects if not o.hide_render and o.type in ("MESH", "CURVE")]
    for obj in list(bpy.context.scene.objects):
        if obj not in parts:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    rig = create_rig("Liu")
    mesh, shoes = skin_appearance(parts, rig, weights_for_liu)
    bpy.context.scene.render.fps = FPS
    existing = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.motion))
    imported = [o for o in bpy.data.objects if o not in existing]
    source = next(o for o in imported if o.type == "ARMATURE")
    source_action = source.animation_data.action
    if not source_action:
        raise RuntimeError("SayMotion source has no conversation action")
    required = {n for pair in SOURCE_PAIRS.values() for n in pair} | set(SOURCE_ROTATIONS.values())
    missing = required - set(source.pose.bones.keys())
    if missing:
        raise RuntimeError(f"Unexpected SayMotion Adult Male skeleton: {sorted(missing)}")
    samples = []
    for frame in range(math.floor(source_action.frame_range[0]), math.floor(source_action.frame_range[1])+1):
        bpy.context.scene.frame_set(frame)
        samples.append(source_sample(source))
    if len(samples) < FPS * 4:
        raise RuntimeError("Conversation source is too short for two gestures")
    actions = make_gestures(rig, samples, shoes)
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
    for action in list(bpy.data.actions):
        if action not in actions:
            bpy.data.actions.remove(action)
    rig["motion_source"] = args.motion.name
    rig["prototype_role"] = "Innkeeper conversation skin; no lip sync"
    rig.animation_data.action = actions[0]
    bpy.context.scene.frame_set(1)
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = int(max(a.frame_range[1] for a in actions))
    for path in (args.blend, args.glb):
        path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.blend))
    if args.previews:
        preview(rig, actions, args.previews)
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
    print(f"NPC_ANIMATION_VALIDATION={json.dumps(validate(document, binary, args.glb.stat().st_size))}")


if __name__ == "__main__":
    main()
