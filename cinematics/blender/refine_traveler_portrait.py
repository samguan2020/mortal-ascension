"""Reproducible, isolated Blender 3.6 Eevee traveler portrait study.

From D:\\Repos\\mortal-ascension in PowerShell:
& 'C:\\Program Files\\Blender Foundation\\Blender 3.6\\blender.exe' `
  --factory-startup -b --python-exit-code 1 `
  --python cinematics\\blender\\refine_traveler_portrait.py

Writes ONLY FirstShot_TravelerStudy.blend and renders/traveler_study_*.
The loaded costume scene, its camera, rig, materials and environment remain
intact in their original scene. Study anatomy is copied from rest-space source
polygons; replacement garments and hair are separate editable objects. A mild
asymmetric stance is baked into study vertices, NOT an animation-ready rig.
No original asset, film, browser import or audio output is modified.

Geometry changes: narrower cut, shoulder/elbow gathering, waist tension and
gravity-directed skirt folds, reduced boots, fitted straps, fewer ornaments,
projected layered hair with fine irregular strands. Source facial identity is
retained, with spatial skin color, subtle pores/SSS and less chalky eyes.
Lighting-only changes: a separate neutral-earth studio with soft key/fill/rim,
contact shadows and portrait cameras. Baseline stills use these SAME lights.
No claim of photorealism, cloth simulation, facial acting or animation readiness.

Offline budget: Eevee, 128 samples, 1200x1500 half-body / 1080x1500 full-body,
no particles, no external textures, study mesh budget 600k evaluated vertices.
The original cinematic environment is not evaluated for study renders.
Each run replaces only this script's named outputs; Blender backups disabled.
Evidence includes input hashes before/after, finite geometry, material resource,
original rig weight checks, camera margins and saved-file reload verification.
Contact-sheet columns, left to right: OLD full, STUDY full, OLD half, STUDY half.
The sheet is a direct image montage, without sharpening or color correction.
Second pass replaces detached sleeve roots with one continuous remeshed upper
garment, a compact crossed collar, tapered hairline locks and directional weave.

Append -- --ornate to load the ACCEPTED FirstShot_TravelerStudy.blend, add a
separate richer costume alternative and write ONLY FirstShot_TravelerOrnate.blend
and renders/traveler_ornate_*. The default simple-study build is unchanged.
The ornate contact sheet compares accepted simple full / ornate full / accepted
simple half / ornate half under the same saved studio cameras and lights.

Append -- --ornate --reference-face for the separate user-illustration-inspired
face, without glasses, on the accepted ornate costume. Writes only
FirstShot_TravelerPortrait.blend and traveler_portrait_* outputs. The reference
is not loaded as a texture or archived. Deterministic sculpt targets below
approximate visible proportions; a single small frontal illustration cannot
establish exact likeness, concealed eye anatomy or an accurate side profile.
Optional --reference-proof <local image> checks its approved SHA256 before/after;
regeneration uses authored parameters and does not require that temporary image.
Add --face-preview to that reference command to render only frontal and
three-quarter checks before refreshing the integrated scene and stills.
The focused facial pass changes brows, skin-only lid hooding, nose/philtrum/lip
landmarks and short clustered facial hair, not costume, lights or scalp groom.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RENDERS = HERE / "renders"
OUTPUT = HERE / "FirstShot_TravelerStudy.blend"
SOURCE_HASH = "95ABFBB2CFF5E190A7DEB069DC3C5376697CF1929C4AD98BB3ADE83CC148896F"
REFERENCE_IMAGE_HASH = "350C9C91C7BA11704A716C33864D1D52E72A3BCB0FA3B019310F670C64CCA7A2"
REFERENCE_FACE_TARGETS = {
    "jaw_width_gain": .15, "cheek_width_gain": .08, "forehead_width_gain": .065,
    "chin_extension_m": .005, "nose_bridge_projection_m": .008,
    "nose_tip_projection_m": .009, "nose_width_gain": .20,
    "cheek_plane_projection_m": .0035, "subcheek_recession_m": .003,
    "eye_horizontal_gain": .08, "eye_vertical_gain": -.16, "lip_projection_m": .0025,
    "brow_ridge_projection_m": .0038, "lower_lid_volume_m": .002,
    "alar_flare_m": .0028, "lower_lip_fullness_m": .004,
}
sys.path.insert(0, str(ROOT / "tools" / "asset-pipeline"))
from build_liu_appearance import mesh_object, ribbon, sphere, stroke

PARTS = []
TAU = math.tau


def digest(path):
    """Hash a preserved input without loading it into memory."""
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest().upper()


def material(name, color, roughness, *, noise=0.025, bump=0.0002,
             metallic=0, sheen=0):
    """Create subtle multiscale variation without external resources."""
    mat = bpy.data.materials.new("Study_" + name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Specular"].default_value = 0.3
    shader.inputs["Sheen"].default_value = sheen
    tex = nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 36
    tex.inputs["Detail"].default_value = 2
    ramp = nodes.new("ShaderNodeValToRGB")
    for element, factor in zip(ramp.color_ramp.elements, (1 - noise, 1 + noise)):
        element.color = (*(v * factor for v in color), 1)
    links.new(tex.outputs["Fac"], ramp.inputs[0])
    links.new(ramp.outputs[0], shader.inputs["Base Color"])
    micro = nodes.new("ShaderNodeTexNoise")
    micro.inputs["Scale"].default_value = 260
    micro.inputs["Detail"].default_value = 2
    relief = nodes.new("ShaderNodeBump")
    relief.inputs["Strength"].default_value = 0.18
    relief.inputs["Distance"].default_value = bump
    links.new(micro.outputs["Fac"], relief.inputs["Height"])
    links.new(relief.outputs[0], shader.inputs["Normal"])
    return mat


def add_weave(mat):
    """Use crossed submillimeter yarns, not large isotropic bump noise."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coordinates = nodes.new("ShaderNodeTexCoord")
    axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(coordinates.outputs["Object"], axes.inputs[0])
    yarns = []
    for axis, frequency in (("X", 4200), ("Z", 3900)):
        scale = nodes.new("ShaderNodeMath")
        scale.operation = "MULTIPLY"
        scale.inputs[1].default_value = frequency
        links.new(axes.outputs[axis], scale.inputs[0])
        sine = nodes.new("ShaderNodeMath")
        sine.operation = "SINE"
        links.new(scale.outputs[0], sine.inputs[0])
        yarns.append(sine)
    weave = nodes.new("ShaderNodeMath")
    weave.operation = "MULTIPLY"
    for index, yarn in enumerate(yarns):
        links.new(yarn.outputs[0], weave.inputs[index])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .28
    bump.inputs["Distance"].default_value = .00022
    links.new(weave.outputs[0], bump.inputs["Height"])
    shader = nodes.get("Principled BSDF")
    links.new(bump.outputs[0], shader.inputs["Normal"])
    roughness = nodes.new("ShaderNodeMapRange")
    roughness.inputs["From Min"].default_value = -1
    roughness.inputs["To Min"].default_value = .80
    roughness.inputs["To Max"].default_value = .94
    links.new(weave.outputs[0], roughness.inputs["Value"])
    links.new(roughness.outputs[0], shader.inputs["Roughness"])
    yarn_color = nodes.new("ShaderNodeMapRange")
    yarn_color.inputs["From Min"].default_value = -1
    yarn_color.inputs["To Min"].default_value = .96
    yarn_color.inputs["To Max"].default_value = 1.04
    links.new(weave.outputs[0], yarn_color.inputs["Value"])
    base = shader.inputs["Base Color"].links[0].from_socket
    mix = nodes.new("ShaderNodeMixRGB")
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1
    links.new(base, mix.inputs[1])
    links.new(yarn_color.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], shader.inputs["Base Color"])


def part(obj, region="body"):
    """Register editable study geometry and its baked-pose region."""
    obj["study_pose_region"] = region
    PARTS.append(obj)
    return obj


def weld_surface(obj):
    """Close coincident UV seams before thickness is generated."""
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    bmesh.ops.remove_doubles(mesh, verts=list(mesh.verts), dist=0.00001)
    bmesh.ops.recalc_face_normals(mesh, faces=list(mesh.faces))
    mesh.to_mesh(obj.data)
    mesh.free()
    obj.data.update()


def interpolate(profiles, z):
    for a, b in zip(profiles, profiles[1:]):
        if a[0] <= z <= b[0]:
            t = (z - a[0]) / (b[0] - a[0])
            return tuple(a[k] * (1 - t) + b[k] * t for k in (1, 2))
    raise ValueError(f"Height {z} outside cloth profiles")


def cloth(name, profiles, mat, *, opening=0, folds=0.006, region="body",
          center=0, rows=65, segments=96):
    """Cut a dense cloth shell with waist-anchored, gravity-directed folds."""
    vertices, faces, uv = [], [], []
    low, high = profiles[0][0], profiles[-1][0]
    for row in range(rows):
        t = row / (rows - 1)
        z = low + (high - low) * t
        rx, ry = interpolate(profiles, z)
        gap = opening * (1 - 0.55 * t)
        for col in range(segments + 1):
            u = col / segments
            theta = gap + (TAU - 2 * gap) * u
            phase = theta * 13 + 0.45 * math.sin(theta * 3) + 0.35 * t
            amplitude = folds * (0.45 + 0.55 * (1 - t))
            pleat = amplitude * (math.cos(phase) + 0.32 * math.cos(theta * 21 + t))
            waist = math.exp(-((z - 0.99) / 0.12) ** 2)
            pleat += 0.0035 * waist * math.sin(theta * 9 + z * 44)
            hem = 0.003 * (1 - t) ** 8 * math.sin(theta * 5 + 0.4)
            vertices.append((center + (rx + pleat) * math.sin(theta),
                             -(ry + pleat * 0.7) * math.cos(theta), z + hem))
            uv.append((u, t))
            if row < rows - 1 and col < segments:
                a = row * (segments + 1) + col
                faces.append((a, a + 1, a + segments + 2, a + segments + 1))
    obj = part(mesh_object(name, vertices, faces, mat, uv), region)
    if opening == 0:
        weld_surface(obj)
    solid = obj.modifiers.new("Turned cloth thickness", "SOLIDIFY")
    solid.thickness = 0.002
    solid.offset = 0
    return obj


TORSO = [(0.945, 0.145, 0.104), (1.00, 0.150, 0.106),
         (1.09, 0.172, 0.116), (1.21, 0.202, 0.124),
         (1.31, 0.199, 0.117), (1.36, 0.169, 0.102),
         (1.40, 0.113, 0.080), (1.431, 0.065, 0.062)]


def front_y(x, z, offset=0.006):
    rx, ry = interpolate(TORSO, z)
    return -ry * math.sqrt(max(0.02, 1 - (x / rx) ** 2)) - offset


def surface_ribbon(name, anchors, widths, mat, offset=.010):
    """Fit a lapel to the new torso rather than the obsolete barrel envelope."""
    points, sampled_widths = [], []
    for i in range(len(anchors) - 1):
        a, b = Vector(anchors[i]), Vector(anchors[i + 1])
        previous = Vector(anchors[max(0, i - 1)])
        following = Vector(anchors[min(len(anchors) - 1, i + 2)])
        for j in range(20):
            t = j / 20
            points.append(.5 * (2 * a + (-previous + b) * t
                               + (2 * previous - 5 * a + 4 * b - following) * t * t
                               + (-previous + 3 * a - 3 * b + following) * t ** 3))
            sampled_widths.append(widths[i] * (1 - t) + widths[i + 1] * t)
    points.append(Vector(anchors[-1]))
    sampled_widths.append(widths[-1])
    vertices, faces = [], []
    for i, (p, width) in enumerate(zip(points, sampled_widths)):
        tangent = points[min(i + 1, len(points) - 1)] - points[max(0, i - 1)]
        across = tangent.cross(Vector((0, -1, 0))).normalized()
        for j in range(9):
            v = p + across * width * (j / 8 - .5)
            v.y = front_y(v.x, max(TORSO[0][0], min(TORSO[-1][0], v.z)), offset)
            v.y -= .0008 * math.sin(j / 8 * math.pi)
            vertices.append(v)
            if i < len(points) - 1 and j < 8:
                a = i * 9 + j
                faces.append((a, a + 1, a + 10, a + 9))
    obj = mesh_object(name, vertices, faces, mat)
    obj.modifiers.new("Folded lapel thickness", "SOLIDIFY").thickness = .002
    bevel = obj.modifiers.new("Soft lapel edge", "BEVEL")
    bevel.width = .001
    bevel.segments = 2
    return part(obj)


