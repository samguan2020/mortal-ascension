# PROTOTYPE - NOT FOR PRODUCTION
# Question: Are traveler garment weights normalized and assigned to the intended bones?
# Date: 2026-10-06

import unittest

from traveler_skinning import weights_for_liu, weights_for_part


class TravelerSkinningTests(unittest.TestCase):
    def test_unknown_part_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "No skinning rule"):
            weights_for_part("new_unclassified_part", (0, 0, 1))

    def test_shoes_follow_correct_foot(self):
        self.assertEqual(weights_for_part("Cloth_shoe_1", (0.1, -0.1, 0.05)), {"Foot.L": 1})
        self.assertEqual(weights_for_part("Cloth_shoe_-1", (-0.1, -0.1, 0.05)), {"Foot.R": 1})

    def test_face_and_gear_are_rigid(self):
        self.assertEqual(weights_for_part("Eye_1", (0.03, -0.1, 1.6)), {"Head": 1})
        self.assertEqual(weights_for_part("Traveler_cloth_pack", (0, 0.25, 1.1)), {"Chest": 1})

    def test_knees_blend_thigh_and_shin(self):
        weights = weights_for_part("Traveler_trouser_1", (0.1, 0, 0.47))
        self.assertEqual(set(weights), {"Thigh.L", "Shin.L"})
        self.assertAlmostEqual(sum(weights.values()), 1)

    def test_skirt_center_blends_both_legs(self):
        weights = weights_for_part("Continuous_underrobe", (0, -0.1, 0.60))
        self.assertEqual(set(weights), {"Hips", "Thigh.L", "Thigh.R"})
        self.assertAlmostEqual(weights["Thigh.L"], weights["Thigh.R"])

    def test_weights_are_normalized_across_garment_height(self):
        for name in ("Sleeve_1", "Continuous_underrobe", "Traveler_trouser_1",
                     "Traveler_boot_upper_1", "Liu_Innkeeper_Head"):
            for index in range(181):
                with self.subTest(name=name, z=index / 100):
                    weights = weights_for_part(name, (0.2, 0, index / 100))
                    self.assertLessEqual(len(weights), 4)
                    self.assertAlmostEqual(sum(weights.values()), 1)
                    self.assertTrue(all(0 < weight <= 1 for weight in weights.values()))


class LiuSkinningTests(unittest.TestCase):
    def test_beard_and_temples_follow_head(self):
        for name in ("Moustache_1", "Beard_lock_0", "Temple_silver_-1"):
            self.assertEqual(weights_for_liu(name, (0.05, -0.12, 1.48)), {"Head": 1})

    def test_long_robe_and_purse_stay_with_hips(self):
        for name in ("Continuous_underrobe", "Split_outer_coat", "Merchant_purse", "Purse_cord"):
            self.assertEqual(weights_for_liu(name, (-0.1, -0.1, 0.50)), {"Hips": 1})

    def test_shared_sleeve_and_cuff_have_matching_weights(self):
        point = (0.36, -0.05, 0.982)
        self.assertEqual(weights_for_liu("Sleeve_1", point), weights_for_liu("Cuff_piping_1", point))

    def test_unrecognized_npc_part_fails(self):
        with self.assertRaisesRegex(ValueError, "No skinning rule"):
            weights_for_liu("Unknown_accessory", (0, 0, 1))


if __name__ == "__main__":
    unittest.main()
