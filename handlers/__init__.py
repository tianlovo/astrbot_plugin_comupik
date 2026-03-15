"""消息处理器模块

提供统一的消息处理接口和适配器实现。
采用接口+适配器设计模式，实现消息处理的解耦和模块化。

处理器映射关系（一对一）：
- Image 组件 -> ImageMessageHandler
- File 组件（图片格式）-> FileImageMessageHandler
- File 组件（非图片格式）-> 无处理器

Usage:
    from handlers import MessageHandlerFactory, HandlerContext

    factory = MessageHandlerFactory()
    factory.register(ImageMessageHandler())
    factory.register(FileImageMessageHandler())

    handler = factory.get_handler(message_component)
    if handler:
        await handler.handle(component, context)
"""

from .base import HandlerContext, MessageHandler
from .factory import MessageHandlerFactory
from .file_image_handler import FileImageMessageHandler
from .image_handler import ImageMessageHandler

__all__ = [
    "HandlerContext",
    "MessageHandler",
    "MessageHandlerFactory",
    "ImageMessageHandler",
    "FileImageMessageHandler",
]
