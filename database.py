"""数据库管理模块

提供图片元数据的持久化存储和查询功能
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from astrbot.api import logger

from .retry_utils import RetryConfig, retry_with_backoff


@dataclass
class ImageRecord:
    """图片记录数据类"""

    id: int | None = None
    message_id: str = ""
    chat_id: str = ""
    sender_id: str = ""
    sender_name: str = ""
    timestamp: int = 0
    file_path: str = ""
    original_url: str = ""
    perceptual_hash: str = ""
    file_size: int = 0
    width: int = 0
    height: int = 0
    created_at: int = 0


class ComuPikDB:
    """ComuPik插件数据库类

    管理图片元数据的存储、查询和去重
    """

    def __init__(self, db_path: Path):
        """初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def init(self) -> None:
        """异步初始化数据库

        创建必要的表结构和索引
        """
        async with self._init_lock:
            if self._initialized:
                return

            # 确保目录存在
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # 连接数据库
            self._conn = await aiosqlite.connect(str(self.db_path))
            self._conn.row_factory = aiosqlite.Row

            # 创建图片记录表
            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS image_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_name TEXT DEFAULT '',
                    timestamp INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    original_url TEXT DEFAULT '',
                    perceptual_hash TEXT DEFAULT '',
                    file_size INTEGER DEFAULT 0,
                    width INTEGER DEFAULT 0,
                    height INTEGER DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    UNIQUE(message_id, chat_id)
                )
            """)

            # 创建索引
            await self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_id ON image_records(chat_id)
            """)
            await self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON image_records(timestamp)
            """)
            await self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_perceptual_hash ON image_records(perceptual_hash)
            """)

            await self._conn.commit()
            self._initialized = True
            logger.info(f"[ComuPikDB] 数据库初始化完成: {self.db_path}")

    @retry_with_backoff(**RetryConfig.DATABASE_RETRY)
    async def add_image(self, record: ImageRecord) -> tuple[bool, int]:
        """添加图片记录

        Args:
            record: 图片记录对象

        Returns:
            (是否成功, 记录ID)
        """
        if not self._conn:
            raise RuntimeError("数据库未初始化")

        try:
            record.created_at = int(datetime.now().timestamp())

            cursor = await self._conn.execute(
                """
                INSERT OR REPLACE INTO image_records
                (message_id, chat_id, sender_id, sender_name, timestamp,
                 file_path, original_url, perceptual_hash, file_size,
                 width, height, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.message_id,
                    record.chat_id,
                    record.sender_id,
                    record.sender_name,
                    record.timestamp,
                    record.file_path,
                    record.original_url,
                    record.perceptual_hash,
                    record.file_size,
                    record.width,
                    record.height,
                    record.created_at,
                ),
            )
            await self._conn.commit()
            return True, cursor.lastrowid or 0
        except Exception as e:
            logger.error(f"[ComuPikDB] 添加图片记录失败: {e}")
            return False, 0

    async def get_image_by_hash(
        self, perceptual_hash: str, threshold: int = 8
    ) -> ImageRecord | None:
        """根据感知哈希查找相似图片

        Args:
            perceptual_hash: 感知哈希值
            threshold: 相似度阈值

        Returns:
            相似图片记录，未找到返回None
        """
        if not self._conn or not perceptual_hash:
            return None

        try:
            # 获取所有有哈希值的记录进行比对
            async with self._conn.execute(
                "SELECT * FROM image_records WHERE perceptual_hash != ''"
            ) as cursor:
                rows = await cursor.fetchall()

                for row in rows:
                    row_hash = row["perceptual_hash"]
                    if self._hash_similarity(perceptual_hash, row_hash) <= threshold:
                        return self._row_to_record(row)

                return None
        except Exception as e:
            logger.error(f"[ComuPikDB] 查询相似图片失败: {e}")
            return None

    def _hash_similarity(self, hash1: str, hash2: str) -> int:
        """计算两个感知哈希的汉明距离

        Args:
            hash1: 哈希值1
            hash2: 哈希值2

        Returns:
            汉明距离
        """
        if len(hash1) != len(hash2):
            return float("inf")  # type: ignore

        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

    async def get_image_by_id(self, image_id: int) -> ImageRecord | None:
        """根据ID获取图片记录

        Args:
            image_id: 图片记录ID

        Returns:
            图片记录，未找到返回None
        """
        if not self._conn:
            return None

        try:
            async with self._conn.execute(
                "SELECT * FROM image_records WHERE id = ?",
                (image_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return self._row_to_record(row) if row else None
        except Exception as e:
            logger.error(f"[ComuPikDB] 查询图片记录失败: {e}")
            return None

    async def get_images_by_chat(
        self,
        chat_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ImageRecord]:
        """获取指定聊天群的图片记录

        Args:
            chat_id: 聊天群ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            图片记录列表
        """
        if not self._conn:
            return []

        try:
            async with self._conn.execute(
                """
                SELECT * FROM image_records
                WHERE chat_id = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (chat_id, limit, offset),
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_record(row) for row in rows]
        except Exception as e:
            logger.error(f"[ComuPikDB] 查询聊天群图片失败: {e}")
            return []

    async def get_all_images(
        self,
        limit: int = 100,
        offset: int = 0,
        start_time: int | None = None,
        end_time: int | None = None,
        exclude_ids: list[int] | None = None,
    ) -> list[ImageRecord]:
        """获取所有图片记录

        Args:
            limit: 返回数量限制
            offset: 偏移量
            start_time: 开始时间戳
            end_time: 结束时间戳
            exclude_ids: 要排除的图片ID列表

        Returns:
            图片记录列表
        """
        if not self._conn:
            return []

        try:
            query = "SELECT * FROM image_records WHERE 1=1"
            params: list[Any] = []

            if start_time is not None:
                query += " AND timestamp >= ?"
                params.append(start_time)
            if end_time is not None:
                query += " AND timestamp <= ?"
                params.append(end_time)
            if exclude_ids:
                placeholders = ",".join(["?"] * len(exclude_ids))
                query += f" AND id NOT IN ({placeholders})"
                params.extend(exclude_ids)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            async with self._conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_record(row) for row in rows]
        except Exception as e:
            logger.error(f"[ComuPikDB] 查询所有图片失败: {e}")
            return []

    async def get_image_count(
        self,
        chat_id: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        exclude_ids: list[int] | None = None,
    ) -> int:
        """获取图片记录数量

        Args:
            chat_id: 可选的聊天群ID过滤
            start_time: 开始时间戳
            end_time: 结束时间戳
            exclude_ids: 要排除的图片ID列表

        Returns:
            记录数量
        """
        if not self._conn:
            return 0

        try:
            query = "SELECT COUNT(*) FROM image_records WHERE 1=1"
            params: list[Any] = []

            if chat_id:
                query += " AND chat_id = ?"
                params.append(chat_id)
            if start_time is not None:
                query += " AND timestamp >= ?"
                params.append(start_time)
            if end_time is not None:
                query += " AND timestamp <= ?"
                params.append(end_time)
            if exclude_ids:
                placeholders = ",".join(["?"] * len(exclude_ids))
                query += f" AND id NOT IN ({placeholders})"
                params.extend(exclude_ids)

            async with self._conn.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"[ComuPikDB] 查询图片数量失败: {e}")
            return 0

    async def delete_image(self, image_id: int) -> bool:
        """删除图片记录

        Args:
            image_id: 图片记录ID

        Returns:
            是否删除成功
        """
        if not self._conn:
            return False

        try:
            await self._conn.execute(
                "DELETE FROM image_records WHERE id = ?",
                (image_id,),
            )
            await self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"[ComuPikDB] 删除图片记录失败: {e}")
            return False

    async def delete_images_by_chat(self, chat_id: str) -> bool:
        """删除指定聊天群的所有图片记录

        Args:
            chat_id: 聊天群ID

        Returns:
            是否删除成功
        """
        if not self._conn:
            return False

        try:
            await self._conn.execute(
                "DELETE FROM image_records WHERE chat_id = ?",
                (chat_id,),
            )
            await self._conn.commit()
            return True
        except Exception as e:
            logger.error(f"[ComuPikDB] 删除聊天群图片记录失败: {e}")
            return False

    def _row_to_record(self, row: aiosqlite.Row) -> ImageRecord:
        """将数据库行转换为记录对象

        Args:
            row: 数据库行

        Returns:
            图片记录对象
        """
        return ImageRecord(
            id=row["id"],
            message_id=row["message_id"],
            chat_id=row["chat_id"],
            sender_id=row["sender_id"],
            sender_name=row["sender_name"],
            timestamp=row["timestamp"],
            file_path=row["file_path"],
            original_url=row["original_url"],
            perceptual_hash=row["perceptual_hash"],
            file_size=row["file_size"],
            width=row["width"],
            height=row["height"],
            created_at=row["created_at"],
        )

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            await self._conn.close()
            self._conn = None
            self._initialized = False
            logger.info("[ComuPikDB] 数据库连接已关闭")
