"""搜索 Provider 注册中心与 failover 编排。

链路顺序固定:Tavily → Brave → Serper → DuckDuckGo
- 某第三方 provider 抛 QuotaExceededError → 标记冷却 1 小时,立即尝试下一个
- 某第三方 provider 抛其他异常 → 不冷却,跳过本次尝试
- 所有第三方都不可用 → 使用 DuckDuckGo 兜底
- DuckDuckGo 也失败 → 抛 RuntimeError

provider 列表在首次调用时懒加载(读 env),用 asyncio.Lock 保护初始化。
运行时只读 _providers,冷却状态由各 provider 内部维护(线程安全由 GIL 保证)。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .base import BaseSearchProvider, SearchQuery, SearchResult, QuotaExceededError
from .tavily import TavilyProvider
from .brave import BraveProvider
from .serper import SerperProvider
from .duckduckgo import DuckDuckGoProvider

logger = logging.getLogger(__name__)

_providers: Optional[list[BaseSearchProvider]] = None
_init_lock = asyncio.Lock()


async def _get_providers() -> list[BaseSearchProvider]:
    """懒加载 provider 列表(线程安全)。"""
    global _providers
    if _providers is not None:
        return _providers

    async with _init_lock:
        if _providers is not None:
            return _providers

        # 延迟导入,避免循环依赖
        from agent_core.config import (
            TAVILY_API_KEY,
            BRAVE_API_KEY,
            SERPER_API_KEY,
            SEARCH_PROVIDER_COOLDOWN_SECONDS,
        )

        providers: list[BaseSearchProvider] = []
        # 按固定 failover 顺序构造;无 key 的第三方 provider 直接跳过(不入链路)
        if TAVILY_API_KEY:
            providers.append(TavilyProvider(TAVILY_API_KEY))
        if BRAVE_API_KEY:
            providers.append(BraveProvider(BRAVE_API_KEY))
        if SERPER_API_KEY:
            providers.append(SerperProvider(SERPER_API_KEY))
        # DuckDuckGo 永远在末尾作兜底
        providers.append(DuckDuckGoProvider())

        _providers = providers
        logger.info(
            "Search providers initialized (failover order): %s",
            [p.name for p in providers],
        )
        return _providers


async def get_search_results(query: SearchQuery) -> tuple[list[SearchResult], str]:
    """按 failover 顺序尝试各 provider,返回 (结果, 使用的 provider 名)。

    逻辑:
      1. 按顺序遍历 provider,跳过不可用的(is_available() False)
      2. 调用 search(),成功且非空则返回
      3. QuotaExceededError → 冷却 + 跳过
      4. 其他 Exception → 跳过(不冷却)
      5. 全部失败 → 最后兜底用 DuckDuckGo(若链路里没有则新建)
      6. DuckDuckGo 也失败 → 抛 RuntimeError
    """
    from agent_core.config import SEARCH_PROVIDER_COOLDOWN_SECONDS

    providers = await _get_providers()

    last_error: Optional[Exception] = None
    ddg_used_in_chain = False

    for provider in providers:
        if provider.name == "duckduckgo":
            ddg_used_in_chain = True

        if not provider.is_available():
            logger.debug("Provider %s skipped (not available)", provider.name)
            continue

        try:
            results = await provider.search(query)
            if results:
                logger.info("Search succeeded via provider: %s", provider.name)
                return results, provider.name
            logger.debug("Provider %s returned empty results", provider.name)
        except QuotaExceededError as e:
            provider.mark_cooldown(SEARCH_PROVIDER_COOLDOWN_SECONDS)
            logger.warning(
                "Provider %s quota exceeded, cooling down %ss: %s",
                provider.name,
                SEARCH_PROVIDER_COOLDOWN_SECONDS,
                e,
            )
            last_error = e
        except Exception as e:
            # 网络抖动等临时故障:不冷却,仅跳过本次
            logger.warning(
                "Provider %s failed (transient, no cooldown): %s: %s",
                provider.name,
                type(e).__name__,
                e,
            )
            last_error = e

    # 链路里所有 provider 都失败(包括 DDG 自己失败的情况)
    # 如果 DDG 没在链路里(理论上不会,因为构造时一定追加),补一次
    if not ddg_used_in_chain:
        try:
            ddg = DuckDuckGoProvider()
            results = await ddg.search(query)
            if results:
                return results, ddg.name
        except Exception as e:
            last_error = e

    raise RuntimeError(f"所有搜索 provider 均不可用,最后错误: {last_error}")


def reset_providers() -> None:
    """重置 provider 列表(主要供测试使用,运行时不应调用)。"""
    global _providers
    _providers = None
