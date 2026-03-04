"""
RefLens — Tree Service
WITH RECURSIVE CTE для построения дерева рефералов.
referrer_id живёт в channel_members, не в users.
"""

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_SAFE_DEPTH = 15  # защита от бесконечной рекурсии


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
        """
        Строит дерево рефералов через WITH RECURSIVE.
        referrer_id — поле channel_members (не users).
        """
        depth_limit = min(max_depth, MAX_SAFE_DEPTH) if max_depth else MAX_SAFE_DEPTH

        query = text("""
            WITH RECURSIVE tree AS (
                -- Корни: участники у которых нет реферера В ЭТОМ канале
                SELECT
                    cm.id        AS member_id,
                    cm.username,
                    cm.referrer_id,
                    0            AS level
                FROM channel_members cm
                WHERE cm.channel_id = :channel_id
                  AND cm.referrer_id IS NULL

                UNION ALL

                -- Рекурсия: дети
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
        """)

        result = await self.session.execute(
            query,
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
        """
        Форматирует дерево в текст с отступами.
        Ограничение: max_lines строк (Telegram лимит сообщения).
        """
        if not nodes:
            return "В этом канале пока нет реферальных связей."

        lines = ["🌳 <b>Дерево рефералов</b>\n"]
        total = len(nodes)
        shown = 0

        for node in nodes[:max_lines]:
            indent = "  " * node.level
            # Ветка: └─ для последнего, ├─ для остальных (упрощённо через •)
            prefix = "⭐" if node.level == 0 and node.direct_count > 0 else "•"
            count_str = f" ({node.direct_count} чел.)" if node.direct_count > 0 else ""
            lines.append(f"{indent}{prefix} @{node.username}{count_str}")
            shown += 1

        if total > max_lines:
            lines.append(f"\n... и ещё {total - shown} участников")

        return "\n".join(lines)
