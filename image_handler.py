"""图片处理模块

提供Telegram图片消息监听、下载、感知哈希计算和去重功能
使用AstrBot Telegram平台适配器接口进行图片下载
"""

import io
from typing import TYPE_CHECKING

import aiofiles
import imagehash
from PIL import Image

from astrbot.api import logger
from astrbot.api.message_components import Image as ImageComponent
from astrbot.core.platform.sources.telegram.tg_event import (
    TelegramPlatformEvent,
)
from astrbot.core.utils.io import download_file

from .retry_utils import RetryConfig, retry_with_backoff

if TYPE_CHECKING:
    from telegram import PhotoSize

    from .database import ComuPikDB, ImageRecord
    from .file_manager import FileManager


class ImageHandler:
    """图片处理类

    处理Telegram图片消息的监听、下载、去重和存储
    使用AstrBot Telegram平台适配器提供的接口
    """

    def __init__(
        self,
        monitor_targets: list[str],
        deduplication_config: dict,
        db: "ComuPikDB",
        file_manager: "FileManager",
    ):
        """初始化图片处理器

        Args:
            monitor_targets: 监控目标列表
            deduplication_config: 去重配置
            db: 数据库对象
            file_manager: 文件管理器对象
        """
        self.monitor_targets = set(monitor_targets)
        self.deduplication_enabled = deduplication_config.get("enabled", True)
        self.deduplication_threshold = deduplication_config.get("threshold", 8)
        self.db = db
        self.file_manager = file_manager

    async def init(self) -> None:
        """异步初始化图片处理器"""
        logger.info(
            f"[ImageHandler] 图片处理器初始化完成，监控目标: {self.monitor_targets}"
        )

    async def process_telegram_message(self, event: TelegramPlatformEvent) -> None:
        """处理Telegram消息事件

        Args:
            event: Telegram消息事件
        """
        try:
            # 检查是否为监控目标
            chat_id = str(event.message_obj.group_id or "")
            if chat_id not in self.monitor_targets:
                return

            # 检查消息中是否包含图片
            message_chain = event.message_obj.message
            has_image = any(isinstance(comp, ImageComponent) for comp in message_chain)

            if not has_image:
                return

            logger.debug(
                f"[ImageHandler] 收到图片消息: chat_id={chat_id}, "
                f"msg_id={event.message_obj.message_id}"
            )

            # 处理图片
            await self._process_message(event)

        except Exception as e:
            logger.error(f"[ImageHandler] 处理消息失败: {e}")

    async def _process_message(self, event: TelegramPlatformEvent) -> None:
        """处理包含图片的消息

        使用AstrBot Telegram适配器提供的接口下载图片

        Args:
            event: Telegram消息事件
        """
        message_obj = event.message_obj
        chat_id = str(message_obj.group_id or "")
        message_id = str(message_obj.message_id)
        timestamp = message_obj.timestamp

        # 获取发送者信息
        sender = message_obj.sender
        sender_id = str(sender.user_id) if sender else ""
        sender_name = sender.nickname or sender.user_id if sender else ""

        # 获取原始消息对象 (telegram.Update)
        raw_message = message_obj.raw_message
        if not raw_message or not hasattr(raw_message, "photo"):
            return

        # 获取最大尺寸的图片
        photos = raw_message.photo
        if not photos:
            return

        # 选择最大尺寸的图片
        largest_photo: PhotoSize = max(photos, key=lambda p: p.file_size or 0)
        file_id = largest_photo.file_id
        file_size = largest_photo.file_size or 0
        width = largest_photo.width or 0
        height = largest_photo.height or 0

        # 构建原始链接
        original_url = f"https://t.me/c/{chat_id.replace('-100', '')}/{message_id}"

        # 使用AstrBot Telegram适配器下载图片
        image_data = await self._download_image(event, largest_photo)
        if not image_data:
            logger.error(f"[ImageHandler] 下载图片失败: file_id={file_id}")
            return

        # 计算感知哈希
        perceptual_hash = ""
        if self.deduplication_enabled:
            perceptual_hash = await self._calculate_perceptual_hash(image_data)

            # 检查是否重复
            existing = await self.db.get_image_by_hash(
                perceptual_hash, self.deduplication_threshold
            )
            if existing:
                logger.info(
                    f"[ImageHandler] 发现重复图片，跳过存储: {existing.file_path}"
                )
                return

        # 生成文件名并保存
        filename = self.file_manager.generate_filename(
            pattern="{timestamp}_{msg_id}_{random}",
            msg_id=message_id,
            chat_id=chat_id,
            ext=".jpg",
        )
        file_path = await self.file_manager.save_file(image_data, filename)

        if not file_path:
            logger.error(f"[ImageHandler] 保存图片失败: {filename}")
            return

        # 保存到数据库
        from .database import ImageRecord

        record = ImageRecord(
            message_id=message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            timestamp=timestamp,
            file_path=str(file_path),
            original_url=original_url,
            perceptual_hash=perceptual_hash,
            file_size=file_size,
            width=width,
            height=height,
        )

        success, record_id = await self.db.add_image(record)
        if success:
            logger.info(f"[ImageHandler] 图片已保存: id={record_id}, path={file_path}")
        else:
            logger.error("[ImageHandler] 保存图片记录失败")

    @retry_with_backoff(**RetryConfig.DOWNLOAD_RETRY)
    async def _download_image(
        self, event: TelegramPlatformEvent, photo: "PhotoSize"
    ) -> bytes | None:
        """从Telegram下载图片

        使用AstrBot Telegram平台适配器提供的接口下载图片
        带有重试机制，确保高可用性

        Args:
            event: Telegram消息事件，用于获取适配器客户端
            photo: Telegram PhotoSize对象

        Returns:
            图片数据，失败返回None
        """
        try:
            # 使用AstrBot Telegram适配器的客户端获取文件
            # 这是AstrBot封装的标准方式，无需直接访问Telegram API
            file_obj = await photo.get_file()

            if not file_obj or not file_obj.file_path:
                logger.error("[ImageHandler] 获取文件对象失败")
                return None

            # 使用AstrBot提供的download_file工具函数下载文件
            # 该函数封装了文件下载逻辑，支持缓存和错误处理
            temp_path = await download_file(file_obj.file_path)

            if not temp_path:
                logger.error("[ImageHandler] 下载文件失败")
                return None

            # 读取下载的文件内容
            async with aiofiles.open(temp_path, "rb") as f:
                return await f.read()

        except Exception as e:
            logger.error(f"[ImageHandler] 下载图片失败: {e}")
            return None

    async def _calculate_perceptual_hash(self, image_data: bytes) -> str:
        """计算图片的感知哈希

        Args:
            image_data: 图片数据

        Returns:
            感知哈希字符串
        """
        try:
            # 使用线程池执行同步的图像处理
            loop = __import__("asyncio").get_event_loop()
            return await loop.run_in_executor(
                None, self._sync_calculate_hash, image_data
            )
        except Exception as e:
            logger.error(f"[ImageHandler] 计算感知哈希失败: {e}")
            return ""

    def _sync_calculate_hash(self, image_data: bytes) -> str:
        """同步计算感知哈希

        Args:
            image_data: 图片数据

        Returns:
            感知哈希字符串
        """
        try:
            image = Image.open(io.BytesIO(image_data))
            # 使用pHash算法
            phash = imagehash.phash(image)
            return str(phash)
        except Exception as e:
            logger.error(f"[ImageHandler] 同步计算哈希失败: {e}")
            return ""

    async def download_image_by_record(self, record: "ImageRecord") -> bytes | None:
        """根据记录重新下载图片

        注意：重新下载需要file_id，但数据库中未存储file_id
        因为Telegram的file_id会过期，长期存储没有意义
        如果需要重新下载功能，建议：
        1. 增加file_id字段并定期更新
        2. 或者从原始消息链接获取（需要Bot在消息发送时就在群组中）

        Args:
            record: 图片记录

        Returns:
            图片数据，失败返回None
        """
        logger.warning(
            f"[ImageHandler] 重新下载功能需要file_id，当前未实现: {record.message_id}"
        )
        return None

    async def close(self) -> None:
        """关闭图片处理器"""
        logger.info("[ImageHandler] 图片处理器已关闭")