def build_anatomy(source, mats):
    """Copy only skin/eyes/brows; retain the approved facial shape."""
    vertices, faces, indices = [], [], []
    remap = {}
    for polygon in source.data.polygons:
        mi = polygon.material_index
        brow = mi == 6 and all(1.59 < source.data.vertices[i].co.z < 1.64
                              and source.data.vertices[i].co.y < -0.10
                              for i in polygon.vertices)
        if mi not in (0, 7, 8, 9) and not brow:
            continue
        face = []
        for index in polygon.vertices:
            if index not in remap:
                remap[index] = len(vertices)
                vertices.append(source.data.vertices[index].co.copy())
            face.append(remap[index])
        faces.append(face)
        indices.append({0: 0, 7: 1, 8: 2, 9: 3}.get(mi, 4))
    obj = part(mesh_object("Study_original_face_and_hands", vertices, faces, mats["skin"]))
    for name in ("eye", "iris", "pupil", "brow"):
        obj.data.materials.append(mats[name])
    for poly, index in zip(obj.data.polygons, indices):
        poly.material_index = index
    colors = obj.data.color_attributes.new(name="SkinTone", type="FLOAT_COLOR", domain="POINT")
    for vertex, datum in zip(obj.data.vertices, colors.data):
        x, y, z = vertex.co
        cheek = math.exp(-((abs(x) - 0.052) / 0.027) ** 2
                         - ((z - 1.558) / 0.026) ** 2) if y < -0.065 else 0
        lip = math.exp(-(x / 0.027) ** 4 - ((z - 1.507) / 0.008) ** 2) if y < -0.13 else 0
        socket = math.exp(-((abs(x) - 0.032) / 0.022) ** 2
                          - ((z - 1.579) / 0.008) ** 2) if y < -0.11 else 0
        variation = 0.008 * math.sin(x * 380 + z * 241) * math.sin(z * 429)
        datum.color = (0.49 + 0.024 * cheek - 0.015 * lip + variation,
                       0.285 - 0.026 * cheek - 0.085 * lip - 0.019 * socket + variation,
                       0.181 - 0.015 * cheek - 0.034 * lip - 0.010 * socket + variation, 1)
    shader = mats["skin"].node_tree.nodes.get("Principled BSDF")
    attribute = mats["skin"].node_tree.nodes.new("ShaderNodeVertexColor")
    attribute.layer_name = "SkinTone"
    mats["skin"].node_tree.links.new(attribute.outputs["Color"], shader.inputs["Base Color"])
    shader.inputs["Subsurface"].default_value = 0.065
    shader.inputs["Subsurface Radius"].default_value = (0.012, 0.005, 0.003)
    shader.inputs["Subsurface Color"].default_value = (0.52, 0.25, 0.16, 1)
    obj.data.update()
    bpy.context.view_layer.update()
    return obj


