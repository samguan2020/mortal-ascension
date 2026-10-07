# PROTOTYPE - NOT FOR PRODUCTION
# Question: Can SayMotion generate reusable GLB animation assets for Tingyu Inn?
# Date: 2026-10-05

"""Deterministic unit tests for SayMotion response parsing."""

import unittest

from generate_saymotion import (
    SayMotionError,
    extract_glb_url,
    extract_job_status,
    require_available_credits,
    select_model,
)


class SayMotionParsingTests(unittest.TestCase):
    def test_job_status_valid_payload_returns_uppercase_status(self) -> None:
        payload = {"status": [{"status": "success"}]}

        result = extract_job_status(payload)

        self.assertEqual(result, "SUCCESS")

    def test_download_nested_glb_returns_secure_url(self) -> None:
        payload = {
            "links": [
                {
                    "urls": [
                        {"files": [{"mp4": "https://example.test/a.mp4"}, {"glb": "https://example.test/a.glb"}]}
                    ]
                }
            ]
        }

        result = extract_glb_url(payload)

        self.assertEqual(result, "https://example.test/a.glb")

    def test_download_without_glb_raises_explicit_error(self) -> None:
        payload = {"links": [{"urls": [{"files": [{"fbx": "https://example.test/a.fbx"}]}]}]}

        with self.assertRaisesRegex(SayMotionError, "did not contain a GLB"):
            extract_glb_url(payload)

    def test_select_model_requested_id_returns_matching_model(self) -> None:
        models = [{"id": "first"}, {"Id": "liu-model"}]

        result = select_model(models, "liu-model")

        self.assertEqual(result, "liu-model")

    def test_credit_balance_zero_raises_before_generation(self) -> None:
        balance = {"credits": 0, "subscription": {"name": "api-freemium"}}

        with self.assertRaisesRegex(SayMotionError, "0 available API credits"):
            require_available_credits(balance)


if __name__ == "__main__":
    unittest.main()
