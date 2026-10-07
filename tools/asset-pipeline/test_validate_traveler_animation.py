# PROTOTYPE - NOT FOR PRODUCTION
# Question: Does skin validation reject malformed or unweighted vertices?
# Date: 2026-10-06

import unittest

from validate_traveler_animation import validate_skin_rows


class SkinValidationTests(unittest.TestCase):
    def test_normalized_rigid_and_blended_weights_pass(self):
        validate_skin_rows([(1, 0, 0, 0), (0.25, 0.75, 0, 0)], [(0, 0, 0, 0), (2, 3, 0, 0)], 17)

    def test_unweighted_and_unnormalized_vertices_fail(self):
        for row in ((0, 0, 0, 0), (0.3, 0.3, 0, 0), (1, 1, 0, 0)):
            with self.assertRaisesRegex(ValueError, "normalized"):
                validate_skin_rows([row], [(0, 1, 0, 0)], 17)

    def test_invalid_weights_fail(self):
        for row in ((float("nan"), 0, 0, 0), (-0.1, 1.1, 0, 0)):
            with self.assertRaises(ValueError):
                validate_skin_rows([row], [(0, 0, 0, 0)], 17)

    def test_joint_bounds_and_attribute_counts_fail(self):
        with self.assertRaisesRegex(ValueError, "out of range"):
            validate_skin_rows([(1, 0, 0, 0)], [(17, 0, 0, 0)], 17)
        with self.assertRaisesRegex(ValueError, "counts"):
            validate_skin_rows([(1, 0, 0, 0)], [], 17)


if __name__ == "__main__":
    unittest.main()
