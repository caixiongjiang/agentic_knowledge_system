#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""=================================================
@PROJECT_NAME: agentic_knowledge_system
@File    : retry_decorator.py
@Author  : caixiongjiang
@Date    : 2025/12/30 16:01
@Function: 
    重试装饰器 - 支持同步和异步函数的重试机制
@Modify History:
    2025/12/30 - 修复内存泄漏和逻辑漏洞问题
@Copyright：Copyright(c) 2024-2026. All Rights Reserved
=================================================="""
from typing import (
    Union,
    Tuple,
    Callable,
    Any,
    Type,
    Optional
)
import asyncio
import logging
import functools
from enum import Enum
import time
import concurrent.futures


class RetryStrategy(Enum):
    """重试策略枚举"""
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"


def retry_async(
    max_retries: int = 3,
    retry_delay: float = 0.5,
    retry_strategy: Union[str, RetryStrategy] = RetryStrategy.FIXED,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    logger: Optional[logging.Logger] = None,
    log_level: int = logging.WARNING,
    raise_on_failure: bool = True,
    default_return_value: Any = None,
    timeout: Optional[float] = None,
    max_delay: float = 60.0
):
    """
    异步函数重试装饰器

    :param max_retries: 最大重试次数，默认3次
    :param retry_delay: 重试延迟时间（秒），默认0.5秒
    :param retry_strategy: 重试策略，支持 'fixed'（固定延迟）、'exponential'（指数退避）、'linear'（线性递增）
    :param exceptions: 需要重试的异常类型，可以是单个异常类型或异常类型元组
    :param logger: 日志记录器，如果为None则创建默认logger
    :param log_level: 日志级别，默认WARNING
    :param raise_on_failure: 所有重试失败后是否抛出异常，默认True
    :param default_return_value: 当raise_on_failure为False时的默认返回值
    :param timeout: 每次调用的超时时间（秒），如果为None则不设置超时
    :param max_delay: 最大延迟时间上限（秒），防止指数退避导致过长等待，默认60秒
    :return: 装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 在wrapper内部初始化logger，避免nonlocal的并发安全问题
            _logger = logger if logger is not None else logging.getLogger(func.__name__)

            # 转换重试策略为枚举类型
            strategy = retry_strategy
            if isinstance(retry_strategy, str):
                try:
                    strategy = RetryStrategy(retry_strategy.lower())
                except ValueError:
                    _logger.error(f"Invalid retry strategy: {retry_strategy}")
                    raise ValueError(f"Invalid retry strategy: {retry_strategy}")

            last_exception = None

            for attempt in range(max_retries):
                try:
                    # 根据是否设置timeout来决定调用方式
                    if timeout is not None:
                        _logger.debug(f"{func.__name__} attempt {attempt + 1}/{max_retries} with timeout {timeout}s")
                        result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                    else:
                        _logger.debug(f"{func.__name__} attempt {attempt + 1}/{max_retries} without timeout")
                        result = await func(*args, **kwargs)

                    if attempt > 0:
                        _logger.info(f"{func.__name__} succeeded on attempt {attempt + 1}")
                    return result

                except (asyncio.TimeoutError, TimeoutError) as e:
                    # 统一处理超时异常（兼容Python 3.11+）
                    last_exception = e
                    _logger.log(
                        log_level,
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} timeout after {timeout}s"
                    )

                    # 如果不是最后一次尝试，则等待后重试
                    if attempt < max_retries - 1:
                        delay = _calculate_delay(retry_delay, attempt, strategy, max_delay)
                        _logger.debug(f"Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)

                except exceptions as e:
                    # 只有当exceptions不是Exception基类时，这个分支才有意义
                    last_exception = e
                    _logger.log(
                        log_level,
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed: {type(e).__name__}: {str(e)}"
                    )

                    # 如果不是最后一次尝试，则等待后重试
                    if attempt < max_retries - 1:
                        delay = _calculate_delay(retry_delay, attempt, strategy, max_delay)
                        _logger.debug(f"Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)

                except Exception as e:
                    # 对于不在重试范围内的异常，直接抛出
                    # 注意：如果exceptions=Exception（默认值），这个分支永远不会执行
                    _logger.error(f"{func.__name__} failed with non-retryable exception: {type(e).__name__}: {str(e)}")
                    raise

            # 所有重试都失败
            error_msg = f"{func.__name__} failed after {max_retries} attempts"
            _logger.error(error_msg)

            if raise_on_failure:
                if last_exception:
                    raise last_exception
                else:
                    raise RuntimeError(error_msg)
            else:
                _logger.warning(f"Returning default value: {default_return_value}")
                return default_return_value

        return wrapper

    return decorator


def retry_sync(
    max_retries: int = 3,
    retry_delay: float = 0.5,
    retry_strategy: Union[str, RetryStrategy] = RetryStrategy.FIXED,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    logger: Optional[logging.Logger] = None,
    log_level: int = logging.WARNING,
    raise_on_failure: bool = True,
    default_return_value: Any = None,
    timeout: Optional[float] = None,
    max_delay: float = 60.0
):
    """
    同步函数重试装饰器
    
    注意：由于Python的限制，同步函数的超时无法真正取消正在执行的函数。
    如果函数超时，它仍会在后台线程中继续运行直到完成。
    建议：对于需要严格超时控制的场景，请使用异步版本 retry_async。

    :param max_retries: 最大重试次数，默认3次
    :param retry_delay: 重试延迟时间（秒），默认0.5秒
    :param retry_strategy: 重试策略，支持 'fixed'（固定延迟）、'exponential'（指数退避）、'linear'（线性递增）
    :param exceptions: 需要重试的异常类型，可以是单个异常类型或异常类型元组
    :param logger: 日志记录器，如果为None则创建默认logger
    :param log_level: 日志级别，默认WARNING
    :param raise_on_failure: 所有重试失败后是否抛出异常，默认True
    :param default_return_value: 当raise_on_failure为False时的默认返回值
    :param timeout: 每次调用的超时时间（秒），如果为None则不设置超时
    :param max_delay: 最大延迟时间上限（秒），防止指数退避导致过长等待，默认60秒
    :return: 装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 在wrapper内部初始化logger，避免nonlocal的并发安全问题
            _logger = logger if logger is not None else logging.getLogger(func.__name__)

            # 转换重试策略为枚举类型
            strategy = retry_strategy
            if isinstance(retry_strategy, str):
                try:
                    strategy = RetryStrategy(retry_strategy.lower())
                except ValueError:
                    _logger.error(f"Invalid retry strategy: {retry_strategy}")
                    raise ValueError(f"Invalid retry strategy: {retry_strategy}")

            last_exception = None

            for attempt in range(max_retries):
                try:
                    # 根据是否设置timeout来决定调用方式
                    if timeout is not None:
                        _logger.debug(f"{func.__name__} attempt {attempt + 1}/{max_retries} with timeout {timeout}s")
                        
                        # 使用ThreadPoolExecutor实现超时
                        # 注意：这里无法真正取消正在执行的函数
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(func, *args, **kwargs)
                            try:
                                result = future.result(timeout=timeout)
                            except concurrent.futures.TimeoutError:
                                # 警告：函数仍在后台运行
                                _logger.warning(
                                    f"{func.__name__} timed out after {timeout}s, "
                                    f"but the function may still be running in background thread"
                                )
                                # 尝试取消（但对于已经在执行的任务无效）
                                future.cancel()
                                raise TimeoutError(f"Function call timed out after {timeout} seconds")
                    else:
                        _logger.debug(f"{func.__name__} attempt {attempt + 1}/{max_retries} without timeout")
                        result = func(*args, **kwargs)

                    if attempt > 0:
                        _logger.info(f"{func.__name__} succeeded on attempt {attempt + 1}")
                    return result

                except TimeoutError as e:
                    # 处理超时异常
                    last_exception = e
                    _logger.log(
                        log_level,
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} timeout after {timeout}s"
                    )

                    # 如果不是最后一次尝试，则等待后重试
                    if attempt < max_retries - 1:
                        delay = _calculate_delay(retry_delay, attempt, strategy, max_delay)
                        _logger.debug(f"Retrying in {delay} seconds...")
                        time.sleep(delay)

                except exceptions as e:
                    last_exception = e
                    _logger.log(
                        log_level,
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed: {type(e).__name__}: {str(e)}"
                    )

                    # 如果不是最后一次尝试，则等待后重试
                    if attempt < max_retries - 1:
                        delay = _calculate_delay(retry_delay, attempt, strategy, max_delay)
                        _logger.debug(f"Retrying in {delay} seconds...")
                        time.sleep(delay)

                except Exception as e:
                    # 对于不在重试范围内的异常，直接抛出
                    # 注意：如果exceptions=Exception（默认值），这个分支永远不会执行
                    _logger.error(f"{func.__name__} failed with non-retryable exception: {type(e).__name__}: {str(e)}")
                    raise

            # 所有重试都失败
            error_msg = f"{func.__name__} failed after {max_retries} attempts"
            _logger.error(error_msg)

            if raise_on_failure:
                if last_exception:
                    raise last_exception
                else:
                    raise RuntimeError(error_msg)
            else:
                _logger.warning(f"Returning default value: {default_return_value}")
                return default_return_value

        return wrapper

    return decorator


def _calculate_delay(base_delay: float, attempt: int, strategy: RetryStrategy, max_delay: float = 60.0) -> float:
    """
    根据重试策略计算延迟时间（带上限限制）

    :param base_delay: 基础延迟时间
    :param attempt: 当前尝试次数（从0开始）
    :param strategy: 重试策略
    :param max_delay: 最大延迟时间上限
    :return: 计算出的延迟时间
    """
    if strategy == RetryStrategy.FIXED:
        delay = base_delay
    elif strategy == RetryStrategy.EXPONENTIAL:
        delay = base_delay * (2 ** attempt)
    elif strategy == RetryStrategy.LINEAR:
        delay = base_delay * (attempt + 1)
    else:
        raise ValueError(f"Unsupported retry strategy: {strategy}")
    
    # 应用最大延迟限制
    return min(delay, max_delay)
