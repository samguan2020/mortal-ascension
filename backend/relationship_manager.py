"""Deterministic, session-scoped NPC affinity rules."""

from typing import Dict


INITIAL_AFFINITY = 50.0
MIN_AFFINITY = 0.0
MAX_AFFINITY = 100.0

STRONG_POSITIVE_PHRASES = (
    "多谢掌柜", "谢谢掌柜", "信得过你", "相信你", "佩服", "救命之恩",
)
POSITIVE_PHRASES = (
    "多谢", "谢谢", "劳烦", "请教", "有劳", "辛苦", "幸会", "久仰",
)
STRONG_NEGATIVE_PHRASES = (
    "滚", "闭嘴", "废物", "老东西", "杀了你", "砸了你的店",
)
NEGATIVE_PHRASES = (
    "骗子", "胡说", "蠢", "威胁", "少废话", "不耐烦",
)


class RelationshipManager:
    """Manage hidden affinity independently for each NPC/player pair."""

    def __init__(self) -> None:
        self.affinity_scores: Dict[str, Dict[str, float]] = {}

    def get_affinity(self, npc_name: str, player_id: str = "player") -> float:
        """Return affinity for one NPC/player pair, creating its initial value."""
        npc_scores = self.affinity_scores.setdefault(npc_name, {})
        return npc_scores.setdefault(player_id, INITIAL_AFFINITY)

    def set_affinity(
        self, npc_name: str, affinity: float, player_id: str = "player"
    ) -> None:
        """Set affinity while enforcing the supported score range."""
        npc_scores = self.affinity_scores.setdefault(npc_name, {})
        npc_scores[player_id] = max(MIN_AFFINITY, min(MAX_AFFINITY, affinity))

    def analyze_message(self, player_message: str) -> Dict[str, object]:
        """Classify a message locally without an additional model request."""
        normalized = "".join(player_message.lower().split())
        if any(phrase in normalized for phrase in STRONG_NEGATIVE_PHRASES):
            return {
                "should_change": True,
                "change_amount": -8,
                "reason": "严重冒犯",
                "sentiment": "negative",
            }
        if any(phrase in normalized for phrase in NEGATIVE_PHRASES):
            return {
                "should_change": True,
                "change_amount": -3,
                "reason": "言辞无礼",
                "sentiment": "negative",
            }
        if any(phrase in normalized for phrase in STRONG_POSITIVE_PHRASES):
            return {
                "should_change": True,
                "change_amount": 3,
                "reason": "表达信任",
                "sentiment": "positive",
            }
        if any(phrase in normalized for phrase in POSITIVE_PHRASES):
            return {
                "should_change": True,
                "change_amount": 1,
                "reason": "礼貌交流",
                "sentiment": "positive",
            }
        return {
            "should_change": False,
            "change_amount": 0,
            "reason": "普通交谈",
            "sentiment": "neutral",
        }

    def projected_affinity(
        self, npc_name: str, player_message: str, player_id: str = "player"
    ) -> tuple[float, Dict[str, object]]:
        """Calculate the post-message score without mutating session state."""
        analysis = self.analyze_message(player_message)
        affinity = self.get_affinity(npc_name, player_id)
        projected = affinity + int(analysis["change_amount"])
        return max(MIN_AFFINITY, min(MAX_AFFINITY, projected)), analysis

    def analyze_and_update_affinity(
        self,
        npc_name: str,
        player_message: str,
        npc_response: str = "",
        player_id: str = "player",
    ) -> Dict[str, object]:
        """Apply deterministic affinity rules after a successful exchange."""
        del npc_response
        old_affinity = self.get_affinity(npc_name, player_id)
        new_affinity, analysis = self.projected_affinity(
            npc_name, player_message, player_id
        )
        self.set_affinity(npc_name, new_affinity, player_id)
        changed = new_affinity != old_affinity
        return {
            "changed": changed,
            "old_affinity": old_affinity,
            "new_affinity": new_affinity,
            "affinity": new_affinity,
            "change_amount": new_affinity - old_affinity,
            "reason": analysis["reason"],
            "sentiment": analysis["sentiment"],
            "old_level": self.get_affinity_level(old_affinity),
            "new_level": self.get_affinity_level(new_affinity),
        }

    def get_affinity_level(self, affinity: float) -> str:
        """Return the hidden relationship stage for a score."""
        if affinity >= 80:
            return "信赖"
        if affinity >= 60:
            return "亲近"
        if affinity >= 40:
            return "客气"
        if affinity >= 20:
            return "疏离"
        return "戒备"

    def get_affinity_modifier(self, affinity: float) -> str:
        """Return prompt guidance that changes the NPC's conversational tone."""
        if affinity >= 80:
            return "把玩家当作可信赖的熟客,语气亲切,愿意透露较私密但可信的线索"
        if affinity >= 60:
            return "对玩家颇有好感,语气温和,愿意多解释一两句"
        if affinity >= 40:
            return "把玩家当作普通客人,礼貌谨慎,只谈适合公开的消息"
        if affinity >= 20:
            return "对玩家有所保留,语气疏淡,回答简短且不主动透露秘密"
        return "对玩家保持戒备,语气冷淡,除必要回应外不透露任何敏感线索"

    def get_all_affinities(self, player_id: str = "player") -> Dict[str, Dict]:
        """Return affinity details for NPCs initialized in this manager."""
        return {
            npc_name: {
                "affinity": self.get_affinity(npc_name, player_id),
                "level": self.get_affinity_level(
                    self.get_affinity(npc_name, player_id)
                ),
                "modifier": self.get_affinity_modifier(
                    self.get_affinity(npc_name, player_id)
                ),
            }
            for npc_name in self.affinity_scores
        }
