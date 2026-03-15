"""消息处理器基类模块

定义统一的消息处理器接口和上下文。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..database import ComuPikDB
    from ..file_manager import FileManager
    from ..nsfw_checker import NSFWChecker


@dataclass
class HandlerContext:
    """处理器上下文

    传递处理器所需的依赖和配置。
    默认值应与 _conf_schema.json 中的默认值保持一致。

    Attributes:
        db: 数据库对象
        file_manager: 文件管理器对象
        deduplication_enabled: 是否启用去重（默认: True）
        deduplication_threshold: 去重阈值（汉明距离，默认: 8）
        file_naming_pattern: 文件命名模式（默认: "{timestamp}_{msg_id}_{random}"）
        monitor_targets: 监控目标集合
        chat_id: 聊天群ID
        sender_id: 发送者ID
        sender_name: 发送者名称
        timestamp: 消息时间戳
        nsfw_enabled: 是否启用NSFW检测（默认: False）
        nsfw_checker: NSFW检测器实例
        nsfw_threshold: NSFW判定阈值（默认: 0.8）
        nsfw_allow_save: 是否允许保存NSFW内容（默认: False）
    """

    db: "ComuPikDB"
    file_manager: "FileManager"
    # 注意：默认值应与 _conf_schema.json 中的默认值保持一致
    deduplication_enabled: bool = (
        True  # _conf_schema.json: deduplication.enabled.default
    )
    deduplication_threshold: int = (
        8  # _conf_schema.json: deduplication.threshold.default
    )
    file_naming_pattern: str = "{timestamp}_{msg_id}_{random}"  # _conf_schema.json: storage.file_naming.default
    monitor_targets: set[str] | None = None
    # 消息元数据
    chat_id: str = ""
    sender_id: str = ""
    sender_name: str = ""
    timestamp: int = 0
    # NSFW 审核配置
    nsfw_enabled: bool = False  # _conf_schema.json: nsfw.enabled.default
    nsfw_checker: Optional["NSFWChecker"] = None
    nsfw_threshold: float = 0.8  # _conf_schema.json: nsfw.threshold.default
    nsfw_allow_save: bool = False  # _conf_schema.json: nsfw.allow_save.default


class MessageHandler(ABC):
    """消息处理器抽象基类

    定义消息处理器的标准接口。
    每个处理器只处理一种特定消息类型（一对一关系）。

    Usage:
        class MyHandler(MessageHandler):
            def can_handle(self, component: Any) -> bool:
                return isinstance(component, SomeType)

            async def handle(self, component: Any, context: HandlerContext) -> bool:
                # 处理逻辑
                return True
    """

    @abstractmethod
    def can_handle(self, component: Any) -> bool:
        """检查是否能处理该组件

        每个处理器只返回 True 当组件为其特定类型。

        Args:
            component: 消息组件

        Returns:
            是否能处理该组件
        """
        pass

    @abstractmethod
    async def handle(self, component: Any, context: HandlerContext) -> bool:
        """处理消息组件

        Args:
            component: 消息组件
            context: 处理器上下文

        Returns:
            处理是否成功
        """
        pass

    def get_handler_type(self) -> str:
        """获取处理器类型标识

        Returns:
            处理器类型字符串
        """
        return self.__class__.__name__
