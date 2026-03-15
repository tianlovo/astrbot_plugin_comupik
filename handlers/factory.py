"""消息处理器工厂模块

提供处理器注册和查找功能，实现一对一映射关系。
"""

from typing import Any

from astrbot.api import logger
from astrbot.api.message_components import File as FileComponent
from astrbot.api.message_components import Image as ImageComponent

from .base import HandlerContext, MessageHandler


class MessageHandlerFactory:
    """消息处理器工厂

    根据消息组件类型返回对应的单一处理器。
    一对一映射关系：每个组件类型只对应一个处理器。

    Attributes:
        _handlers: 处理器映射表，key 为组件类型，value 为处理器实例
    """

    def __init__(self):
        """初始化处理器工厂"""
        self._handlers: dict[type, MessageHandler] = {}
        self._initialized = False

    def register(self, handler: MessageHandler) -> None:
        """注册处理器

        将处理器与能处理的组件类型关联。

        Args:
            handler: 处理器实例
        """
        # 这里需要根据 handler 类型推断能处理的组件类型
        from .file_image_handler import FileImageMessageHandler
        from .image_handler import ImageMessageHandler

        if isinstance(handler, ImageMessageHandler):
            self._handlers[ImageComponent] = handler
            logger.info(
                f"[MessageHandlerFactory] 注册处理器: {handler.get_handler_type()} -> ImageComponent"
            )
        elif isinstance(handler, FileImageMessageHandler):
            self._handlers[FileComponent] = handler
            logger.info(
                f"[MessageHandlerFactory] 注册处理器: {handler.get_handler_type()} -> FileComponent"
            )
        else:
            logger.warning(
                f"[MessageHandlerFactory] 未知的处理器类型: {handler.get_handler_type()}"
            )

    def get_handler(self, component: Any) -> MessageHandler | None:
        """获取处理器

        根据组件类型返回对应的单一处理器。
        一对一映射：每个组件只由一个处理器处理。

        Args:
            component: 消息组件

        Returns:
            对应的处理器实例，如果没有则返回 None
        """
        component_type = type(component)

        # 直接根据组件类型查找
        handler = self._handlers.get(component_type)

        if handler:
            # 进一步检查 handler 是否能处理该组件
            if handler.can_handle(component):
                logger.debug(
                    f"[MessageHandlerFactory] 找到处理器: {handler.get_handler_type()}"
                )
                return handler
            else:
                # 虽然类型匹配，但 handler 拒绝处理（如 File 组件不是图片）
                logger.debug(
                    f"[MessageHandlerFactory] 处理器 {handler.get_handler_type()} 拒绝处理该组件"
                )
                return None

        logger.debug(
            f"[MessageHandlerFactory] 未找到组件类型 {component_type} 的处理器"
        )
        return None

    def initialize_default_handlers(self, context: HandlerContext) -> None:
        """初始化默认处理器

        注册所有默认的处理器。

        Args:
            context: 处理器上下文（用于初始化处理器）
        """
        if self._initialized:
            return

        from .file_image_handler import FileImageMessageHandler
        from .image_handler import ImageMessageHandler

        # 注册图片处理器
        self.register(ImageMessageHandler())

        # 注册文件图片处理器
        self.register(FileImageMessageHandler())

        self._initialized = True
        logger.info("[MessageHandlerFactory] 默认处理器初始化完成")

    def get_registered_handlers(self) -> list[str]:
        """获取已注册的处理器列表

        Returns:
            处理器类型名称列表
        """
        return [handler.get_handler_type() for handler in self._handlers.values()]
