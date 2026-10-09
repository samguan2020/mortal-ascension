"""Build an original Eevee cinematic study without changing game/source assets.

Run with Blender 3.6: --factory-startup -b --python-exit-code 1 --python <script>
Append -- --preview to also render a 10-second, 960x540, 24 fps H.264 preview.
Use -- --final to load the approved FirstShot_BronzeJade.blend, add ambient
motion and render an independent 1080p version without replacing the preview.
The default output is FirstShot_BronzeJade.blend and renders/bronze_jade_1080.png.
Regeneration replaces these outputs: save hand-edited scenes under another name.
The previous FirstShot.blend blockout remains untouched.
This is a cinematic material study, separate from the game's art direction.
"""

import argparse
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector, noise


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RNG = random.Random(42)


def material(name, color, emission=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = 0.9
    if emission:
        shader.inputs["Emission"].default_value = (*color, 1)
        shader.inputs["Emission Strength"].default_value = emission
    return mat


def weathered_material(name, dark, light, scale=5, metallic=0, moss=False):
    mat = material(name, dark)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = 0.48 if metallic else 0.83
    coordinates = nodes.new("ShaderNodeTexCoord")
    stretch = nodes.new("ShaderNodeVectorMath")
    stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = (2.6, 2.6, 0.65) if moss else (1, 1, 1)
    links.new(coordinates.outputs["Generated"], stretch.inputs[0])
    grain = nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = scale
    grain.inputs["Detail"].default_value = 5
    grain.inputs["Roughness"].default_value = 0.72
    links.new(stretch.outputs["Vector"], grain.inputs["Vector"])
    colors = nodes.new("ShaderNodeValToRGB")
    colors.color_ramp.elements[0].position = 0.23
    colors.color_ramp.elements[0].color = (*dark, 1)
    colors.color_ramp.elements[1].position = 0.77
    colors.color_ramp.elements[1].color = (*light, 1)
    links.new(grain.outputs["Fac"], colors.inputs["Fac"])
    links.new(colors.outputs["Color"], shader.inputs["Base Color"])
    if metallic:
        patina = colors.color_ramp.elements.new(0.34)
        patina.color = (0.055, 0.19, 0.145, 1)
        metal = colors.color_ramp.elements.new(0.55)
        metal.color = (*light, 1)
        roughness = nodes.new("ShaderNodeMapRange")
        roughness.inputs["To Min"].default_value = 0.3
        roughness.inputs["To Max"].default_value = 0.72
        links.new(grain.outputs["Fac"], roughness.inputs["Value"])
        links.new(roughness.outputs["Result"], shader.inputs["Roughness"])
    if moss:
        geometry = nodes.new("ShaderNodeNewGeometry")
        normal = nodes.new("ShaderNodeSeparateXYZ")
        links.new(geometry.outputs["Normal"], normal.inputs[0])
        mask = nodes.new("ShaderNodeMath")
        mask.operation = "MULTIPLY"
        links.new(normal.outputs["Z"], mask.inputs[0])
        links.new(grain.outputs["Fac"], mask.inputs[1])
        coverage = nodes.new("ShaderNodeMapRange")
        coverage.clamp = True
        coverage.inputs["From Min"].default_value = 0.10
        coverage.inputs["From Max"].default_value = 0.40
        links.new(mask.outputs[0], coverage.inputs["Value"])
        mix = nodes.new("ShaderNodeMixRGB")
        mix.inputs[2].default_value = (0.07, 0.19, 0.055, 1)
        links.new(coverage.outputs["Result"], mix.inputs[0])
        links.new(colors.outputs[0], mix.inputs[1])
        links.new(mix.outputs[0], shader.inputs["Base Color"])
    fine = nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 145
    fine.inputs["Detail"].default_value = 3
    links.new(stretch.outputs["Vector"], fine.inputs["Vector"])
    pores = nodes.new("ShaderNodeBump")
    pores.inputs["Strength"].default_value = 0.4
    pores.inputs["Distance"].default_value = 0.06
    links.new(fine.outputs["Fac"], pores.inputs["Height"])
    relief = nodes.new("ShaderNodeBump")
    relief.inputs["Strength"].default_value = 0.65
    relief.inputs["Distance"].default_value = 0.10 if metallic else 0.28
    links.new(grain.outputs["Fac"], relief.inputs["Height"])
    links.new(pores.outputs["Normal"], relief.inputs["Normal"])
    links.new(relief.outputs["Normal"], shader.inputs["Normal"])
    return mat


def mesh(name, vertices, faces, materials):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    for mat in materials:
        data.materials.append(mat)
    return obj


def block(name, location, scale, mat, bevel=0.1):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new("Worn edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        obj.data.use_auto_smooth = True
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def line(name, points, radius, mat):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.bevel_depth = radius
    data.bevel_resolution = 2
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (*co, 1)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    data.materials.append(mat)
    return obj


def crag(name, center, radius, height, mats):
    vertices = []
    count, rings = 96, 72
    phase = RNG.random() * math.tau
    seed = RNG.uniform(0, 100)
    for ring in range(rings):
        z = ring / (rings - 1)
        width = (1 - z ** 6) ** 0.7 * 0.78 + 0.11
        for i in range(count):
            angle = i / count * math.tau + phase
            buttress = 1 + 0.13 * math.sin(angle * 7 + phase) + 0.06 * math.sin(angle * 13)
            sample = Vector((math.cos(angle) * 3, math.sin(angle) * 3, z * 4 + seed))
            weathering = noise.noise(sample) * 0.24 + noise.noise(sample * 3.7) * 0.035
            strata = 0.025 * math.sin(z * 92 + noise.noise(sample) * 2)
            r = radius * width * (buttress + weathering + strata)
            vertices.append((
                center[0] + math.cos(angle) * r + math.sin(z * 2.3) * radius * 0.16,
                center[1] + math.sin(angle) * r * 0.7,
                center[2] + z * height + z ** 3 * radius * (
                    math.sin(angle * 3 + phase) * 0.09 + noise.noise(sample) * 0.13),
            ))
    faces = []
    for ring in range(rings - 1):
        for i in range(count):
            a = ring * count + i
            b = ring * count + (i + 1) % count
            faces.append((a, b, b + count, a + count))
    faces.append(tuple(range((rings - 1) * count, rings * count)))
    obj = mesh(name, vertices, faces, mats)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def roof(name, center, width, depth, mat, bronze):
    verts = []
    steps, rows = 48, 12
    def roof_height(x, y):
        return center[2] + 0.8 * (abs(x) / (width / 2)) ** 5 + 0.9 * (1 - abs(y) / (depth / 2)) ** 2

    for row in range(rows + 1):
        y = (row / rows - 0.5) * depth
        for i in range(steps + 1):
            x = (i / steps - 0.5) * width
            verts.append((center[0] + x, center[1] + y, roof_height(x, y)))
    faces = [(row * (steps + 1) + i, row * (steps + 1) + i + 1,
              (row + 1) * (steps + 1) + i + 1, (row + 1) * (steps + 1) + i)
             for row in range(rows) for i in range(steps)]
    obj = mesh(name, verts, faces, [mat])
    obj.modifiers.new("Roof thickness", "SOLIDIFY").thickness = 0.22
    for i in range(steps + 1):
        x = (i / steps - 0.5) * width
        points = [(center[0] + x, center[1] + (row / rows - 0.5) * depth,
                   roof_height(x, (row / rows - 0.5) * depth) + 0.04)
                  for row in range(rows + 1)]
        line(name + "_tile_roll", points, 0.055, mat)
    for y in (-depth / 2, 0, depth / 2):
        points = [(center[0] + (i / steps - 0.5) * width, center[1] + y,
                   roof_height((i / steps - 0.5) * width, y) + 0.03)
                  for i in range(steps + 1)]
        line(name + "_bronze_edge", points, 0.065, bronze)


def pine(base, height, bark, needles):
    x, y, z = base
    trunk = line("Pine_trunk", [(x, y, z), (x + 0.35, y, z + height * 0.45),
                               (x + 0.15, y + 0.1, z + height * 0.75),
                               (x + 0.7, y, z + height)], height * 0.028, bark)
    for point, radius in zip(trunk.data.splines[0].points, (1, 0.72, 0.42, 0.1)):
        point.radius = radius
    foliage = bpy.data.meshes.get("Pine_needle_spray")
    if foliage is None:
        vertices, faces = [], []
        for _ in range(2300):
            angle = RNG.random() * math.tau
            distance = math.sqrt(RNG.random())
            origin = Vector((math.cos(angle) * distance, math.sin(angle) * distance * 0.7,
                             RNG.uniform(-0.20, 0.30) * (1 - distance * 0.5)))
            tip = origin + Vector((math.cos(angle) * 0.22, math.sin(angle) * 0.22,
                                   RNG.uniform(-0.08, 0.11)))
            side = Vector((-math.sin(angle), math.cos(angle), 0)) * 0.017
            first = len(vertices)
            vertices.extend((origin - side, origin + side, tip))
            faces.append((first, first + 1, first + 2))
        template = mesh("Needle_template", vertices, faces, [needles])
        foliage = template.data
        foliage.name = "Pine_needle_spray"
        bpy.data.objects.remove(template, do_unlink=True)
    for tier in range(12):
        level = z + height * (0.35 + tier * 0.052)
        width = height * (0.38 - tier * 0.022) * RNG.uniform(0.8, 1.15)
        angle = tier * 2.4 + 0.4
        tip = Vector((x + math.cos(angle) * width + 0.4,
                      y + math.sin(angle) * width * 0.7, level + 0.25))
        branch = line("Pine_branch", [(x + 0.2, y, level - 0.2),
                                     (tip.x, tip.y, level - 0.1), tip], height * 0.009, bark)
        for point, radius in zip(branch.data.splines[0].points, (1, 0.5, 0.08)):
            point.radius = radius
        for _ in range(6):
            obj = bpy.data.objects.new("Pine_needle_cluster", foliage)
            bpy.context.collection.objects.link(obj)
            obj.location = tip + Vector((RNG.uniform(-0.45, 0.45) * width,
                                         RNG.uniform(-0.6, 0.6), RNG.uniform(-0.12, 0.15)))
            obj.scale = (width * 0.48, width * 0.40, 1)
            obj.rotation_euler.z = RNG.uniform(-0.8, 0.8)


def ledge(name, center, size, mats):
    vertices = []
    count = 48
    radii = [RNG.uniform(0.91, 1.06) for _ in range(count)]
    for z, scale in ((-10, 0.35), (-7, 0.65), (-4, 0.9), (-1, 1.03), (0, 1)):
        for i, radius in enumerate(radii):
            angle = i / count * math.tau
            vertices.append((center[0] + math.cos(angle) * size[0] * radius * scale,
                             center[1] + math.sin(angle) * size[1] * radius * scale,
                             center[2] + z + (RNG.uniform(-0.4, 0.4) if z else 0)))
    faces = [tuple(range(4 * count, 5 * count))]
    for row in range(4):
        for i in range(count):
            a, b = row * count + i, row * count + (i + 1) % count
            faces.append((a, b, b + count, a + count))
    obj = mesh(name, vertices, faces, mats)
    bevel = obj.modifiers.new("Fractured cliff edges", "BEVEL")
    bevel.width = 0.16
    bevel.segments = 3
    obj.data.use_auto_smooth = True
    obj.modifiers.new("Cliff normals", "WEIGHTED_NORMAL")
    return obj


def traveler():
    source = ROOT / "assets" / "source" / "characters" / "player_traveler_rigged.blend"
    with bpy.data.libraries.load(str(source), link=False) as (available, loaded):
        names = ["Traveler_Skinned_Appearance", "Traveler_Rig"]
        if not all(name in available.objects for name in names):
            raise RuntimeError("Traveler source objects missing")
        loaded.objects = names
    parent = bpy.data.objects.new("Traveler_placement", None)
    bpy.context.collection.objects.link(parent)
    parent.location = (-4.0, -0.6, 4.15)
    parent.rotation_euler.z = math.pi
    parent.scale = (1.75,) * 3
    for obj in loaded.objects:
        bpy.context.collection.objects.link(obj)
        if obj.parent is None:
            obj.parent = parent
        if obj.type == "ARMATURE":
            if obj.animation_data:
                for track in obj.animation_data.nla_tracks:
                    track.mute = True
                action = obj.animation_data.action
                if action:
                    for curve in action.fcurves:
                        if not any(mod.type == "CYCLES" for mod in curve.modifiers):
                            curve.modifiers.new("CYCLES")


def scroll_panel(name, center, width, height, bronze):
    path = [(-0.5, -0.5), (-0.5, 0.5), (0.5, 0.5), (0.5, -0.28),
            (-0.20, -0.28), (-0.20, 0.20), (0.18, 0.20), (0.18, -0.02)]
    points = [(center[0] + x * width, center[1], center[2] + z * height) for x, z in path]
    line(name, points, 0.035, bronze)


def gate(stone, roof_mat, bronze, jade, glow):
    ledge("Gate_island", (3, 31, 7.55), (7.4, 4.7), [stone])
    for z, width, depth in ((7.65, 12.5, 6.8), (7.95, 11.6, 5.8), (8.22, 10.8, 4.8)):
        block("Gate_foundation_course", (3, 31, z), (width, depth, 0.4), stone, 0.07)
    for x in (-1.2, 7.2):
        block("Gate_pier", (x, 31, 13.8), (1.35, 1.8, 11), stone, 0.09)
        block("Gate_foot", (x, 31, 8.95), (2.1, 2.5, 1), stone)
        block("Gate_bronze_foot", (x, 31, 9.48), (1.55, 2, 0.15), bronze, 0.04)
        for z in (10.2, 12.5, 14.8, 17.1, 18.7):
            block("Gate_bronze_collar", (x, 31, z), (1.44, 1.91, 0.20), bronze, 0.025)
        block("Gate_jade_channel", (x, 30.075, 14.1), (0.18, 0.10, 8.6), jade, 0.04)
        for z in (11.3, 13.6, 15.9, 18):
            for offset in (-0.43, 0.43):
                scroll_panel("Pier_cloud_scroll", (x + offset, 30.06, z), 0.34, 1.05, bronze)
        for tier in range(3):
            block("Dougong_cross_arm", (x, 31, 19 + tier * 0.28),
                  (1.9 + tier * 0.65, 2.3 + tier * 0.25, 0.22), bronze, 0.05)
            for offset in (-0.6, 0.6):
                block("Dougong_support", (x + offset, 31, 19.12 + tier * 0.28),
                      (0.24, 2.5 + tier * 0.3, 0.25), stone, 0.04)
    block("Gate_lintel", (3, 31, 19.55), (11, 1.9, 1.05), stone)
    for z in (19.1, 19.95):
        block("Lintel_bronze_border", (3, 29.99, z), (10.8, 0.08, 0.09), bronze, 0.02)
    for index in range(15):
        scroll_panel("Lintel_thunder_pattern", (-1.95 + index * 0.70, 29.98, 19.52),
                     0.54, 0.47, bronze)
    roof("Gate_lower_eaves", (3, 31, 20.12), 14, 4.5, roof_mat, bronze)
    block("Gate_upper_tier", (3, 31, 21.15), (6, 1.8, 1.15), stone)
    block("Gate_jade_tablet", (3, 30.04, 21.18), (2.7, 0.18, 0.74), jade)
    for x in (2.05, 3, 3.95):
        scroll_panel("Tablet_relief", (x, 29.93, 21.18), 0.56, 0.48, bronze)
    roof("Gate_upper_eaves", (3, 31, 21.82), 9, 3.3, roof_mat, bronze)

    vertices, faces = [], []
    count = 128
    for y, radius in ((30.4, 2.12), (30.4, 1.48), (30.85, 2.12), (30.85, 1.48)):
        for i in range(count):
            angle = i / count * math.tau
            vertices.append((3 + radius * math.cos(angle), y, 14.3 + radius * math.sin(angle)))
    for first, second in ((0, 1), (2, 0), (1, 3), (3, 2)):
        for i in range(count):
            j = (i + 1) % count
            faces.append((first * count + i, first * count + j,
                          second * count + j, second * count + i))
    disc = mesh("Jade_bi_relic", vertices, faces, [jade])
    bevel = disc.modifiers.new("Carved jade edges", "BEVEL")
    bevel.width = 0.045
    bevel.segments = 3
    disc.data.use_auto_smooth = True
    disc.modifiers.new("Jade normals", "WEIGHTED_NORMAL")
    for radius, mat, thickness in ((2.15, bronze, 0.055), (1.48, glow, 0.018), (1.61, bronze, 0.025)):
        points = [(3 + radius * math.cos(i / count * math.tau), 30.34,
                   14.3 + radius * math.sin(i / count * math.tau)) for i in range(count + 1)]
        line("Bi_inlay", points, thickness, mat)
    for index in range(12):
        angle = index / 12 * math.tau
        points = []
        for radial, offset in ((1.76, -0.10), (1.99, -0.10), (1.99, 0.10),
                               (1.83, 0.10), (1.83, 0), (1.92, 0)):
            points.append((3 + radial * math.cos(angle + offset), 30.32,
                           14.3 + radial * math.sin(angle + offset)))
        line("Bi_cloud_carving", points, 0.022, bronze)


def valley_clouds():
    fog = bpy.data.materials.new("Low_valley_cloud_volume")
    fog.use_nodes = True
    nodes, links = fog.node_tree.nodes, fog.node_tree.links
    nodes.clear()
    coordinates = nodes.new("ShaderNodeTexCoord")
    cloud = nodes.new("ShaderNodeTexNoise")
    cloud.inputs["Scale"].default_value = 5
    cloud.inputs["Detail"].default_value = 3
    links.new(coordinates.outputs["Generated"], cloud.inputs["Vector"])
    density = nodes.new("ShaderNodeMapRange")
    density.clamp = True
    density.inputs["From Min"].default_value = 0.38
    density.inputs["From Max"].default_value = 0.7
    density.inputs["To Min"].default_value = 0
    density.inputs["To Max"].default_value = 0.13
    links.new(cloud.outputs["Fac"], density.inputs["Value"])
    separate = nodes.new("ShaderNodeSeparateXYZ")
    links.new(coordinates.outputs["Generated"], separate.inputs[0])
    envelope = nodes.new("ShaderNodeValToRGB")
    envelope.color_ramp.elements[0].color = (0, 0, 0, 1)
    envelope.color_ramp.elements[1].color = (0, 0, 0, 1)
    envelope.color_ramp.elements.new(0.45).color = (1, 1, 1, 1)
    links.new(separate.outputs["Z"], envelope.inputs[0])
    multiply = nodes.new("ShaderNodeMath")
    multiply.operation = "MULTIPLY"
    links.new(density.outputs["Result"], multiply.inputs[0])
    links.new(envelope.outputs[0], multiply.inputs[1])
    volume = nodes.new("ShaderNodeVolumePrincipled")
    volume.inputs["Color"].default_value = (0.61, 0.78, 0.83, 1)
    volume.inputs["Anisotropy"].default_value = 0.35
    volume.inputs["Emission Color"].default_value = (0.22, 0.37, 0.40, 1)
    links.new(multiply.outputs[0], volume.inputs["Density"])
    links.new(multiply.outputs[0], volume.inputs["Emission Strength"])
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(volume.outputs["Volume"], output.inputs["Volume"])
    block("Valley_cloud_bank", (0, 73, 0.5), (180, 130, 10), fog, bevel=0)


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    RNG.seed(42)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.use_gtao = True
    scene.eevee.gtao_distance = 2
    scene.eevee.use_soft_shadows = True
    scene.eevee.taa_render_samples = 96
    scene.eevee.shadow_cube_size = "2048"
    scene.eevee.shadow_cascade_size = "4096"
    scene.eevee.use_shadow_high_bitdepth = True
    scene.eevee.volumetric_samples = 64
    scene.eevee.volumetric_tile_size = "4"
    scene.eevee.use_volumetric_shadows = True
    scene.eevee.use_bloom = True
    scene.eevee.bloom_intensity = 0.055
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start = 1
    scene.frame_end = 240
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0.2
    scene.world = bpy.data.worlds.new("Blue_green_evening_sky")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = (0.22, 0.39, 0.47, 1)
    background.inputs["Strength"].default_value = 0.6

    stone = [weathered_material("Mossy_karst_rock", (0.052, 0.09, 0.09),
                                (0.34, 0.35, 0.26), moss=True)]
    distant = [weathered_material("Distant_mineral_cliffs", (0.065, 0.16, 0.17),
                                  (0.20, 0.30, 0.25), moss=True)]
    ivory = weathered_material("Gate_weathered_sandstone", (0.14, 0.15, 0.11),
                               (0.44, 0.40, 0.27), scale=7)
    dark = weathered_material("Glazed_peacock_roof_tiles", (0.012, 0.055, 0.051),
                              (0.065, 0.23, 0.19), metallic=0.25)
    gold = weathered_material("Patinated_ritual_bronze", (0.055, 0.07, 0.045),
                              (0.51, 0.28, 0.075), scale=9, metallic=0.78)
    jade = weathered_material("Carved_green_jade", (0.02, 0.12, 0.085),
                              (0.18, 0.53, 0.33), scale=3)
    jade_shader = jade.node_tree.nodes.get("Principled BSDF")
    jade_shader.inputs["Roughness"].default_value = 0.28
    jade_shader.inputs["Subsurface"].default_value = 0.14
    jade_shader.inputs["Subsurface Color"].default_value = (0.12, 0.42, 0.23, 1)
    jade_shader.inputs["Subsurface Radius"].default_value = (0.35, 0.7, 0.4)
    glow = material("Quiet_jade_light", (0.18, 0.65, 0.38), 2)
    bark = weathered_material("Pine_bark", (0.025, 0.023, 0.015), (0.16, 0.11, 0.055), scale=14)
    needles = material("Pine_needles", (0.035, 0.12, 0.045))
    earth = weathered_material("Cliff_top_moss_and_soil", (0.05, 0.068, 0.033),
                               (0.22, 0.25, 0.12), scale=11)

    ledge("Natural_traveler_ledge", (-3.7, -0.2, 4.13), (5, 3.5), [earth])
    traveler()
    pine((-7.6, 0.9, 4.13), 5.9, bark, needles)
    pine((-6.6, 2.0, 4.13), 3.5, bark, needles)
    for index in range(26):
        x, y = RNG.uniform(-7.5, -0.3), RNG.uniform(-2.6, 2.6)
        if abs(x + 4) < 0.8 and abs(y + 0.6) < 0.9:
            continue
        crag(f"Ledge_loose_rock_{index}", (x, y, 4.08),
             RNG.uniform(0.12, 0.4), RNG.uniform(0.12, 0.38), stone)
    for index in range(7):
        block("Old_paving_slab", (-4.0 + index * 0.6, -0.45 + index * 0.30, 4.14),
              (0.85, 0.60, 0.07), ivory, 0.07)
    for row, y in enumerate((22, 45, 70, 100)):
        for side in (-1, 1):
            for index in range(3):
                x = side * (21 + index * 13 + RNG.uniform(-2, 2))
                crag(f"Mountain_{row}_{side}_{index}", (x, y + RNG.uniform(-5, 5), -9),
                     RNG.uniform(5, 9), RNG.uniform(20, 31), distant if row > 0 else stone)
    gate(ivory, dark, gold, jade, glow)
    for index in range(6):
        crag(f"Suspended_fragment_{index}", (RNG.uniform(-4, 10), 30 + RNG.uniform(-3, 3),
                                           RNG.uniform(1, 5)), RNG.uniform(0.35, 0.7),
             RNG.uniform(0.8, 1.8), stone)
    valley_clouds()

    bpy.ops.object.light_add(type="SUN", location=(10, -10, 30))
    sun = bpy.context.object
    sun.name = "Warm_sun"
    sun.rotation_euler = (math.radians(48), math.radians(-25), math.radians(-42))
    sun.data.energy = 3.4
    sun.data.angle = math.radians(4)
    sun.data.color = (1.0, 0.79, 0.48)
    sun.data.use_shadow = True
    sun.data.use_contact_shadow = True
    bpy.ops.object.light_add(type="SUN")
    sky_fill = bpy.context.object
    sky_fill.name = "Cool_sky_fill"
    sky_fill.rotation_euler = (math.radians(25), math.radians(40), math.radians(135))
    sky_fill.data.energy = 0.65
    sky_fill.data.color = (0.39, 0.64, 1)
    sky_fill.data.use_shadow = False
    bpy.ops.object.light_add(type="AREA", location=(0, -6, 17))
    fill = bpy.context.object
    fill.name = "Traveler_soft_fill"
    fill.data.energy = 1400
    fill.data.size = 12
    fill.data.color = (0.68, 0.81, 1)
    fill.rotation_euler = (Vector((-4, 0, 5)) - fill.location).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.light_add(type="AREA", location=(0, 18, 23))
    gate_light = bpy.context.object
    gate_light.name = "Gate_warm_bounce"
    gate_light.data.energy = 7000
    gate_light.data.size = 9
    gate_light.data.color = (1, 0.75, 0.42)
    gate_light.rotation_euler = (Vector((3, 31, 15)) - gate_light.location).to_track_quat("-Z", "Y").to_euler()

    bpy.ops.object.camera_add(location=(10, -24, 11))
    camera = bpy.context.object
    camera.name = "CAM_ValleyReveal"
    camera.data.lens = 32
    camera.data.clip_end = 400
    camera.data.dof.use_dof = False
    scene.camera = camera
    for frame, location in [(1, (10, -24, 11)), (240, (9, -22, 11))]:
        camera.location = location
        camera.rotation_euler = (Vector((0, 22, 11)) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_euler", frame=frame)
    for curve in camera.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = "LINEAR"

    scene.world.mist_settings.start = 28
    scene.world.mist_settings.depth = 145
    scene.world.mist_settings.falloff = "LINEAR"
    scene.view_layers[0].use_pass_mist = True
    scene.use_nodes = True
    nodes = scene.node_tree.nodes
    nodes.clear()
    layers = nodes.new("CompositorNodeRLayers")
    mix = nodes.new("CompositorNodeMixRGB")
    mix.blend_type = "MIX"
    mix.inputs[2].default_value = (0.22, 0.37, 0.40, 1)
    haze = nodes.new("CompositorNodeMath")
    haze.operation = "MULTIPLY"
    haze.inputs[1].default_value = 0.72
    composite = nodes.new("CompositorNodeComposite")
    scene.node_tree.links.new(layers.outputs["Image"], mix.inputs[1])
    scene.node_tree.links.new(layers.outputs["Mist"], haze.inputs[0])
    scene.node_tree.links.new(haze.outputs[0], mix.inputs[0])
    scene.node_tree.links.new(mix.outputs[0], composite.inputs[0])
    scene.frame_set(1)
    return scene


def add_ambient_motion(scene):
    """Animate cloud texture coordinates and jade emission, not scene geometry."""
    fog_tree = bpy.data.materials["Low_valley_cloud_volume"].node_tree
    cloud = next(node for node in fog_tree.nodes if node.type == "TEX_NOISE")
    coordinates = next(node for node in fog_tree.nodes if node.type == "TEX_COORD")
    flow = fog_tree.nodes.new("ShaderNodeVectorMath")
    flow.name = "Cloud_flow"
    flow.operation = "ADD"
    fog_tree.links.new(coordinates.outputs["Generated"], flow.inputs[0])
    fog_tree.links.new(flow.outputs["Vector"], cloud.inputs["Vector"])
    # Offset the texture only; the cloud bank's vertical envelope stays fixed.
    for frame, offset in ((1, (0, 0, 0)), (240, (0.075, 0.018, 0))):
        flow.inputs[1].default_value = offset
        flow.inputs[1].keyframe_insert(data_path="default_value", frame=frame)
    for curve in fog_tree.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = "LINEAR"

    glow_tree = bpy.data.materials["Quiet_jade_light"].node_tree
    strength = glow_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for frame, value in ((1, 2), (61, 3.4), (121, 2), (181, 3.4), (240, 2)):
        strength.default_value = value
        strength.keyframe_insert(data_path="default_value", frame=frame)
    for curve in glow_tree.animation_data.action.fcurves:
        for key in curve.keyframe_points:
            key.interpolation = "BEZIER"
            key.handle_left_type = "AUTO_CLAMPED"
            key.handle_right_type = "AUTO_CLAMPED"
    scene.frame_set(1)


def validate_ambient_motion(scene):
    """Check actual evaluated shader values over the entire ten-second shot."""
    flow = bpy.data.materials["Low_valley_cloud_volume"].node_tree.nodes["Cloud_flow"].inputs[1]
    glow = bpy.data.materials["Quiet_jade_light"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    if (scene.frame_start, scene.frame_end, scene.render.fps, scene.render.fps_base) != (1, 240, 24, 1):
        raise RuntimeError("Ambient animation requires frames 1-240 at 24 fps")
    values = []
    for frame in range(1, 241):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        expected = Vector((0.075, 0.018, 0)) * ((frame - 1) / 239)
        if (Vector(flow.default_value) - expected).length > 0.00001:
            raise RuntimeError(f"Cloud flow is not linear at frame {frame}")
        value = glow.default_value
        if not 1.9999 <= value <= 3.4001:
            raise RuntimeError(f"Jade emission exceeds its subtle range at frame {frame}: {value}")
        values.append(value)
    if max(values) - min(values) < 1.39:
        raise RuntimeError("Jade emission is not animated")
    scene.frame_set(1)
    print("AMBIENT_PASS: linear cloud flow and bounded jade glow across all 240 frames", flush=True)


def validate_framing(scene):
    from bpy_extras.object_utils import world_to_camera_view

    subjects = [bpy.data.objects[name] for name in
                ("Traveler_Skinned_Appearance", "Gate_upper_eaves", "Jade_bi_relic", "Gate_island")]
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        for subject in subjects:
            evaluated = subject.evaluated_get(bpy.context.evaluated_depsgraph_get())
            points = [world_to_camera_view(scene, scene.camera, evaluated.matrix_world @ Vector(corner))
                      for corner in evaluated.bound_box]
            if not all(0.02 < p.x < 0.98 and 0.02 < p.y < 0.98 and p.z > 0 for p in points):
                raise RuntimeError(f"{subject.name} clips frame {frame}: {[tuple(p) for p in points]}")
    scene.frame_set(1)
    print("FRAMING_PASS: traveler and gate inside camera bounds across all frames", flush=True)


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--final", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.final:
        approved_scene = HERE / "FirstShot_BronzeJade.blend"
        if not approved_scene.is_file():
            raise FileNotFoundError(f"Build and approve the base scene first: {approved_scene}")
        bpy.ops.wm.open_mainfile(filepath=str(approved_scene))
        scene = bpy.context.scene
        add_ambient_motion(scene)
        validate_ambient_motion(scene)
    else:
        scene = build()
    validate_framing(scene)
    renders = HERE / "renders"
    renders.mkdir(exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(renders / ("bronze_jade_final_1080.png" if args.final else "bronze_jade_1080.png"))
    if not args.final:
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "FirstShot_BronzeJade.blend"))
    bpy.ops.render.render(write_still=True)
    print("STILL_COMPLETE", scene.render.filepath, flush=True)
    if args.preview or args.final:
        scene.render.resolution_percentage = 100 if args.final else 50
        scene.eevee.taa_render_samples = 48 if args.final else 16
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "HIGH" if args.final else "MEDIUM"
        scene.render.filepath = str(renders / ("bronze_jade_final.mp4" if args.final else "bronze_jade_preview.mp4"))
        if args.final:
            bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "FirstShot_BronzeJade_Final.blend"))
        bpy.ops.render.render(animation=True)
        print("FINAL_COMPLETE" if args.final else "PREVIEW_COMPLETE", scene.render.filepath, flush=True)


if __name__ == "__main__":
    main()
