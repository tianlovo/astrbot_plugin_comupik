"""图片处理模块

提供Telegram图片消息监听、下载、感知哈希计算和去重功能
使用AstrBot Telegram平台适配器接口进行图片下载
"""

from typing import TYPE_CHECKING

from astrbot.api import logger
from astrbot.core.platform.sources.telegram.tg_event import (
    TelegramPlatformEvent,
)

from .handlers import HandlerContext, MessageHandlerFactory

if TYPE_CHECKING:
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
        # 默认值与 _conf_schema.json 中的默认值保持一致
        self.deduplication_enabled = deduplication_config.get(
            "enabled", True
        )  # _conf_schema.json: deduplication.enabled.default
        self.deduplication_threshold = deduplication_config.get(
            "threshold", 8
        )  # _conf_schema.json: deduplication.threshold.default
        self.file_naming_pattern = storage_config.get(
            "file_naming",
            "{timestamp}_{msg_id}_{random}",  # _conf_schema.json: storage.file_naming.default
        )
        self.db = db
        self.file_manager = file_manager

        # 创建处理器上下文
        self._handler_context = HandlerContext(
            db=self.db,
            file_manager=self.file_manager,
            deduplication_enabled=self.deduplication_enabled,
            deduplication_threshold=self.deduplication_threshold,
            file_naming_pattern=self.file_naming_pattern,
            monitor_targets=self.monitor_targets,
        )

        # 处理器工厂（在init中初始化）
        self._handler_factory: MessageHandlerFactory | None = None

    async def init(self) -> None:
        """异步初始化图片处理器"""
        # 初始化处理器工厂并注册默认处理器
        self._handler_factory = MessageHandlerFactory()
        self._handler_factory.initialize_default_handlers(self._handler_context)

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
            logger.info(
                f"[ImageHandler] 收到消息: chat_id={chat_id}, 监控目标={self.monitor_targets}"
            )

            if chat_id not in self.monitor_targets:
                logger.info(f"[ImageHandler] 聊天群 {chat_id} 不在监控目标中，跳过")
                return

            # 获取消息链
            message_chain = event.message_obj.message
            logger.info(f"[ImageHandler] 消息内容: {message_chain}")

            # 检查处理器工厂是否已初始化
            if not self._handler_factory:
                logger.error("[ImageHandler] 处理器工厂未初始化")
                return

            # 遍历消息链，对每个组件调用工厂获取单一处理器
            processed_count = 0
            for component in message_chain:
                handler = self._handler_factory.get_handler(component)
                if handler:
                    logger.info(
                        f"[ImageHandler] 找到处理器 {handler.get_handler_type()}，开始处理组件"
                    )
                    success = await handler.handle(component, self._handler_context)
                    if success:
                        processed_count += 1
                        logger.info("[ImageHandler] 组件处理成功")
                    else:
                        logger.warning("[ImageHandler] 组件处理失败")

            if processed_count > 0:
                logger.info(
                    f"[ImageHandler] 消息处理完成，成功处理 {processed_count} 个图片组件"
                )
            else:
                logger.info("[ImageHandler] 消息中未找到可处理的图片组件")

        except Exception as e:
            logger.error(f"[ImageHandler] 处理消息失败: {e}")

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
