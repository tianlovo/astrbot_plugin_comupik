# ComuPik Python SDK

Python SDK 用于在 Python 项目中接入 ComuPik 图片服务。

## 安装

```bash
pip install aiohttp
```

## 快速开始

```python
import asyncio
from comupik import ComuPikClient

async def main():
    # 创建客户端
    client = ComuPikClient("http://127.0.0.1:8080")
    
    # 获取统计信息
    stats = await client.get_stats()
    print(f"总图片数: {stats['total_images']}")
    
    # 轮询新图片
    async for image in client.poll_images():
        print(f"新图片: {image['id']} - {image['file_path']}")

asyncio.run(main())
```

## 完整 SDK 代码

```python
"""ComuPik Python SDK

提供便捷的 Python 接口访问 ComuPik API 服务。
"""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional

import aiohttp


@dataclass
class ImageInfo:
    """图片信息数据类"""
    id: int
    message_id: str
    chat_id: str
    sender_id: str
    sender_name: str
    timestamp: int
    file_path: str
    original_url: str
    file_size: int
    width: int
    height: int
    created_at: int
    status: str


@dataclass
class StatsInfo:
    """统计信息数据类"""
    total_images: int
    total_size_bytes: int
    avg_size_bytes: int
    chat_count: int
    oldest_timestamp: int
    newest_timestamp: int


class ComuPikError(Exception):
    """ComuPik SDK 异常基类"""
    pass


class APIError(ComuPikError):
    """API 调用异常"""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(f"API Error {status_code}: {message}")


class ImageNotFoundError(ComuPikError):
    """图片不存在异常"""
    pass


class ImageExpiredError(ComuPikError):
    """图片已过期异常"""
    pass


class ComuPikClient:
    """ComuPik API 客户端

    提供便捷的接口访问 ComuPik 图片服务。

    Example:
        ```python
        client = ComuPikClient("http://127.0.0.1:8080")

        # 获取统计信息
        stats = await client.get_stats()

        # 轮询新图片
        async for image in client.poll_images(interval=30):
            await process_image(image)
        ```
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        """初始化客户端

        Args:
            base_url: API 基础 URL
        """
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._known_ids: set[int] = set()
        self._last_end_time: int = int(time.time())

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def close(self):
        """关闭客户端连接"""
        if self._session:
            await self._session.close()
            self._session = None

    def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """发送 HTTP 请求

        Args:
            method: HTTP 方法
            path: API 路径
            **kwargs: 请求参数

        Returns:
            响应数据

        Raises:
            APIError: API 调用失败
        """
        url = f"{self.base_url}{path}"
        session = self._get_session()

        async with session.request(method, url, **kwargs) as resp:
            data = await resp.json()

            if resp.status >= 400:
                raise APIError(
                    data.get("message", "Unknown error"),
                    status_code=resp.status
                )

            return data

    async def health_check(self) -> bool:
        """健康检查

        Returns:
            服务是否正常
        """
        try:
            data = await self._request("GET", "/api/health")
            return data.get("status") == "ok"
        except Exception:
            return False

    async def get_stats(self) -> StatsInfo:
        """获取统计信息

        Returns:
            统计信息

        Raises:
            APIError: API 调用失败
        """
        data = await self._request("GET", "/api/stats")
        stats = data["data"]
        return StatsInfo(
            total_images=stats["total_images"],
            total_size_bytes=stats["total_size_bytes"],
            avg_size_bytes=stats["avg_size_bytes"],
            chat_count=stats["chat_count"],
            oldest_timestamp=stats["oldest_timestamp"],
            newest_timestamp=stats["newest_timestamp"],
        )

    async def list_images(
        self,
        start_time: int,
        end_time: int,
        exclude_ids: Optional[list[int]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ImageInfo], int]:
        """获取图片列表

        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            exclude_ids: 要排除的图片ID列表，用于轮询时避免重复获取已处理的图片
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            (图片列表, 总数)

        Raises:
            APIError: API 调用失败

        Note:
            exclude_ids 的必要性：
            由于时间戳是秒级的，同一秒内发送的多张图片会有相同的 timestamp。
            在轮询场景中，如果不排除已处理的图片ID，可能会重复获取相同的图片。
            建议客户端维护一个已处理ID的集合，每次查询时传入 exclude_ids。
        """
        params = {
            "start_time": start_time,
            "end_time": end_time,
            "exclude_ids": json.dumps(exclude_ids or []),
            "limit": limit,
            "offset": offset,
        }

        data = await self._request("GET", "/api/images", params=params)
        result = data["data"]

        images = [
            ImageInfo(
                id=img["id"],
                message_id=img["message_id"],
                chat_id=img["chat_id"],
                sender_id=img["sender_id"],
                sender_name=img["sender_name"],
                timestamp=img["timestamp"],
                file_path=img["file_path"],
                original_url=img["original_url"],
                file_size=img["file_size"],
                width=img["width"],
                height=img["height"],
                created_at=img["created_at"],
                status=img["status"],
            )
            for img in result["images"]
        ]

        return images, result["total"]

    async def get_image(self, image_id: int) -> ImageInfo:
        """获取单个图片信息

        Args:
            image_id: 图片ID

        Returns:
            图片信息

        Raises:
            ImageNotFoundError: 图片不存在
            APIError: API 调用失败
        """
        try:
            data = await self._request("GET", f"/api/images/{image_id}")
        except APIError as e:
            if e.status_code == 404:
                raise ImageNotFoundError(f"图片不存在: {image_id}")
            raise

        img = data["data"]
        return ImageInfo(
            id=img["id"],
            message_id=img["message_id"],
            chat_id=img["chat_id"],
            sender_id=img["sender_id"],
            sender_name=img["sender_name"],
            timestamp=img["timestamp"],
            file_path=img["file_path"],
            original_url=img["original_url"],
            file_size=img["file_size"],
            width=img["width"],
            height=img["height"],
            created_at=img["created_at"],
            status=img["status"],
        )

    async def download_image(
        self,
        filename: str,
        save_path: Optional[Path] = None,
    ) -> Optional[bytes]:
        """下载图片文件

        Args:
            filename: 文件名
            save_path: 保存路径（可选）

        Returns:
            图片数据，如果图片不可用返回 None

        Raises:
            ImageNotFoundError: 图片不存在
            ImageExpiredError: 图片已过期
            APIError: API 调用失败
        """
        url = f"{self.base_url}/api/file/{filename}"
        session = self._get_session()

        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.read()
                if save_path:
                    save_path.write_bytes(data)
                return data
            elif resp.status == 202:
                # 正在下载中
                return None
            elif resp.status == 404:
                raise ImageNotFoundError(f"图片不存在: {filename}")
            elif resp.status == 410:
                raise ImageExpiredError(f"图片已过期: {filename}")
            else:
                raise APIError(f"下载失败: {resp.status}", status_code=resp.status)

    async def poll_images(
        self,
        interval: int = 30,
        start_from: Optional[int] = None,
    ) -> AsyncIterator[ImageInfo]:
        """轮询新图片

        持续轮询获取新图片，是一个异步生成器。

        Args:
            interval: 轮询间隔（秒）
            start_from: 开始时间戳（默认从当前时间开始）

        Yields:
            新图片信息

        Example:
            ```python
            async for image in client.poll_images(interval=30):
                print(f"新图片: {image.id}")
                # 下载图片
                data = await client.download_image(
                    Path(image.file_path).name
                )
            ```
        """
        if start_from:
            self._last_end_time = start_from

        while True:
            current_time = int(time.time())

            try:
                images, _ = await self.list_images(
                    start_time=self._last_end_time,
                    end_time=current_time,
                    exclude_ids=list(self._known_ids),
                    limit=100,
                )

                for image in images:
                    self._known_ids.add(image.id)
                    yield image

                self._last_end_time = current_time

            except Exception as e:
                print(f"轮询出错: {e}")

            await asyncio.sleep(interval)

    def reset_poll_state(self):
        """重置轮询状态

        清除已知的图片ID和时间戳，重新开始轮询。
        """
        self._known_ids.clear()
        self._last_end_time = int(time.time())
```

