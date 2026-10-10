"""Isolated, static Hero refinement using the portrait pipeline's shared helpers."""

import json
import math
import time

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


HERO_HASH = "EAC98668108CC7B50BDDACC05E1D42A1FB4E0B2D136DC3A68803EDA074BEF93D"
PREFIX = "traveler_flowing"


def rest_point(api, point, region):
    """Invert the existing mild baked pose without changing the source rig."""
    result = point.copy()
    for _ in range(9):
        result += point - api.pose_point(result, region)
    if (api.pose_point(result, region) - point).length > 1e-6:
        raise RuntimeError("Flowing face inverse-pose residual exceeds one micron")
    return result


def sculpt(point):
    """Small anatomical edits; preserve identity and the complete ocular assembly."""
    p = point.copy()
    x, y, z = p
    front = min(1, max(0, (-y - .095) / .045))

    def field(cx, cz, sx, sz):
        return front * math.exp(-((abs(x) - cx) / sx) ** 2 - ((z - cz) / sz) ** 2)

    p.x -= math.copysign(.0018 * field(.020, 1.547, .013, .013), x)
    p.y -= .0016 * field(0, 1.566, .010, .020)
    p.z += .0009 * field(0, 1.549, .012, .008)
    p.y -= .0010 * field(.057, 1.566, .018, .015)
    p.y += .0008 * field(.056, 1.536, .025, .024)
    p.x -= math.copysign(.0007 * field(.071, 1.493, .019, .014), x)
    p.z += .0012 * field(.029, 1.509, .007, .007)
    p.y += .0007 * field(.029, 1.509, .008, .006)
    p.z += .0007 * field(.009, 1.516, .006, .004)
    p.y += .0022 * field(.036, 1.598, .021, .005)
    p.y += .0010 * field(.036, 1.584, .019, .004)
    p.z += .0005 * field(.036, 1.598, .019, .005)
    return p


def refine_face(api, collection):
    """Reshape copied facial surfaces and replace rectangular brow boundaries."""
    head = next(o for o in collection.objects if o.name.startswith("Portrait_reference_face_and_hands"))
    ocular = {i for p in head.data.polygons if p.material_index in (1, 2, 3) for i in p.vertices}
    eyes_before = {i: head.data.vertices[i].co.copy() for i in ocular}
    changed = 0
    for obj in list(collection.objects):
        if not obj.name.startswith("Portrait_") or obj.hide_render:
            continue
        if obj.name.startswith(("Portrait_angled_flat_brow", "Portrait_brow_fiber",
                                "Portrait_short_moustache")):
            obj.hide_render = obj.hide_viewport = True
            continue
        for vertex in obj.data.vertices:
            if obj == head and (vertex.index in ocular or vertex.co.z < 1.46):
                continue
            region = "body" if obj == head else "head"
            old = rest_point(api, vertex.co, region)
            new = sculpt(old)
            if (new - old).length > 1e-7:
                vertex.co = api.pose_point(new, region)
                changed += 1
        obj.data.update()
    bpy.context.view_layer.update()

    def face(x, z, offset=.0007):
        origin = api.pose_point(Vector((x, -.5, z)), "head")
        direction = (api.pose_point(Vector((x, 0, z)), "head") - origin).normalized()
        hit, position, normal, _ = head.ray_cast(origin, direction)
        if not hit:
            raise RuntimeError(f"Flowing facial detail missed skin: {x}, {z}")
        return position + normal * offset

    boundary = bpy.data.materials["Portrait_feathered_brow_density"]
    brow_mat = next(m for m in head.data.materials if "dark_brows" in m.name)
    for side in (-1, 1):
        vertices, faces = [], []
        for row in range(49):
            t = row / 48
            x = side * (.009 + .060 * t)
            z = 1.610 + .0058 * math.sin(math.pi * t * .88) - .0020 * t
            width = .0078 * math.sin(math.pi * (.10 + .90 * t)) ** .7
            for col in range(7):
                vertices.append(face(x, z + (col / 6 - .5) * width))
                if row < 48 and col < 6:
                    a = row * 7 + col
                    faces.append((a, a + 1, a + 8, a + 7))
        brow = api.part(api.mesh_object("Flowing_graceful_brow", vertices, faces, boundary), "head")
        opacity = brow.data.color_attributes.new(name="PortraitHairOpacity", type="FLOAT_COLOR", domain="POINT")
        for index, datum in enumerate(opacity.data):
            row, col = divmod(index, 7)
            datum.color = (1, 1, 1, .93 * math.sin(math.pi * col / 6) ** .5
                           * min(1, row / 5, (48 - row) / 5))
        for i in range(35):
            t = (i + .19 * math.sin(i * 2.4)) / 35
            x = side * (.011 + .056 * t)
            z = 1.610 + .0058 * math.sin(math.pi * t * .88) - .002 * t
            z += .0015 * math.sin(i * 2.4)
            api.part(api.stroke("Flowing_brow_growth", [face(x, z), face(x + side * .0018, z + .0007)],
                                .00012, brow_mat, [.5, .02]), "head")
        for i in range(65):
            t, depth = (i * .618033989) % 1, (i * .754877666) % 1
            x = side * (.004 + .030 * t)
            z = 1.530 - .008 * t - .006 * depth * math.sin(.22 + t * math.pi * .78)
            api.part(api.stroke("Flowing_groomed_moustache",
                                [face(x, z), face(x + side * .0008, z - .0008)],
                                .00010, brow_mat, [.5, .02]), "head")
    delta = max((head.data.vertices[i].co - p).length for i, p in eyes_before.items())
    if delta > 1e-7:
        raise RuntimeError("Flowing refinement displaced ocular components")
    coordinates = api.np.array([list(head.data.vertices[i].co) for i in sorted(ocular)], dtype=api.np.float32)
    return {"anatomy_object": head.name, "changed_surface_vertices": changed,
            "ocular_vertices_checked": len(ocular), "ocular_maximum_displacement_m": delta,
            "ocular_sha256": api.hashlib.sha256(coordinates.tobytes()).hexdigest()}


