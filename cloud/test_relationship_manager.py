"""Network-free tests for deterministic session affinity rules."""

import unittest

from backend.relationship_manager import RelationshipManager


class RelationshipManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = RelationshipManager()

    def test_affinity_level_boundaries_return_expected_stages(self):
        expected = {
            0: "戒备",
            19.9: "戒备",
            20: "疏离",
            40: "客气",
            60: "亲近",
            80: "信赖",
            100: "信赖",
        }
        for score, stage in expected.items():
            with self.subTest(score=score):
                self.assertEqual(self.manager.get_affinity_level(score), stage)

    def test_affinity_modifier_exists_at_every_stage_boundary(self):
        for score in (0, 20, 40, 60, 80, 100):
            with self.subTest(score=score):
                self.assertTrue(self.manager.get_affinity_modifier(score))

    def test_new_pair_starts_at_fifty(self):
        self.assertEqual(self.manager.get_affinity("柳掌柜", "new_player"), 50.0)

    def test_set_affinity_clamps_scores_to_supported_range(self):
        self.manager.set_affinity("柳掌柜", 150)
        self.assertEqual(self.manager.get_affinity("柳掌柜"), 100.0)
        self.manager.set_affinity("柳掌柜", -50)
        self.assertEqual(self.manager.get_affinity("柳掌柜"), 0.0)
        self.manager.set_affinity("柳掌柜", 65.5)
        self.assertEqual(self.manager.get_affinity("柳掌柜"), 65.5)

    def test_affinity_isolated_between_sessions_and_npcs(self):
        self.manager.set_affinity("柳掌柜", 90, "player_a")
        self.manager.set_affinity("柳掌柜", 10, "player_b")
        self.manager.set_affinity("测试NPC", 25, "player_a")

        self.assertEqual(self.manager.get_affinity("柳掌柜", "player_a"), 90)
        self.assertEqual(self.manager.get_affinity("柳掌柜", "player_b"), 10)
        self.assertEqual(self.manager.get_affinity("测试NPC", "player_a"), 25)

    def test_local_rules_classify_messages_without_model_calls(self):
        cases = {
            "多谢掌柜，我相信你": 3,
            "你这个骗子": -3,
            "滚开，老东西": -8,
            "北边山路怎么走？": 0,
        }
        for message, change in cases.items():
            with self.subTest(message=message):
                self.assertEqual(
                    self.manager.analyze_message(message)["change_amount"], change
                )

    def test_projected_affinity_does_not_mutate_session(self):
        projected, analysis = self.manager.projected_affinity(
            "柳掌柜", "多谢掌柜"
        )

        self.assertEqual(projected, 53)
        self.assertEqual(analysis["sentiment"], "positive")
        self.assertEqual(self.manager.get_affinity("柳掌柜"), 50)

    def test_successful_exchange_applies_change(self):
        result = self.manager.analyze_and_update_affinity(
            "柳掌柜", "滚开，老东西", "客官请自重。"
        )

        self.assertTrue(result["changed"])
        self.assertEqual(result["old_affinity"], 50)
        self.assertEqual(result["new_affinity"], 42)
        self.assertEqual(self.manager.get_affinity("柳掌柜"), 42)


if __name__ == "__main__":
    unittest.main()
