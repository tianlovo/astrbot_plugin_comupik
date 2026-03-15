"""图片处理模块

提供Telegram图片消息监听、下载、感知哈希计算和去重功能
使用AstrBot Telegram平台适配器接口进行图片下载
"""

import io
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
import imagehash
from PIL import Image

from astrbot.api import logger
from astrbot.api.message_components import File as FileComponent
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
        storage_config: dict,
        db: "ComuPikDB",
        file_manager: "FileManager",
    ):
        """初始化图片处理器

        Args:
            monitor_targets: 监控目标列表
            deduplication_config: 去重配置
            storage_config: 存储配置
            db: 数据库对象
            file_manager: 文件管理器对象
        """
        self.monitor_targets = set(monitor_targets)
        self.deduplication_enabled = deduplication_config.get("enabled", True)
        self.deduplication_threshold = deduplication_config.get("threshold", 8)
        self.file_naming_pattern = storage_config.get(
            "file_naming", "{timestamp}_{msg_id}_{random}"
        )
        self.db = db
        self.file_manager = file_manager

    async def init(self) -> None:
        """异步初始化图片处理器"""
        logger.info(
            f"[ImageHandler] 图片处理器初始化完成，监控目标: {self.monitor_targets}"
        )

    def _check_has_image(self, message_chain: list) -> bool:
        """检查消息链中是否包含图片

        支持直接发送的图片(Image)和以文件形式发送的图片(File)

        Args:
            message_chain: 消息链

        Returns:
            是否包含图片
        """
        # 支持的图片文件扩展名
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}

        for comp in message_chain:
            # 检查是否为图片组件
            if isinstance(comp, ImageComponent):
                return True

            # 检查是否为文件组件且是图片文件
            if isinstance(comp, FileComponent):
                # 从文件名判断是否为图片
                file_name = comp.name or ""
                file_ext = Path(file_name).suffix.lower()
                if file_ext in image_extensions:
                    logger.info(f"[_check_has_image] 发现图片文件: {file_name}")
                    return True

        return False

    async def process_telegram_message(self, event: TelegramPlatformEvent) -> None:
        """处理Telegram消息事件

        Args:
            event: Telegram消息事件
        """
        try:
            # 检查是否为监控目标
            chat_id = str(event.message_obj.group_id or "")
            logger.info(
                f"[ImageHandler] 收到消息: chat_id={chat_id}, 监控目标={self.monitor_targets}"
            )

            if chat_id not in self.monitor_targets:
                logger.info(f"[ImageHandler] 聊天群 {chat_id} 不在监控目标中，跳过")
                return

            # 检查消息中是否包含图片（包括直接发送的图片和以文件形式发送的图片）
            message_chain = event.message_obj.message
            has_image = self._check_has_image(message_chain)

            logger.info(
                f"[ImageHandler] 消息内容: {message_chain}, 包含图片={has_image}"
            )

            if not has_image:
                logger.info("[ImageHandler] 消息不包含图片，跳过")
                return

            logger.info(
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

        logger.info(
            f"[_process_message] 开始处理: chat_id={chat_id}, msg_id={message_id}"
        )

        # 获取发送者信息
        sender = message_obj.sender
        sender_id = str(sender.user_id) if sender else ""
        sender_name = sender.nickname or sender.user_id if sender else ""

        # 获取原始消息对象 (telegram.Update)
        raw_message = message_obj.raw_message
        logger.info(
            f"[_process_message] raw_message={raw_message}, type={type(raw_message)}"
        )

        if not raw_message:
            logger.warning("[_process_message] raw_message 为空")
            return

        # raw_message 是 Update 对象，photo 在 Update.message 中
        # 检查 raw_message 是否有 message 属性，以及 message 是否有 photo 属性
        if hasattr(raw_message, "message") and raw_message.message:
            message = raw_message.message
            logger.info(f"[_process_message] 从 Update 中获取 message: {message}")
        else:
            logger.warning("[_process_message] raw_message 没有 message 属性")
            return

        if not hasattr(message, "photo"):
            logger.warning("[_process_message] message 没有 photo 属性")
            return

        # 获取最大尺寸的图片
        photos = message.photo
        logger.info(
            f"[_process_message] photos={photos}, count={len(photos) if photos else 0}"
        )

        if not photos:
            logger.warning("[_process_message] photos 为空")
            return

        # 选择最大尺寸的图片
        largest_photo: PhotoSize = max(photos, key=lambda p: p.file_size or 0)
        logger.info(
            f"[_process_message] 选择最大图片: file_id={largest_photo.file_id}, size={largest_photo.file_size}"
        )
        file_id = largest_photo.file_id
        file_size = largest_photo.file_size or 0
        width = largest_photo.width or 0
        height = largest_photo.height or 0

        # 构建原始链接
        original_url = f"https://t.me/c/{chat_id.replace('-100', '')}/{message_id}"

        # 使用AstrBot Telegram适配器下载图片
        logger.info(f"[_process_message] 开始下载图片: file_id={file_id}")
        image_data = await self._download_image(event, largest_photo)
        if not image_data:
            logger.error(f"[ImageHandler] 下载图片失败: file_id={file_id}")
            return
        logger.info(f"[_process_message] 图片下载成功: size={len(image_data)} bytes")

        # 计算感知哈希
        perceptual_hash = ""
        if self.deduplication_enabled:
            perceptual_hash = await self._calculate_perceptual_hash(image_data)
            logger.info(f"[_process_message] 计算感知哈希: {perceptual_hash}")

            # 检查是否重复
            existing = await self.db.get_image_by_hash(
                perceptual_hash, self.deduplication_threshold
            )
            if existing:
                # 计算实际匹配度（汉明距离）
                from .database import hamming_distance

                distance = hamming_distance(perceptual_hash, existing.perceptual_hash)
                similarity = max(0, 100 - distance * 10)  # 估算相似度百分比

                logger.warning(
                    f"[ImageHandler] 发现重复图片，跳过存储:\n"
                    f"  - 当前图片哈希: {perceptual_hash}\n"
                    f"  - 已有图片哈希: {existing.perceptual_hash}\n"
                    f"  - 汉明距离: {distance} (阈值: {self.deduplication_threshold})\n"
                    f"  - 估算相似度: {similarity}%\n"
                    f"  - 已有图片ID: {existing.id}\n"
                    f"  - 已有图片路径: {existing.file_path}\n"
                    f"  - 当前图片已删除"
                )

                # 删除当前重复图片（从内存中释放，因为已经下载了）
                del image_data
                return

        # 生成文件名并保存，使用配置的命名模式
        filename = self.file_manager.generate_filename(
            pattern=self.file_naming_pattern,
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

        logger.info(f"[_process_message] 准备保存到数据库: file_path={file_path}")

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

        logger.info(f"[_process_message] 调用 db.add_image: record={record}")
        success, record_id = await self.db.add_image(record)
        logger.info(
            f"[_process_message] db.add_image 返回: success={success}, record_id={record_id}"
        )

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

            # 生成临时文件路径，使用 FileManager 的 tmp_dir
            # 符合 AstrBot 存储规范: data/plugin_data/{plugin_name}/
            import uuid

            temp_filename = f"download_{uuid.uuid4().hex}.jpg"
            temp_path = str(self.file_manager.tmp_dir / temp_filename)

            logger.info(f"[_download_image] 开始下载到临时路径: {temp_path}")

            # 使用AstrBot提供的download_file工具函数下载文件
            # 需要提供 path 参数指定下载目标路径
            await download_file(file_obj.file_path, temp_path)

            # 检查文件是否下载成功
            if not Path(temp_path).exists():
                logger.error("[ImageHandler] 下载文件失败: 文件不存在")
                return None

            logger.info(
                f"[_download_image] 下载完成，文件大小: {Path(temp_path).stat().st_size} bytes"
            )

            # 读取下载的文件内容
            async with aiofiles.open(temp_path, "rb") as f:
                image_data = await f.read()

            # 清理临时文件
            try:
                Path(temp_path).unlink()
                logger.info(f"[_download_image] 临时文件已清理: {temp_path}")
            except Exception as e:
                logger.warning(f"[_download_image] 清理临时文件失败: {e}")

            return image_data

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
