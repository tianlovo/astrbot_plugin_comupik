"""ComuPik 插件主模块

Telegram群组/频道图片自动收集、存储管理及API服务插件
"""

import time
import traceback
from datetime import datetime

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.platform.sources.telegram.tg_event import (
    TelegramPlatformEvent,
)

from .api_server import APIServer
from .config import ComuPikConfig
from .database import ComuPikDB
from .file_manager import FileManager
from .telegram_image_handler import ImageHandler


@register(
    "astrbot_plugin_comupik",
    "ComuPik",
    "Telegram群组/频道图片自动收集、存储管理及API服务插件",
    "1.1.4",
)
class ComuPikPlugin(Star):
    """ComuPik插件主类

    实现Telegram图片消息监听、下载、去重、存储及API服务功能
    支持错误通知和重试机制
    """

    def __init__(self, context: Context, config: AstrBotConfig):
        """初始化插件

        Args:
            context: 插件上下文
            config: 插件配置
        """
        super().__init__(context)
        self.context = context
        self.cfg = ComuPikConfig(config, context)
        self.db: ComuPikDB | None = None
        self.file_manager: FileManager | None = None
        self.image_handler: ImageHandler | None = None
        self.api_server: APIServer | None = None
        # 错误通知去重，记录最近通知的错误
        self._recent_errors: dict[str, float] = {}
        self._error_dedup_window = 300  # 5分钟内不重复通知相同错误
        # 初始化通知标志，防止重复发送
        self._init_notification_sent = False

    async def initialize(self) -> None:
        """异步初始化插件"""
        try:
            # 验证配置
            valid, error_msg = self.cfg.validate()
            if not valid:
                logger.warning(f"[ComuPikPlugin] 配置验证失败: {error_msg}")
                logger.warning("[ComuPikPlugin] 插件将在配置完善后正常工作")

            # 初始化数据库
            self.db = ComuPikDB(self.cfg.db_path)
            await self.db.init()

            # 初始化文件管理器
            self.file_manager = FileManager(
                self.cfg.data_dir,
                self.cfg.tmp_subdir,
                self.cfg.cleanup_config,
            )
            await self.file_manager.init()

            # 初始化图片处理器
            # 使用AstrBot Telegram适配器提供的接口，无需直接传入bot_token
            self.image_handler = ImageHandler(
                self.cfg.monitor_targets,
                self.cfg.deduplication_config,
                self.cfg.storage_config,
                self.db,
                self.file_manager,
                self.cfg.nsfw_config,
            )
            await self.image_handler.init()

            # 初始化API服务器
            if self.cfg.api_enabled:
                self.api_server = APIServer(
                    self.cfg.api_host,
                    self.cfg.api_port,
                    self.db,
                    self.file_manager,
                    self.image_handler,
                )
                await self.api_server.start()

            logger.info("[ComuPikPlugin] 插件初始化完成")

            # 发送初始化成功通知给超级管理员（仅发送一次）
            if self.cfg.super_admin and not self._init_notification_sent:
                await self._send_notification(
                    "ComuPik插件初始化成功", "插件已成功初始化并开始运行", "✅"
                )
                self._init_notification_sent = True

        except Exception as e:
            logger.error(f"[ComuPikPlugin] 插件初始化失败: {e}")
            self._handle_error("插件初始化错误", e)
            raise

    @filter.platform_adapter_type(filter.PlatformAdapterType.TELEGRAM)
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_telegram_message(self, event: TelegramPlatformEvent) -> None:
        """处理Telegram消息事件

        将消息转发给图片处理器处理

        Args:
            event: Telegram消息事件
        """
        try:
            if self.image_handler:
                await self.image_handler.process_telegram_message(event)
        except Exception as e:
            logger.error(f"[ComuPikPlugin] 处理Telegram消息失败: {e}")
            self._handle_error("消息处理错误", e)

    @filter.command("chatid")
    async def cmd_chatid(self, event: TelegramPlatformEvent) -> None:
        """查询当前群组/频道的ID

        指令: /chatid
        在群组或频道中发送此指令，Bot会回复当前聊天的ID
        """
        chat_type = "群组"
        try:
            # 获取群组ID
            chat_id = event.message_obj.group_id
            if not chat_id:
                await event.send(
                    event.plain_result(
                        "❌ 无法获取群组ID，请确保在群组或频道中使用此指令"
                    )
                )
                return

            # 获取群组信息
            chat_title = ""
            chat_type = "群组"
            raw_message = event.message_obj.raw_message
            if raw_message and hasattr(raw_message, "chat"):
                chat = raw_message.chat
                chat_title = getattr(chat, "title", "")
                chat_type_raw = getattr(chat, "type", "")
                if chat_type_raw == "channel":
                    chat_type = "频道"

            # 构建回复消息
            reply_text = (
                f"📋 <b>{chat_type}信息</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<b>{chat_type}名称:</b> {chat_title or '未知'}\n"
                f"<b>{chat_type}ID:</b> <code>{chat_id}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💡 将此ID添加到监控目标列表即可收集本{chat_type}图片"
            )

            await event.send(event.plain_result(reply_text))

            logger.info(f"[ComuPikPlugin] 已回复{chat_type}ID查询: chat_id={chat_id}")

        except Exception as e:
            logger.error(f"[ComuPikPlugin] 处理{chat_type}ID查询失败: {e}")
            self._handle_error("群组ID查询错误", e)
            await event.send(event.plain_result(f"❌ 查询失败: {e}"))

    @filter.command("myid")
    async def cmd_myid(self, event: TelegramPlatformEvent) -> None:
        """查询当前用户的TG ID

        指令: /myid
        在私聊或群组中发送此指令，Bot会回复当前用户的TG ID
        """
        try:
            # 获取用户ID
            user_id = (
                event.message_obj.sender.user_id if event.message_obj.sender else None
            )
            if not user_id:
                await event.send(event.plain_result("❌ 无法获取用户ID"))
                return

            # 获取用户信息
            user_name = event.message_obj.sender.nickname or "未知"

            # 判断是私聊还是群组
            chat_id = event.message_obj.group_id
            is_private = not chat_id

            # 构建回复消息
            if is_private:
                reply_text = (
                    f"👤 <b>用户信息</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"<b>用户名:</b> {user_name}\n"
                    f"<b>用户ID:</b> <code>{user_id}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"💡 将此ID配置为超级管理员可接收错误通知"
                )
            else:
                reply_text = (
                    f"👤 <b>用户信息</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"<b>用户名:</b> {user_name}\n"
                    f"<b>用户ID:</b> <code>{user_id}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"💡 建议私聊Bot获取ID，避免在群组中暴露"
                )

            await event.send(event.plain_result(reply_text))

            logger.info(f"[ComuPikPlugin] 已回复用户ID查询: user_id={user_id}")

        except Exception as e:
            logger.error(f"[ComuPikPlugin] 处理用户ID查询失败: {e}")
            self._handle_error("用户ID查询错误", e)
            await event.send(event.plain_result(f"❌ 查询失败: {e}"))

    async def _send_notification(
        self, title: str, message: str, icon: str = "ℹ️"
    ) -> None:
        """向超级管理员发送普通通知

        Args:
            title: 通知标题
            message: 通知内容
            icon: 通知图标
        """
        if not self.cfg.super_admin:
            return

        try:
            # 构建通知消息
            current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            notification_text = (
                f"{icon} <b>{title}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<b>时间:</b> {current_time_str}\n"
                f"<b>信息:</b>\n"
                f"<pre>{message[:500]}</pre>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
            )

            # 发送消息给超级管理员
            from astrbot.core.platform.sources.telegram.tg_adapter import (
                TelegramPlatformAdapter,
            )

            # 获取Telegram适配器
            tg_adapter = None
            for adapter in self.context.platform_manager.platform_insts:
                if isinstance(adapter, TelegramPlatformAdapter):
                    tg_adapter = adapter
                    break

            if tg_adapter and tg_adapter.client:
                await tg_adapter.client.send_message(
                    chat_id=self.cfg.super_admin,
                    text=notification_text,
                    parse_mode="HTML",
                )
                logger.info(
                    f"[ComuPikPlugin] 通知已发送给超级管理员: {self.cfg.super_admin}"
                )

        except Exception as e:
            logger.error(f"[ComuPikPlugin] 发送通知失败: {e}")

    async def _send_error_notification(
        self, error_type: str, error_msg: str, stack_trace: str = ""
    ) -> None:
        """向超级管理员发送错误通知

        Args:
            error_type: 错误类型
            error_msg: 错误信息
            stack_trace: 堆栈跟踪
        """
        if not self.cfg.super_admin:
            return

        try:
            # 错误去重检查
            current_time = time.time()
            error_key = f"{error_type}:{error_msg[:50]}"

            if error_key in self._recent_errors:
                last_time = self._recent_errors[error_key]
                if current_time - last_time < self._error_dedup_window:
                    # 5分钟内已通知过相同错误
                    return

            # 更新错误记录时间
            self._recent_errors[error_key] = current_time

            # 清理过期的错误记录
            self._recent_errors = {
                k: v
                for k, v in self._recent_errors.items()
                if current_time - v < self._error_dedup_window
            }

            # 构建错误通知消息
            current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            notification_text = (
                f"🚨 <b>ComuPik插件错误通知</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<b>错误类型:</b> {error_type}\n"
                f"<b>发生时间:</b> {current_time_str}\n"
                f"<b>错误信息:</b>\n"
                f"<pre>{error_msg[:500]}</pre>\n"
            )

            if stack_trace:
                # 截断堆栈信息，避免消息过长
                truncated_stack = (
                    stack_trace[:1000] + "..."
                    if len(stack_trace) > 1000
                    else stack_trace
                )
                notification_text += f"<b>堆栈跟踪:</b>\n<pre>{truncated_stack}</pre>\n"

            notification_text += "━━━━━━━━━━━━━━━━━━\n"

            # 发送消息给超级管理员
            # 使用AstrBot的消息发送API
            from astrbot.core.platform.sources.telegram.tg_adapter import (
                TelegramPlatformAdapter,
            )

            # 获取Telegram适配器
            tg_adapter = None
            for adapter in self.context.platform_manager.platform_insts:
                if isinstance(adapter, TelegramPlatformAdapter):
                    tg_adapter = adapter
                    break

            if tg_adapter and tg_adapter.client:
                await tg_adapter.client.send_message(
                    chat_id=self.cfg.super_admin,
                    text=notification_text,
                    parse_mode="HTML",
                )
                logger.info(
                    f"[ComuPikPlugin] 错误通知已发送给超级管理员: {self.cfg.super_admin}"
                )

        except Exception as e:
            logger.error(f"[ComuPikPlugin] 发送错误通知失败: {e}")

    def _handle_error(self, error_type: str, exception: Exception) -> None:
        """处理错误并发送通知

        Args:
            error_type: 错误类型
            exception: 异常对象
        """
        error_msg = str(exception)
        stack_trace = traceback.format_exc()

        logger.error(f"[ComuPikPlugin] {error_type}: {error_msg}")

        # 异步发送错误通知
        try:
            import asyncio

            asyncio.create_task(
                self._send_error_notification(error_type, error_msg, stack_trace)
            )
        except Exception as e:
            logger.error(f"[ComuPikPlugin] 创建错误通知任务失败: {e}")

    @filter.command("comupik_stats")
    async def stats_command(self, event: AstrMessageEvent):
        """显示 ComuPik 图片统计信息

        命令: /comupik_stats
        显示数据库中的图片统计信息，包括总数、总大小、聊天群数量等。
        """
        try:
            # 获取统计信息
            stats = await self.db.get_statistics()

            # 格式化文件大小
            def format_size(size_bytes: int) -> str:
                """将字节转换为可读格式"""
                if size_bytes < 1024:
                    return f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    return f"{size_bytes / 1024:.2f} KB"
                elif size_bytes < 1024 * 1024 * 1024:
                    return f"{size_bytes / (1024 * 1024):.2f} MB"
                else:
                    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

            # 格式化时间戳
            def format_timestamp(ts: int) -> str:
                """将时间戳转换为可读格式"""
                if ts == 0:
                    return "无数据"
                from datetime import datetime

                return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

            # 构建统计信息消息
            stats_text = (
                f"📊 <b>ComuPik 图片统计</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📁 <b>总图片数:</b> {stats['total_count']} 张\n"
                f"💾 <b>总大小:</b> {format_size(stats['total_size'])}\n"
                f"📊 <b>平均大小:</b> {format_size(stats['avg_file_size'])}\n"
                f"💬 <b>聊天群数:</b> {stats['chat_count']} 个\n"
            )

            # 添加时间信息（如果有数据）
            if stats["total_count"] > 0:
                stats_text += (
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📅 <b>最早图片:</b> {format_timestamp(stats['oldest_image'])}\n"
                    f"📅 <b>最新图片:</b> {format_timestamp(stats['newest_image'])}\n"
                )

            stats_text += "━━━━━━━━━━━━━━━━━━"

            # 发送消息
            await event.send(event.plain_result(stats_text))

        except Exception as e:
            logger.error(f"[ComuPikPlugin] 获取统计信息失败: {e}")
            await event.send(event.plain_result("❌ 获取统计信息失败，请稍后重试"))

    async def terminate(self) -> None:
        """插件卸载时清理资源"""
        try:
            if self.api_server:
                await self.api_server.stop()
            if self.image_handler:
                await self.image_handler.close()
            if self.file_manager:
                await self.file_manager.close()
            if self.db:
                await self.db.close()
            logger.info("[ComuPikPlugin] 插件已卸载，资源已清理")
        except Exception as e:
            logger.error(f"[ComuPikPlugin] 插件卸载时出错: {e}")
            self._handle_error("插件卸载错误", e)
