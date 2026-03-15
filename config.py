"""配置管理模块

提供插件配置的读取和管理功能
"""

from __future__ import annotations

from typing import Any

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.star.context import Context
from astrbot.core.star.star_tools import StarTools


class ComuPikConfig:
    """ComuPik插件配置类

    管理插件的所有配置项，提供便捷的访问方式
    """

    def __init__(self, config: AstrBotConfig, context: Context):
        """初始化配置

        Args:
            config: AstrBot配置对象
            context: 插件上下文
        """
        self.config = config
        self.context = context

        # 设置数据目录
        self._plugin_name = "astrbot_plugin_comupik"
        self.data_dir = StarTools.get_data_dir(self._plugin_name)

        # 数据库路径
        self.db_path = self.data_dir / "comupik_data.db"

        logger.info(f"[ComuPikPlugin] 数据目录: {self.data_dir}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项

        Args:
            key: 配置项键名
            default: 默认值

        Returns:
            配置项值
        """
        return self.config.get(key, default)

    @property
    def super_admin(self) -> str:
        """获取超级管理员TG ID"""
        return str(self.get("super_admin", "")).strip()

    @property
    def monitor_targets(self) -> list[str]:
        """获取监控目标列表"""
        targets = self.get("monitor_targets", [])
        return [str(t) for t in targets] if targets else []

    @property
    def api_enabled(self) -> bool:
        """API服务是否启用"""
        api_config = self.get("api_server", {})
        # 默认值与 _conf_schema.json: api_server.enabled.default 保持一致
        return api_config.get("enabled", True)

    @property
    def api_host(self) -> str:
        """获取API服务器监听地址"""
        api_config = self.get("api_server", {})
        # 默认值与 _conf_schema.json: api_server.host.default 保持一致
        return api_config.get("host", "127.0.0.1")

    @property
    def api_port(self) -> int:
        """获取API服务器监听端口"""
        api_config = self.get("api_server", {})
        # 默认值与 _conf_schema.json: api_server.port.default 保持一致
        return api_config.get("port", 8080)

    @property
    def cleanup_config(self) -> dict:
        """获取清理配置"""
        # 默认值与 _conf_schema.json: cleanup.*.default 保持一致
        return self.get(
            "cleanup",
            {
                "enabled": True,  # _conf_schema.json: cleanup.enabled.default
                "interval_hours": 24,  # _conf_schema.json: cleanup.interval_hours.default
                "max_age_hours": 72,  # _conf_schema.json: cleanup.max_age_hours.default
            },
        )

    @property
    def deduplication_config(self) -> dict:
        """获取去重配置"""
        # 默认值与 _conf_schema.json: deduplication.*.default 保持一致
        return self.get(
            "deduplication",
            {
                "enabled": True,  # _conf_schema.json: deduplication.enabled.default
                "threshold": 8,  # _conf_schema.json: deduplication.threshold.default
            },
        )

    @property
    def storage_config(self) -> dict:
        """获取存储配置"""
        # 默认值与 _conf_schema.json: storage.*.default 保持一致
        return self.get(
            "storage",
            {
                "tmp_subdir": "tmp",  # _conf_schema.json: storage.tmp_subdir.default
                "file_naming": "{timestamp}_{msg_id}_{random}",  # _conf_schema.json: storage.file_naming.default
            },
        )

    @property
    def tmp_subdir(self) -> str:
        """获取临时文件子目录名"""
        # 默认值与 _conf_schema.json: storage.tmp_subdir.default 保持一致
        return self.storage_config.get("tmp_subdir", "tmp")

    @property
    def file_naming_pattern(self) -> str:
        """获取文件命名模式"""
        # 默认值与 _conf_schema.json: storage.file_naming.default 保持一致
        return self.storage_config.get("file_naming", "{timestamp}_{msg_id}_{random}")

    def validate(self) -> tuple[bool, str]:
        """验证配置有效性

        Returns:
            (是否有效, 错误信息)
        """
        if not self.monitor_targets:
            return False, "监控目标列表为空"

        # 验证监控目标格式
        for target in self.monitor_targets:
            try:
                int(target)
            except ValueError:
                return False, f"监控目标格式错误: {target}"

        return True, ""
