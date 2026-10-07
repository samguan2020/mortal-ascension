# PROTOTYPE - NOT FOR PRODUCTION
# Question: Can deterministic garment weights preserve the traveler's appearance in motion?
# Date: 2026-10-06

"""Blender-independent weight rules for the fitted traveler deform rig."""

import math


def smoothstep(low, high, value):
    t = max(0.0, min(1.0, (value - low) / (high - low)))
    return t * t * (3 - 2 * t)


def blend(first, second, amount):
    return {first: 1 - amount, second: amount}


def weights_for_part(name, point):
    x, _, z = point
    side = "L" if x >= 0 else "R"
    if name.startswith("MPFB_Hand_"):
        weights = {f"Hand.{side}": 1.0}
    elif name.startswith(("Sleeve_", "Cuff_piping_")):
        weights = blend(f"Forearm.{side}", f"UpperArm.{side}", smoothstep(1.08, 1.22, z))
        along_arm = (abs(x) - 0.20) * 0.52 - (z - 1.31) * 0.85
        chest = 1 - smoothstep(0.0, 0.11, along_arm)
        weights = {bone: weight * (1 - chest) for bone, weight in weights.items()}
        weights["Chest"] = chest
    elif name.startswith(("Cloth_shoe_", "Shoe_seam_")):
        weights = {f"Foot.{side}": 1.0}
    elif name.startswith(("Traveler_boot_upper_", "Boot_binding_")):
        weights = blend(f"Foot.{side}", f"Shin.{side}", smoothstep(0.095, 0.20, z))
    elif name.startswith("Traveler_trouser_"):
        weights = blend(f"Shin.{side}", f"Thigh.{side}", smoothstep(0.36, 0.57, z))
    elif name in ("Continuous_underrobe", "Split_outer_coat", "Sash_hanging_end"):
        if z < 0.90:
            leg = 1 - smoothstep(0.54, 0.88, z)
            left = smoothstep(-0.065, 0.065, x)
            weights = {"Hips": 1 - leg, "Thigh.L": leg * left, "Thigh.R": leg * (1 - left)}
        else:
            weights = blend("Hips", "Chest", smoothstep(1.0, 1.28, z))
    elif name in ("Waist_sash", "Cloth_knot"):
        weights = {"Hips": 1.0}
    elif name in ("Tailored_shoulder_yoke", "Inner_cross_collar", "Outer_cross_lapel",
                   "Lapel_stitched_edge") or name.startswith("Travel_pack_strap_"):
        weights = blend("Hips", "Chest", smoothstep(1.0, 1.28, z))
    elif name.startswith(("Traveler_cloth_pack", "Traveler_bedroll", "Bedroll_binding_",
                          "Pack_cross_tie", "Pack_tie_knot")):
        weights = {"Chest": 1.0}
    elif name == "Liu_Innkeeper_Head":
        weights = blend("Neck", "Head", smoothstep(1.435, 1.50, z))
    elif name.startswith(("Eye_", "Iris_", "Pupil_", "Eyebrow_", "Fitted_scalp", "Swept_hair_",
                          "Tied_hair_bun", "Bun_fold_", "Bun_binding", "Wooden_hairpin",
                          "Traveler_hair_tie")):
        weights = {"Head": 1.0}
    else:
        raise ValueError(f"No skinning rule for traveler part: {name}")
    result = {bone: weight for bone, weight in weights.items() if weight > 1e-8}
    if not result or len(result) > 4 or not all(math.isfinite(w) and 0 < w <= 1 for w in result.values()):
        raise ValueError(f"Invalid skin weights for {name}: {result}")
    total = sum(result.values())
    return {bone: weight / total for bone, weight in result.items()}


def weights_for_liu(name, point):
    if name.startswith(("Moustache_", "Beard_lock_", "Temple_silver_")):
        return {"Head": 1.0}
    if name == "Merchant_purse" or name.startswith("Purse_cord"):
        return {"Hips": 1.0}
    if name in ("Continuous_underrobe", "Split_outer_coat", "Sash_hanging_end") and point[2] < 1.0:
        return {"Hips": 1.0}
    return weights_for_part(name, point)
