"""Application entry point for the long-polling demo bot."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.handlers import fallback, feedback, orders, start, tickets
from app.bot.middlewares.common import (
    DatabaseSessionMiddleware,
    ErrorHandlerMiddleware,
    ThrottlingMiddleware,
    UserContextMiddleware,
)
from app.config import Settings, get_settings
from app.infrastructure.db.engine import build_engine, build_session_factory, session_scope
from app.infrastructure.redis.client import build_fsm_storage, build_redis

logger = logging.getLogger(__name__)


async def _workspace_reaper(
    factory: async_sessionmaker[AsyncSession], *, interval_seconds: int = 300
) -> None:
    """Periodically remove expired workspaces; deletion is idempotent."""
    from app.infrastructure.db.repositories import WorkspaceRepo

    while True:
        try:
            async with session_scope(factory) as session:
                removed = await WorkspaceRepo(session).purge_expired()
            if removed:
                logger.info("expired workspaces purged count=%s", removed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("workspace TTL cleanup failed")
        await asyncio.sleep(interval_seconds)


def build_dispatcher(
    settings: Settings,
    factory: async_sessionmaker[AsyncSession],
    redis_client: Redis,
    storage: RedisStorage,
) -> Dispatcher:
    """Build the dispatcher without performing network I/O (useful for tests)."""
    dp = Dispatcher(storage=storage)
    # Outer middlewares are registered from outermost to innermost.
    dp.update.outer_middleware(ErrorHandlerMiddleware())
    dp.update.outer_middleware(DatabaseSessionMiddleware(factory, settings))
    dp.update.outer_middleware(UserContextMiddleware())
    dp.update.outer_middleware(ThrottlingMiddleware(redis_client))
    dp.include_routers(
        start.router, tickets.router, orders.router, feedback.router, fallback.router
    )
    return dp


async def run_polling(settings: Settings) -> None:
    """Start long polling and gracefully close all clients on shutdown."""
    engine = build_engine(settings)
    factory = build_session_factory(engine)
    redis_client = build_redis(settings)
    storage = build_fsm_storage(redis_client)
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher(settings, factory, redis_client, storage)
    reaper = asyncio.create_task(_workspace_reaper(factory), name="workspace-reaper")
    try:
        logger.info("starting Telegram CRM demo with long polling")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        reaper.cancel()
        with suppress(asyncio.CancelledError):
            await reaper
        await storage.close()
        await redis_client.aclose()
        await bot.session.close()
        await engine.dispose()


def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_polling(settings))


if __name__ == "__main__":
    main()
