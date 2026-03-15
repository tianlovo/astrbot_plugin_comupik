"""图片消息处理器

处理直接发送的图片消息（Image组件）。
"""

import io
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
from PIL import Image

from astrbot.api import logger
from astrbot.api.message_components import Image as ImageComponent
from astrbot.core.utils.io import download_file

from ..retry_utils import RetryConfig, retry_with_backoff
from .base import HandlerContext, MessageHandler

if TYPE_CHECKING:
    pass


class ImageMessageHandler(MessageHandler):
    """图片消息处理器

    处理直接发送的图片消息（Image组件）。
    一对一关系：只处理 Image 类型组件。

    Attributes:
        SUPPORTED_IMAGE_EXTENSIONS: 支持的图片文件扩展名集合
    """

    SUPPORTED_IMAGE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".bmp",
        ".tiff",
    }

    def can_handle(self, component: Any) -> bool:
        """检查是否能处理该组件

        只处理 Image 类型的组件。

        Args:
            component: 消息组件

        Returns:
            是否为 Image 类型
        """
        return isinstance(component, ImageComponent)

    async def handle(self, component: ImageComponent, context: HandlerContext) -> bool:
        """处理图片消息组件

        Args:
            component: Image 消息组件
            context: 处理器上下文

        Returns:
            处理是否成功
        """
        try:
            logger.info(f"[ImageMessageHandler] 开始处理图片: {component}")

            # 获取图片URL
            image_url = component.url or component.file
            if not image_url:
                logger.error("[ImageMessageHandler] 图片URL为空")
                return False

            # 下载图片
            image_data = await self._download_image(image_url, context)
            if not image_data:
                logger.error("[ImageMessageHandler] 下载图片失败")
                return False

            # 处理图片（保存、计算哈希等）
            success = await self._process_image_data(image_data, component, context)
            return success

        except Exception as e:
            logger.error(f"[ImageMessageHandler] 处理图片失败: {e}")
            return False

    @retry_with_backoff(**RetryConfig.DOWNLOAD_RETRY)
    async def _download_image(
        self, image_url: str, context: HandlerContext
    ) -> bytes | None:
        """下载图片

        Args:
            image_url: 图片URL
            context: 处理器上下文

        Returns:
            图片数据，失败返回None
        """
        try:
            import uuid

            # 生成临时文件路径
            temp_filename = f"download_{uuid.uuid4().hex}.jpg"
            temp_path = str(context.file_manager.tmp_dir / temp_filename)

            logger.info(f"[ImageMessageHandler] 开始下载到: {temp_path}")

            # 下载文件
            await download_file(image_url, temp_path)

            # 检查文件是否存在
            if not Path(temp_path).exists():
                logger.error("[ImageMessageHandler] 下载失败: 文件不存在")
                return None

            # 读取文件内容
            async with aiofiles.open(temp_path, "rb") as f:
                image_data = await f.read()

            # 清理临时文件
            try:
                Path(temp_path).unlink()
            except Exception as e:
                logger.warning(f"[ImageMessageHandler] 清理临时文件失败: {e}")

            logger.info(f"[ImageMessageHandler] 下载完成: {len(image_data)} bytes")
            return image_data

        except Exception as e:
            logger.error(f"[ImageMessageHandler] 下载图片失败: {e}")
            return None

    async def _process_image_data(
        self, image_data: bytes, component: ImageComponent, context: HandlerContext
    ) -> bool:
        """处理图片数据

        Args:
            image_data: 图片二进制数据
            component: Image 组件
            context: 处理器上下文

        Returns:
            处理是否成功
        """
        try:
            from PIL import Image

            # 打开图片获取信息
            image = Image.open(io.BytesIO(image_data))
            width, height = image.size
            file_size = len(image_data)

            # 计算感知哈希
            perceptual_hash = ""
            if context.deduplication_enabled:
                perceptual_hash = self._calculate_perceptual_hash(image)
                logger.info(f"[ImageMessageHandler] 感知哈希: {perceptual_hash}")

                # 检查是否重复
                from ..database import ImageRecord

                existing = await context.db.get_image_by_hash(
                    perceptual_hash, context.deduplication_threshold
                )
                if existing:
                    # 计算相似度
                    from ..database import hamming_distance

                    distance = hamming_distance(
                        perceptual_hash, existing.perceptual_hash
                    )
                    similarity = max(0, 100 - distance * 10)

                    logger.warning(
                        f"[ImageMessageHandler] 发现重复图片，跳过保存:\n"
                        f"  - 当前哈希: {perceptual_hash}\n"
                        f"  - 已有哈希: {existing.perceptual_hash}\n"
                        f"  - 汉明距离: {distance}\n"
                        f"  - 相似度: {similarity}%"
                    )
                    # 重复图片检测成功，返回 True 表示已处理（跳过保存）
                    return True

            # 生成文件名
            filename = context.file_manager.generate_filename(
                pattern=context.file_naming_pattern,
                msg_id=str(component.id) if hasattr(component, "id") else "0",
                ext=".jpg",
            )

            # 保存文件
            file_path = await context.file_manager.save_file(image_data, filename)
            logger.info(f"[ImageMessageHandler] 文件已保存: {file_path}")

            # 保存到数据库
            record = ImageRecord(
                message_id=str(component.id) if hasattr(component, "id") else "0",
                chat_id="",
                sender_id="",
                sender_name="",
                timestamp=0,
                file_path=str(file_path),
                original_url=component.url or component.file or "",
                perceptual_hash=perceptual_hash,
                file_size=file_size,
                width=width,
                height=height,
            )

            success, record_id = await context.db.add_image(record)
            if success:
                logger.info(f"[ImageMessageHandler] 图片已保存到数据库: id={record_id}")
                return True
            else:
                logger.error("[ImageMessageHandler] 保存到数据库失败")
                return False

        except Exception as e:
            logger.error(f"[ImageMessageHandler] 处理图片数据失败: {e}")
            return False

    def _calculate_perceptual_hash(self, image: Image.Image) -> str:
        """计算感知哈希

        Args:
            image: PIL Image对象

        Returns:
            感知哈希字符串
        """
        try:
            import imagehash

            # 计算平均哈希
            hash_value = imagehash.average_hash(image)
            return str(hash_value)
        except Exception as e:
            logger.error(f"[ImageMessageHandler] 计算感知哈希失败: {e}")
            return ""
