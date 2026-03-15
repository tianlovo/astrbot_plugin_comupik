"""文件管理模块

提供插件数据目录管理、文件访问锁定和定时清理功能
"""

import asyncio
import random
import string
from datetime import datetime, timedelta
from pathlib import Path

from astrbot.api import logger


class FileLock:
    """文件访问锁

    用于管理文件的并发访问，防止清理任务删除正在使用的文件
    """

    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = {}
        self._access_counts: dict[str, int] = {}
        self._global_lock = asyncio.Lock()

    async def acquire(self, file_path: str) -> bool:
        """获取文件锁

        Args:
            file_path: 文件路径

        Returns:
            是否成功获取锁
        """
        async with self._global_lock:
            if file_path not in self._locks:
                self._locks[file_path] = asyncio.Lock()
                self._access_counts[file_path] = 0

        lock = self._locks[file_path]
        try:
            await lock.acquire()
            async with self._global_lock:
                self._access_counts[file_path] += 1
            return True
        except Exception:
            return False

    async def release(self, file_path: str) -> None:
        """释放文件锁

        Args:
            file_path: 文件路径
        """
        async with self._global_lock:
            if file_path in self._access_counts:
                self._access_counts[file_path] -= 1

        if file_path in self._locks:
            try:
                self._locks[file_path].release()
            except RuntimeError:
                pass

    def is_locked(self, file_path: str) -> bool:
        """检查文件是否被锁定

        Args:
            file_path: 文件路径

        Returns:
            是否被锁定
        """
        return self._access_counts.get(file_path, 0) > 0


