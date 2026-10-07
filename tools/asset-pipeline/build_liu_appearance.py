# PROTOTYPE - NOT FOR PRODUCTION
# Question: Can tailored cloth meshes and authored details improve Liu's static appearance?
# Date: 2026-10-05

"""Build the original Liu v2 appearance from the preserved MPFB source."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_liu_innkeeper import add_uv_sphere, create_material, smooth
from validate_liu_appearance import read_glb, validate


TAU = math.tau
ASSETS: list[bpy.types.Object] = []


def face_transform(point) -> Vector:
    result = Vector(point)
    blend = min(1.0, max(0.0, (result.z - 1.39) / 0.08))
    result.x *= 1 + 0.24 * blend
    result.y = -0.025 + (result.y + 0.025) * (1 + 0.16 * blend)
    result.z = 1.43 + (result.z - 1.43) * (1 + 0.22 * blend)
    return result


def mesh_object(name, vertices, faces, material, uvs=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    if uvs:
        layer = mesh.uv_layers.new(name="ClothUV")
        for polygon in mesh.polygons:
            for loop in polygon.loop_indices:
                layer.data[loop].uv = uvs[mesh.loops[loop].vertex_index]
    smooth(obj)
    ASSETS.append(obj)
    return obj


def cloth_material(name, base, edge, size=512):
    image = bpy.data.images.new(name + "_woven_color", width=size, height=size)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    weave = 0.96 + 0.035 * np.sin(x * TAU * 128) * np.cos(y * TAU * 128)
    weave += 0.025 * np.sin(x * TAU * 5 + np.sin(y * TAU * 3))
    diamond = np.abs((x * 12) % 1 - 0.5) + np.abs((y * 16) % 1 - 0.5)
    motif = (np.abs(diamond - 0.38) < 0.025).astype(np.float32) * 0.07
    rgb = np.array(base)[None, None, :] * (weave + motif)[:, :, None]
    border = (y < 0.07) | (y > 0.97)
    key = ((np.floor(x * 48) % 2 == 0) & (y < 0.055) & (y > 0.025))
    rgb[border] = np.array(edge) * 0.62
    rgb[key | ((y > 0.065) & (y < 0.073))] = edge
    pixels = np.ones((size, size, 4), dtype=np.float32)
    pixels[:, :, :3] = np.clip(rgb, 0, 1)
    image.pixels.foreach_set(pixels.ravel())
    image.pack()
    material = create_material(name, (*base, 1), 0.86)
    nodes = material.node_tree.nodes
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    material.node_tree.links.new(texture.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
    return material


def loft(name, profiles, material, *, opening=0.0, folds=0.01, segments=64):
    vertices, faces, uvs = [], [], []
    for j, (z, rx, ry) in enumerate(profiles):
        for i in range(segments + 1):
            t = i / segments
            theta = opening + (TAU - 2 * opening) * t
            pleat = folds * (0.7 * math.cos(theta * 12) + 0.3 * math.cos(theta * 19))
            vertices.append(((rx + pleat) * math.sin(theta),
                             -(ry + pleat * 0.7) * math.cos(theta), z))
            uvs.append((t, j / (len(profiles) - 1)))
            if i < segments and j < len(profiles) - 1:
                a = j * (segments + 1) + i
                faces.append((a, a + 1, a + segments + 2, a + segments + 1))
    obj = mesh_object(name, vertices, faces, material, uvs)
    if opening == 0:
        editable = bmesh.new()
        editable.from_mesh(obj.data)
        bmesh.ops.remove_doubles(editable, verts=list(editable.verts), dist=0.00001)
        editable.to_mesh(obj.data)
        editable.free()
    modifier = obj.modifiers.new("Fabric thickness", "SOLIDIFY")
    modifier.thickness = 0.006
    modifier.offset = 0
    subdivision = obj.modifiers.new("Tailored surface", "SUBSURF")
    subdivision.levels = 1
    return obj


def stroke(name, points, radius, material, radii=None):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 4
    curve.bevel_depth = radius
    curve.bevel_resolution = 1
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for index, (point, position) in enumerate(zip(spline.bezier_points, points)):
        point.co = position
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
        point.radius = radii[index] if radii else 1
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    curve.materials.append(material)
    ASSETS.append(obj)
    return obj


def sphere(name, location, scale, material):
    obj = add_uv_sphere(name, location, scale, material, 24, 16)
    ASSETS.append(obj)
    return obj


def ribbon(name, points, widths, material, conform=False):
    if conform:
        samples, sample_widths = [], []
        for i in range(len(points) - 1):
            for step in range(8):
                t = step / 8
                samples.append(Vector(points[i]).lerp(Vector(points[i + 1]), t))
                sample_widths.append(widths[i] * (1 - t) + widths[i + 1] * t)
        points, widths = [*samples, Vector(points[-1])], [*sample_widths, widths[-1]]
    vertices, uvs, faces = [], [], []
    columns = 7 if conform else 2
    for i, (point, width) in enumerate(zip(points, widths)):
        point = Vector(point)
        tangent = Vector(points[min(i + 1, len(points) - 1)]) - Vector(points[max(0, i - 1)])
        across = tangent.cross(Vector((0, -1, 0))).normalized()
        for column in range(columns):
            t = column / (columns - 1)
            vertices.append(point + across * width * (t - 0.5))
            uvs.append((t, i / (len(points) - 1)))
            if i < len(points) - 1 and column < columns - 1:
                a = i * columns + column
                faces.append((a, a + 1, a + columns + 1, a + columns))
    if conform:
        envelope = [
            (0.94, 0.234, 0.161), (1.02, 0.224, 0.156), (1.20, 0.249, 0.157),
            (1.25, 0.269, 0.169), (1.325, 0.272, 0.162), (1.36, 0.245, 0.15),
            (1.395, 0.170, 0.115), (1.44, 0.080, 0.077),
        ]
        for vertex in vertices:
            for (z0, rx0, ry0), (z1, rx1, ry1) in zip(envelope, envelope[1:]):
                if z0 <= vertex.z <= z1:
                    t = (vertex.z - z0) / (z1 - z0)
                    rx, ry = rx0 * (1 - t) + rx1 * t, ry0 * (1 - t) + ry1 * t
                    y = -ry * math.sqrt(max(0, 1 - (vertex.x / rx) ** 2))
                    vertex.y = y - (0.024 if name == "Outer_cross_lapel" else 0.017)
                    break
    obj = mesh_object(name, vertices, faces, material, uvs)
    obj["ribbon_columns"] = columns
    thickness = obj.modifiers.new("Turned fabric edge", "SOLIDIFY")
    thickness.thickness = 0.005
    bevel = obj.modifiers.new("Soft seam", "BEVEL")
    bevel.width = 0.003
    bevel.segments = 2
    return obj


def sleeve(side, cloth, lining, trim):
    # A loft along the arm, with the upper rings buried inside the shoulder.
    centers = [
        (0.140, 0.005, 1.292, 0.092, 0.098),
        (0.213, 0.006, 1.301, 0.119, 0.123),
        (0.262, -0.003, 1.248, 0.112, 0.12),
        (0.298, -0.021, 1.171, 0.105, 0.118),
        (0.327, -0.037, 1.080, 0.109, 0.131),
        (0.353, -0.050, 1.002, 0.122, 0.153),
        (0.358, -0.052, 0.982, 0.122, 0.153),
    ]
    vertices, faces, uvs = [], [], []
    axis = Vector((0.55 * side, -0.1, -0.83)).normalized()
    across = Vector((0, 1, 0))
    down = axis.cross(across).normalized()
    for j, (x, y, z, rx, ry) in enumerate(centers):
        for i in range(49):
            t = i / 48
            angle = t * TAU
            pleat = 1 + 0.045 * math.cos(angle * 7 + j * 0.5)
            v = Vector((x * side, y, z)) + across * math.cos(angle) * rx * pleat
            v += down * math.sin(angle) * ry * pleat
            vertices.append(v)
            uvs.append((t, 1 - j / (len(centers) - 1)))
            if i < 48 and j < len(centers) - 1:
                a = j * 49 + i
                faces.append((a, a + 1, a + 50, a + 49))
    obj = mesh_object(f"Sleeve_{side}", vertices, faces, cloth, uvs)
    solid = obj.modifiers.new("Lined sleeve thickness", "SOLIDIFY")
    solid.thickness = 0.009
    obj.data.materials.append(lining)
    solid.material_offset = 1
    sub = obj.modifiers.new("Soft sleeve", "SUBSURF")
    sub.levels = 1
    edge = [vertices[-49 + i] for i in range(49)]
    stroke(f"Cuff_piping_{side}", edge, 0.003, trim)
    return Vector((0.358 * side, -0.052, 0.982)), axis


def hand_from_source(human, rig, side, wrist_target, direction, skin):
    suffix = "L" if side > 0 else "R"
    wrist = rig.data.bones[f"wrist.{suffix}"].head_local
    tip = rig.data.bones[f"finger3-3.{suffix}"].tail_local
    source_axis = (tip - wrist).normalized()
    rotation = source_axis.rotation_difference(direction)
    evaluated = human.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = bpy.data.meshes.new_from_object(evaluated)
    selected = {
        v.index for v in mesh.vertices
        if side * v.co.x > 0.40 and v.co.z < 1.065 and v.co.z > 0.84 and v.co.y < -0.15
        and (v.co - wrist).dot(source_axis) > -0.018
    }
    faces = [list(poly.vertices) for poly in mesh.polygons if all(i in selected for i in poly.vertices)]
    used = sorted({i for face in faces for i in face})
    if len(used) < 80:
        raise RuntimeError(f"MPFB hand extraction failed: {len(used)} vertices")
    indices = {old: new for new, old in enumerate(used)}
    vertices = [wrist_target + rotation @ ((mesh.vertices[i].co - wrist) * 0.80) for i in used]
    obj = mesh_object(f"MPFB_Hand_{suffix}", vertices, [[indices[i] for i in f] for f in faces], skin)
    bpy.data.meshes.remove(mesh)
    return obj


def facial_details(head, rig, hair, silver, skin):
    eye_white = create_material("Warm_ivory_eyes", (0.66, 0.58, 0.43, 1), 0.40)
    iris = create_material("Dark_brown_iris", (0.048, 0.026, 0.011, 1), 0.32)
    pupil = create_material("Pupil", (0.003, 0.004, 0.004, 1), 0.24)
    for side in (-1, 1):
        center = face_transform((0.030 * side, -0.125, 1.563))
        sphere(f"Eye_{side}", center, (0.014, 0.0115, 0.009), eye_white)
        sphere(f"Iris_{side}", center + Vector((0, -0.011, -0.001)), (0.005, 0.0019, 0.0053), iris)
        sphere(f"Pupil_{side}", center + Vector((0, -0.0128, -0.001)), (0.0023, 0.001, 0.0031), pupil)

    def on_face(x, z, offset=0.0015):
        sample = face_transform((x, -0.3, z))
        hit, point, _, _ = head.ray_cast(sample, Vector((0, 1, 0)))
        if not hit:
            raise RuntimeError(f"Facial detail misses the face: {(x, z)}")
        point.y -= offset
        return point

    for side in (-1, 1):
        points = [on_face(side * x, z) for x, z in [(0.013, 1.580), (0.025, 1.584), (0.041, 1.582), (0.05, 1.578)]]
        stroke(f"Eyebrow_{side}", points, 0.0036, hair, [0.55, 1, 0.85, 0.10])
        for strand in range(4):
            points = [on_face(side * x, z - strand * 0.001) for x, z in [(0.004, 1.513), (0.013, 1.510), (0.025, 1.503)]]
            stroke(f"Moustache_{side}_{strand}", points, 0.0014, hair, [0.5, 1, 0.1])
        stroke(f"Temple_silver_{side}", [
            face_transform((0.072 * side, -0.056, 1.595)),
            face_transform((0.077 * side, -0.04, 1.568)),
            face_transform((0.075 * side, -0.035, 1.548)),
        ], 0.004, silver, [0.3, 1, 0.1])
    for strand in range(15):
        x = (strand - 7) * 0.0027
        start = on_face(x, 1.481 + 0.003 * abs(x) / 0.02)
        stroke(f"Beard_lock_{strand}", [start, start + Vector((x * 0.05, -0.004, -0.012)),
                                      Vector((x * 0.60, start.y + 0.002, start.z - 0.032))],
               0.0023, silver if strand % 5 == 0 else hair, [0.9, 1, 0.05])


def create_hair(head, hair, highlight, tie, trim):
    center = Vector((0, -0.024, 1.635))

    def scalp(theta, fraction, offset=0.007):
        limit = 1.47 - 0.36 * math.cos(theta)
        phi = 0.012 + fraction * limit
        direction = Vector((math.sin(theta) * math.sin(phi),
                            -math.cos(theta) * math.sin(phi), math.cos(phi)))
        hit, point, normal, _ = head.ray_cast(center + direction * 0.5, -direction)
        if not hit:
            raise RuntimeError("Scalp projection missed the head")
        return point + normal * offset

    vertices, faces = [], []
    for j in range(21):
        for i in range(81):
            vertices.append(scalp(i / 80 * TAU, j / 20))
            if j < 20 and i < 80:
                a = j * 81 + i
                faces.append((a, a + 81, a + 82, a + 1))
    scalp_mesh = mesh_object("Fitted_scalp", vertices, faces, hair)
    editable = bmesh.new()
    editable.from_mesh(scalp_mesh.data)
    bmesh.ops.remove_doubles(editable, verts=list(editable.verts), dist=0.00001)
    editable.to_mesh(scalp_mesh.data)
    editable.free()
    for i in range(48):
        theta = i / 48 * TAU
        points = [scalp(theta + 0.18 * (1 - f), f, 0.009)
                  for f in (0.99, 0.85, 0.65, 0.42, 0.20, 0.06)]
        stroke(f"Swept_hair_{i}", points, 0.0018, highlight,
               [0.1, 0.8, 1, 1, 0.8, 0.1])
    bun = face_transform((0, 0.032, 1.699)) - Vector((0, 0, 0.040))
    sphere("Tied_hair_bun", bun, (0.044, 0.037, 0.038), hair)
    for i in range(7):
        angle = i / 7 * TAU
        points = [bun + Vector((math.sin(angle) * 0.043, math.cos(angle) * 0.034, -0.020)),
                  bun + Vector((math.sin(angle) * 0.044, math.cos(angle) * 0.037, 0.007)),
                  bun + Vector((math.sin(angle) * 0.023, math.cos(angle) * 0.021, 0.035))]
        stroke(f"Bun_fold_{i}", points, 0.002, highlight)
    stroke("Bun_binding", [bun + Vector((math.sin(i / 32 * TAU) * 0.045,
                                         math.cos(i / 32 * TAU) * 0.039, -0.010)) for i in range(33)], 0.004, tie)
    stroke("Wooden_hairpin", [bun + Vector((-0.075, 0, 0)), bun + Vector((0.077, 0, 0.010))], 0.0035, trim)


def build_character():
    human = bpy.data.objects["Liu_Innkeeper_Body"]
    rig = bpy.data.objects["Liu_Innkeeper_Rig"]
    head = bpy.data.objects["Liu_Innkeeper_Head"]
    for obj in list(bpy.context.scene.objects):
        if obj not in (human, rig, head):
            bpy.data.objects.remove(obj, do_unlink=True)
    skin = create_material("Warm_stylized_skin", (0.53, 0.30, 0.18, 1), 0.78)
    green = cloth_material("Ink_teal_woven_robe", (0.16, 0.25, 0.235), (0.56, 0.48, 0.32))
    brown = cloth_material("Walnut_woven_surcoat", (0.32, 0.22, 0.155), (0.63, 0.47, 0.29))
    red = cloth_material("Clay_red_sash", (0.40, 0.16, 0.105), (0.70, 0.49, 0.26))
    ivory = create_material("Undyed_linen", (0.57, 0.47, 0.32, 1), 0.95)
    trim = create_material("Aged_brass_and_ochre", (0.37, 0.23, 0.095, 1), 0.55)
    hair = create_material("Ink_brown_hair", (0.016, 0.012, 0.010, 1), 0.70)
    silver = create_material("Warm_grey_hair", (0.19, 0.16, 0.12, 1), 0.80)
    highlight = create_material("Hair_ridges", (0.036, 0.025, 0.017, 1), 0.72)
    head.data.materials.clear()
    head.data.materials.append(skin)
    for vertex in head.data.vertices:
        vertex.co = face_transform(vertex.co)
    editable = bmesh.new()
    editable.from_mesh(head.data)
    bmesh.ops.delete(editable, geom=[v for v in editable.verts
                    if v.co.z < 1.475 and abs(v.co.x) > 0.080], context="VERTS")
    editable.to_mesh(head.data)
    editable.free()
    head.data.update()
    ASSETS.append(head)

    loft("Continuous_underrobe", [
        (0.12, 0.282, 0.185), (0.14, 0.285, 0.185), (0.23, 0.277, 0.180),
        (0.45, 0.260, 0.171), (0.68, 0.235, 0.157), (0.89, 0.208, 0.140),
        (0.98, 0.210, 0.142), (1.12, 0.223, 0.146), (1.28, 0.252, 0.147),
        (1.34, 0.241, 0.137), (1.39, 0.150, 0.096), (1.42, 0.069, 0.064),
    ], green, folds=0.006)
    loft("Split_outer_coat", [
        (0.24, 0.286, 0.187), (0.26, 0.287, 0.190), (0.48, 0.268, 0.180),
        (0.72, 0.246, 0.163), (0.88, 0.224, 0.153), (1.02, 0.224, 0.151),
        (1.20, 0.244, 0.151), (1.31, 0.236, 0.142), (1.355, 0.197, 0.126),
        (1.40, 0.085, 0.073),
    ], brown, opening=0.42, folds=0.006)
    loft("Tailored_shoulder_yoke", [
        (1.25, 0.256, 0.160), (1.285, 0.267, 0.164), (1.325, 0.267, 0.156),
        (1.360, 0.240, 0.144), (1.395, 0.163, 0.108), (1.422, 0.079, 0.070),
    ], brown, opening=0.42, folds=0.001)
    loft("Waist_sash", [(0.875, 0.232, 0.160), (0.884, 0.234, 0.161),
                       (0.957, 0.230, 0.159), (0.966, 0.225, 0.155)], red, folds=0.002)
    ribbon("Inner_cross_collar", [(-0.060, -0.082, 1.416), (-0.093, -0.123, 1.37),
                                  (-0.014, -0.154, 1.25), (0.080, -0.162, 1.10),
                                  (0.163, -0.151, 0.958)], [0.026] * 5, ivory, conform=True)
    lapel = ribbon("Outer_cross_lapel", [(0.061, -0.083, 1.417), (0.100, -0.126, 1.36),
                                (0.025, -0.163, 1.25), (-0.091, -0.172, 1.09),
                                (-0.175, -0.157, 0.958)], [0.030, 0.045, 0.05, 0.05, 0.04], brown, conform=True)
    stroke("Lapel_stitched_edge", [v.co + Vector((0, -0.003, 0))
                                  for v in list(lapel.data.vertices)[::lapel["ribbon_columns"]]], 0.0016, trim)
    for side in (-1, 1):
        wrist, direction = sleeve(side, brown, ivory, trim)
        hand_from_source(human, rig, side, wrist, direction, skin)
        sphere(f"Cloth_shoe_{side}", (side * 0.117, -0.059, 0.063), (0.078, 0.166, 0.055), hair)
        stroke(f"Shoe_seam_{side}", [(side * 0.117 - 0.04, -0.17, 0.091),
                                    (side * 0.117, -0.201, 0.088),
                                    (side * 0.117 + 0.04, -0.17, 0.091)], 0.002, ivory)
    ribbon("Sash_hanging_end", [(0.125, -0.166, 0.949), (0.146, -0.185, 0.845),
                               (0.121, -0.205, 0.70), (0.136, -0.205, 0.57)], [0.056] * 4, red)
    sphere("Cloth_knot", (0.126, -0.17, 0.925), (0.038, 0.020, 0.035), red)
    stroke("Purse_cord", [(-0.17, -0.12, 0.94), (-0.238, -0.106, 0.85), (-0.243, -0.1, 0.75)], 0.004, trim)
    sphere("Merchant_purse", (-0.248, -0.10, 0.728), (0.049, 0.037, 0.065), brown)
    facial_details(head, rig, hair, silver, skin)
    create_hair(head, hair, highlight, red, trim)
    human.hide_render = True
    human.hide_set(True)
    rig.hide_render = True
    rig.hide_set(True)
    return head


def validate_character(head):
    bpy.context.view_layer.update()
    if bpy.data.objects["Inner_cross_collar"].dimensions.z <= 0:
        raise RuntimeError("Missing collar")
    neck_top = face_transform((0, 0, 1.48)).z - 0.032
    collar_top = max(v.co.z for v in bpy.data.objects["Outer_cross_lapel"].data.vertices)
    if neck_top - collar_top < 0.030:
        raise RuntimeError("Collar obscures the neck")
    if not all(math.isfinite(c) for obj in ASSETS for c in obj.dimensions):
        raise RuntimeError("Non-finite character geometry")
    if head.data.uv_layers:
        print("MPFB head UV preserved")
    print(f"NECK_CLEARANCE={neck_top - collar_top:.4f}m")


def stage_preview(directory, prefix="liu-v2"):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.use_gtao = True
    scene.eevee.gtao_distance = 0.12
    scene.eevee.gtao_factor = 1.1
    scene.eevee.use_soft_shadows = True
    scene.render.resolution_x = 960
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    scene.world.color = (0.22, 0.22, 0.22)
    ground = create_material("Studio_ground", (0.105, 0.13, 0.13, 1), 1)
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.name = "PREVIEW_ground"
    bpy.context.object.data.materials.append(ground)
    for name, position, energy, color, size in [
        ("Key", (-3, -4, 5), 430, (1, 0.86, 0.70), 4),
        ("Fill", (3, -1, 2.5), 210, (0.70, 0.83, 1), 3),
        ("Rim", (1, 3, 4), 540, (1, 0.91, 0.76), 3),
    ]:
        data = bpy.data.lights.new("PREVIEW_" + name, "AREA")
        data.energy, data.color, data.size = energy, color, size
        obj = bpy.data.objects.new("PREVIEW_" + name, data)
        scene.collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = (Vector((0, 0, 1)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    data = bpy.data.cameras.new("PREVIEW_camera")
    camera = bpy.data.objects.new("PREVIEW_camera", data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    data.type = "ORTHO"
    directory.mkdir(parents=True, exist_ok=True)
    for name, position, target, scale in [
        ("front", (0, -5, 2.0), (0, 0, 0.91), 2.03),
        ("three-quarter", (2.7, -5, 2.1), (0, 0, 0.91), 2.03),
        ("profile", (5, -0.3, 1.8), (0, 0, 0.91), 2.03),
        ("back", (2.2, 5, 2.0), (0, 0, 0.91), 2.03),
        ("portrait", (0.6, -4, 1.9), (0, -0.02, 1.53), 0.61),
    ]:
        camera.location = position
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        data.ortho_scale = scale
        scene.render.filepath = str(directory / f"{prefix}-{name}.png")
        bpy.ops.render.render(write_still=True)


def export_appearance(head, destination, name):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in ASSETS:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.join()
    head.name = name
    # Export only the visible static appearance, not an unused MPFB armature.
    bpy.ops.export_scene.gltf(filepath=str(destination), export_format="GLB", use_selection=True,
                              export_animations=False, export_skins=False, export_morph=False,
                              export_apply=True, export_materials="EXPORT")
    print(f"ASSET_VALIDATION={validate(read_glb(destination), destination.stat().st_size)}")
    print(f"APPEARANCE_GLB={destination}")


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
    head = build_character()
    validate_character(head)
    for path in (args.blend, args.glb):
        path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.blend))
    if args.previews:
        stage_preview(args.previews)
    export_appearance(head, args.glb, "Liu_V2_Static_Appearance")


if __name__ == "__main__":
    main()
