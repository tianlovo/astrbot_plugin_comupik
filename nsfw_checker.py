"""NSFW 内容检测模块

提供对外部 NSFW 检测服务的调用封装。
参考: https://github.com/helloxz/nsfw
"""

from dataclasses import dataclass

import aiohttp

from astrbot.api import logger


@dataclass
class NSFWResult:
    """NSFW 检测结果"""

    sfw: float  # 安全系数 0.0-1.0
    nsfw: float  # 风险系数 0.0-1.0
    is_nsfw: bool  # 是否为 NSFW 内容
    raw_response: dict  # 原始响应


class NSFWChecker:
    """NSFW 内容检测器

    调用外部 NSFW 检测服务进行图片内容审核。

    Example:
        ```python
        checker = NSFWChecker("http://127.0.0.1:6086", token="xxx")
        result = await checker.check_image(image_data)

        if result.is_nsfw:
            print(f"检测到 NSFW 内容，风险系数: {result.nsfw}")
        ```
    """

    def __init__(
        self,
        api_url: str = "http://127.0.0.1:6086",
        token: str | None = None,
        timeout: int = 30,
    ):
        """初始化 NSFW 检测器

        Args:
            api_url: NSFW 检测服务地址
            token: 访问令牌（可选）
            timeout: 请求超时时间（秒）
        """
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """关闭 HTTP 会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _get_headers(self) -> dict:
        """获取请求头"""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def check_image(
        self,
        image_data: bytes,
        filename: str = "image.jpg",
    ) -> NSFWResult | None:
        """检测图片是否为 NSFW 内容

        通过上传图片文件到检测服务进行审核。

        Args:
            image_data: 图片二进制数据
            filename: 文件名（用于表单）

        Returns:
            NSFW 检测结果，失败返回 None
        """
        url = f"{self.api_url}/api/upload_check"

        try:
            session = await self._get_session()

            # 准备 multipart 表单数据
            data = aiohttp.FormData()
            data.add_field(
                "file",
                image_data,
                filename=filename,
                content_type="image/jpeg",
            )

            logger.debug(f"[NSFWChecker] 开始检测图片: {filename}")

            async with session.post(
                url,
                data=data,
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as response:
                if response.status != 200:
                    logger.error(f"[NSFWChecker] 检测请求失败: HTTP {response.status}")
                    return None

                result = await response.json()

                if result.get("code") != 200:
                    logger.error(f"[NSFWChecker] 检测服务返回错误: {result.get('msg')}")
                    return None

                data = result.get("data", {})
                nsfw_result = NSFWResult(
                    sfw=float(data.get("sfw", 0)),
                    nsfw=float(data.get("nsfw", 0)),
                    is_nsfw=bool(data.get("is_nsfw", False)),
                    raw_response=result,
                )

                logger.info(
                    f"[NSFWChecker] 检测完成: sfw={nsfw_result.sfw:.4f}, "
                    f"nsfw={nsfw_result.nsfw:.4f}, is_nsfw={nsfw_result.is_nsfw}"
                )

                return nsfw_result

        except aiohttp.ClientError as e:
            logger.error(f"[NSFWChecker] 网络请求失败: {e}")
            return None
        except Exception as e:
            logger.error(f"[NSFWChecker] 检测过程出错: {e}")
            return None

    async def check_image_by_url(self, image_url: str) -> NSFWResult | None:
        """通过 URL 检测图片

        Args:
            image_url: 图片 URL

        Returns:
            NSFW 检测结果，失败返回 None
        """
        url = f"{self.api_url}/api/url_check"

        try:
            session = await self._get_session()

            logger.debug(f"[NSFWChecker] 开始检测图片 URL: {image_url}")

            async with session.post(
                url,
                json={"url": image_url},
                headers={
                    **self._get_headers(),
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as response:
                if response.status != 200:
                    logger.error(f"[NSFWChecker] 检测请求失败: HTTP {response.status}")
                    return None

                result = await response.json()

                if result.get("code") != 200:
                    logger.error(f"[NSFWChecker] 检测服务返回错误: {result.get('msg')}")
                    return None

                data = result.get("data", {})
                nsfw_result = NSFWResult(
                    sfw=float(data.get("sfw", 0)),
                    nsfw=float(data.get("nsfw", 0)),
                    is_nsfw=bool(data.get("is_nsfw", False)),
                    raw_response=result,
                )

                logger.info(
                    f"[NSFWChecker] URL 检测完成: sfw={nsfw_result.sfw:.4f}, "
                    f"nsfw={nsfw_result.nsfw:.4f}, is_nsfw={nsfw_result.is_nsfw}"
                )

                return nsfw_result

        except aiohttp.ClientError as e:
            logger.error(f"[NSFWChecker] 网络请求失败: {e}")
            return None
        except Exception as e:
            logger.error(f"[NSFWChecker] 检测过程出错: {e}")
            return None

    def is_nsfw(self, result: NSFWResult, threshold: float = 0.8) -> bool:
        """根据阈值判断是否为 NSFW

        Args:
            result: NSFW 检测结果
            threshold: 判定阈值（默认 0.8）

        Returns:
            是否为 NSFW 内容
        """
        return result.nsfw >= threshold
