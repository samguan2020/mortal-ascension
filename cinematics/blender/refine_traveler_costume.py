"""Add an editable cinematic wardrobe without changing the accepted traveler.

Blender 3.6: --factory-startup -b --python-exit-code 1 --python <this script>
Loads FirstShot_BronzeJade_Final.blend; saves FirstShot_Costume.blend and
renders scene, front and rear wardrobe stills. It does not replace any video.
"""

import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools" / "asset-pipeline"))
from build_liu_appearance import cloth_material, loft, mesh_object, ribbon, sphere, stroke
from traveler_skinning import weights_for_part

PARTS = []
TAU = math.tau


def add(obj, rule):
    obj["cinematic_skinning_rule"] = rule
    PARTS.append(obj)
    return obj


def ellipse(rx, ry, z, opening=0.0, center=(0, 0)):
    return [(center[0] + rx * math.sin(opening + (TAU - 2 * opening) * i / 96),
             center[1] - ry * math.cos(opening + (TAU - 2 * opening) * i / 96), z)
            for i in range(97)]


def hem(name, rx, ry, z, mat, rule, opening=0.0, radius=0.0025):
    return add(stroke(name, ellipse(rx, ry, z, opening), radius, mat), rule)


def tassel(name, origin, length, mat, rule):
    x, y, z = origin
    add(sphere(name + "_knot", origin, (0.013, 0.012, 0.017), mat), rule)
    for i in range(11):
        offset = (i - 5) * 0.0018
        add(stroke(name + "_thread", [(x + offset, y, z - 0.01),
                                     (x + offset * 1.2, y + 0.009, z - length * 0.55),
                                     (x + offset * 1.8, y + 0.014, z - length)],
                   0.0011, mat), rule)


def embroidered_border(name, rx, ry, z, thread, rule, opening=0.5):
    hem(name + "_top", rx, ry, z + 0.020, thread, rule, opening)
    hem(name + "_bottom", rx, ry, z - 0.020, thread, rule, opening)
    for i in range(32):
        theta = opening + (TAU - 2 * opening) * (i + 0.5) / 32
        points = []
        for offset, height in ((-0.035, 0), (0, 0.014), (0.035, 0), (0, -0.014), (-0.035, 0)):
            angle = theta + offset
            points.append((rx * math.sin(angle), -ry * math.cos(angle), z + height))
        add(stroke(name + "_diamond_stitch", points, 0.0014, thread), rule)


def cuff(side, cloth, thread):
    axis = Vector((0.55 * side, -0.1, -0.83)).normalized()
    across = Vector((0, 1, 0))
    down = axis.cross(across).normalized()
    center = Vector((0.353 * side, -0.050, 1.002))
    vertices, faces, uvs = [], [], []
    for row in range(5):
        t = row / 4
        middle = center - axis * (0.07 * (1 - t))
        for i in range(65):
            theta = i / 64 * TAU
            point = middle + across * math.cos(theta) * 0.134 + down * math.sin(theta) * 0.166
            vertices.append(point)
            uvs.append((i / 64, t))
            if row < 4 and i < 64:
                a = row * 65 + i
                faces.append((a, a + 1, a + 66, a + 65))
    obj = add(mesh_object(f"Cinematic_cuff_{side}", vertices, faces, cloth, uvs), "Sleeve_cinematic")
    obj.modifiers.new("Turned cuff", "SOLIDIFY").thickness = 0.004
    for row in (0, 4):
        add(stroke(f"Cuff_braid_{side}", vertices[row * 65:(row + 1) * 65], 0.003, thread),
            "Cuff_piping_cinematic")
    for i in range(24):
        theta = (i + 0.5) / 24 * TAU
        points = []
        for dt, along in ((-0.055, -0.035), (0, -0.018), (0.055, -0.035), (0, -0.052)):
            points.append(center + axis * along + across * math.cos(theta + dt) * 0.137
                          + down * math.sin(theta + dt) * 0.169)
        add(stroke("Cuff_cloud_stitch", points, 0.0015, thread), "Cuff_piping_cinematic")