def catmull(points, t):
    """Interpolate authored S-curve stations with continuous tangents."""
    position = min(t, 1 - 1e-9) * (len(points) - 1)
    i = int(position)
    u = position - i
    a, b, c, d = (points[max(0, min(len(points) - 1, j))] for j in (i - 1, i, i + 1, i + 2))
    return .5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u
                 + (-a + 3 * b - 3 * c + d) * u ** 3)


def build_hair(api):
    """Five flattened, ridged lock volumes with subordinate split tapered ends."""
    mat = api.material("flowing_natural_hair", (.006, .0065, .007), .74, noise=.035, bump=0)
    mat.blend_method = mat.shadow_method = "HASHED"
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    opacity = nodes.new("ShaderNodeVertexColor")
    opacity.layer_name = "FlowingRootOpacity"
    links.new(opacity.outputs["Alpha"], nodes["Principled BSDF"].inputs["Alpha"])
    uv = nodes.new("ShaderNodeTexCoord")
    stretch = nodes.new("ShaderNodeVectorMath")
    stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = (170, 3, 1)
    links.new(uv.outputs["UV"], stretch.inputs[0])
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1
    noise.inputs["Detail"].default_value = 2
    links.new(stretch.outputs[0], noise.inputs["Vector"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .38
    bump.inputs["Distance"].default_value = .0008
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs[0], nodes["Principled BSDF"].inputs["Normal"])
    roughness = nodes.new("ShaderNodeMapRange")
    roughness.inputs["To Min"].default_value = .62
    roughness.inputs["To Max"].default_value = .80
    links.new(noise.outputs["Fac"], roughness.inputs["Value"])
    links.new(roughness.outputs[0], nodes["Principled BSDF"].inputs["Roughness"])
    tint = nodes.new("ShaderNodeValToRGB")
    tint.color_ramp.elements[0].position = .28
    tint.color_ramp.elements[0].color = (.0025, .0028, .003, 1)
    tint.color_ramp.elements[1].position = .72
    tint.color_ramp.elements[1].color = (.012, .0125, .013, 1)
    links.new(noise.outputs["Fac"], tint.inputs[0])
    links.new(tint.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
    nodes["Principled BSDF"].inputs["Specular"].default_value = .22
    scalp = bpy.data.objects["Hero_lifted_continuous_swept_locks"]
    tree = BVHTree.FromPolygons([v.co for v in scalp.data.vertices],
                               [list(p.vertices) for p in scalp.data.polygons])
    paths = [
        [(-.100, .043, 1.653), (-.121, .068, 1.515), (-.168, .173, 1.386), (-.177, .272, 1.245), (-.108, .263, 1.112)],
        [(-.070, .090, 1.658), (-.072, .130, 1.504), (-.105, .251, 1.382), (-.081, .301, 1.217), (.013, .292, 1.056)],
        [(.002, .106, 1.667), (.006, .142, 1.520), (.016, .263, 1.372), (.071, .318, 1.203), (.155, .310, 1.089)],
        [(.069, .088, 1.654), (.078, .124, 1.507), (.111, .250, 1.383), (.175, .330, 1.229), (.237, .308, 1.131)],
        [(.103, .039, 1.639), (.132, .062, 1.500), (.177, .161, 1.388), (.232, .262, 1.283), (.275, .281, 1.193)],
    ]
    root_distances, lengths = [], []
    fiber_vertices, fiber_faces = [], []

    def lock(name, controls, width, depth, phase, principal=False):
        points = [api.pose_point(Vector(p), "head") for p in controls]
        root, normal, _, _ = tree.find_nearest(points[0])
        points[0] = root - normal * .003
        vertices, faces, uvs = [], [], []
        columns = 24 if principal else 12
        samples = []
        for row in range(65):
            t = row / 64
            p = catmull(points, t)
            tangent = (catmull(points, min(1, t + .001)) - catmull(points, max(0, t - .001))).normalized()
            lateral = Vector((1, .17 * math.sin(math.pi * t + phase), .05))
            across = (lateral - tangent * lateral.dot(tangent)).normalized()
            normal = tangent.cross(across).normalized()
            taper = (.75 + .25 * math.sin(math.pi * t)) * max(.004, (1 - t ** 3)) ** 1.05
            taper *= 1 + .045 * math.sin(t * 15 + phase) * math.sin(math.pi * t)
            ring = []
            for col in range(columns + 1):
                angle = math.tau * col / columns
                ridge = 1 + .025 * math.cos(angle * 5 + .3 * math.sin(t * 7 + phase))
                point = (p + across * (width * taper * math.cos(angle))
                         + normal * (depth * taper * math.sin(angle) * ridge))
                if t < .22:
                    surface, outward, _, _ = tree.find_nearest(point)
                    blend = min(1, t / .22)
                    blend = blend * blend * (3 - 2 * blend)
                    point = (surface + outward * .0004).lerp(point, blend)
                vertices.append(point)
                ring.append(point)
                uvs.append((col / columns, t))
                if row < 64 and col < columns:
                    a = row * (columns + 1) + col
                    faces.append((a, a + 1, a + columns + 2, a + columns + 1))
            samples.append(ring)
        obj = api.part(api.mesh_object(name, vertices, faces, mat, uvs), "head")
        opacity = obj.data.color_attributes.new(name="FlowingRootOpacity", type="FLOAT_COLOR", domain="POINT")
        for index, datum in enumerate(opacity.data):
            t = (index // (columns + 1)) / 64
            fade = min(1, t / .20)
            datum.color = (1, 1, 1, fade * fade * (3 - 2 * fade))
        obj["flowing_principal"] = principal
        obj["flowing_root"] = list(points[0])
        obj["flowing_tip"] = list(points[-1])
        obj["pose_status"] = "Authored static wind; not simulated or animation-ready"
        root_distances.append(max(tree.find_nearest(p)[3] for p in samples[0]))
        lengths.append(sum((catmull(points, (i + 1) / 64) - catmull(points, i / 64)).length for i in range(64)))
        if principal:
            for strand in range(14):
                angle = math.tau * (strand + .27) / 14
                col = angle / math.tau * columns
                left = int(col)
                start = len(fiber_vertices)
                for row in range(24):
                    t = row / 23
                    sample = samples[round(t * 64)]
                    point = sample[left].lerp(sample[(left + 1) % columns], col - left)
                    center = sum(sample[:-1], Vector()) / columns
                    point += (point - center).normalized() * (.00055 * math.sin(math.pi * t))
                    for corner in range(3):
                        a = math.tau * corner / 3
                        radius = .00014 * math.sin(math.pi * t) ** .5
                        fiber_vertices.append(point + Vector((math.cos(a), math.sin(a), 0)) * radius)
                        if row < 23:
                            i = start + row * 3 + corner
                            n = start + row * 3 + (corner + 1) % 3
                            fiber_faces.append((i, n, n + 3, i + 3))

    for i, path in enumerate(paths):
        lock(f"Flowing_principal_lock_{i + 1}", path, (.037, .043, .047, .041, .031)[i],
             .010 if i in (0, 4) else .013, i, True)
        for j in range(2):
            smaller = [list(p) for p in path]
            for k, p in enumerate(smaller):
                t = k / 4
                p[0] += (j * 2 - 1) * (.010 + .023 * math.sin(math.pi * t)) + .018 * t ** 3
                p[1] += .008 + .012 * math.sin(math.pi * t + j * .5)
                p[2] += (.060 + .010 * math.sin(i) if j else -.014) * t
            lock(f"Flowing_split_lock_{i + 1}_{j + 1}", smaller, .010 + .002 * j, .004, i + j)
    fiber = api.material("flowing_soft_fibers", (.009, .0095, .010), .78, noise=.025, bump=0)
    fiber.node_tree.nodes["Principled BSDF"].inputs["Specular"].default_value = .18
    api.part(api.mesh_object("Flowing_longitudinal_fine_fibers", fiber_vertices, fiber_faces, fiber), "head")
    if max(root_distances) > .0005:
        raise RuntimeError(f"Long hair roots detached: {root_distances}")
    return {"principal_masses": 5, "secondary_locks": 10,
            "root_maximum_surface_distance_m": max(root_distances),
            "principal_arc_lengths_m": lengths[::3],
            "new_hair_vertices": 5 * 65 * 25 + 10 * 65 * 13 + len(fiber_vertices),
            "wind": "Authored S curves toward character right; static, no simulation"}


def validate_hair(api, scene):
    """Check rendered root contact, gear intersections and long-hair framing."""
    from bpy_extras.object_utils import world_to_camera_view

    hair = [o for o in scene.objects if o.name.startswith(("Flowing_principal_lock", "Flowing_split_lock"))]
    if len(hair) != 15 or sum(bool(o["flowing_principal"]) for o in hair) != 5:
        raise RuntimeError("Flowing long-hair mass count changed")
    vertices, polygons = [], []
    for name in ("Study_editable_baked_character", "Ornate_fitted_layers_and_craft"):
        for obj in bpy.data.collections[name].objects:
            if obj.hide_render or obj.type != "MESH":
                continue
            offset = len(vertices)
            vertices.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
            polygons.extend([offset + i for i in p.vertices] for p in obj.data.polygons)
    gear = BVHTree.FromPolygons(vertices, polygons)
    scalp = bpy.data.objects["Hero_lifted_continuous_swept_locks"]
    roots = BVHTree.FromPolygons([v.co for v in scalp.data.vertices],
                                [list(p.vertices) for p in scalp.data.polygons])
    max_distance = 0
    bounds = [1, 1, 0, 0]
    for obj in hair:
        tree = BVHTree.FromPolygons([v.co for v in obj.data.vertices],
                                   [list(p.vertices) for p in obj.data.polygons])
        if tree.overlap(gear):
            raise RuntimeError(f"Long hair intersects preserved wardrobe: {obj.name}")
        columns = 25 if obj["flowing_principal"] else 13
        max_distance = max(max_distance, max(roots.find_nearest(v.co)[3] for v in obj.data.vertices[:columns]))
        if max_distance > .0005:
            raise RuntimeError(f"Saved long hair roots lost scalp contact: {max_distance}")
        for name in ("rear", "flowing_side", "flowing_rear"):
            camera = scene.objects.get("Study_camera_" + name)
            if camera is None:
                if name == "rear":
                    raise RuntimeError("Required rear camera missing")
                continue
            for vertex in obj.data.vertices:
                p = world_to_camera_view(scene, camera, vertex.co)
                bounds = [min(bounds[0], p.x), min(bounds[1], p.y), max(bounds[2], p.x), max(bounds[3], p.y)]
                if not (.02 < p.x < .98 and .02 < p.y < .98 and p.z > 0):
                    raise RuntimeError(f"Long hair clipped in {name}: {obj.name}")
    return {"wardrobe_triangle_intersections": 0, "root_maximum_distance_m": max_distance,
            "rear_side_hair_normalized_bounds": bounds}


def run(api, preview_only=False):
    """Load only accepted Hero and publish only this branch's named outputs."""
    started = time.perf_counter()
    output = api.HERE / "FirstShot_TravelerFlowing.blend"
    source = api.ROOT / "assets" / "source" / "characters" / "player_traveler_rigged.blend"
    accepted = api.HERE / "FirstShot_TravelerHero.blend"
    preserved = [source, api.HERE / "refine_traveler_costume.py"]
    preserved += [p for p in api.HERE.glob("*.blend") if p != output]
    preserved += [p for p in api.RENDERS.iterdir() if p.is_file() and not p.name.startswith(PREFIX + "_")]
    before = {str(p.relative_to(api.ROOT)): api.digest(p) for p in preserved}
    if api.digest(accepted) != HERO_HASH or api.digest(source) != api.SOURCE_HASH:
        raise RuntimeError("Accepted Hero or source rig fingerprint changed")
    bpy.ops.wm.open_mainfile(filepath=str(accepted))
    scene = bpy.context.scene
    original = next(s for s in bpy.data.scenes if s.camera and s.camera.name == "CAM_ValleyReveal")
    original_name, original_camera = original.name, original.camera.name
    hero = bpy.data.collections["Hero_localized_face_and_groom"]
    editable = {o.name for o in hero.objects if o.name.startswith("Portrait_")}
    protected = [o.name for o in scene.objects if o.name not in editable]
    fingerprint = api.studio_fingerprint(scene, protected)
    api.PARTS.clear()
    face = refine_face(api, hero)
    hair = build_hair(api)
    collection = bpy.data.collections.new("Flowing_face_details_and_long_hair")
    scene.collection.children.link(collection)
    for obj in api.PARTS:
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        collection.objects.link(obj)
        if obj.type != "MESH":
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.convert(target="MESH")
    names = ("Study_editable_baked_character", "Ornate_fitted_layers_and_craft",
             "Hero_localized_face_and_groom", collection.name)

    def validate():
        api.PARTS.clear()
        api.PARTS.extend(o for name in names for o in bpy.data.collections[name].objects if not o.hide_render)
        evidence = api.validate(bpy.context.scene, bpy.data.scenes[original_name], original_camera)
        if api.studio_fingerprint(bpy.context.scene, protected) != fingerprint:
            raise RuntimeError("Flowing refinement changed preserved scalp, wardrobe or studio")
        head = bpy.data.objects[face["anatomy_object"]]
        ocular = {i for p in head.data.polygons if p.material_index in (1, 2, 3) for i in p.vertices}
        coordinates = api.np.array([list(head.data.vertices[i].co) for i in sorted(ocular)], dtype=api.np.float32)
        if api.hashlib.sha256(coordinates.tobytes()).hexdigest() != face["ocular_sha256"]:
            raise RuntimeError("Saved ocular assembly differs from validated face")
        evidence["hair_validation"] = validate_hair(api, bpy.context.scene)
        return evidence

    evidence = validate()
    timings = {}
    for name in ("front", "threequarter"):
        start = time.perf_counter()
        api.render(scene, name, f"{PREFIX}_{name}.png")
        timings[name] = round(time.perf_counter() - start, 2)
    if not preview_only:
        for name in ("half", "full", "rear"):
            start = time.perf_counter()
            api.render(scene, name, f"{PREFIX}_{name}.png")
            timings[name] = round(time.perf_counter() - start, 2)
        center = Vector((.07, .16, 1.415))
        for name, offset in (("flowing_side", Vector((4, .1, .18))),
                             ("flowing_rear", Vector((.1, 4, .20)))):
            bpy.ops.object.camera_add(location=center + offset)
            camera = bpy.context.object
            camera.name = "Study_camera_" + name
            camera.data.type = "ORTHO"
            camera.data.ortho_scale = .90
            api.point_at(camera, center)
            start = time.perf_counter()
            api.render(scene, name, f"{PREFIX}_hair_{name.split('_')[1]}.png")
            timings[name] = round(time.perf_counter() - start, 2)
        api.contact_sheet(PREFIX, ("traveler_hero_full.png", f"{PREFIX}_full.png",
                                  "traveler_hero_half.png", f"{PREFIX}_half.png"))
        api.contact_sheet(PREFIX + "_face", ("traveler_hero_front.png", f"{PREFIX}_front.png",
                                            "traveler_hero_threequarter.png", f"{PREFIX}_threequarter.png"))
        scene.camera = bpy.data.objects["Study_camera_half"]
        scene.render.resolution_x, scene.render.resolution_y = 1200, 1500
        scene.render.filepath = str(api.RENDERS / f"{PREFIX}_half.png")
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=str(output))
        bpy.ops.wm.open_mainfile(filepath=str(output))
        api.render(bpy.context.scene, "half", f"{PREFIX}_reload_half.png")
        evidence["reload_difference"] = api.compare_reload(PREFIX)
        evidence.update(validate())
        evidence["saved_scene_sha256"] = api.digest(output)
    after = {str(p.relative_to(api.ROOT)): api.digest(p) for p in preserved}
    if before != after:
        raise RuntimeError("Flowing run modified preserved files")
    evidence.update({"variant": "flowing_refinement", "preview_only": preview_only,
                     "face": face, "hair": hair, "render_seconds": timings,
                     "total_seconds": round(time.perf_counter() - started, 2),
                     "preserved_hashes_before": before, "preserved_hashes_after": after,
                     "protected_objects": len(protected), "scalp_wardrobe_studio_unchanged": True,
                     "budget_vertices": 600000, "reload_verified": not preview_only})
    suffix = "preview_evidence" if preview_only else "evidence"
    (api.RENDERS / f"{PREFIX}_{suffix}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("FLOWING_VERIFIED", json.dumps({k: v for k, v in evidence.items()
          if not k.startswith("preserved_hashes")}), flush=True)
