"""API服务模块

提供RESTful API服务，包括图片列表查询和文件访问接口
支持时间范围查询和排除指定图片ID
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web

from astrbot.api import logger

if TYPE_CHECKING:
    from .database import ComuPikDB
    from .file_manager import FileManager
    from .telegram_image_handler import ImageHandler


class APIServer:
    """API服务器类

    提供轻量级HTTP服务，处理图片查询和文件访问请求
    支持图片状态管理：downloading, available, expired
    """

    def __init__(
        self,
        host: str,
        port: int,
        db: "ComuPikDB",
        file_manager: "FileManager",
        image_handler: "ImageHandler",
    ):
        """初始化API服务器

        Args:
            host: 监听地址
            port: 监听端口
            db: 数据库对象
            file_manager: 文件管理器对象
            image_handler: 图片处理器对象
        """
        self.host = host
        self.port = port
        self.db = db
        self.file_manager = file_manager
        self.image_handler = image_handler
        self.app = web.Application()
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

        # 注册路由
        self._setup_routes()

    def _setup_routes(self) -> None:
        """设置API路由"""
        self.app.router.add_get("/api/images", self.handle_list_images)
        self.app.router.add_get("/api/images/{id}", self.handle_get_image)
        self.app.router.add_get("/api/file/{filename}", self.handle_get_file)
        self.app.router.add_get("/api/stats", self.handle_get_stats)
        self.app.router.add_get("/api/health", self.handle_health_check)

    async def start(self) -> None:
        """启动API服务器"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        logger.info(f"[APIServer] API服务器已启动: http://{self.host}:{self.port}")

    async def stop(self) -> None:
        """停止API服务器"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("[APIServer] API服务器已停止")

    async def handle_health_check(self, request: web.Request) -> web.Response:
        """健康检查接口

        GET /api/health
        """
        return web.json_response(
            {
                "status": "ok",
                "service": "comupik-api",
                "version": "1.0.0",
            }
        )

    async def handle_get_stats(self, request: web.Request) -> web.Response:
        """获取统计信息接口

        GET /api/stats
        返回数据库图片统计信息，包括总数、总大小、聊天群数量等。
        """
        try:
            stats = await self.db.get_statistics()

            return web.json_response(
                {
                    "status": "ok",
                    "data": {
                        "total_images": stats["total_count"],
                        "total_size_bytes": stats["total_size"],
                        "avg_size_bytes": stats["avg_file_size"],
                        "chat_count": stats["chat_count"],
                        "oldest_timestamp": stats["oldest_image"],
                        "newest_timestamp": stats["newest_image"],
                    },
                }
            )
        except Exception as e:
            logger.error(f"[APIServer] 获取统计信息失败: {e}")
            return web.json_response(
                {"status": "error", "message": str(e)},
                status=500,
            )

    async def handle_list_images(self, request: web.Request) -> web.Response:
        """获取图片列表接口

        GET /api/images?start_time={required}&end_time={required}&exclude_ids={required}&limit=100&offset=0

        参数说明:
        - start_time: 开始时间戳（必填）
        - end_time: 结束时间戳（必填）
        - exclude_ids: 要排除的图片ID列表，JSON格式数组（必填，可为空）
        - limit: 返回数量限制（默认100，最大1000）
        - offset: 偏移量（默认0）
        """
        try:
            # 解析查询参数
            start_time = request.query.get("start_time")
            end_time = request.query.get("end_time")
            exclude_ids_str = request.query.get("exclude_ids", "[]")
            limit = int(request.query.get("limit", 100))
            offset = int(request.query.get("offset", 0))

            # 验证必填参数
            if not start_time or not end_time:
                return web.json_response(
                    {
                        "status": "error",
                        "message": "缺少必填参数: start_time 和 end_time 为必填项",
                    },
                    status=400,
                )

            # 转换时间戳
            try:
                start_ts = int(start_time)
                end_ts = int(end_time)
            except ValueError:
                return web.json_response(
                    {"status": "error", "message": "时间戳格式错误"},
                    status=400,
                )

            # 解析exclude_ids
            try:
                exclude_ids = json.loads(exclude_ids_str)
                if not isinstance(exclude_ids, list):
                    exclude_ids = []
                # 转换为整数列表
                exclude_ids = [int(x) for x in exclude_ids if str(x).isdigit()]
            except json.JSONDecodeError:
                exclude_ids = []

            # 限制返回数量
            limit = min(limit, 1000)

            # 查询数据
            images = await self.db.get_all_images(
                limit, offset, start_ts, end_ts, exclude_ids
            )
            total = await self.db.get_image_count(None, start_ts, end_ts, exclude_ids)

            # 构建响应，包含图片状态
            data = []
            for img in images:
                # 判断图片状态
                status = await self._get_image_status(img)

                data.append(
                    {
                        "id": img.id,
                        "message_id": img.message_id,
                        "chat_id": img.chat_id,
                        "sender_id": img.sender_id,
                        "sender_name": img.sender_name,
                        "timestamp": img.timestamp,
                        "file_path": img.file_path,
                        "original_url": img.original_url,
                        "file_size": img.file_size,
                        "width": img.width,
                        "height": img.height,
                        "created_at": img.created_at,
                        "status": status,
                    }
                )

            return web.json_response(
                {
                    "status": "ok",
                    "data": {
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                        "start_time": start_ts,
                        "end_time": end_ts,
                        "images": data,
                    },
                }
            )

        except Exception as e:
            logger.error(f"[APIServer] 获取图片列表失败: {e}")
            return web.json_response(
                {"status": "error", "message": str(e)},
                status=500,
            )

    async def _get_image_status(self, img) -> str:
        """获取图片状态

        Args:
            img: 图片记录对象

        Returns:
            状态字符串: downloading, available, expired
        """
        from pathlib import Path

        file_path = Path(img.file_path)

        # 检查文件是否正在下载
        if self.file_manager.is_file_downloading(file_path.name):
            return "downloading"

        # 检查文件是否存在
        if await self.file_manager.file_exists(file_path):
            return "available"

        # 文件不存在，视为已过期
        return "expired"

    async def handle_get_image(self, request: web.Request) -> web.Response:
        """获取单个图片信息接口

        GET /api/images/{id}
        """
        try:
            image_id = int(request.match_info["id"])
            image = await self.db.get_image_by_id(image_id)

            if not image:
                return web.json_response(
                    {"status": "error", "message": "图片不存在"},
                    status=404,
                )

            # 获取图片状态
            status = await self._get_image_status(image)

            return web.json_response(
                {
                    "status": "ok",
                    "data": {
                        "id": image.id,
                        "message_id": image.message_id,
                        "chat_id": image.chat_id,
                        "sender_id": image.sender_id,
                        "sender_name": image.sender_name,
                        "timestamp": image.timestamp,
                        "file_path": image.file_path,
                        "original_url": image.original_url,
                        "file_size": image.file_size,
                        "width": image.width,
                        "height": image.height,
                        "created_at": image.created_at,
                        "status": status,
                    },
                }
            )

        except ValueError:
            return web.json_response(
                {"status": "error", "message": "无效的图片ID"},
                status=400,
            )
        except Exception as e:
            logger.error(f"[APIServer] 获取图片信息失败: {e}")
            return web.json_response(
                {"status": "error", "message": str(e)},
                status=500,
            )

    async def handle_get_file(self, request: web.Request) -> web.Response:
        """获取文件接口

        GET /api/file/{filename}

        返回图片文件内容或状态信息
        - 文件正在下载: 返回downloading状态
        - 文件已过期: 返回expired状态
        - 文件可用: 返回文件内容
        """
        try:
            filename = request.match_info["filename"]

            # 安全检查：防止目录遍历攻击
            if ".." in filename or "/" in filename or "\\" in filename:
                return web.json_response(
                    {"status": "error", "message": "非法文件名"},
                    status=400,
                )

            # 检查文件是否正在下载
            if self.file_manager.is_file_downloading(filename):
                return web.json_response(
                    {
                        "status": "downloading",
                        "message": "文件正在下载中",
                        "filename": filename,
                    },
                    status=202,
                )

            # 获取文件路径
            file_path = self.file_manager.get_tmp_path(filename)

            # 检查文件是否存在
            if await self.file_manager.file_exists(file_path):
                # 读取文件
                data = await self.file_manager.read_file(file_path)
                if data:
                    # 根据扩展名设置Content-Type
                    content_type = self._get_content_type(filename)
                    return web.Response(
                        body=data,
                        content_type=content_type,
                        headers={
                            "Content-Disposition": f'inline; filename="{filename}"',
                        },
                    )

            # 文件不存在，视为已过期
            return web.json_response(
                {
                    "status": "expired",
                    "message": "文件已过期",
                    "filename": filename,
                },
                status=410,
            )

        except Exception as e:
            logger.error(f"[APIServer] 获取文件失败: {e}")
            return web.json_response(
                {"status": "error", "message": str(e)},
                status=500,
            )

    def _get_content_type(self, filename: str) -> str:
        """根据文件名获取Content-Type

        Args:
            filename: 文件名

        Returns:
            Content-Type字符串
        """
        ext = Path(filename).suffix.lower()
        content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        return content_types.get(ext, "application/octet-stream")