def build_costume():
    PARTS.clear()
    indigo = cloth_material("Costume_indigo_brocade", (0.035, 0.085, 0.11), (0.39, 0.31, 0.14))
    teal = cloth_material("Costume_jade_shoulder_weave", (0.045, 0.15, 0.14), (0.45, 0.36, 0.19))
    oxblood = cloth_material("Costume_ochre_red_lining", (0.21, 0.057, 0.038), (0.50, 0.32, 0.12))
    linen = cloth_material("Costume_layered_linen", (0.40, 0.36, 0.24), (0.62, 0.52, 0.30))
    leather = cloth_material("Costume_worn_leather", (0.09, 0.041, 0.019), (0.28, 0.16, 0.057))
    for material in (indigo, teal, oxblood, linen, leather):
        nodes, links = material.node_tree.nodes, material.node_tree.links
        shader = nodes["Principled BSDF"]
        shader.inputs["Sheen"].default_value = 0.18
        fiber = nodes.new("ShaderNodeTexNoise")
        fiber.inputs["Scale"].default_value = 210
        fiber.inputs["Detail"].default_value = 2
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.22
        bump.inputs["Distance"].default_value = 0.001
        links.new(fiber.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    subject = bpy.data.objects["Traveler_Skinned_Appearance"]
    for slot in subject.material_slots:
        if slot.material.name == "Traveler_slate_blue_coat":
            slot.material = slot.material.copy()
            slot.material.name = "Costume_matching_slate_sleeves"
            nodes, links = slot.material.node_tree.nodes, slot.material.node_tree.links
            base = nodes["Principled BSDF"].inputs["Base Color"]
            texture = base.links[0].from_socket
            tint = nodes.new("ShaderNodeMixRGB")
            tint.blend_type = "MULTIPLY"
            tint.inputs[0].default_value = 1
            tint.inputs[2].default_value = (0.50, 0.70, 0.73, 1)
            links.new(texture, tint.inputs[1])
            links.new(tint.outputs[0], base)
    thread = bpy.data.materials["Aged_brass_and_ochre"].copy()
    thread.name = "Costume_old_gold_thread"
    shader = thread.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (0.43, 0.27, 0.075, 1)
    shader.inputs["Metallic"].default_value = 0.32
    shader.inputs["Roughness"].default_value = 0.65
    jade = bpy.data.materials["Carved_green_jade"]

    add(loft("Costume_inner_pleated_skirt", [
        (0.305, 0.255, 0.185), (0.32, 0.256, 0.185), (0.50, 0.249, 0.179),
        (0.72, 0.244, 0.175), (0.89, 0.231, 0.165),
    ], linen, opening=0.28, folds=0.007), "Split_outer_coat")
    add(loft("Costume_split_travel_coat", [
        (0.37, 0.288, 0.207), (0.385, 0.286, 0.205), (0.55, 0.270, 0.194),
        (0.75, 0.256, 0.181), (0.89, 0.244, 0.172), (0.98, 0.237, 0.163),
    ], indigo, opening=0.60, folds=0.014), "Split_outer_coat")
    embroidered_border("Coat_hem", 0.293, 0.212, 0.405, thread, "Split_outer_coat", opening=0.60)
    hem("Linen_hem", 0.262, 0.191, 0.325, thread, "Split_outer_coat", opening=0.28, radius=0.0018)
    for sign in (-1, 1):
        points = [(sign * rx * math.sin(0.60), -ry * math.cos(0.60) - 0.006, z)
                  for z, rx, ry in ((0.38, 0.293, 0.213), (0.55, 0.277, 0.20),
                                    (0.75, 0.263, 0.187), (0.965, 0.245, 0.172))]
        add(stroke("Split_coat_edge", points, 0.003, thread), "Split_outer_coat")

    add(loft("Costume_shoulder_lining", [
        (1.19, 0.31, 0.204), (1.22, 0.311, 0.205), (1.30, 0.285, 0.176),
        (1.36, 0.250, 0.157), (1.40, 0.171, 0.120), (1.438, 0.089, 0.082),
    ], oxblood, opening=0.56, folds=0.002), "Tailored_shoulder_yoke")
    add(loft("Costume_layered_shoulder_mantle", [
        (1.225, 0.312, 0.207), (1.245, 0.314, 0.208), (1.30, 0.292, 0.18),
        (1.36, 0.255, 0.161), (1.40, 0.177, 0.125), (1.443, 0.091, 0.084),
    ], teal, opening=0.56, folds=0.002), "Tailored_shoulder_yoke")
    embroidered_border("Mantle_border", 0.316, 0.212, 1.246, thread, "Tailored_shoulder_yoke", opening=0.56)
    hem("Mantle_upper_piping", 0.095, 0.089, 1.442, thread, "Tailored_shoulder_yoke", opening=0.56)
    for sign in (-1, 1):
        add(stroke("Mantle_front_seam", [
            (sign * 0.050, -0.078, 1.440), (sign * 0.10, -0.11, 1.395),
            (sign * 0.151, -0.151, 1.30), (sign * 0.167, -0.184, 1.23),
        ], 0.003, thread), "Tailored_shoulder_yoke")
        cuff(sign, indigo, thread)

    lapel = add(ribbon("Costume_cross_lapel", [
        (0.062, -0.09, 1.437), (0.106, -0.136, 1.36), (0.025, -0.178, 1.25),
        (-0.093, -0.191, 1.09), (-0.176, -0.179, 0.973),
    ], [0.042, 0.055, 0.060, 0.058, 0.050], oxblood, conform=True), "Outer_cross_lapel")
    for vertex in lapel.data.vertices:
        vertex.co.y -= 0.020
    columns = lapel["ribbon_columns"]
    for column in (0, columns - 1):
        add(stroke("Lapel_brocade_edge", [
            v.co + Vector((0, -0.004, 0)) for v in list(lapel.data.vertices)[column::columns]
        ], 0.0022, thread), "Lapel_stitched_edge")

    add(loft("Costume_wide_leather_waistband", [
        (0.883, 0.246, 0.179), (0.895, 0.247, 0.180),
        (0.962, 0.242, 0.173), (0.977, 0.239, 0.171),
    ], leather, folds=0.001), "Waist_sash")
    for z, rx, ry in ((0.897, 0.251, 0.184), (0.967, 0.246, 0.178)):
        hem("Belt_stitched_edge", rx, ry, z, thread, "Waist_sash", radius=0.0018)
    add(sphere("Costume_bronze_buckle", (0, -0.190, 0.935), (0.051, 0.013, 0.033), thread), "Waist_sash")
    add(sphere("Costume_jade_buckle_inlay", (0, -0.205, 0.935), (0.026, 0.008, 0.020), jade), "Waist_sash")
    for sign in (-1, 1):
        for index in range(4):
            theta = sign * (0.30 + index * 0.19)
            add(sphere("Belt_bronze_stud", (0.252 * math.sin(theta), -0.185 * math.cos(theta), 0.934),
                       (0.006, 0.005, 0.008), thread), "Waist_sash")
        sash = add(ribbon("Costume_layered_sash", [
            (sign * 0.14, -0.19, 0.94), (sign * 0.17, -0.206, 0.81),
            (sign * 0.19, -0.22, 0.65), (sign * 0.17, -0.23, 0.49),
        ], [0.043, 0.049, 0.048, 0.04], oxblood), "Sash_hanging_end")
        for column in (0, 1):
            add(stroke("Sash_gold_border", [v.co + Vector((0, -0.004, 0))
                                           for v in list(sash.data.vertices)[column::2]],
                       0.0018, thread), "Sash_hanging_end")
        tassel("Sash_fringe", (sign * 0.17, -0.23, 0.48), 0.065, thread, "Sash_hanging_end")

    add(stroke("Jade_charm_cord", [(-0.19, -0.14, 0.94), (-0.26, -0.18, 0.85),
                                  (-0.265, -0.19, 0.76)], 0.0035, oxblood), "Waist_sash")
    add(sphere("Jade_wayfarer_charm", (-0.265, -0.192, 0.755), (0.026, 0.012, 0.038), jade), "Waist_sash")
    tassel("Jade_charm_tassel", (-0.265, -0.192, 0.71), 0.07, thread, "Waist_sash")
    add(sphere("Travel_purse", (-0.28, 0.052, 0.81), (0.058, 0.048, 0.080), leather), "Waist_sash")
    add(stroke("Purse_drawstring", [(-0.24, 0.025, 0.94), (-0.28, 0.052, 0.89),
                                  (-0.30, 0.09, 0.855)], 0.004, thread), "Waist_sash")
    add(sphere("Pilgrim_gourd_lower", (0.30, 0.07, 0.75), (0.046, 0.040, 0.059), leather), "Waist_sash")
    add(sphere("Pilgrim_gourd_upper", (0.30, 0.07, 0.820), (0.029, 0.028, 0.036), leather), "Waist_sash")
    add(stroke("Gourd_suspension", [(0.22, 0.08, 0.95), (0.30, 0.072, 0.86),
                                  (0.32, 0.09, 0.80)], 0.004, thread), "Waist_sash")

    for sign in (-1, 1):
        add(stroke("Pack_leather_reinforcement", [
            (sign * 0.10, 0.288, 1.275), (sign * 0.125, 0.309, 1.16),
            (sign * 0.10, 0.29, 1.01),
        ], 0.010, leather), "Traveler_cloth_pack")
        for index in range(9):
            z = 1.045 + index * 0.025
            x = sign * (0.10 + 0.019 * math.sin(index / 8 * math.pi))
            add(stroke("Pack_hand_stitch", [(x - 0.007, 0.318, z),
                                            (x + 0.007, 0.318, z + 0.004)],
                       0.0012, thread), "Traveler_cloth_pack")
        for z in (0.14, 0.20, 0.245):
            add(stroke("Boot_cross_binding", ellipse(0.083, 0.087, z, center=(sign * 0.105, 0)),
                       0.003, oxblood), "Traveler_boot_upper_cinematic")
    for index in range(2):
        x = 0.165 + index * 0.049
        scroll = add(loft("Pack_scroll_case", [(1.03, 0.023, 0.023), (1.04, 0.024, 0.024),
                                             (1.31, 0.024, 0.024), (1.32, 0.023, 0.023)],
                          leather, segments=32, folds=0), "Traveler_cloth_pack")
        scroll.location = (x, 0.252, 0)
        add(sphere("Scroll_paper_end", (x, 0.252, 1.322), (0.020, 0.020, 0.005), linen), "Traveler_cloth_pack")
        for z in (1.06, 1.28):
            add(stroke("Scroll_binding", ellipse(0.028, 0.028, z, center=(x, 0.252)),
                       0.0025, thread), "Traveler_cloth_pack")
    add(stroke("Costume_jade_hairpin", [(-0.093, 0.075, 1.735), (0.087, 0.075, 1.735)],
               0.004, thread), "Wooden_hairpin")
    add(sphere("Hairpin_jade_tip", (0.097, 0.075, 1.735), (0.014, 0.009, 0.009), jade), "Wooden_hairpin")
    for sign in (-1, 1):
        add(ribbon("Costume_hair_streamer", [
            (sign * 0.016, 0.102, 1.734), (sign * 0.035, 0.143, 1.62),
            (sign * 0.040, 0.132, 1.49),
        ], [0.012, 0.016, 0.018], oxblood), "Traveler_hair_tie")


def fit_embroidery():
    """Keep raised embroidery above the evaluated pleats, not inside them."""
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    targets = {
        "Coat_hem": bpy.data.objects["Costume_split_travel_coat"].evaluated_get(graph),
        "Split_coat_edge": bpy.data.objects["Costume_split_travel_coat"].evaluated_get(graph),
        "Mantle_border": bpy.data.objects["Costume_layered_shoulder_mantle"].evaluated_get(graph),
    }
    for part in PARTS:
        for prefix, surface in targets.items():
            if not part.name.startswith(prefix):
                continue
            for spline in part.data.splines:
                for point in spline.bezier_points:
                    found, position, normal, _ = surface.closest_point_on_mesh(point.co)
                    if not found:
                        raise RuntimeError(f"Cannot fit embroidery: {part.name}")
                    if normal.dot(Vector((position.x, position.y, 0))) < 0:
                        normal = -normal
                    point.co = position + normal * 0.006


def bind_costume(rig):
    """Reuse the traveler's existing deterministic garment-weight rules."""
    collection = bpy.data.collections.new("Cinematic_traveler_costume")
    bpy.context.scene.collection.children.link(collection)
    for index, part in enumerate(PARTS):
        rule = part["cinematic_skinning_rule"]
        bpy.ops.object.select_all(action="DESELECT")
        part.select_set(True)
        bpy.context.view_layer.objects.active = part
        bpy.ops.object.convert(target="MESH")
        part = bpy.context.object
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        groups = {bone.name: part.vertex_groups.new(name=bone.name) for bone in rig.data.bones}
        for vertex in part.data.vertices:
            for bone, weight in weights_for_part(rule, vertex.co).items():
                groups[bone].add([vertex.index], weight, "REPLACE")
        modifier = part.modifiers.new("Cinematic wardrobe skin", "ARMATURE")
        modifier.object = rig
        part.parent = rig
        collection.objects.link(part)
        for owner in list(part.users_collection):
            if owner != collection:
                owner.objects.unlink(part)
        PARTS[index] = part
    bpy.ops.object.select_all(action="DESELECT")


def validate_costume(scene):
    from bpy_extras.object_utils import world_to_camera_view

    for part in PARTS:
        if not part.data.vertices or any(not v.groups for v in part.data.vertices):
            raise RuntimeError(f"Unweighted costume geometry: {part.name}")
        for vertex in part.data.vertices:
            if abs(sum(group.weight for group in vertex.groups) - 1) > 0.0001:
                raise RuntimeError(f"Invalid weights in {part.name}")
    for frame in (1, 61, 120, 181, 240):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        for part in PARTS:
            evaluated = part.evaluated_get(graph)
            for corner in evaluated.bound_box:
                point = world_to_camera_view(scene, scene.camera, evaluated.matrix_world @ Vector(corner))
                if not (0.015 < point.x < 0.985 and 0.015 < point.y < 0.985 and point.z > 0):
                    raise RuntimeError(f"Costume clips frame {frame}: {part.name}")
    scene.frame_set(1)
    print(f"COSTUME_PASS: {len(PARTS)} weighted parts; five animation poses remain in frame", flush=True)


def portraits(scene, renders):
    subject = bpy.data.objects["Traveler_Skinned_Appearance"]
    root = bpy.data.objects["Traveler_placement"]
    for obj in scene.objects:
        if obj.type in {"MESH", "CURVE"} and obj != subject and obj not in PARTS:
            obj.hide_render = True
    scene.use_nodes = False
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.035, 0.048, 0.044, 1)
    scene.render.resolution_x = 960
    scene.render.resolution_y = 1080
    scene.view_settings.exposure = 0
    for name, position, energy in (
        ("Portrait_warm_key", (2, -3, 3.1), 850),
        ("Portrait_cool_rim", (-2, 2, 2.8), 1100),
    ):
        bpy.ops.object.light_add(type="AREA", location=root.matrix_world @ Vector(position))
        light = bpy.context.object
        light.name = name
        light.data.energy = energy
        light.data.size = 3
        light.rotation_euler = (root.matrix_world @ Vector((0, 0, 1)) - light.location).to_track_quat("-Z", "Y").to_euler()
    for name, position in (("front", (2.5, -5, 2.2)), ("rear", (-2.6, 4.8, 2.2))):
        bpy.ops.object.camera_add(location=root.matrix_world @ Vector(position))
        camera = bpy.context.object
        camera.name = "Costume_portrait_" + name
        camera.data.type = "ORTHO"
        camera.data.ortho_scale = 3.8
        camera.rotation_euler = (root.matrix_world @ Vector((0, 0, 0.91)) - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.camera = camera
        scene.render.filepath = str(renders / f"traveler_costume_{name}.png")
        bpy.ops.render.render(write_still=True)
        print("PORTRAIT_COMPLETE", scene.render.filepath, flush=True)


def main():
    source = HERE / "FirstShot_BronzeJade_Final.blend"
    if not source.is_file():
        raise FileNotFoundError(f"Approved cinematic scene missing: {source}")
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    scene.frame_set(1)
    build_costume()
    fit_embroidery()
    bind_costume(bpy.data.objects["Traveler_Rig"])
    validate_costume(scene)
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_percentage = 100
    scene.eevee.taa_render_samples = 96
    renders = HERE / "renders"
    renders.mkdir(exist_ok=True)
    scene.render.filepath = str(renders / "traveler_costume_scene.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "FirstShot_Costume.blend"))
    bpy.ops.render.render(write_still=True)
    print("SCENE_COMPLETE", scene.render.filepath, flush=True)
    portraits(scene, renders)


if __name__ == "__main__":
    main()
