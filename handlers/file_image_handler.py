"""文件图片消息处理器

处理以文件形式发送的图片消息（File组件且为图片格式）。
"""

from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.api.message_components import File as FileComponent

from .base import HandlerContext, MessageHandler
from .image_handler import ImageMessageHandler


class FileImageMessageHandler(MessageHandler):
    """文件图片消息处理器

    处理以文件形式发送的图片消息（File组件且为图片格式）。
    一对一关系：只处理 File 类型且为图片格式的组件。

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

    def __init__(self):
        """初始化文件图片处理器"""
        self._image_handler = ImageMessageHandler()

    def can_handle(self, component: Any) -> bool:
        """检查是否能处理该组件

        只处理 File 类型且为图片格式的组件。

        Args:
            component: 消息组件

        Returns:
            是否为 File 类型且为图片格式
        """
        if not isinstance(component, FileComponent):
            return False

        # 检查文件扩展名是否为图片格式
        file_name = component.name or ""
        file_ext = Path(file_name).suffix.lower()

        is_image = file_ext in self.SUPPORTED_IMAGE_EXTENSIONS
        if is_image:
            logger.info(f"[FileImageMessageHandler] 发现图片文件: {file_name}")
        return is_image

    async def handle(self, component: FileComponent, context: HandlerContext) -> bool:
        """处理文件图片消息组件

        将 File 组件转换为 Image 组件，然后使用 ImageMessageHandler 处理。

        Args:
            component: File 消息组件（图片文件）
            context: 处理器上下文

        Returns:
            处理是否成功
        """
        try:
            logger.info(f"[FileImageMessageHandler] 开始处理文件图片: {component.name}")

            # 将 File 组件转换为 Image 组件
            from astrbot.api.message_components import Image as ImageComponent

            # 使用 URL 而不是直接访问 file 属性，避免同步下载警告
            # 参考: AstrBot 警告 "不可以在异步上下文中同步等待下载"
            image_component = ImageComponent(
                file=component.url,  # 使用 URL 作为 file 参数
                url=component.url,
            )
            # 复制其他属性
            if hasattr(component, "id"):
                image_component.id = component.id

            # 使用 ImageMessageHandler 处理
            return await self._image_handler.handle(image_component, context)

        except Exception as e:
            logger.error(f"[FileImageMessageHandler] 处理文件图片失败: {e}")
            return False