class FileManager:
    """文件管理类

    管理插件数据目录、临时文件和定时清理任务
    """

    def __init__(
        self,
        data_dir: Path,
        tmp_subdir: str,
        cleanup_config: dict,
    ):
        """初始化文件管理器

        Args:
            data_dir: 插件数据目录
            tmp_subdir: 临时文件子目录名
            cleanup_config: 清理配置
        """
        self.data_dir = data_dir
        self.tmp_dir = data_dir / tmp_subdir
        self.cleanup_config = cleanup_config
        self.file_lock = FileLock()
        self._cleanup_task: asyncio.Task | None = None
        self._running = False
        self._downloading_files: set[str] = set()
        self._download_lock = asyncio.Lock()

    async def init(self) -> None:
        """异步初始化文件管理器"""
        # 创建必要的目录
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[FileManager] 数据目录: {self.data_dir}")
        logger.info(f"[FileManager] 临时目录: {self.tmp_dir}")

        # 启动定时清理任务
        if self.cleanup_config.get("enabled", True):
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("[FileManager] 定时清理任务已启动")

    def generate_filename(
        self,
        pattern: str,
        msg_id: str = "",
        chat_id: str = "",
        ext: str = ".jpg",
    ) -> str:
        """生成文件名

        Args:
            pattern: 命名模式
            msg_id: 消息ID
            chat_id: 聊天群ID
            ext: 文件扩展名

        Returns:
            生成的文件名
        """
        timestamp = int(datetime.now().timestamp())
        random_str = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=8)
        )

        filename = pattern.format(
            timestamp=timestamp,
            msg_id=msg_id,
            chat_id=chat_id,
            random=random_str,
        )

        # 确保有扩展名
        if not filename.endswith(ext):
            filename += ext

        return filename

    def get_tmp_path(self, filename: str) -> Path:
        """获取临时文件完整路径

        Args:
            filename: 文件名

        Returns:
            完整路径
        """
        return self.tmp_dir / filename

    async def save_file(self, data: bytes, filename: str) -> Path | None:
        """保存文件到临时目录

        Args:
            data: 文件数据
            filename: 文件名

        Returns:
            保存的文件路径，失败返回None
        """
        file_path = self.get_tmp_path(filename)

        # 获取文件锁
        if not await self.file_lock.acquire(str(file_path)):
            logger.warning(f"[FileManager] 无法获取文件锁: {file_path}")
            return None

        try:
            # 写入文件
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._write_file, file_path, data)
            logger.debug(f"[FileManager] 文件已保存: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"[FileManager] 保存文件失败: {e}")
            return None
        finally:
            await self.file_lock.release(str(file_path))

    def _write_file(self, file_path: Path, data: bytes) -> None:
        """同步写入文件

        Args:
            file_path: 文件路径
            data: 文件数据
        """
        file_path.write_bytes(data)

    async def read_file(self, file_path: str | Path) -> bytes | None:
        """读取文件

        Args:
            file_path: 文件路径

        Returns:
            文件数据，失败返回None
        """
        path = Path(file_path)

        if not path.exists():
            return None

        # 获取文件锁
        if not await self.file_lock.acquire(str(path)):
            logger.warning(f"[FileManager] 无法获取文件锁: {path}")
            return None

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, path.read_bytes)
        except Exception as e:
            logger.error(f"[FileManager] 读取文件失败: {e}")
            return None
        finally:
            await self.file_lock.release(str(path))

    async def file_exists(self, file_path: str | Path) -> bool:
        """检查文件是否存在

        Args:
            file_path: 文件路径

        Returns:
            是否存在
        """
        path = Path(file_path)
        return path.exists()

    async def delete_file(self, file_path: str | Path) -> bool:
        """删除文件

        Args:
            file_path: 文件路径

        Returns:
            是否删除成功
        """
        path = Path(file_path)

        # 检查文件是否被锁定
        if self.file_lock.is_locked(str(path)):
            logger.debug(f"[FileManager] 文件被锁定，跳过删除: {path}")
            return False

        try:
            if path.exists():
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, path.unlink)
                logger.debug(f"[FileManager] 文件已删除: {path}")
            return True
        except Exception as e:
            logger.error(f"[FileManager] 删除文件失败: {e}")
            return False

    async def _cleanup_loop(self) -> None:
        """定时清理循环"""
        # 默认值与 _conf_schema.json: cleanup.interval_hours.default 保持一致
        interval_hours = self.cleanup_config.get("interval_hours", 24)
        interval_seconds = interval_hours * 3600

        while self._running:
            try:
                await asyncio.sleep(interval_seconds)
                await self._do_cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[FileManager] 清理任务出错: {e}")

    async def _do_cleanup(self) -> None:
        """执行清理任务"""
        # 默认值与 _conf_schema.json: cleanup.max_age_hours.default 保持一致
        max_age_hours = self.cleanup_config.get("max_age_hours", 72)
        max_age = timedelta(hours=max_age_hours)
        now = datetime.now()

        try:
            # 获取临时目录中的所有文件
            loop = asyncio.get_event_loop()
            files = await loop.run_in_executor(
                None, lambda: list(self.tmp_dir.iterdir())
            )

            deleted_count = 0
            skipped_count = 0

            for file_path in files:
                if not file_path.is_file():
                    continue

                # 检查文件是否被锁定
                if self.file_lock.is_locked(str(file_path)):
                    skipped_count += 1
                    continue

                # 检查文件年龄
                try:
                    stat = await loop.run_in_executor(None, file_path.stat)
                    mtime = datetime.fromtimestamp(stat.st_mtime)
                    age = now - mtime

                    if age > max_age:
                        if await self.delete_file(file_path):
                            deleted_count += 1
                except Exception as e:
                    logger.error(f"[FileManager] 检查文件失败 {file_path}: {e}")

            logger.info(
                f"[FileManager] 清理完成: 删除 {deleted_count} 个文件, "
                f"跳过 {skipped_count} 个锁定文件"
            )
        except Exception as e:
            logger.error(f"[FileManager] 清理任务执行失败: {e}")

    async def mark_downloading(self, filename: str) -> None:
        """标记文件正在下载

        Args:
            filename: 文件名
        """
        async with self._download_lock:
            self._downloading_files.add(filename)

    async def unmark_downloading(self, filename: str) -> None:
        """取消文件正在下载标记

        Args:
            filename: 文件名
        """
        async with self._download_lock:
            self._downloading_files.discard(filename)

    def is_file_downloading(self, filename: str) -> bool:
        """检查文件是否正在下载

        Args:
            filename: 文件名

        Returns:
            是否正在下载
        """
        return filename in self._downloading_files

    async def close(self) -> None:
        """关闭文件管理器"""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("[FileManager] 文件管理器已关闭")
