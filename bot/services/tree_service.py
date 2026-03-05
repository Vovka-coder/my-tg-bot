"""
RefLens - Tree Service
WITH RECURSIVE CTE for building referral tree.
referrer_id lives in channel_members, not in users.
"""

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_SAFE_DEPTH = 15

_TREE_QUERY = text(
    """
    WITH RECURSIVE tree AS (
        SELECT
            cm.id        AS member_id,
            cm.username,
            cm.referrer_id,
            0            AS level
        FROM channel_members cm
        WHERE cm.channel_id = :channel_id
          AND cm.referrer_id IS NULL

        UNION ALL

        SELECT
            cm.id,
            cm.username,
            cm.referrer_id,
            tree.level + 1
        FROM channel_members cm
        JOIN tree ON cm.referrer_id = tree.member_id
        WHERE cm.channel_id = :channel_id
          AND tree.level + 1 <= :depth_limit
    )
    SELECT
        tree.member_id,
        tree.username,
        tree.referrer_id,
        tree.level,
        COUNT(children.id) AS direct_count
    FROM tree
    LEFT JOIN channel_members children
        ON children.referrer_id = tree.member_id
       AND children.channel_id = :channel_id
    GROUP BY tree.member_id, tree.username, tree.referrer_id, tree.level
    ORDER BY tree.level, direct_count DESC, tree.member_id
    """
)


@dataclass
class TreeNode:
    member_id: int
    username: str
    referrer_id: Optional[int]
    level: int
    direct_count: int


class TreeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_tree(
        self,
        channel_id: int,
        max_depth: Optional[int] = None,
    ) -> List[TreeNode]:
        """Build referral tree via WITH RECURSIVE CTE."""
        depth_limit = min(max_depth, MAX_SAFE_DEPTH) if max_depth else MAX_SAFE_DEPTH

        result = await self.session.execute(
            _TREE_QUERY,
            {"channel_id": channel_id, "depth_limit": depth_limit},
        )
        rows = result.fetchall()

        return [
            TreeNode(
                member_id=row.member_id,
                username=row.username or f"id{row.member_id}",
                referrer_id=row.referrer_id,
                level=row.level,
                direct_count=int(row.direct_count),
            )
            for row in rows
        ]

    @staticmethod
    def format_tree(nodes: List[TreeNode], max_lines: int = 50) -> str:
        """Format tree as indented text for Telegram message."""
        if not nodes:
            return "No referral connections in this channel yet."

        lines = ["🌳 <b>Referral Tree</b>\n"]
        total = len(nodes)
        shown = 0

        for node in nodes[:max_lines]:
            indent = "  " * node.level
            prefix = "⭐" if node.level == 0 and node.direct_count > 0 else "•"
            count_str = f" ({node.direct_count})" if node.direct_count > 0 else ""
            lines.append(f"{indent}{prefix} @{node.username}{count_str}")
            shown += 1

        if total > max_lines:
            lines.append(f"\n... and {total - shown} more")

        return "\n".join(lines)