## 使用示例

### 基本轮询

```python
import asyncio
from comupik import ComuPikClient

async def main():
    client = ComuPikClient("http://127.0.0.1:8080")

    # 轮询新图片（每30秒）
    async for image in client.poll_images(interval=30):
        print(f"收到新图片: {image.id}")
        print(f"  发送者: {image.sender_name}")
        print(f"  大小: {image.file_size} bytes")
        print(f"  尺寸: {image.width}x{image.height}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 下载图片

```python
import asyncio
from pathlib import Path
from comupik import ComuPikClient, ImageNotFoundError, ImageExpiredError

async def download_example():
    client = ComuPikClient("http://127.0.0.1:8080")

    async with client:
        # 获取图片信息
        image = await client.get_image(1)
        filename = Path(image.file_path).name

        try:
            # 下载图片
            data = await client.download_image(
                filename,
                save_path=Path(f"./downloads/{filename}")
            )
            print(f"下载成功: {len(data)} bytes")

        except ImageNotFoundError:
            print("图片不存在")
        except ImageExpiredError:
            print("图片已过期")

asyncio.run(download_example())
```

### 批量下载

```python
import asyncio
from pathlib import Path
from comupik import ComuPikClient

async def batch_download():
    client = ComuPikClient("http://127.0.0.1:8080")
    download_dir = Path("./downloads")
    download_dir.mkdir(exist_ok=True)

    async with client:
        # 获取最近1小时的图片
        end_time = int(time.time())
        start_time = end_time - 3600

        images, total = await client.list_images(
            start_time=start_time,
            end_time=end_time,
            limit=50
        )

        print(f"找到 {total} 张图片")

        # 下载所有图片
        for image in images:
            if image.status == "available":
                filename = Path(image.file_path).name
                try:
                    await client.download_image(
                        filename,
                        save_path=download_dir / filename
                    )
                    print(f"✓ 下载成功: {filename}")
                except Exception as e:
                    print(f"✗ 下载失败: {filename} - {e}")