def build_hair(head, mats):
    """Project irregular overlapping locks onto the actual copied head."""
    center = Vector((0, -0.024, 1.635))

    def scalp(theta, fraction, lift=0.005):
        angle = (theta + math.pi) % TAU - math.pi
        limit = 1.65 - 0.33 * math.cos(theta)
        limit += .20 * math.exp(-((abs(angle) - 1.32) / .34) ** 2)
        limit += .075 * math.sin(theta * 2 + .8) + .014 * math.sin(theta * 11)
        phi = 0.014 + fraction * limit
        direction = Vector((math.sin(theta) * math.sin(phi),
                            -math.cos(theta) * math.sin(phi), math.cos(phi)))
        hit, point, normal, _ = head.ray_cast(center + direction * 0.5, -direction)
        if not hit:
            raise RuntimeError("Study scalp projection missed the copied head")
        edge = min(1, max(0, (fraction - .89) / .12))
        return point + normal * (lift * (1 - edge) + .0008 * edge)

    vertices, faces = [], []
    for row in range(33):
        for col in range(129):
            vertices.append(scalp(col / 128 * TAU, row / 32 * .972))
            if row < 32 and col < 128:
                a = row * 129 + col
                faces.append((a, a + 129, a + 130, a + 1))
    boundary = mats["hair"].copy()
    boundary.name = "Study_feathered_hair_boundary"
    boundary.blend_method = "HASHED"
    boundary.use_screen_refraction = False
    boundary.shadow_method = "HASHED"
    attr = boundary.node_tree.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "HairlineOpacity"
    boundary.node_tree.links.new(attr.outputs["Alpha"],
                                boundary.node_tree.nodes.get("Principled BSDF").inputs["Alpha"])
    scalp_mesh = part(mesh_object("Study_irregular_hairline", vertices, faces, boundary), "head")
    colors = scalp_mesh.data.color_attributes.new(name="HairlineOpacity", type="FLOAT_COLOR", domain="POINT")
    for i, color in enumerate(colors.data):
        fraction = (i // 129) / 32
        opacity = min(1, max(0, (1 - fraction) / .085))
        color.color = (1, 1, 1, opacity)
    weld_surface(scalp_mesh)
    for i in range(55):
        theta = -.2 + i / 55 * TAU
        end = 1.012 + .026 * math.sin(i * 2.4)
        vertices, faces = [], []
        for row in range(13):
            t = row / 12
            fraction = .80 + (end - .80) * t
            width = (.031 + .014 * math.sin(i * 1.73)) * (1 - t ** 3) + .0004
            middle = theta + .32 * (1 - t)
            for col in range(5):
                vertices.append(scalp(middle + width * (col / 4 - .5), fraction,
                                      .005 + .001 * math.sin(col / 4 * math.pi)))
                if row < 12 and col < 4:
                    a = row * 5 + col
                    faces.append((a, a + 5, a + 6, a + 1))
        lock = part(mesh_object("Study_tapered_hairline_lock", vertices, faces, boundary), "head")
        colors = lock.data.color_attributes.new(name="HairlineOpacity", type="FLOAT_COLOR", domain="POINT")
        for index, color in enumerate(colors.data):
            t = (index // 5) / 12
            edge = abs((index % 5) / 4 - .5) * 2
            color.color = (1, 1, 1, (1 - .75 * t ** 2) * (1 - .85 * edge ** 3))
        for strand in range(2):
            points = [scalp(theta + .32 * (1 - t) + (strand - 1) * .006,
                            .84 + (end + .025 - .84) * t, .003)
                      for t in (0, .3, .65, .88, 1)]
            part(stroke("Study_hairline_tip", points, .00032, mats["hair"],
                        [1, 1, .7, .35, .02]), "head")
    # Small overlapping swept locks, not bright evenly spaced wire ridges.
    for i in range(59):
        theta = i / 59 * TAU + 0.029 * math.sin(i * 2.39)
        points = [scalp(theta + 0.84 * (1 - f) ** 1.2, f,
                        0.0053 + 0.001 * math.sin(f * math.pi))
                  for f in (1.0, 0.91, 0.73, 0.50, 0.27, 0.08)]
        part(stroke("Study_swept_lock", points, 0.0009 + 0.0003 * math.sin(i * 1.7),
                    mats["hair"], [0.08, 0.8, 1, 1, 0.7, 0.1]), "head")
    for i in range(190):
        theta = i * 2.399963
        points = [scalp(theta + 0.84 * (1 - f) ** 1.2, f, 0.0061)
                  for f in (0.99, 0.86, 0.63, 0.38, 0.15)]
        part(stroke("Study_fine_hair", points, 0.00024,
                    mats["hair_light"] if i % 4 == 0 else mats["hair"],
                    [0.1, 0.6, 1, 0.8, 0.1]), "head")
    bun = Vector((0.005, 0.049, 1.735))
    part(sphere("Study_folded_hair_knot", bun, (0.035, 0.041, 0.028), mats["hair"]), "head")
    for i in range(15):
        angle = i / 15 * TAU
        points = [bun + Vector((math.sin(angle + t * 0.8) * radius,
                                math.cos(angle + t * 0.8) * radius * 1.1, height))
                  for t, radius, height in ((0, .025, -.019), (.3, .036, -.007),
                                            (.7, .03, .018), (1, .012, .025))]
        part(stroke("Study_bun_lock", points, .0007, mats["hair"]), "head")
    part(stroke("Study_hair_binding", [(bun.x + .034 * math.sin(i / 40 * TAU),
                                       bun.y + .042 * math.cos(i / 40 * TAU),
                                       bun.z - .010) for i in range(41)],
                .003, mats["sash"]), "head")
    part(stroke("Study_wooden_hairpin", [(-.052, .046, 1.728), (.061, .057, 1.734)],
                .0028, mats["leather"]), "head")
    for sign in (-1, 1):
        for i in range(7):
            theta = sign * (1.18 + i * .025)
            points = [scalp(theta + sign * .07 * t, .91 + .17 * t, .003)
                      for t in (0, .3, .6, .85, 1)]
            part(stroke("Study_temple_lock", points, .0010,
                        mats["hair"], [.7, 1, .65, .3, .02]), "head")


def build_sleeve(side, mats):
    profiles = [(.120, .001, 1.292, .058, .064),
                (.170, .001, 1.280, .064, .066),
                (.216, -.006, 1.247, .063, .067),
                (.252, -.018, 1.192, .066, .073),
                (.282, -.029, 1.131, .070, .080),
                (.315, -.042, 1.060, .076, .089),
                (.350, -.052, .989, .074, .086)]
    vertices, faces = [], []
    axis = Vector((.55 * side, -.1, -.83)).normalized()
    across = Vector((0, 1, 0))
    down = axis.cross(across).normalized()
    rows, columns = 61, 64
    for row in range(rows):
        t = row / (rows - 1) * (len(profiles) - 1)
        index = min(int(t), len(profiles) - 2)
        f = t - index
        values = []
        for k in range(5):
            a, b = profiles[index][k], profiles[index + 1][k]
            previous = profiles[max(0, index - 1)][k]
            following = profiles[min(len(profiles) - 1, index + 2)][k]
            values.append(.5 * ((2 * a) + (-previous + b) * f
                               + (2 * previous - 5 * a + 4 * b - following) * f * f
                               + (-previous + 3 * a - 3 * b + following) * f ** 3))
        x, y, z, rx, ry = values
        for col in range(columns + 1):
            theta = col / columns * TAU
            fold = .0018 * math.sin(theta * 7 + t * .35)
            elbow = math.exp(-((z - 1.16) / .065) ** 2)
            fold += .003 * elbow * math.cos(z * 110 + theta * 2) * max(0, math.cos(theta))
            p = Vector((x * side, y, z))
            p += across * math.cos(theta) * (rx + fold)
            p += down * math.sin(theta) * (ry + fold)
            vertices.append(p)
            if row < rows - 1 and col < columns:
                a = row * (columns + 1) + col
                faces.append((a, a + 1, a + columns + 2, a + columns + 1))
    obj = part(mesh_object(f"Study_cut_sleeve_{side}", vertices, faces, mats["cloth"]), "arm")
    weld_surface(obj)
    obj.modifiers.new("Sleeve thickness", "SOLIDIFY").thickness = .0025
    cuff_points = vertices[-65:]
    part(stroke("Study_dark_turned_cuff", cuff_points, .003, mats["lining"]), "arm")
    # A narrow same-cloth cuff, without any metal piping.
    cuff_vertices = [p + axis * shift for shift in (-.024, 0) for p in cuff_points]
    cuff_faces = [(i, i + 1, i + 66, i + 65) for i in range(64)]
    part(mesh_object("Study_cuff_facing", cuff_vertices, cuff_faces, mats["lining"]), "arm")


def build_clothes(mats):
    upper = cloth("Study_fitted_cross_robe", TORSO, mats["cloth"], folds=.001)
    for vertex in upper.data.vertices:
        if vertex.co.z > 1.405:
            vertex.co.z = 1.405 + (vertex.co.z - 1.405) * .1
    cloth("Study_weighted_outer_skirt",
          [(.38, .226, .149), (.40, .225, .149), (.58, .215, .143),
           (.76, .189, .129), (.93, .148, .109), (.967, .145, .106)],
          mats["cloth"], opening=.40, folds=.010)
    cloth("Study_inner_ramie_skirt",
          [(.32, .184, .130), (.34, .185, .130), (.56, .173, .122),
           (.78, .158, .112), (.956, .139, .102)],
          mats["linen"], folds=.006)
    vertices, faces = [], []
    for row in range(41):
        t = row / 40
        z = 1.424 - .153 * t
        left, right = -.069 + .059 * t, .069 - .079 * t
        for col in range(25):
            x = left + (right - left) * col / 24
            vertices.append((x, front_y(x, z, .005), z))
            if row < 40 and col < 24:
                a = row * 25 + col
                faces.append((a, a + 1, a + 26, a + 25))
    part(mesh_object("Study_inner_cross_chest", vertices, faces, mats["linen"]))
    under = surface_ribbon("Study_under_cross_facing",
                   [(-.063, 0, 1.422), (-.065, 0, 1.373), (.004, 0, 1.278)],
                   [.033, .038, .016], mats["lining"], offset=.009)
    outer = surface_ribbon("Study_cross_lapel",
                   [(.063, 0, 1.422), (.060, 0, 1.373), (-.008, 0, 1.261),
                    (-.092, 0, 1.095), (-.132, 0, .990)],
                   [.034, .041, .037, .034, .03], mats["lining"], offset=.018)
    for obj, inner_columns in ((under, (0, 1)), (outer, (6, 7))):
        obj.data.materials.append(mats["linen"])
        for polygon in obj.data.polygons:
            if polygon.index % 8 in inner_columns and polygon.center.z > 1.29:
                polygon.material_index = 1
    cloth("Study_soft_wrapped_sash", [(.934, .153, .113), (.942, .155, .114),
                                    (.974, .153, .113), (1.007, .151, .111)],
          mats["sash"], folds=.0015, rows=18)
    part(ribbon("Study_short_sash_end", [(.105, -.096, .976), (.131, -.134, .893),
                                        (.140, -.145, .777), (.121, -.158, .67)],
                [.045, .044, .040, .035], mats["sash"]))
    part(sphere("Study_sash_knot", (.106, -.100, .975), (.022, .016, .023), mats["sash"]))
    for side in (-1, 1):
        build_sleeve(side, mats)
        cloth(f"Study_trouser_{side}",
              [(.19, .039, .043), (.24, .043, .047), (.28, .055, .061), (.44, .066, .071),
               (.62, .072, .073), (.80, .059, .064)],
              mats["trouser"], center=side * .100, folds=.003, region="leg", rows=40)
        cloth(f"Study_soft_boot_{side}",
              [(.057, .053, .063), (.08, .058, .067), (.13, .056, .060),
               (.19, .051, .056), (.242, .049, .053)],
              mats["leather"], center=side * .100, folds=.0014, region="leg", rows=32)
        part(sphere(f"Study_fitted_shoe_{side}", (side * .100, -.047, .048),
                    (.059, .125, .040), mats["leather"]), "leg")
        part(sphere(f"Study_thin_sole_{side}", (side * .100, -.045, .021),
                    (.060, .126, .014), mats["sole"]), "leg")
        for z in (.178, .217):
            points = [(side * .100 + .054 * math.sin(i / 40 * TAU),
                       -.059 * math.cos(i / 40 * TAU), z + .003 * math.sin(i / 40 * TAU))
                      for i in range(41)]
            part(stroke("Study_boot_cloth_binding", points, .0018, mats["sash"]), "leg")
    part(stroke("Study_jade_suspension", [(-.133, -.076, .970), (-.166, -.119, .88),
                                         (-.169, -.145, .815)], .002, mats["sash"]))
    charm = part(sphere("Study_retained_jade_charm", (-.169, -.146, .790),
                        (.020, .008, .030), mats["jade"]))
    charm["identity"] = "Traveler jade charm, restrained non-emissive stone"
    part(stroke("Study_jade_carving", [(-.176, -.154, .803), (-.162, -.1545, .808),
                                      (-.161, -.1545, .786), (-.175, -.154, .779)],
                .00065, mats["jade_dark"]))
    for i in range(7):
        x = -.169 + (i - 3) * .0013
        part(stroke("Study_charm_fringe", [(x, -.146, .761), (x + .003, -.147, .737),
                                         (x + .005, -.146, .724 + .002 * math.sin(i))],
                    .0006, mats["sash"]))
    # The loaded bundle settles against the back, with straps continuing around shoulders.
    pack = part(sphere("Study_loaded_canvas_pack", (.012, .175, 1.159),
                       (.132, .073, .151), mats["pack"]))
    pack.rotation_euler.y = -.065
    roll = part(sphere("Study_compressed_bedroll", (.009, .185, 1.303),
                       (.152, .047, .040), mats["linen"]))
    roll.rotation_euler.y = -.045
    for side in (-1, 1):
        x = side * .127
        points = [(x, front_y(x, z, .012), z) for z in (1.02, 1.10, 1.21, 1.31, 1.38)]
        points += [(side * .140, -.015, 1.390), (side * .135, .065, 1.378),
                   (side * .107, .153, 1.315), (side * .107, .228, 1.244)]
        strap_vertices = [(p[0] + dx, p[1], p[2]) for p in points for dx in (-.010, .010)]
        strap_faces = [(i * 2, i * 2 + 1, i * 2 + 3, i * 2 + 2)
                       for i in range(len(points) - 1)]
        strap = part(mesh_object("Study_loadbearing_pack_strap", strap_vertices,
                                 strap_faces, mats["leather"]))
        bpy.context.view_layer.objects.active = strap
        sub = strap.modifiers.new("Fitted strap sampling", "SUBSURF")
        sub.subdivision_type = "SIMPLE"
        sub.levels = 3
        bpy.ops.object.modifier_apply(modifier=sub.name)
        bpy.context.view_layer.update()
        surface = bpy.data.objects["Study_fitted_cross_robe"]
        for vertex in strap.data.vertices:
            if vertex.co.y < .14:
                found, position, normal, _ = surface.closest_point_on_mesh(vertex.co)
                if not found:
                    raise RuntimeError("Cannot fit study pack strap")
                if normal.dot(Vector((position.x, position.y, 0))) < 0:
                    normal = -normal
                vertex.co = position + normal * .006
        strap.modifiers.new("Strap edge", "SOLIDIFY").thickness = .003
        part(sphere("Study_small_bronze_fastener", (x, front_y(x, 1.18, .017), 1.18),
                    (.009, .003, .012), mats["bronze"]))
        part(stroke("Study_bedroll_binding",
                    [(side * .086, .185 + .0405 * math.cos(i / 40 * TAU),
                      1.303 + .035 * math.sin(i / 40 * TAU)) for i in range(41)],
                    .0022, mats["sash"]))
    for sign in (-1, 1):
        points = []
        for i in range(25):
            t = i / 24
            x, z = .012 + sign * (-.08 + .16 * t), 1.267 - .235 * t
            radial = math.sqrt(max(.01, 1 - ((x - .012) / .132) ** 2
                                    - ((z - 1.159) / .151) ** 2))
            points.append((x, .175 + .073 * radial + .003, z))
        part(stroke("Study_fitted_pack_tie", points, .002, mats["sash"]))


def pose_point(point, region):
    p = point.copy()
    if region == "arm" or (region == "body" and p.z < 1.05 and abs(p.x) > .30):
        side = 1 if p.x > 0 else -1
        pivot = Vector((side * .19, 0, 1.325))
        p = pivot + Matrix.Rotation(side * .13, 3, "Y") @ (p - pivot)
        p.y -= (.025 if side == 1 else .005) * max(0, (1.29 - p.z) / .4)
    if region == "leg":
        side = 1 if p.x > 0 else -1
        t = max(0, min(1, (.87 - p.z) / .75))
        p.x += side * .010 * t
        if side == -1:
            p.y += .049 * t
    if region == "head" or (region == "body" and p.z > 1.405):
        pivot = Vector((0, -.025, 1.44))
        rotated = pivot + Matrix.Rotation(-.075, 3, "Z") @ (
            Matrix.Rotation(.025, 3, "Y") @ (p - pivot))
        t = 1 if region == "head" else min(1, max(0, (p.z - 1.405) / .09))
        p = p.lerp(rotated, t * t * (3 - 2 * t))
    t = max(0, min(1, (p.z - .85) / .75))
    p.x += .018 * t
    p.y += .010 * t
    return p


def fit_neckline(head):
    """Fit upper fabric edges to the actual neck, avoiding intersecting triangles."""
    for name, clearance in (("Study_fitted_cross_robe", .003),
                            ("Study_inner_cross_chest", .005),
                            ("Study_under_cross_facing", .012),
                            ("Study_cross_lapel", .010)):
        obj = bpy.data.objects[name]
        for vertex in obj.data.vertices:
            if vertex.co.y < -.015 and vertex.co.z > 1.37:
                found, position, _, _ = head.ray_cast(
                    Vector((vertex.co.x, -.5, vertex.co.z)), Vector((0, 1, 0)))
                if found:
                    vertex.co.y = min(vertex.co.y, position.y - clearance)
            if vertex.co.z <= 1.415:
                continue
            center = Vector((0, -.025, vertex.co.z))
            radial = (vertex.co - center).normalized()
            found, position, normal, _ = head.ray_cast(center + radial * .5, -radial)
            if not found:
                raise RuntimeError(f"Neckline projection missed: {name} at {tuple(vertex.co)}")
            t = min(1, (vertex.co.z - 1.415) / .006)
            target = position + radial * clearance
            vertex.co = vertex.co.lerp(target, t * t * (3 - 2 * t))
        obj.data.update()


def neck_facing(head, mats):
    """Continue the crossed facing around the neck without exposed cut-off ends."""
    vertices, faces = [], []
    segments = 80
    for row in range(9):
        t = row / 8
        z = 1.398 + .028 * t
        for col in range(segments + 1):
            angle = .91 + (TAU - 1.82) * col / segments
            radial = Vector((math.sin(angle), -math.cos(angle), 0))
            center = Vector((0, -.025, 1.422))
            found, point, _, _ = head.ray_cast(center + radial * .5, -radial)
            if not found:
                raise RuntimeError("Back-neck facing missed head")
            p = point + radial * (.007 + .004 * (1 - t))
            rx, ry = interpolate(TORSO, z)
            shoulder = Vector(((rx + .003) * math.sin(angle),
                               -(ry + .003) * math.cos(angle), z))
            p = shoulder.lerp(p, t * t * (3 - 2 * t))
            p.z = z
            vertices.append(p)
            if row < 8 and col < segments:
                a = row * (segments + 1) + col
                faces.append((a, a + 1, a + segments + 2, a + segments + 1))
    obj = part(mesh_object("Study_continuous_back_neck_facing", vertices, faces, mats["lining"]))
    obj.data.materials.append(mats["linen"])
    for polygon in obj.data.polygons:
        if polygon.index // segments >= 7:
            polygon.material_index = 1
    obj.modifiers.new("Collar fold thickness", "SOLIDIFY").thickness = .0015


def bake_study_pose():
    """Bake only the study's mild weight shift; remove no original modifiers."""
    for i, obj in enumerate(PARTS):
        region = obj["study_pose_region"]
        if obj.name == "Study_fitted_cross_robe" or obj.name.startswith("Study_cut_sleeve_"):
            obj.modifiers.clear()
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.convert(target="MESH")
        obj = bpy.context.object
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        for vertex in obj.data.vertices:
            vertex.co = pose_point(vertex.co, region)
        obj.data.update()
        obj["pose_status"] = "Static baked study; not skinned or animation validated"
        PARTS[i] = obj
    bpy.ops.object.select_all(action="DESELECT")


def join_upper_garment():
    """Unify overlapping volumes into one continuous shoulder/armpit surface."""
    upper = bpy.data.objects["Study_fitted_cross_robe"]
    sleeves = [bpy.data.objects[f"Study_cut_sleeve_{side}"] for side in (-1, 1)]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in [upper, *sleeves]:
        mesh = bmesh.new()
        mesh.from_mesh(obj.data)
        bmesh.ops.holes_fill(mesh, edges=[e for e in mesh.edges if e.is_boundary], sides=0)
        bmesh.ops.recalc_face_normals(mesh, faces=list(mesh.faces))
        mesh.to_mesh(obj.data)
        mesh.free()
        obj.select_set(True)
    for sleeve in sleeves:
        PARTS.remove(sleeve)
    bpy.context.view_layer.objects.active = upper
    bpy.ops.object.join()
    upper.data.remesh_voxel_size = .0025
    bpy.ops.object.voxel_remesh()
    shoulder = upper.vertex_groups.new(name="Shoulder_transition")
    for vertex in upper.data.vertices:
        x, _, z = vertex.co
        weight = math.exp(-((abs(x) - .205) / .065) ** 2 - ((z - 1.275) / .065) ** 2)
        if weight > .01:
            shoulder.add([vertex.index], weight, "REPLACE")
    blend = upper.modifiers.new("Shoulder slope relaxation", "SMOOTH")
    blend.vertex_group = shoulder.name
    blend.factor = 1
    blend.iterations = 35
    bpy.ops.object.modifier_apply(modifier=blend.name)
    smooth = upper.modifiers.new("Continuous cloth transition", "SMOOTH")
    smooth.factor = .8
    smooth.iterations = 5
    bpy.ops.object.modifier_apply(modifier=smooth.name)
    for vertex in upper.data.vertices:
        x, y, z = vertex.co
        if y < -.025 and 1.01 < z < 1.29 and abs(x) < .20:
            diagonal = z - (1.03 + .92 * abs(x))
            fade = math.exp(-((abs(x) - .15) / .065) ** 2)
            fold = .0025 * math.exp(-(diagonal / .020) ** 2) * fade
            fold -= .0015 * math.exp(-((diagonal - .020) / .015) ** 2) * fade
            vertex.co.y -= fold
    for polygon in upper.data.polygons:
        polygon.use_smooth = True
    upper.data.update()
    upper["construction"] = "Single connected remeshed torso/sleeves; baked static clothing volume"
    upper.select_set(False)


def point_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def make_stage():
    scene = bpy.data.scenes.new("Traveler_Study_Studio")
    bpy.context.window.scene = scene
    world = bpy.data.worlds.new("Study_earth_studio_world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (.16, .145, .125, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = .28
    scene.world = world
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.use_gtao = True
    scene.eevee.gtao_distance = .12
    scene.eevee.gtao_factor = 1.12
    scene.eevee.use_soft_shadows = True
    scene.eevee.taa_render_samples = 128
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGB"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    floor = material("earth_backdrop", (.12, .105, .086), .93, noise=.018, bump=.0001)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, .006))
    bpy.context.object.name = "Study_ground_contact"
    bpy.context.object.data.materials.append(floor)
    for name, position, energy, size, color in (
        ("key", (-2.7, -3.4, 4.0), 370, 2.4, (1, .88, .75)),
        ("fill", (2.6, -2.2, 2.3), 125, 2.8, (.79, .86, 1)),
        ("rim", (1.5, 1.6, 3.2), 260, 1.8, (1, .91, .79)),
    ):
        bpy.ops.object.light_add(type="AREA", location=position)
        obj = bpy.context.object
        obj.name = "Study_" + name
        obj.data.energy = energy
        obj.data.shape = "DISK"
        obj.data.size = size
        obj.data.color = color
        obj.data.use_shadow = True
        obj.data.use_contact_shadow = True
        point_at(obj, (0, 0, 1.1))
    for name, location, target, scale in (
        ("full", (2.2, -5.8, 2.25), (0, 0, .90), 2.02),
        ("half", (1.0, -4.8, 1.98), (0, -.01, 1.385), .89),
        ("rear", (-2.6, 5, 2.3), (0, 0, .90), 2.02),
    ):
        bpy.ops.object.camera_add(location=location)
        cam = bpy.context.object
        cam.name = "Study_camera_" + name
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = scale
        cam.data.lens = 75
        point_at(cam, target)
    return scene


def render(scene, camera, filename):
    scene.camera = bpy.data.objects["Study_camera_" + camera]
    scene.render.resolution_x = 1200 if camera == "half" else 1080
    scene.render.resolution_y = 1500
    scene.render.filepath = str(RENDERS / filename)
    bpy.ops.render.render(write_still=True)
    print("STUDY_RENDER", scene.render.filepath, flush=True)


def contact_sheet(prefix="traveler_study", names=None):
    """Montage matching-lighting comparisons without postprocessing."""
    width, height, tile_width = 2400, 840, 600
    pixels = np.empty((height, width, 4), dtype=np.float32)
    pixels[:] = (.035, .031, .026, 1)
    if names is None:
        names = tuple(f"{prefix}_{name}.png" for name in ("before_full", "full", "before_half", "half"))
    for column, name in enumerate(names):
        image = bpy.data.images.load(str(RENDERS / name),
                                     check_existing=False)
        tile_height = round(tile_width * image.size[1] / image.size[0])
        image.scale(tile_width, tile_height)
        data = np.empty(tile_width * tile_height * 4, dtype=np.float32)
        image.pixels.foreach_get(data)
        y = (height - tile_height) // 2
        pixels[y:y + tile_height, column * tile_width:(column + 1) * tile_width] = (
            data.reshape(tile_height, tile_width, 4))
        bpy.data.images.remove(image)
    sheet = bpy.data.images.new("Study_comparison_sheet", width, height)
    sheet.pixels.foreach_set(pixels.ravel())
    sheet.filepath_raw = str(RENDERS / f"{prefix}_contact_sheet.png")
    sheet.file_format = "PNG"
    sheet.save()
    bpy.data.images.remove(sheet)


def compare_reload(prefix="traveler_study"):
    """Allow subpixel Eevee variation, but reject visible saved-scene changes."""
    arrays = []
    for name in (f"{prefix}_half.png", f"{prefix}_reload_half.png"):
        image = bpy.data.images.load(str(RENDERS / name), check_existing=False)
        if tuple(image.size) != (1200, 1500):
            raise RuntimeError(f"Wrong reload proof dimensions: {name}")
        pixels = np.empty(1200 * 1500 * 4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        arrays.append(pixels.reshape(-1, 4)[:, :3])
        bpy.data.images.remove(image)
    difference = np.abs(arrays[0] - arrays[1]) * 255
    result = {"mean_absolute_8bit": float(difference.mean()),
              "p99_absolute_8bit": float(np.percentile(difference, 99)),
              "maximum_absolute_8bit": float(difference.max()),
              "mean_limit_8bit": .1, "p99_limit_8bit": 1}
    if result["mean_absolute_8bit"] > .1 or result["p99_absolute_8bit"] > 1:
        raise RuntimeError(f"Saved render differs visibly: {result}")
    return result


def validate(scene, original, original_camera):
    """Fail explicitly on geometry, rig, resource or full-body framing defects."""
    from bpy_extras.object_utils import world_to_camera_view

    if original.camera.name != original_camera:
        raise RuntimeError("Original cinematic camera changed")
    totals = {"study_meshes": 0, "study_vertices": 0, "original_weighted_vertices": 0}
    scene.camera = bpy.data.objects["Study_camera_full"]
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1500
    bpy.context.view_layer.update()
    margins = [1.0, 1.0, 0.0, 0.0]
    for obj in PARTS:
        if obj.type != "MESH" or any(m.type == "ARMATURE" for m in obj.modifiers):
            raise RuntimeError(f"Unexpected unbaked study object: {obj.name}")
        totals["study_meshes"] += 1
        totals["study_vertices"] += len(obj.data.vertices)
        for vertex in obj.data.vertices:
            point = obj.matrix_world @ vertex.co
            if not all(math.isfinite(v) for v in point):
                raise RuntimeError(f"Nonfinite geometry: {obj.name}")
            projected = world_to_camera_view(scene, scene.camera, point)
            margins = [min(margins[0], projected.x), min(margins[1], projected.y),
                       max(margins[2], projected.x), max(margins[3], projected.y)]
            if not (.035 < projected.x < .965 and .035 < projected.y < .965 and projected.z > 0):
                raise RuntimeError(f"Full-body framing clips {obj.name}")
    if totals["study_vertices"] > 600000:
        raise RuntimeError(f"Study exceeds offline mesh budget: {totals}")
    upper = bmesh.new()
    upper.from_mesh(bpy.data.objects["Study_fitted_cross_robe"].data)
    pending = set(upper.verts)
    component_sizes = []
    while pending:
        stack = [pending.pop()]
        size = 0
        while stack:
            vertex = stack.pop()
            size += 1
            for edge in vertex.link_edges:
                neighbor = edge.other_vert(vertex)
                if neighbor in pending:
                    pending.remove(neighbor)
                    stack.append(neighbor)
        component_sizes.append(size)
    nonmanifold = sum(not edge.is_manifold for edge in upper.edges)
    upper.free()
    if len(component_sizes) != 1 or nonmanifold:
        raise RuntimeError(f"Disconnected/nonmanifold upper garment: {component_sizes}, {nonmanifold}")
    totals["upper_garment_connected_components"] = len(component_sizes)
    totals["upper_garment_vertices"] = component_sizes[0]
    totals["upper_garment_nonmanifold_edges"] = nonmanifold
    for obj in original.objects:
        armatures = [m for m in obj.modifiers if m.type == "ARMATURE"]
        if not armatures:
            continue
        if any(m.object is None for m in armatures):
            raise RuntimeError(f"Missing preserved armature: {obj.name}")
        for vertex in obj.data.vertices:
            total = sum(g.weight for g in vertex.groups)
            if abs(total - 1) > .0001:
                raise RuntimeError(f"Invalid preserved skin weights: {obj.name}")
            totals["original_weighted_vertices"] += 1
    missing = [image.name for image in bpy.data.images
               if image.source == "FILE" and not image.packed_file
               and not Path(bpy.path.abspath(image.filepath)).is_file()]
    if missing:
        raise RuntimeError(f"Missing external image resources: {missing}")
    totals["full_body_normalized_bounds"] = margins
    totals["study_armature_modifiers"] = 0
    totals["pose"] = "Static baked pose; animation readiness not claimed"
    return totals


def ornate_surface(name, target, predicate, mat, clearance=.002, radial_origin=None):
    """Lift selected exterior faces from accepted clothing, preserving its fit."""
    vertices, faces, remap = [], [], {}
    for polygon in target.data.polygons:
        center = polygon.center
        if not predicate(center):
            continue
        radial = center - radial_origin if radial_origin is not None else Vector((center.x, center.y, 0))
        if polygon.normal.dot(radial) <= 0:
            continue
        face = []
        for index in polygon.vertices:
            if index not in remap:
                remap[index] = len(vertices)
                vertex = target.data.vertices[index]
                vertices.append(vertex.co + vertex.normal * clearance)
            face.append(remap[index])
        faces.append(face)
    if not faces:
        raise RuntimeError(f"Empty fitted ornate panel: {name}")
    obj = part(mesh_object(name, vertices, faces, mat))
    editable = bmesh.new()
    editable.from_mesh(obj.data)
    if target.name == "Study_weighted_outer_skirt":
        bmesh.ops.subdivide_edges(editable, edges=list(editable.edges), cuts=2, use_grid_fill=True)
    boundary = [v for v in editable.verts if any(e.is_boundary for e in v.link_edges)]
    for _ in range(12):
        positions = {}
        for vertex in boundary:
            neighbors = [e.other_vert(vertex).co for e in vertex.link_edges if e.is_boundary]
            if neighbors:
                positions[vertex] = vertex.co.lerp(sum(neighbors, Vector()) / len(neighbors), .65)
        for vertex, position in positions.items():
            vertex.co = position
    editable.to_mesh(obj.data)
    editable.free()
    for vertex in obj.data.vertices:
        found, position, normal, _ = target.closest_point_on_mesh(vertex.co)
        if not found:
            raise RuntimeError(f"Cannot conform smoothed panel: {name}")
        vertex.co = position + normal * clearance
    obj.data.update()
    obj["ornate_support"] = target.name
    obj["ornate_clearance_m"] = clearance
    obj.modifiers.new("Fine turned panel edge", "SOLIDIFY").thickness = .001
    return obj


def ornate_stitches(name, support, paths, mat, width=.0009):
    """Lay flat thread strips on actual cloth, not bright tubular gold wire."""
    bpy.context.view_layer.update()
    vertices, faces = [], []
    for path in paths:
        samples = []
        for a, b in zip(path, path[1:]):
            for j in range(4):
                samples.append(Vector(a).lerp(Vector(b), j / 4))
        samples.append(Vector(path[-1]))
        for i, point in enumerate(samples):
            found, position, normal, _ = support.closest_point_on_mesh(point)
            if not found:
                raise RuntimeError(f"Embroidery missed {support.name}")
            tangent = samples[min(i + 1, len(samples) - 1)] - samples[max(0, i - 1)]
            across = normal.cross(tangent).normalized()
            if across.length < .5:
                raise RuntimeError(f"Degenerate embroidery tangent: {name}")
            start = len(vertices)
            for sign in (-1, 1):
                sample = position + across * sign * width / 2
                hit, surface, normal, _ = support.closest_point_on_mesh(sample)
                if not hit:
                    raise RuntimeError(f"Thread edge missed {support.name}")
                vertices.append(surface + normal * .0016)
            if i:
                faces.append((start - 2, start, start + 1, start - 1))
    obj = part(mesh_object(name, vertices, faces, mat))
    obj["ornate_support"] = support.name
    obj["ornate_flat_thread"] = True
    return obj


def ornate_radial_panel(name, target, z_limits, angles, mat, clearance=.002):
    """Fit clean cut lines by ray sampling instead of selecting coarse face rows."""
    vertices, faces = [], []
    rows, columns = 49, max(12, round((angles[1] - angles[0]) * 60))
    for row in range(rows):
        z = z_limits[0] + (z_limits[1] - z_limits[0]) * row / (rows - 1)
        center = pose_point(Vector((0, 0, z)), "body")
        for col in range(columns + 1):
            angle = angles[0] + (angles[1] - angles[0]) * col / columns
            radial = Vector((math.sin(angle), -math.cos(angle), 0))
            found, position, normal, _ = target.ray_cast(center + radial * .8, -radial)
            if not found:
                raise RuntimeError(f"Fitted panel misses support: {name}, {z}, {angle}")
            vertices.append(position + normal * clearance)
            if row < rows - 1 and col < columns:
                a = row * (columns + 1) + col
                faces.append((a, a + 1, a + columns + 2, a + columns + 1))
    obj = part(mesh_object(name, vertices, faces, mat))
    if angles[1] - angles[0] == TAU:
        weld_surface(obj)
    obj.modifiers.new("Fine turned edge", "SOLIDIFY").thickness = .001
    obj["ornate_support"] = target.name
    obj["ornate_clearance_m"] = clearance
    return obj


def ornate_box(name, location, scale, mat, bevel=.006):
    """A softly constructed leather/metal form instead of spherical ornaments."""
    bpy.ops.mesh.primitive_cube_add(size=2, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    edge = obj.modifiers.new("Rounded worked edge", "BEVEL")
    edge.width = bevel
    edge.segments = 3
    obj.modifiers.new("Weighted broad faces", "WEIGHTED_NORMAL")
    return part(obj)


def build_ornate_details():
    """Enrich the accepted baked study with a small hierarchy of fitted layers."""
    mats = {
        "mantle": material("ornate_deep_teal_silk", (.030, .073, .068), .65,
                           noise=.04, bump=.00015, sheen=.18),
        "red": material("ornate_madder_cotton", (.115, .034, .025), .86,
                       noise=.045, bump=.0002),
        "band": material("ornate_indigo_bands", (.026, .050, .062), .83,
                        noise=.05, bump=.0002),
        "thread": material("ornate_flax_embroidery", (.37, .275, .125), .90,
                          noise=.045, bump=.00005),
        "leather": bpy.data.materials["Study_worn_walnut_leather"],
        "bronze": bpy.data.materials["Study_aged_bronze"],
        "jade": bpy.data.materials["Study_soft_jade"],
        "linen": bpy.data.materials["Study_undyed_ramie"],
    }
    for key in ("red", "band"):
        add_weave(mats[key])
    upper = bpy.data.objects["Study_fitted_cross_robe"]
    mantle = ornate_surface("Ornate_split_shoulder_mantle", upper,
        lambda p: 1.297 + .021 * math.tanh((p.x - .01) / .04) < p.z < 1.405
        and (p.y > .01 or abs(p.x - .01) > .102), mats["mantle"], .003)
    mantle_band = ornate_surface("Ornate_mantle_woven_border", mantle,
        lambda p: p.z < 1.319 + .021 * math.tanh((p.x - .01) / .04), mats["band"], .0012)
    paths = []
    for side in (-1, 1):
        z = 1.287 if side < 0 else 1.329
        for i in range(5):
            x = side * (.12 + i * .016) + .01
            paths.append([(x - .006, -.13, z), (x, -.14, z + .006),
                          (x + .006, -.13, z), (x, -.14, z - .006),
                          (x - .006, -.13, z)])
    ornate_stitches("Ornate_mantle_flat_lozenges", mantle_band, paths, mats["thread"], .0008)

    for name in ("Study_cross_lapel", "Study_under_cross_facing"):
        obj = bpy.data.objects[name]
        obj.data.materials[0] = mats["red"]
    lapel = bpy.data.objects["Study_cross_lapel"]
    paths = []
    for i in range(12):
        z = 1.07 + i * .023
        centers = [p.center for p in lapel.data.polygons if p.material_index == 0
                   and p.normal.y < -.3 and abs(p.center.z - z) < .004]
        if not centers:
            raise RuntimeError(f"No front lapel surface at height {z}")
        center = sum(centers, Vector()) / len(centers)
        paths.append([center + Vector((-.004, -.003, -.002)),
                      center + Vector((0, -.003, .003)),
                      center + Vector((.004, -.003, -.002))])
    ornate_stitches("Ornate_lapel_wheat_stitches", lapel, paths, mats["thread"], .00075)

    skirt = bpy.data.objects["Study_weighted_outer_skirt"]
    hem = ornate_radial_panel("Ornate_weighted_hem_band", skirt,
                              (.395, .445), (.43, TAU - .43), mats["band"], .003)
    ornate_radial_panel("Ornate_robe_overlap_panel", skirt,
                        (.49, .935), (-.68, -.43), mats["red"], .0025)
    paths = []
    for i in range(24):
        theta = .51 + (TAU - 1.02) * i / 23
        paths.append([Vector((.225 * math.sin(theta + a),
                              -.15 * math.cos(theta + a), .42 + z))
                      for a, z in ((-.026, -.007), (-.026, .007), (0, .007),
                                   (0, -.007), (.026, -.007), (.026, .007))])
    ornate_stitches("Ornate_hem_meander_weave", hem, paths, mats["thread"], .001)
    for obj in [o for o in bpy.context.scene.objects if o.name.startswith("Study_cuff_facing")]:
        obj.hide_render = True
        obj.hide_viewport = True
        side = 1 if sum(v.co.x for v in obj.data.vertices) > 0 else -1
        axis = Vector((.55 * side, -.1, -.83)).normalized()
        center = Vector((side * .350, -.052, .989))
        posed_center = pose_point(center, "arm")
        posed_axis = (pose_point(center + axis * .05, "arm") - posed_center).normalized()
        cuff = ornate_surface(f"Ornate_fitted_cuff_band_{side}", upper,
            lambda p: (p - posed_center).length < .14
            and -.031 < (p - posed_center).dot(posed_axis) < -.002,
            mats["red"], .0018, radial_origin=posed_center)
        paths = []
        front = [p.center for p in cuff.data.polygons if p.normal.y < -.5]
        if not front:
            raise RuntimeError("No outward cuff surface for embroidery")
        low, high = min(p.x for p in front), max(p.x for p in front)
        centers = []
        for i in range(7):
            x = low + (high - low) * (.12 + .76 * i / 6)
            nearby = sorted(front, key=lambda p: abs(p.x - x))[:12]
            centers.append(sum(nearby, Vector()) / len(nearby))
        for i, center_point in enumerate(centers):
            tangent = (centers[min(i + 1, 6)] - centers[max(0, i - 1)]).normalized()
            paths.append([center_point - tangent * .0035,
                          center_point + posed_axis * .004,
                          center_point + tangent * .0035])
        ornate_stitches(f"Ornate_cuff_flat_clouds_{side}", cuff, paths, mats["thread"], .0009)

    sash = bpy.data.objects["Study_soft_wrapped_sash"]
    sash.data.materials[0] = mats["red"]
    bpy.data.objects["Study_short_sash_end"].data.materials[0] = mats["red"]
    bpy.data.objects["Study_sash_knot"].hide_render = True
    bpy.data.objects["Study_sash_knot"].hide_viewport = True
    ornate_radial_panel("Ornate_structured_waist_belt", sash,
                        (.957, .982), (0, TAU), mats["leather"], .002)
    location = pose_point(Vector((.008, -.121, .969)), "body")
    ornate_box("Ornate_aged_bronze_fastening", location, (.024, .004, .014),
               mats["bronze"], .004)
    ornate_box("Ornate_buckle_recess", location + Vector((0, -.0045, 0)),
               (.015, .001, .008), mats["leather"], .002)
    part(stroke("Ornate_buckle_tongue", [location + Vector((-.015, -.006, 0)),
                                        location + Vector((.009, -.006, 0))],
                .0011, mats["bronze"]))
    pouch = ornate_box("Ornate_belt_pouch",
                       pose_point(Vector((.178, -.035, .872)), "body"),
                       (.037, .027, .047), mats["leather"], .012)
    ornate_box("Ornate_pouch_folded_flap", pouch.location + Vector((0, -.026, .018)),
               (.038, .006, .023), mats["leather"], .007)
    for x in (.155, .180):
        points = [pose_point(Vector(p), "body") for p in
                  ((x - .015, -.061, .975), (x, -.059, .94), (x, -.060, .91))]
        found, position, normal, _ = sash.closest_point_on_mesh(points[0])
        if not found:
            raise RuntimeError("Pouch suspension missed waist sash")
        points[0] = position + normal * .003
        part(ribbon("Ornate_pouch_suspension", points, [.010] * 3, mats["leather"]))
    part(sphere("Ornate_pouch_bronze_stud", pouch.location + Vector((0, -.033, .016)),
                (.004, .002, .004), mats["bronze"]))
    for index in range(2):
        x = -.129 - index * .040
        top = pose_point(Vector((x, .228, 1.313 - index * .033)), "body")
        bottom = top - Vector((0, 0, .235))
        part(stroke("Ornate_scroll_case", [bottom, top], .017, mats["leather"]))
        part(sphere("Ornate_scroll_paper_end", top, (.015, .015, .003), mats["linen"]))
        for z in (top.z - .032, bottom.z + .03):
            part(stroke("Ornate_scroll_tie", [(top.x + .019 * math.sin(i / 32 * TAU),
                                               top.y + .019 * math.cos(i / 32 * TAU), z)
                                              for i in range(33)], .0014, mats["red"]))
    for z in (1.11, 1.26):
        part(stroke("Ornate_pack_scroll_retainer",
                    [pose_point(Vector(p), "body") for p in
                     ((-.08, .225, z), (-.13, .259, z), (-.173, .244, z),
                      (-.17, .187, z), (-.10, .182, z))], .003, mats["leather"]))
    for x in (-.083, .095):
        part(sphere("Ornate_pack_rivet", pose_point(Vector((x, .229, 1.25)), "body"),
                    (.004, .002, .004), mats["bronze"]))
    bpy.ops.mesh.primitive_torus_add(major_segments=32, minor_segments=8,
        location=(-.169, -.149, .824), rotation=(math.pi / 2, 0, 0),
        major_radius=.005, minor_radius=.001)
    ring = bpy.context.object
    ring.name = "Ornate_jade_suspension_ring"
    ring.data.materials.append(mats["bronze"])
    part(ring)
    for z in (.752, .743):
        part(sphere("Ornate_charm_cord_bead", (-.169, -.146, z),
                    (.003, .003, .003), mats["red"]))
    part(sphere("Ornate_hairpin_jade_end", pose_point(Vector((.063, .057, 1.734)), "head"),
                (.008, .004, .004), mats["jade"]))
    hair_ribbon = part(ribbon("Ornate_short_hair_ribbon",
                [pose_point(Vector(p), "head") for p in
                 ((.023, .081, 1.732), (.04, .126, 1.666), (.033, .126, 1.595))],
                [.010, .015, .012], mats["red"]))
    hair_ribbon.modifiers.new("Soft ribbon drape", "SUBSURF").levels = 2


def validate_ornate_supports(objects):
    """Check exterior layer/thread faces against their actual supporting mesh."""
    results = {}
    for obj in objects:
        if not obj.get("ornate_support"):
            continue
        target = bpy.data.objects[obj["ornate_support"]]
        distances = []
        for polygon in obj.data.polygons:
            found, position, normal, _ = target.closest_point_on_mesh(polygon.center)
            if not found:
                raise RuntimeError(f"Lost support surface for {obj.name}")
            if polygon.normal.dot(normal) > .5:
                distances.append((polygon.center - position).dot(normal))
        if not distances or min(distances) < -.0001:
            raise RuntimeError(f"Ornate layer penetrates support: {obj.name}, {min(distances) if distances else 'no exterior faces'}")
        results[obj.name] = {"outward_faces": len(distances), "minimum_clearance_m": min(distances)}
    return results


def ornate_main():
    """Load the accepted simple study; never regenerate or overwrite it."""
    output = HERE / "FirstShot_TravelerOrnate.blend"
    source = ROOT / "assets" / "source" / "characters" / "player_traveler_rigged.blend"
    preserved = [source, HERE / "refine_traveler_costume.py"]
    preserved += [p for p in HERE.glob("*.blend") if p != output]
    preserved += [p for p in RENDERS.iterdir() if p.is_file()
                  and not p.name.startswith("traveler_ornate_")]
    before = {str(p.relative_to(ROOT)): digest(p) for p in preserved}
    expected = {
        HERE / "FirstShot_TravelerStudy.blend": "C4C35AE0FE987FEDE8C2C4E976287DB90E7B2BCA4B72D1B4273F362ECB4FE32F",
        RENDERS / "traveler_study_half.png": "48B3DAF4D520CDEA3B767E1BF62D7F55FCA97C7297F678F14BA286E3614AA255",
        RENDERS / "traveler_study_full.png": "E9605DB8F2B3F7BD5D6262527B44AF1DBBAD7F55E2D8FF3C0D9D8477821E9016",
        RENDERS / "mortal_ascension_clipchamp.mp4": "E01E645DAC8248F959195639A1E9EEF92B55FE0D4647643F1E5D4F4DBD811469",
        source: SOURCE_HASH,
    }
    for path, expected_hash in expected.items():
        if digest(path) != expected_hash:
            raise RuntimeError(f"Accepted input fingerprint changed: {path.name}")
    bpy.ops.wm.open_mainfile(filepath=str(HERE / "FirstShot_TravelerStudy.blend"))
    scene = bpy.context.scene
    original = next(s for s in bpy.data.scenes if s.camera and s.camera.name == "CAM_ValleyReveal")
    original_name, original_camera = original.name, original.camera.name
    base_parts = list(bpy.data.collections["Study_editable_baked_character"].objects)
    PARTS.clear()
    build_ornate_details()
    extras = bpy.data.collections.new("Ornate_fitted_layers_and_craft")
    scene.collection.children.link(extras)
    for index, obj in enumerate(PARTS):
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.convert(target="MESH")
        obj = bpy.context.object
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        obj["pose_status"] = "Static fitted overlay on accepted baked study"
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        extras.objects.link(obj)
        PARTS[index] = obj
    extras_count = len(PARTS)
    attachment_checks = validate_ornate_supports(PARTS)
    PARTS.extend(base_parts)
    evidence = validate(scene, original, original_camera)
    for name in ("full", "half", "rear"):
        render(scene, name, f"traveler_ornate_{name}.png")
    bpy.ops.object.camera_add(location=(.8, -4, 1.42))
    detail = bpy.context.object
    detail.name = "Study_camera_craft"
    detail.data.type = "ORTHO"
    detail.data.ortho_scale = .54
    point_at(detail, (0, -.05, 1.03))
    render(scene, "craft", "traveler_ornate_craft.png")
    contact_sheet("traveler_ornate", ("traveler_study_full.png", "traveler_ornate_full.png",
                                     "traveler_study_half.png", "traveler_ornate_half.png"))
    bpy.ops.file.pack_all()
    scene.camera = bpy.data.objects["Study_camera_half"]
    scene.render.resolution_x, scene.render.resolution_y = 1200, 1500
    scene.render.filepath = str(RENDERS / "traveler_ornate_half.png")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    bpy.ops.wm.open_mainfile(filepath=str(output))
    if bpy.data.scenes[original_name].camera.name != original_camera:
        raise RuntimeError("Ornate scene did not preserve the cinematic camera")
    render(bpy.context.scene, "half", "traveler_ornate_reload_half.png")
    difference = compare_reload("traveler_ornate")
    after = {str(p.relative_to(ROOT)): digest(p) for p in preserved}
    if before != after:
        raise RuntimeError("Ornate generation changed a preserved file")
    evidence.update({"variant": "ornate", "ornate_detail_objects": extras_count,
                     "surface_attachment_checks": attachment_checks,
                     "preserved_hashes": after, "accepted_fingerprints_verified": True,
                     "reload_verified": True, "reload_half_pixel_difference": difference,
                     "comparison_columns": ["accepted simple full", "ornate full",
                                             "accepted simple half", "ornate half"],
                     "lighting": "Unchanged accepted studio cameras, lights, world and exposure",
                     "limitations": ["Static baked pose, not animation-ready",
                                     "Procedural tailoring and flat-thread motifs, not final hero art"],
                     "outputs": [p.name for p in RENDERS.glob("traveler_ornate_*.png")]})
    (RENDERS / "traveler_ornate_evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("ORNATE_VERIFIED", json.dumps({k: v for k, v in evidence.items() if k != "preserved_hashes"}), flush=True)


def reference_face_point(point, ocular=False):
    """Edit measured source landmarks; hood skin over round ocular components."""
    p = point.copy()
    if p.z < 1.46:
        return p
    x, y, z = p
    settings = REFERENCE_FACE_TARGETS
    jaw = math.exp(-((z - 1.491) / .034) ** 2)
    cheek = math.exp(-((z - 1.560) / .035) ** 2)
    forehead = math.exp(-((z - 1.663) / .048) ** 2)
    p.x *= 1 + settings["jaw_width_gain"] * jaw + settings["cheek_width_gain"] * cheek
    p.x *= 1 + settings["forehead_width_gain"] * forehead
    front = min(1, max(0, (-y - .065) / .065))
    nose = math.exp(-(x / .023) ** 2)
    p.x *= 1 + settings["nose_width_gain"] * nose * math.exp(-((z - 1.547) / .025) ** 2) * front
    p.y -= front * nose * (
        settings["nose_bridge_projection_m"] * math.exp(-((z - 1.578) / .026) ** 2)
        + settings["nose_tip_projection_m"] * math.exp(-((z - 1.547) / .013) ** 2))
    p.y -= front * settings["cheek_plane_projection_m"] * math.exp(
        -((abs(x) - .060) / .022) ** 2 - ((z - 1.567) / .020) ** 2)
    p.y += front * settings["subcheek_recession_m"] * math.exp(
        -((abs(x) - .054) / .024) ** 2 - ((z - 1.528) / .020) ** 2)
    p.z -= settings["chin_extension_m"] * math.exp(-((z - 1.478) / .021) ** 2) * front
    p.y -= .003 * jaw * math.exp(-(x / .031) ** 2) * front
    eye = math.exp(-((abs(x) - .034) / .023) ** 2 - ((z - 1.592) / .018) ** 2)
    p.x += math.copysign(1, x) * (abs(x) - .034) * settings["eye_horizontal_gain"] * eye
    if not ocular:
        p.z += (z - 1.592) * settings["eye_vertical_gain"] * eye
        socket = math.exp(-((abs(x) - .034) / .023) ** 2)
        hood = math.exp(-((z - 1.601) / .006) ** 2) * socket * front
        p.y -= .0025 * hood
        p.z -= .0014 * hood
        p.y -= settings["lower_lid_volume_m"] * socket * front * math.exp(-((z - 1.582) / .0045) ** 2)
    p.y -= settings["lip_projection_m"] * front * math.exp(-(x / .030) ** 4 - ((z - 1.514) / .010) ** 2)
    p.y += .0025 * front * math.exp(-(x / .004) ** 2 - ((z - 1.528) / .007) ** 2)
    p.y -= .002 * front * math.exp(-((abs(x) - .006) / .003) ** 2 - ((z - 1.527) / .006) ** 2)
    cupid = front * math.exp(-((abs(x) - .009) / .006) ** 2 - ((z - 1.515) / .005) ** 2)
    p.z += .002 * cupid
    p.y -= .0025 * cupid
    lower_lip = front * math.exp(-(x / .026) ** 4 - ((z - 1.501) / .006) ** 2)
    p.y -= settings["lower_lip_fullness_m"] * lower_lip
    p.z -= .0012 * lower_lip
    alae = front * math.exp(-((abs(x) - .018) / .007) ** 2 - ((z - 1.542) / .007) ** 2)
    p.x += math.copysign(settings["alar_flare_m"] * alae, x)
    p.y -= .0025 * alae
    p.y -= settings["brow_ridge_projection_m"] * front * math.exp(
        -((abs(x) - .037) / .030) ** 2 - ((z - 1.614) / .012) ** 2)
    return p


def build_reference_face():
    """Author an approximate mature face and swept-back groom; never use photo pixels."""
    mats = {
        "skin": material("portrait_natural_skin", (.47, .270, .175), .55, bump=.00012),
        "eye": bpy.data.materials["Study_warm_sclera"],
        "iris": bpy.data.materials["Study_brown_iris"],
        "pupil": bpy.data.materials["Study_pupil"],
        "brow": material("portrait_dark_brows", (.009, .007, .005), .78, bump=.00005),
        "hair": material("portrait_black_hair", (.006, .0065, .007), .62, noise=.04, bump=.00008),
        "fiber": material("portrait_hair_fiber", (.010, .011, .012), .55, noise=.04, bump=0),
        "tie": material("portrait_muted_red_tie", (.13, .025, .019), .82, bump=.0001),
    }
    head = build_anatomy(bpy.data.objects["Traveler_Skinned_Appearance"], mats)
    head.name = "Portrait_reference_face_and_hands"
    editable = bmesh.new()
    editable.from_mesh(head.data)
    bmesh.ops.delete(editable, geom=[f for f in editable.faces if f.material_index == 4], context="FACES")
    editable.to_mesh(head.data)
    editable.free()
    raw = [v.co.copy() for v in head.data.vertices]
    iris_indices = {i for p in head.data.polygons if p.material_index == 2 for i in p.vertices}
    ocular_indices = {i for p in head.data.polygons if p.material_index in (1, 2, 3) for i in p.vertices}
    for vertex in head.data.vertices:
        vertex.co = reference_face_point(vertex.co, vertex.index in ocular_indices)
    colors = head.data.color_attributes["SkinTone"]
    lip_mask = head.data.color_attributes.new(name="PortraitLipMask", type="FLOAT_COLOR", domain="POINT")
    for vertex, color in zip(head.data.vertices, colors.data):
        x, y, z = vertex.co
        cheek = math.exp(-((abs(x) - .065) / .03) ** 2 - ((z - 1.560) / .023) ** 2) if y < -.08 else 0
        upper_lip = math.exp(-(x / .031) ** 4 - ((z - 1.516) / .0055) ** 2) if y < -.14 else 0
        lower_lip = math.exp(-(x / .029) ** 4 - ((z - 1.500) / .006) ** 2) if y < -.14 else 0
        lip = max(upper_lip, lower_lip)
        color.color = (.47 + .017 * cheek - .025 * upper_lip,
                       .270 - .020 * cheek - .068 * lip, .175 - .011 * cheek - .012 * lip, 1)
        lip_mask.data[vertex.index].color = (lip, lip, lip, 1)
    shader = mats["skin"].node_tree.nodes["Principled BSDF"]
    attribute = mats["skin"].node_tree.nodes.new("ShaderNodeVertexColor")
    attribute.layer_name = "PortraitLipMask"
    roughness = mats["skin"].node_tree.nodes.new("ShaderNodeMapRange")
    roughness.inputs["To Min"].default_value = .55
    roughness.inputs["To Max"].default_value = .43
    mats["skin"].node_tree.links.new(attribute.outputs["Color"], roughness.inputs["Value"])
    mats["skin"].node_tree.links.new(roughness.outputs[0], shader.inputs["Roughness"])
    head.data.update()
    bpy.context.view_layer.update()

    def face(x, z, offset=.001):
        found, position, normal, _ = head.ray_cast(Vector((x, -.5, z)), Vector((0, 1, 0)))
        if not found:
            raise RuntimeError(f"Reference facial detail misses anatomy at {x}, {z}")
        return position + normal * offset

    beard = material("portrait_soft_facial_hair", (.012, .009, .007), .88, noise=.025, bump=0)
    beard.blend_method = "HASHED"
    beard.shadow_method = "HASHED"
    opacity = beard.node_tree.nodes.new("ShaderNodeVertexColor")
    opacity.layer_name = "PortraitHairOpacity"
    beard.node_tree.links.new(opacity.outputs["Alpha"], beard.node_tree.nodes["Principled BSDF"].inputs["Alpha"])
    brow_boundary = mats["brow"].copy()
    brow_boundary.name = "Portrait_feathered_brow_density"
    brow_boundary.blend_method = "HASHED"
    brow_boundary.shadow_method = "HASHED"
    opacity = brow_boundary.node_tree.nodes.new("ShaderNodeVertexColor")
    opacity.layer_name = "PortraitHairOpacity"
    brow_boundary.node_tree.links.new(opacity.outputs["Alpha"], brow_boundary.node_tree.nodes["Principled BSDF"].inputs["Alpha"])
    for side in (-1, 1):
        vertices, faces = [], []
        for row in range(33):
            t = row / 32
            x = side * (.003 + .033 * t)
            top = 1.530 - .008 * t + .0007 * math.sin(t * 19)
            for col in range(7):
                across = col / 6
                depth = .0085 * math.sin(.22 + t * math.pi * .78)
                vertices.append(face(x, top - across * depth, .0008))
                if row < 32 and col < 6:
                    a = row * 7 + col
                    faces.append((a, a + 1, a + 8, a + 7))
        patch = part(mesh_object("Portrait_moustache_density", vertices, faces, beard), "head")
        colors = patch.data.color_attributes.new(name="PortraitHairOpacity", type="FLOAT_COLOR", domain="POINT")
        for i, color in enumerate(colors.data):
            along, across = (i // 7) / 32, (i % 7) / 6
            clusters = .83 + .17 * math.sin(along * 31 + across * 11) ** 2
            color.color = (1, 1, 1, .96 * clusters * math.sin(across * math.pi) ** .28 * math.sin(along * math.pi) ** .25)
    vertices, faces = [], []
    for row in range(25):
        t = row / 24
        z = 1.495 - .029 * t
        width = .023 * (1 - .57 * t) * (1 + .06 * math.sin(t * 23))
        for col in range(17):
            vertices.append(face(width * (col / 8 - 1), z + .0006 * math.sin(col * 1.7 + t), .0008))
            if row < 24 and col < 16:
                a = row * 17 + col
                faces.append((a, a + 1, a + 18, a + 17))
    patch = part(mesh_object("Portrait_goatee_density", vertices, faces, beard), "head")
    colors = patch.data.color_attributes.new(name="PortraitHairOpacity", type="FLOAT_COLOR", domain="POINT")
    for i, color in enumerate(colors.data):
        t, across = (i // 17) / 24, (i % 17) / 16
        clusters = .84 + .16 * math.sin(t * 23 + across * 17) ** 2
        color.color = (1, 1, 1, .96 * clusters * math.sin(t * math.pi) ** .23 * math.sin(across * math.pi) ** .30)
    for side in (-1, 1):
        vertices, faces = [], []
        for row in range(33):
            t = row / 32
            x = side * (.010 + .059 * t)
            z = 1.613 + .0035 * math.sin(t * math.pi * .85) - .002 * t
            thickness = .0105 * (1 - .83 * t ** 4) * (.55 + .45 * min(1, t * 10))
            for col in range(7):
                vertices.append(face(x, z + (col / 6 - .5) * thickness
                                     + .00035 * math.sin(t * 47 + col), .0007))
                if row < 32 and col < 6:
                    a = row * 7 + col
                    faces.append((a, a + 1, a + 8, a + 7))
        brow = part(mesh_object("Portrait_angled_flat_brow", vertices, faces, brow_boundary), "head")
        colors = brow.data.color_attributes.new(name="PortraitHairOpacity", type="FLOAT_COLOR", domain="POINT")
        for i, color in enumerate(colors.data):
            t, across = (i // 7) / 32, (i % 7) / 6
            color.color = (1, 1, 1, .99 * min(1, across * 5, (1 - across) * 5)
                           * min(1, t * 16, (1 - t) * 12))
        for i in range(55):
            t = (i + .16 * math.sin(i * 2.39)) / 54
            x = side * (.011 + .055 * t)
            z = 1.613 + .0035 * math.sin(t * math.pi * .85) - .002 * t
            z += .0035 * math.sin(i * 2.399)
            part(stroke("Portrait_brow_fiber",
                        [face(x, z, .001), face(x + side * .0018, z + .0008, .001)],
                        .00016, mats["brow"], [.7, .05]), "head")
        for i in range(110):
            t, depth = (i * .618033989) % 1, (i * .754877666) % 1
            x = side * (.003 + .033 * t)
            top = 1.530 - .008 * t + .0007 * math.sin(t * 19)
            z = top - depth * .007 * math.sin(.22 + t * math.pi * .78)
            length = .0013 + .001 * ((i * .569840296) % 1)
            part(stroke("Portrait_short_moustache",
                        [face(x, z, .0008), face(x + side * .0006, z - length, .0007)],
                        .00013, mats["brow"], [.7, .05]), "head")
    for i in range(260):
        t, across = (i * .618033989) % 1, (i * .754877666) % 1
        x = (2 * across - 1) * .022 * (1 - .57 * t)
        z = 1.494 - .027 * t
        length = .0013 + .001 * ((i * .569840296) % 1)
        part(stroke("Portrait_chin_goatee",
                    [face(x, z, .0008), face(x * .985, z - length, .0007)],
                    .00013, mats["brow"], [.7, .05]), "head")
    vertices, faces = [], []
    for row in range(13):
        t = row / 12
        for col in range(9):
            x = (col / 4 - 1) * (.006 - .0035 * t)
            vertices.append(face(x, 1.495 - .004 * t, .0006))
            if row < 12 and col < 8:
                a = row * 9 + col
                faces.append((a, a + 1, a + 10, a + 9))
    patch = part(mesh_object("Portrait_soft_sub_lip_patch", vertices, faces, beard), "head")
    colors = patch.data.color_attributes.new(name="PortraitHairOpacity", type="FLOAT_COLOR", domain="POINT")
    for i, color in enumerate(colors.data):
        t, across = (i // 9) / 12, (i % 9) / 8
        color.color = (1, 1, 1, .65 * math.sin(t * math.pi) ** .4 * math.sin(across * math.pi) ** .4)

    center = Vector((0, -.024, 1.635))

    def scalp(theta, fraction, ridge=0):
        angle = (theta + math.pi) % TAU - math.pi
        limit = 1.52 - .43 * math.cos(theta) + .035 * math.sin(theta * 3 + .4)
        limit += .38 * math.exp(-((abs(angle) - 1.3) / .34) ** 2)
        phi = .015 + fraction * limit
        radial = Vector((math.sin(theta) * math.sin(phi),
                         -math.cos(theta) * math.sin(phi), math.cos(phi)))
        found, position, normal, _ = head.ray_cast(center + radial * .5, -radial)
        if not found:
            raise RuntimeError("Swept reference groom missed sculpted head")
        padding = .005 + .014 * math.sin(min(1, fraction) * math.pi) ** 1.5
        padding += .004 * (1 - fraction) + ridge
        if fraction > .94:
            padding *= max(.15, (1.04 - fraction) / .10)
        return position + radial * padding

    vertices, faces = [], []
    for row in range(41):
        for col in range(129):
            vertices.append(scalp(col / 128 * TAU, row / 40 * .992))
            if row < 40 and col < 128:
                a = row * 129 + col
                faces.append((a, a + 129, a + 130, a + 1))
    boundary = mats["hair"].copy()
    boundary.name = "Portrait_feathered_hairline"
    boundary.blend_method = "HASHED"
    boundary.shadow_method = "HASHED"
    opacity = boundary.node_tree.nodes.new("ShaderNodeVertexColor")
    opacity.layer_name = "PortraitHairOpacity"
    boundary.node_tree.links.new(opacity.outputs["Alpha"], boundary.node_tree.nodes["Principled BSDF"].inputs["Alpha"])
    cap = part(mesh_object("Portrait_swept_back_hair_mass", vertices, faces, boundary), "head")
    colors = cap.data.color_attributes.new(name="PortraitHairOpacity", type="FLOAT_COLOR", domain="POINT")
    for i, color in enumerate(colors.data):
        t = (i // 129) / 40
        color.color = (1, 1, 1, min(1, (1 - t) / .06))
    weld_surface(cap)
    cap.modifiers.new("Soft continuous groom mass", "SUBSURF").levels = 1
    for i in range(34):
        theta = i / 34 * TAU + .018 * math.sin(i * 1.7)
        vertices, faces = [], []
        for row in range(25):
            f = .09 + .915 * row / 24
            mid = theta + .40 * (1 - f)
            half_width = .075 * math.sin(f * math.pi * .90) + .008
            for col in range(7):
                across = col / 6
                vertices.append(scalp(mid + (across - .5) * half_width * 2, f,
                                      .001 + .0012 * math.sin(across * math.pi) ** 2))
                if row < 24 and col < 6:
                    a = row * 7 + col
                    faces.append((a, a + 7, a + 8, a + 1))
        lock = part(mesh_object("Portrait_swept_hair_clump", vertices, faces, boundary), "head")
        colors = lock.data.color_attributes.new(name="PortraitHairOpacity", type="FLOAT_COLOR", domain="POINT")
        for index, color in enumerate(colors.data):
            t, across = (index // 7) / 24, (index % 7) / 6
            color.color = (1, 1, 1, min(1, (1 - t) / .055) * (.3 + .7 * math.sin(across * math.pi)))
        lock.modifiers.new("Smooth swept locks", "SUBSURF").levels = 1
        for strand in range(2):
            points = [scalp(theta + .40 * (1 - f) + .015 * (strand - .5), f, .002)
                      for f in (.998, .89, .70, .47, .26, .10)]
            part(stroke("Portrait_swept_hair_fiber", points, .00035, mats["fiber"],
                        [.05, .6, 1, .8, .4, .05]), "head")
    for sign in (-1, 1):
        for i in range(6):
            theta = sign * (1.18 + i * .035)
            points = [scalp(theta + sign * .05 * t, .93 + .11 * t)
                      for t in (0, .35, .7, 1)]
            part(stroke("Portrait_temple_flow", points, .0006, mats["hair"],
                        [.6, 1, .6, .05]), "head")
    bun = Vector((.004, .035, 1.760))
    part(sphere("Portrait_gathered_bun_root", (.004, .035, 1.735),
                (.028, .025, .025), mats["hair"]), "head")
    part(sphere("Portrait_high_tied_bun", bun, (.041, .033, .029), mats["hair"]), "head")
    for i in range(17):
        angle = i / 17 * TAU
        part(stroke("Portrait_bun_fold",
                    [bun + Vector((math.sin(angle + t * .6) * r,
                                    math.cos(angle + t * .6) * r * .82, z))
                     for t, r, z in ((0, .030, -.019), (.4, .044, -.005),
                                     (.8, .030, .021), (1, .009, .026))],
                    .00065, mats["fiber"]), "head")
    part(stroke("Portrait_red_bun_tie",
                [bun + Vector((.041 * math.sin(i / 48 * TAU),
                                .033 * math.cos(i / 48 * TAU), -.013)) for i in range(49)],
                .0027, mats["tie"]), "head")
    for i in range(9):
        x = (i - 4) * .007
        part(stroke("Portrait_nape_lock",
                    [(x, .081, 1.621), (x * 1.14, .086, 1.565),
                     (x * 1.18, .079, 1.493 + .009 * math.sin(i))],
                    .005, mats["hair"], [.7, 1, .035]), "head")
    head["reference_provenance"] = "User-provided stylized illustration; approximate authored sculpt, no identity inference"
    head["reference_sculpt_targets"] = json.dumps(REFERENCE_FACE_TARGETS)
    eyes = []
    for sign in (-1, 1):
        indices = [i for i in iris_indices if raw[i].x * sign > 0]
        if not indices:
            raise RuntimeError("Missing reference eye geometry")
        eyes.append(sum((head.data.vertices[i].co for i in indices), Vector()) / len(indices))
    separation = (eyes[1] - eyes[0]).length
    if not .060 < separation < .095 or abs(eyes[0].z - eyes[1].z) > .002:
        raise RuntimeError(f"Misaligned sculpted eyes: {eyes}")
    return {"iris_centers_rest": [list(p) for p in eyes], "iris_separation_m": separation,
            "sculpt_targets": REFERENCE_FACE_TARGETS, "glasses_geometry_created": False}


def reference_face_main(reference_proof=None, preview_only=False):
    """Preserve both prior alternatives and render the integrated no-glasses study."""
    output = HERE / "FirstShot_TravelerPortrait.blend"
    source = ROOT / "assets" / "source" / "characters" / "player_traveler_rigged.blend"
    preserved = [source, HERE / "refine_traveler_costume.py"]
    preserved += [p for p in HERE.glob("*.blend") if p != output]
    preserved += [p for p in RENDERS.iterdir() if p.is_file()
                  and not p.name.startswith("traveler_portrait_")]
    before = {str(p.relative_to(ROOT)): digest(p) for p in preserved}
    if digest(source) != SOURCE_HASH:
        raise RuntimeError("Original source changed before portrait variant")
    if reference_proof is not None and digest(reference_proof) != REFERENCE_IMAGE_HASH:
        raise RuntimeError("User reference image fingerprint does not match")
    bpy.ops.wm.open_mainfile(filepath=str(HERE / "FirstShot_TravelerOrnate.blend"))
    scene = bpy.context.scene
    original = next(s for s in bpy.data.scenes if s.camera and s.camera.name == "CAM_ValleyReveal")
    original_name, original_camera = original.name, original.camera.name
    prefixes = ("Study_irregular_hairline", "Study_tapered_hairline_lock", "Study_hairline_tip",
                "Study_swept_lock", "Study_fine_hair", "Study_folded_hair_knot", "Study_bun_lock",
                "Study_hair_binding", "Study_wooden_hairpin", "Study_temple_lock",
                "Study_temple_flyaway", "Study_original_face_and_hands",
                "Ornate_hairpin_jade_end", "Ornate_short_hair_ribbon")
    for obj in scene.objects:
        if obj.name.startswith(prefixes):
            obj.hide_render = True
            obj.hide_viewport = True
    base_parts = [o for name in ("Study_editable_baked_character", "Ornate_fitted_layers_and_craft")
                  for o in bpy.data.collections[name].objects if not o.hide_render]
    PARTS.clear()
    face_evidence = build_reference_face()
    bake_study_pose()
    for obj in PARTS:
        if any(word in obj.name.lower() for word in ("glasses", "spectacle", "lens")):
            raise RuntimeError(f"Unexpected eyewear in reference variant: {obj.name}")
        for slot in obj.material_slots:
            if slot.material and slot.material.use_nodes:
                if any(node.type == "TEX_IMAGE" for node in slot.material.node_tree.nodes):
                    raise RuntimeError(f"Reference face unexpectedly uses an image texture: {obj.name}")
    cap = bpy.data.objects["Portrait_swept_back_hair_mass"]
    root = bpy.data.objects["Portrait_gathered_bun_root"]
    bun = bpy.data.objects["Portrait_high_tied_bun"]
    overlaps = []
    for first, second in ((cap, root), (root, bun)):
        high = min(max(v.co.z for v in first.data.vertices), max(v.co.z for v in second.data.vertices))
        low = max(min(v.co.z for v in first.data.vertices), min(v.co.z for v in second.data.vertices))
        overlaps.append(high - low)
    if min(overlaps) < .003:
        raise RuntimeError(f"Reference bun appears detached: {overlaps}")
    face_evidence["bun_vertical_overlap_m"] = overlaps
    face_evidence["facial_components_use_image_textures"] = False
    collection = bpy.data.collections.new("Portrait_reference_sculpt_and_groom")
    scene.collection.children.link(collection)
    for obj in PARTS:
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        collection.objects.link(obj)
    PARTS.extend(base_parts)
    evidence = validate(scene, original, original_camera)
    center = pose_point(Vector((0, -.025, 1.618)), "head")
    for name, offset, scale in (("front", Vector((-.30, -4, .025)), .42),
                                ("threequarter", Vector((2.5, -4, .20)), .44)):
        bpy.ops.object.camera_add(location=center + offset)
        camera = bpy.context.object
        camera.name = "Study_camera_" + name
        camera.data.type = "ORTHO"
        camera.data.ortho_scale = scale
        point_at(camera, center)
    for name in ("front", "threequarter"):
        render(scene, name, f"traveler_portrait_{name}.png")
    if preview_only:
        after = {str(p.relative_to(ROOT)): digest(p) for p in preserved}
        if before != after:
            raise RuntimeError("Facial preview changed a preserved input")
        if reference_proof is not None and digest(reference_proof) != REFERENCE_IMAGE_HASH:
            raise RuntimeError("Reference changed during facial preview")
        print("FACIAL_PREVIEW_VERIFIED: frontal and three-quarter only; integrated outputs not refreshed", flush=True)
        return
    for name in ("half", "full", "rear"):
        render(scene, name, f"traveler_portrait_{name}.png")
    contact_sheet("traveler_portrait", ("traveler_ornate_full.png", "traveler_portrait_full.png",
                                       "traveler_ornate_half.png", "traveler_portrait_half.png"))
    bpy.ops.file.pack_all()
    scene.camera = bpy.data.objects["Study_camera_half"]
    scene.render.resolution_x, scene.render.resolution_y = 1200, 1500
    scene.render.filepath = str(RENDERS / "traveler_portrait_half.png")
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    bpy.ops.wm.open_mainfile(filepath=str(output))
    if bpy.data.scenes[original_name].camera.name != original_camera:
        raise RuntimeError("Reference variant lost preserved cinematic camera")
    render(bpy.context.scene, "half", "traveler_portrait_reload_half.png")
    difference = compare_reload("traveler_portrait")
    after = {str(p.relative_to(ROOT)): digest(p) for p in preserved}
    if before != after:
        raise RuntimeError("Reference variant changed a preserved input")
    if reference_proof is not None and digest(reference_proof) != REFERENCE_IMAGE_HASH:
        raise RuntimeError("Read-only reference changed during generation")
    evidence.update({"variant": "ornate_reference_face_without_glasses",
                     "focused_likeness_correction": 1,
                     "facial_geometry": face_evidence, "preserved_hashes": after,
                     "reference_image_sha256": REFERENCE_IMAGE_HASH,
                     "reference_proof_checked": reference_proof is not None,
                     "reference_bitmap_embedded": False, "reload_verified": True,
                     "reload_half_pixel_difference": difference,
                     "comparison_columns": ["prior ornate full", "reference-face full",
                                             "prior ornate half", "reference-face half"],
                     "limitations": ["Approximate reference-inspired sculpt, not an exact likeness or photoreal reconstruction",
                                     "Single small frontal illustration leaves side profile and concealed eyes uncertain",
                                     "Static baked pose; no facial animation or cloth simulation"],
                     "outputs": [p.name for p in RENDERS.glob("traveler_portrait_*.png")]})
    (RENDERS / "traveler_portrait_evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("REFERENCE_FACE_VERIFIED", json.dumps({k: v for k, v in evidence.items() if k != "preserved_hashes"}), flush=True)


def main():
    """Build, render, reopen and verify only the authorized study outputs."""
    preserved = [ROOT / "assets" / "source" / "characters" / "player_traveler_rigged.blend"]
    preserved += [p for p in HERE.glob("*.blend") if p != OUTPUT]
    preserved += list(RENDERS.glob("traveler_costume_*.png"))
    preserved += [RENDERS / name for name in
                  ("bronze_jade_final.mp4", "bronze_jade_preview.mp4", "bronze_jade_1080.png")
                  if (RENDERS / name).is_file()]
    before = {str(p.relative_to(ROOT)): digest(p) for p in preserved}
    if digest(preserved[0]) != SOURCE_HASH:
        raise RuntimeError("Accepted traveler source hash does not match approval")
    bpy.ops.wm.open_mainfile(filepath=str(HERE / "FirstShot_Costume.blend"))
    original = bpy.context.scene
    original_name = original.name
    original_camera = original.camera.name
    source = bpy.data.objects["Traveler_Skinned_Appearance"]
    scene = make_stage()
    RENDERS.mkdir(exist_ok=True)
    mats = {
        "skin": material("warm_skin", (.49, .285, .181), .53, noise=.025, bump=.00012),
        "eye": material("warm_sclera", (.43, .40, .33), .26, noise=.01, bump=0),
        "iris": material("brown_iris", (.043, .022, .012), .22, noise=.10, bump=0),
        "pupil": material("pupil", (.002, .002, .0018), .16, noise=0, bump=0),
        "hair": material("ink_hair", (.010, .008, .0065), .64, noise=.08, bump=.0001),
        "hair_light": material("hair_fiber", (.013, .010, .008), .65, noise=.08, bump=0),
        "brow": material("matte_brows", (.016, .012, .009), .78, noise=.06, bump=0),
        "cloth": material("washed_indigo_ramie", (.051, .105, .119), .87, noise=.07,
                          bump=.00045, sheen=.12),
        "lining": material("quiet_silk_facing", (.068, .139, .142), .54, noise=.025,
                           bump=.0001, sheen=.23),
        "linen": material("undyed_ramie", (.285, .268, .211), .91, noise=.055, bump=.00045),
        "sash": material("faded_ochre_cotton", (.142, .089, .047), .9,
                        noise=.06, bump=.0004),
        "leather": material("worn_walnut_leather", (.048, .027, .016), .66,
                           noise=.12, bump=.0003),
        "sole": material("dark_worn_soles", (.023, .018, .012), .88, bump=.0005),
        "trouser": material("charcoal_cotton", (.044, .054, .055), .94, bump=.0004),
        "pack": material("weathered_canvas", (.153, .127, .074), .94,
                        noise=.09, bump=.0006),
        "bronze": material("aged_bronze", (.15, .095, .034), .56, noise=.16,
                          bump=.0002, metallic=.65),
        "jade": material("soft_jade", (.047, .18, .13), .32, noise=.13,
                        bump=.00007),
        "jade_dark": material("jade_incision", (.028, .10, .068), .49, bump=0),
    }
    head = build_anatomy(source, mats)
    for name in ("cloth", "linen", "sash", "pack", "trouser"):
        add_weave(mats[name])
    build_hair(head, mats)
    build_clothes(mats)
    fit_neckline(head)
    neck_facing(head, mats)
    bake_study_pose()
    join_upper_garment()
    study_collection = bpy.data.collections.new("Study_editable_baked_character")
    scene.collection.children.link(study_collection)
    for obj in PARTS:
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        study_collection.objects.link(obj)

    # Original rest-space geometry under identical cameras/lights is a fairer
    # comparison than the previously flat-lit costume contact sheet.
    baseline = bpy.data.collections.new("Study_reference_old_costume")
    scene.collection.children.link(baseline)
    for obj in [source, *bpy.data.collections["Cinematic_traveler_costume"].objects]:
        copy = obj.copy()
        copy.name = "Study_baseline_" + obj.name
        copy.parent = None
        copy.matrix_world = Matrix.Identity(4)
        copy.animation_data_clear()
        for modifier in list(copy.modifiers):
            if modifier.type == "ARMATURE":
                copy.modifiers.remove(modifier)
        baseline.objects.link(copy)
    study_collection.hide_render = True
    render(scene, "full", "traveler_study_before_full.png")
    render(scene, "half", "traveler_study_before_half.png")
    study_collection.hide_render = False
    baseline.hide_render = True
    baseline.hide_viewport = True
    render(scene, "full", "traveler_study_full.png")
    render(scene, "half", "traveler_study_half.png")
    render(scene, "rear", "traveler_study_rear.png")
    contact_sheet()
    evidence = validate(scene, original, original_camera)
    bpy.ops.file.pack_all()
    bpy.context.preferences.filepaths.save_version = 0
    scene.camera = bpy.data.objects["Study_camera_half"]
    scene.render.resolution_x, scene.render.resolution_y = 1200, 1500
    scene.render.filepath = str(RENDERS / "traveler_study_half.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
    bpy.ops.wm.open_mainfile(filepath=str(OUTPUT))
    if bpy.context.scene.name != "Traveler_Study_Studio":
        raise RuntimeError("Reload did not restore the isolated study scene")
    if bpy.data.scenes[original_name].camera.name != original_camera:
        raise RuntimeError("Saved original camera was not preserved")
    render(bpy.context.scene, "half", "traveler_study_reload_half.png")
    reload_difference = compare_reload()
    after = {str(p.relative_to(ROOT)): digest(p) for p in preserved}
    if before != after:
        raise RuntimeError("A preserved input changed during generation")
    evidence.update({"preserved_hashes": after, "source_hash_verified": True,
                     "visual_iteration": 2,
                     "reload_verified": True, "blender_version": bpy.app.version_string,
                     "reload_half_pixel_difference": reload_difference,
                     "contact_sheet_columns": ["old full", "study full", "old half", "study half"],
                     "render_engine": "BLENDER_EEVEE", "samples": 128,
                     "baseline": "Old rest-space costume with identical studio lights/cameras",
                     "limitations": ["Baked static pose; no animation validation",
                                     "Procedural garment folds, not simulated cloth",
                                     "Original facial anatomy; no facial performance"],
                     "outputs": [p.name for p in RENDERS.glob("traveler_study_*.png")]})
    (RENDERS / "traveler_study_evidence.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8")
    print("STUDY_VERIFIED", json.dumps(evidence), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline traveler study; --ornate preserves the accepted simple study.")
    parser.add_argument("--ornate", action="store_true", help="Build a separate ornate alternative from the accepted study")
    parser.add_argument("--reference-face", action="store_true", help="Create a separate reference-inspired face without glasses")
    parser.add_argument("--reference-proof", type=Path, help="Optional read-only local reference image fingerprint check")
    parser.add_argument("--face-preview", action="store_true", help="Render reference frontal/three-quarter for inspection before integrated stills")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.reference_face and not args.ornate:
        parser.error("--reference-face requires --ornate")
    if args.reference_proof is not None and not args.reference_face:
        parser.error("--reference-proof requires --reference-face")
    if args.face_preview and not args.reference_face:
        parser.error("--face-preview requires --reference-face")
    if args.reference_face:
        reference_face_main(args.reference_proof, args.face_preview)
    elif args.ornate:
        ornate_main()
    else:
        main()
