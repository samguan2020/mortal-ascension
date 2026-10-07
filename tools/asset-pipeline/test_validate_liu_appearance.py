# PROTOTYPE - NOT FOR PRODUCTION
# Question: Does asset validation reject misleading or unusable static exports?
# Date: 2026-10-05

from copy import deepcopy
import unittest

from validate_liu_appearance import validate


def asset_fixture():
    return {
        "meshes": [{"primitives": [
            {"attributes": {"POSITION": 0, "TEXCOORD_0": 1}, "indices": 2, "material": i}
            for i in range(3)
        ]}],
        "accessors": [{"count": 1000}, {"count": 1000}, {"count": 3000}],
        "materials": [{"pbrMetallicRoughness": {"baseColorTexture": {"index": i}}} for i in range(3)],
        "images": [{"bufferView": i} for i in range(3)],
    }


class AppearanceValidationTests(unittest.TestCase):
    def test_valid_static_textured_asset_reports_actual_counts(self):
        result = validate(asset_fixture(), 1048576)
        self.assertEqual(3000, result["triangles"])
        self.assertEqual(3, result["textured_primitives"])
        self.assertEqual(1, result["size_mib"])

    def test_unused_skeleton_is_rejected(self):
        fixture = asset_fixture()
        fixture["skins"] = [{}]
        with self.assertRaisesRegex(ValueError, "skinning"):
            validate(fixture, 1048576)

    def test_animation_is_not_mislabeled_as_static(self):
        fixture = asset_fixture()
        fixture["animations"] = [{}]
        with self.assertRaisesRegex(ValueError, "animation"):
            validate(fixture, 1048576)

    def test_garment_without_uv_is_rejected(self):
        fixture = asset_fixture()
        del fixture["meshes"][0]["primitives"][0]["attributes"]["TEXCOORD_0"]
        with self.assertRaisesRegex(ValueError, "UV"):
            validate(fixture, 1048576)

    def test_external_texture_is_rejected(self):
        fixture = asset_fixture()
        fixture["images"][0] = {"uri": "external.png"}
        with self.assertRaisesRegex(ValueError, "embedded"):
            validate(fixture, 1048576)

    def test_material_budget_is_enforced(self):
        fixture = asset_fixture()
        primitive = fixture["meshes"][0]["primitives"][0]
        fixture["meshes"][0]["primitives"] = [deepcopy(primitive) for _ in range(21)]
        with self.assertRaisesRegex(ValueError, "20 material"):
            validate(fixture, 1048576)

    def test_triangle_budget_is_enforced(self):
        fixture = asset_fixture()
        fixture["accessors"][2]["count"] = 100002
        with self.assertRaisesRegex(ValueError, "Triangle count"):
            validate(fixture, 1048576)

    def test_file_budget_is_enforced(self):
        with self.assertRaisesRegex(ValueError, "8 MiB"):
            validate(asset_fixture(), 8 * 1048576 + 1)


if __name__ == "__main__":
    unittest.main()