asyncio.run(batch_download())
```

### 监控统计信息

```python
import asyncio
from comupik import ComuPikClient

async def monitor_stats():
    client = ComuPikClient("http://127.0.0.1:8080")

    async with client:
        while True:
            stats = await client.get_stats()

            # 格式化文件大小
            def format_size(size):
                for unit in ["B", "KB", "MB", "GB"]:
                    if size < 1024:
                        return f"{size:.2f} {unit}"
                    size /= 1024
                return f"{size:.2f} TB"

            print(f"\n=== ComuPik 统计 ===")
            print(f"总图片数: {stats.total_images}")
            print(f"总大小: {format_size(stats.total_size_bytes)}")
            print(f"平均大小: {format_size(stats.avg_size_bytes)}")
            print(f"聊天群数: {stats.chat_count}")

            await asyncio.sleep(60)  # 每分钟更新

asyncio.run(monitor_stats())
```

## 异常处理

```python
from comupik import (
    ComuPikClient,
    ComuPikError,
    APIError,
    ImageNotFoundError,
    ImageExpiredError,
)

async def error_handling():
    client = ComuPikClient()

    try:
        image = await client.get_image(99999)
    except ImageNotFoundError:
        print("图片不存在")
    except APIError as e:
        print(f"API 错误: {e.message} (状态码: {e.status_code})")
    except ComuPikError as e:
        print(f"SDK 错误: {e}")
    except Exception as e:
        print(f"未知错误: {e}")
```
