"""Copy the accepted Flowing character into the existing ten-second HD shot.

Blender 3.6, offline Eevee; run from the repository root in PowerShell:
& 'C:\\Program Files\\Blender Foundation\\Blender 3.6\\blender.exe' `
  --factory-startup -b --python-exit-code 1 `
  --python cinematics\\blender\\build_flowing_film.py -- --build
Repeat with --render after inspecting flowing_film_preview_0001/0120/0240.png.
--verify reloads the saved scene and checks geometry, grounding and motion.
Outputs are relative to this script: FirstShot_FlowingFilm.blend and
renders/bronze_jade_flowing.mp4 (silent 240-frame 1920x1080/24 H.264).
Only new outputs are written. Original scenes, portraits and movies are hashed.
The body is a static baked portrait pose, NOT a new rig or physics simulation.
Long-hair shape keys author gentle secondary motion with stationary roots.
Budget: 599,433 unchanged character vertices, 16 animated hair meshes,
48 Eevee samples at full HD; original avatar hidden to avoid double rendering.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import numpy as np


HERE = Path(__file__).resolve().parent
RENDERS = HERE / "renders"
SOURCE = HERE / "FirstShot_TravelerFlowing.blend"
BASE = HERE / "FirstShot_Costume.blend"
OUTPUT = HERE / "FirstShot_FlowingFilm.blend"
MOVIE = RENDERS / "bronze_jade_flowing.mp4"
COLLECTIONS = (
    "Study_editable_baked_character",
    "Ornate_fitted_layers_and_craft",
    "Hero_localized_face_and_groom",
    "Flowing_face_details_and_long_hair",
)
KNOWN_HASHES = {
    SOURCE.name: "4458071900028B6A5AA1DC47AA1B1E7B393FF7533ED2E36F137EAA1EEB83C495",
    BASE.name: "133CEDCF2A962E64690FEDD401C515023E88A1EB1BCDA148E672E6B95DCCC247",
    "renders/mortal_ascension_clipchamp.mp4":
        "E01E645DAC8248F959195639A1E9EEF92B55FE0D4647643F1E5D4F4DBD811469",
}
SAMPLE_FRAMES = (1, 45, 95, 120, 145, 195, 240)


def digest(path):
    """Hash a file without allocating its entire contents."""
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest().upper()


def preserved_hashes():
    """Include all prior scenes and accepted portrait/film outputs."""
    files = [p for p in HERE.glob("*.blend") if p != OUTPUT]
    files += list(RENDERS.glob("traveler_*.png"))
    files += [RENDERS / name for name in (
        "bronze_jade_costume.mp4", "mortal_ascension_clipchamp.mp4")]
    result = {p.relative_to(HERE).as_posix(): digest(p) for p in files}
    for name, expected in KNOWN_HASHES.items():
        if result[name] != expected:
            raise RuntimeError(f"Accepted source hash changed: {name}")
    return result


def mesh_digest(obj):
    """Fingerprint coordinates, topology and original material assignments."""
    mesh = obj.data
    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", coords)
    indices = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", indices)
    materials = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("material_index", materials)
    state = hashlib.sha256(coords.tobytes() + indices.tobytes() + materials.tobytes())
    state.update("\n".join(m.name for m in mesh.materials).encode())
    return state.hexdigest()


def film_objects():
    return [o for o in bpy.context.scene.objects if "flowing_film_source" in o]


def hair_objects():
    return [o for o in film_objects() if o.name.startswith((
        "Flowing_principal_lock", "Flowing_split_lock",
        "Flowing_longitudinal_fine_fibers"))]


def add_hair_motion(obj):
    """Bend only the lower free lengths, sharing a field with the fine fibers."""
    obj.shape_key_add(name="Basis")
    key = obj.shape_key_add(name="Root_locked_breeze")
    key.slider_min = -1
    for vertex, target in zip(obj.data.vertices, key.data):
        t = max(0, min(1, (1.45 - vertex.co.z) / .40))
        weight = t * t * (3 - 2 * t)
        target.co += Vector((.042, 0, .004)) * weight
    for frame, value in ((1, -.35), (45, .85), (95, -.75),
                         (145, 1), (195, -.65), (240, .25)):
        key.value = value
        key.keyframe_insert("value", frame=frame)
    for curve in obj.data.shape_keys.animation_data.action.fcurves:
        for point in curve.keyframe_points:
            point.handle_left_type = point.handle_right_type = "AUTO_CLAMPED"
    obj["motion_contract"] = "Static body; authored root-locked lower-hair bend"


def movie_settings(scene):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.render.resolution_percentage = 100
    scene.render.fps, scene.render.fps_base = 24, 1
    scene.frame_start, scene.frame_end = 1, 240
    scene.eevee.taa_render_samples = 48
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = str(MOVIE)
    scene.render.use_sequencer = False


def build():
    """Append only the four accepted visible mesh sets, never studio staging."""
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    scene = bpy.context.scene
    scene.frame_set(1)
    placement = bpy.data.objects["Traveler_placement"]
    transform = placement.matrix_world.copy()
    old = [placement, *placement.children_recursive]
    old += list(bpy.data.collections["Cinematic_traveler_costume"].all_objects)
    for obj in set(old):
        obj.hide_render = obj.hide_viewport = True
    bpy.data.collections["Cinematic_traveler_costume"].hide_render = True
    bpy.data.collections["Cinematic_traveler_costume"].hide_viewport = True
    with bpy.data.libraries.load(str(SOURCE), link=False) as (available, loaded):
        if not set(COLLECTIONS).issubset(available.collections):
            raise RuntimeError("Accepted character collections are missing")
        loaded.collections = list(COLLECTIONS)
    copied = []
    for source_collection in loaded.collections:
        target = bpy.data.collections.new("Film_" + source_collection.name)
        scene.collection.children.link(target)
        for obj in list(source_collection.objects):
            if obj.hide_render:
                continue
            if obj.type != "MESH" or obj.modifiers or obj.parent:
                raise RuntimeError(f"Unexpected non-baked character object: {obj.name}")
            obj["flowing_film_source"] = obj.name
            obj["flowing_film_mesh_sha256"] = mesh_digest(obj)
            obj["flowing_film_collection"] = source_collection.name
            target.objects.link(obj)
            source_collection.objects.unlink(obj)
            copied.append(obj)
    if sum(len(o.data.vertices) for o in copied) != 599433:
        raise RuntimeError("Did not copy the complete accepted visible character")
    # Feet sit on the existing paving, not the portrait studio floor.
    soles = [o for o in copied if o.name.startswith("Study_thin_sole_")]
    min_z = min(v.co.z for o in soles for v in o.data.vertices)
    ground = ground_heights(scene, transform, soles)
    transform.translation.z = max(ground) - min_z * placement.scale.z + .001
    anchor = bpy.data.objects.new("FlowingFilm_placement", None)
    scene.collection.objects.link(anchor)
    anchor.matrix_world = transform
    for obj in copied:
        obj.parent = anchor
    for obj in hair_objects():
        add_hair_motion(obj)
    scene["flowing_film_old_objects"] = json.dumps(sorted({o.name for o in old}))
    scene["flowing_film_source_sha256"] = digest(SOURCE)
    scene["flowing_film_base_sha256"] = digest(BASE)
    movie_settings(scene)
    bpy.context.view_layer.update()
    return scene


def ground_heights(scene, transform, soles):
    surfaces = [o for o in scene.objects if o.name.startswith((
        "Natural_traveler_ledge", "Old_paving_slab"))]
    heights = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for sole in soles:
        points = [transform @ sole.matrix_basis @ v.co for v in sole.data.vertices]
        center = sum(points, Vector()) / len(points)
        hits = []
        for surface in surfaces:
            evaluated = surface.evaluated_get(depsgraph)
            inv = evaluated.matrix_world.inverted()
            hit, point, _, _ = evaluated.ray_cast(
                inv @ Vector((center.x, center.y, 10)),
                (inv.to_3x3() @ Vector((0, 0, -1))).normalized())
            if hit:
                hits.append((evaluated.matrix_world @ point).z)
        if not hits:
            raise RuntimeError(f"No ground beneath {sole.name}")
        heights.append(max(hits))
    return heights


def wardrobe_tree(objects):
    vertices, faces = [], []
    for obj in objects:
        offset = len(vertices)
        vertices.extend(v.co.copy() for v in obj.data.vertices)
        faces.extend([offset + i for i in p.vertices] for p in obj.data.polygons)
    return BVHTree.FromPolygons(vertices, faces)


def validate(scene):
    """Check identity, all-frame coverage and sampled exact hair/wardrobe overlap."""
    if (scene.frame_start, scene.frame_end, scene.render.fps, scene.render.fps_base,
        scene.render.resolution_x, scene.render.resolution_y,
        scene.render.resolution_percentage) != (1, 240, 24, 1, 1920, 1080, 100):
        raise RuntimeError("Ten-second full-HD frame contract changed")
    if scene.camera.name != "CAM_ValleyReveal":
        raise RuntimeError("Cinematic camera was replaced")
    objects = film_objects()
    if len(objects) != 1095 or sum(len(o.data.vertices) for o in objects) != 599433:
        raise RuntimeError("Accepted character object/vertex counts changed")
    for obj in objects:
        if obj.hide_render or mesh_digest(obj) != obj["flowing_film_mesh_sha256"]:
            raise RuntimeError(f"Accepted appearance changed: {obj.name}")
    old = json.loads(scene["flowing_film_old_objects"])
    if not all(bpy.data.objects[n].hide_render for n in old):
        raise RuntimeError("Old cinematic traveler is still visible")
    face = next(o for o in objects if o.name.startswith("Portrait_reference_face_and_hands"))
    hair = hair_objects()
    if len(hair) != 16 or any("glasses" in o.name.lower() for o in objects):
        raise RuntimeError("Wrong face/hair variant copied")
    anchor = bpy.data.objects["FlowingFilm_placement"]
    soles = [o for o in objects if o.name.startswith("Study_thin_sole_")]
    ground = ground_heights(scene, anchor.matrix_world, soles)
    gaps = [min((o.matrix_world @ v.co).z for v in o.data.vertices) - z
            for o, z in zip(soles, ground)]
    if not all(-.001 <= gap <= .008 for gap in gaps):
        raise RuntimeError(f"Feet not grounded: {gaps}")
    coords = np.array([tuple(o.matrix_world @ v.co) for o in objects for v in o.data.vertices])
    if not np.isfinite(coords).all():
        raise RuntimeError("Non-finite character bounds")
    lower, upper = coords.min(axis=0), coords.max(axis=0)
    corners = [Vector((x, y, z)) for x in (lower[0] - .08, upper[0] + .08)
               for y in (lower[1], upper[1]) for z in (lower[2], upper[2] + .01)]
    coverage, jade, clouds = [], [], []
    for frame in range(1, 241):
        scene.frame_set(frame)
        projected = [world_to_camera_view(scene, scene.camera, p) for p in corners]
        if not all(.015 < p.x < .985 and .015 < p.y < .985 and p.z > 0 for p in projected):
            raise RuntimeError(f"Character clips frame {frame}")
        coverage.append((max(p.y for p in projected) - min(p.y for p in projected)) * 1080)
        for name in ("Gate_upper_eaves", "Jade_bi_relic", "Gate_island"):
            obj = bpy.data.objects[name]
            points = [world_to_camera_view(scene, scene.camera, obj.matrix_world @ Vector(p))
                      for p in obj.bound_box]
            if not all(.015 < p.x < .985 and .015 < p.y < .985 and p.z > 0 for p in points):
                raise RuntimeError(f"Gate clips frame {frame}: {name}")
        jade.append(bpy.data.materials["Quiet_jade_light"].node_tree.nodes[
            "Principled BSDF"].inputs["Emission Strength"].default_value)
        clouds.append(list(bpy.data.materials["Low_valley_cloud_volume"].node_tree.nodes[
            "Cloud_flow"].inputs[1].default_value))
    if min(coverage) < 190 or max(jade) - min(jade) < 1.39:
        raise RuntimeError("Character too small or jade motion lost")
    if (Vector(clouds[-1]) - Vector(clouds[0])).length < .07:
        raise RuntimeError("Cloud motion lost")
    gear = wardrobe_tree([o for o in objects if o["flowing_film_collection"] in COLLECTIONS[:2]])
    motion, screen_motion, root_max = {}, {}, 0.0
    for obj in hair:
        if "flowing_principal" not in obj:
            continue
        columns = 25 if obj["flowing_principal"] else 13
        tips = []
        for frame in SAMPLE_FRAMES:
            scene.frame_set(frame)
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                tree = BVHTree.FromPolygons([v.co for v in mesh.vertices],
                                           [list(p.vertices) for p in mesh.polygons])
                overlaps = len(tree.overlap(gear))
                if overlaps:
                    raise RuntimeError(f"Hair/wardrobe intersection: {obj.name}, {frame}, {overlaps}")
                root_max = max(root_max, max(
                    (mesh.vertices[i].co - obj.data.vertices[i].co).length for i in range(columns)))
                tips.append(anchor.matrix_world @ mesh.vertices[-1].co)
            finally:
                evaluated.to_mesh_clear()
        distance = max((a - b).length for a in tips for b in tips)
        if distance < .025:
            raise RuntimeError(f"Insufficient free-tip motion: {obj.name}, {distance}")
        motion[obj.name] = distance
        scene.frame_set(1)
        projected_tips = [world_to_camera_view(scene, scene.camera, p) for p in tips]
        screen_motion[obj.name] = max(
            Vector(((a.x - b.x) * 1920, (a.y - b.y) * 1080)).length
            for a in projected_tips for b in projected_tips)
    if root_max > 1e-7:
        raise RuntimeError(f"Hair roots displaced: {root_max}")
    scene.frame_set(1)
    return {
        "objects": len(objects), "vertices": int(len(coords)),
        "face": face.name, "face_materials": [m.name for m in face.data.materials],
        "collections": {n: sum(o["flowing_film_collection"] == n for o in objects) for n in COLLECTIONS},
        "all_mesh_fingerprints_match": True, "old_objects_hidden": old,
        "world_bounds": [lower.tolist(), upper.tolist()], "sole_ground_gaps_m": gaps,
        "all_240_frames_character_height_pixels": [min(coverage), max(coverage)],
        "all_240_frames_character_and_gate_covered": True,
        "sampled_frames": SAMPLE_FRAMES, "hair_wardrobe_intersections": 0,
        "hair_root_displacement_local_m": root_max, "hair_tip_peak_to_peak_world_m": motion,
        "hair_tip_motion_pixels_fixed_camera": screen_motion,
        "body": "Static baked accepted pose; no walking, rig or physics",
        "cloud_start_end": [clouds[0], clouds[-1]], "jade_range": [min(jade), max(jade)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--build", action="store_true")
    modes.add_argument("--render", action="store_true")
    modes.add_argument("--verify", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    started = time.perf_counter()
    before = preserved_hashes()
    scene = build() if args.build else None
    if args.build:
        evidence = validate(scene)
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
    bpy.ops.wm.open_mainfile(filepath=str(OUTPUT))
    scene = bpy.context.scene
    evidence = validate(scene)
    evidence["scene_reload_verified"] = True
    evidence["scene_sha256"] = digest(OUTPUT)
    if args.build:
        timings = {}
        scene.render.image_settings.file_format = "PNG"
        for frame in (1, 120, 240):
            scene.frame_set(frame)
            scene.render.filepath = str(RENDERS / f"flowing_film_preview_{frame:04d}.png")
            start = time.perf_counter()
            bpy.ops.render.render(write_still=True)
            timings[str(frame)] = round(time.perf_counter() - start, 2)
        evidence["preview_seconds"] = timings
    elif args.render:
        if MOVIE.exists():
            raise FileExistsError(f"Refusing to replace completed source movie: {MOVIE}")
        movie_settings(scene)
        intermediate = RENDERS / "flowing_film_rendering.mp4"
        scene.render.filepath = str(intermediate)
        start = time.perf_counter()
        bpy.ops.render.render(animation=True)
        evidence["render_seconds"] = round(time.perf_counter() - start, 2)
        if not intermediate.is_file() or intermediate.stat().st_size < 100000:
            raise RuntimeError("Movie render did not produce a usable file")
        intermediate.rename(MOVIE)
        evidence["movie_sha256"] = digest(MOVIE)
    after = preserved_hashes()
    if before != after:
        raise RuntimeError("A preserved source changed during this run")
    evidence["preserved_hashes_before"] = before
    evidence["preserved_hashes_after"] = after
    evidence["total_seconds"] = round(time.perf_counter() - started, 2)
    mode = "build" if args.build else "render" if args.render else "verify"
    (RENDERS / f"flowing_film_{mode}_evidence.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8")
    print("FLOWING_FILM_VERIFIED", mode, evidence["total_seconds"], flush=True)


if __name__ == "__main__":
    main()
