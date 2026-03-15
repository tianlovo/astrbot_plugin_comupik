"""重试工具模块

提供带指数退避的重试装饰器和工具函数
"""

import asyncio
import functools
from collections.abc import Callable
from typing import Any, TypeVar, cast

from astrbot.api import logger

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int, float], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """重试装饰器，支持指数退避策略

    Args:
        max_retries: 最大重试次数，默认3次
        base_delay: 基础延迟时间（秒），默认1秒
        max_delay: 最大延迟时间（秒），默认60秒
        exceptions: 需要重试的异常类型，默认所有Exception
        on_retry: 重试时的回调函数，参数为(异常, 重试次数, 延迟时间)

    Returns:
        装饰器函数

    示例:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        async def download_image():
            # 可能失败的操作
            pass
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt >= max_retries:
                        logger.error(
                            f"[Retry] {func.__name__} 在 {max_retries} 次重试后仍然失败: {e}"
                        )
                        raise

                    # 计算延迟时间（指数退避）
                    delay = min(base_delay * (2**attempt), max_delay)

                    logger.warning(
                        f"[Retry] {func.__name__} 第 {attempt + 1} 次尝试失败: {e}, "
                        f"{delay}秒后重试..."
                    )

                    # 调用重试回调
                    if on_retry:
                        try:
                            on_retry(e, attempt + 1, delay)
                        except Exception as callback_error:
                            logger.error(f"[Retry] 回调函数执行失败: {callback_error}")

                    await asyncio.sleep(delay)

            # 理论上不会执行到这里，但为了类型检查
            if last_exception:
                raise last_exception
            raise RuntimeError("重试逻辑异常")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt >= max_retries:
                        logger.error(
                            f"[Retry] {func.__name__} 在 {max_retries} 次重试后仍然失败: {e}"
                        )
                        raise

                    # 计算延迟时间（指数退避）
                    delay = min(base_delay * (2**attempt), max_delay)

                    logger.warning(
                        f"[Retry] {func.__name__} 第 {attempt + 1} 次尝试失败: {e}, "
                        f"{delay}秒后重试..."
                    )

                    # 调用重试回调
                    if on_retry:
                        try:
                            on_retry(e, attempt + 1, delay)
                        except Exception as callback_error:
                            logger.error(f"[Retry] 回调函数执行失败: {callback_error}")

                    # 同步函数使用time.sleep
                    import time

                    time.sleep(delay)

            # 理论上不会执行到这里
            if last_exception:
                raise last_exception
            raise RuntimeError("重试逻辑异常")

        # 根据函数类型返回对应的wrapper
        if asyncio.iscoroutinefunction(func):
            return cast(Callable[..., T], async_wrapper)
        else:
            return cast(Callable[..., T], sync_wrapper)

    return decorator


async def retry_operation(
    operation: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    *args: Any,
    **kwargs: Any,
) -> T:
    """执行带重试的操作

    Args:
        operation: 要执行的操作函数
        max_retries: 最大重试次数
        base_delay: 基础延迟时间
        max_delay: 最大延迟时间
        exceptions: 需要重试的异常类型
        *args: 操作函数的参数
        **kwargs: 操作函数的关键字参数

    Returns:
        操作函数的返回值

    Raises:
        最后一次重试失败的异常
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(operation):
                return await operation(*args, **kwargs)
            else:
                return operation(*args, **kwargs)
        except exceptions as e:
            last_exception = e

            if attempt >= max_retries:
                logger.error(f"[Retry] 操作在 {max_retries} 次重试后仍然失败: {e}")
                raise

            delay = min(base_delay * (2**attempt), max_delay)
            logger.warning(
                f"[Retry] 第 {attempt + 1} 次尝试失败: {e}, {delay}秒后重试..."
            )
            await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
    raise RuntimeError("重试逻辑异常")


class RetryConfig:
    """重试配置类

    提供默认的重试配置参数
    """

    # 图片下载重试配置
    DOWNLOAD_RETRY = {
        "max_retries": 3,
        "base_delay": 1.0,
        "max_delay": 30.0,
        "exceptions": (Exception,),
    }

    # 数据库操作重试配置
    DATABASE_RETRY = {
        "max_retries": 3,
        "base_delay": 0.5,
        "max_delay": 10.0,
        "exceptions": (Exception,),
    }

    # API请求重试配置
    API_RETRY = {
        "max_retries": 3,
        "base_delay": 1.0,
        "max_delay": 30.0,
        "exceptions": (Exception,),
    }

    # 文件操作重试配置
    FILE_RETRY = {
        "max_retries": 3,
        "base_delay": 0.5,
        "max_delay": 10.0,
        "exceptions": (Exception,),
    }
