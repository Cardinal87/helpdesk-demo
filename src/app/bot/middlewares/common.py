"""Update middlewares.

Order (outermost first in dispatcher registration):
1. DatabaseSession — opens an explicit transaction per update, injects Services.
2. UserContext — loads/creates the user row and puts language into data.
3. Throttling — Redis-backed per-user command rate limit.
4. Errors — maps domain errors to friendly localized messages; logs internals
   with traceback but never leaks them to the user. BOT_TOKEN/PII are not logged.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.application.context import Services
from app.config import Settings
from app.domain.errors import (
    AccessDeniedError,
    AttachmentLimitError,
    DomainError,
    FeedbackAlreadyExistsError,
    InvalidTransitionError,
    NoActiveRoleError,
    ValidationError,
    WorkspaceExpiredError,
)
from app.infrastructure.db.engine import session_scope

logger = logging.getLogger(__name__)


class DatabaseSessionMiddleware(BaseMiddleware):
    """One explicit transaction per update; commit on success, rollback on error."""

    def __init__(self, factory: Any, settings: Settings) -> None:
        self._factory = factory
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with session_scope(self._factory) as session:
            services = Services(session=session, settings=self._settings)
            data["services"] = services
            # aiogram expands middleware context into handler keyword arguments;
            # handlers deliberately accept this shared mapping as ``data``.
            data["data"] = data
            tg_user = data.get("event_from_user")
            if tg_user is not None:
                user = await services.users.get_or_create(
                    telegram_id=tg_user.id,
                    display_name=(tg_user.full_name or "")[:255],
                    language=self._settings.default_language,
                )
                data["lang"] = user.language or self._settings.default_language
                data["telegram_id"] = tg_user.id
            return await handler(event, data)


class UserContextMiddleware(BaseMiddleware):
    """Ensure a users[] row exists and expose 'lang' to handlers/services."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        svc: Services | None = data.get("services")
        tg_user = data.get("event_from_user")
        if svc is not None and tg_user is not None:
            lang = svc.settings.default_language
            try:
                user = await svc.users.get_or_create(
                    telegram_id=tg_user.id,
                    display_name=(tg_user.full_name or "")[:255],
                    language=lang,
                )
                data["lang"] = user.language or lang
                data["telegram_id"] = tg_user.id
            except Exception:  # DB hiccup must not break context injection entirely
                logger.exception("user context init failed")
                data["lang"] = lang
                data["telegram_id"] = tg_user.id
        return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """Redis fixed-window limiter: N updates per minute per user."""

    LIMIT = 60
    WINDOW_SECONDS = 60

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is not None and self._redis is not None:
            key = f"throttle:{tg_user.id}"
            try:
                pipe = self._redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, self.WINDOW_SECONDS, nx=True)
                count, _ = await pipe.execute()
                if int(count) > self.LIMIT:
                    logger.info("rate limit hit user=%s", tg_user.id)
                    cb = data.get("callback_query")
                    msg = data.get("message")
                    from app.bot.i18n import t

                    text = t(data.get("lang", "ru"), "err_rate_limited")
                    if cb:
                        await cb.answer(text, show_alert=True)
                    elif msg:
                        await msg.answer(text)
                    return
            except Exception:
                logger.exception("throttling redis error; allowing update")
        return await handler(event, data)


ERROR_KEYS: list[tuple[type[DomainError], str]] = [
    (AccessDeniedError, "err_access"),
    (NoActiveRoleError, "err_session_expired"),
    (WorkspaceExpiredError, "err_workspace_expired"),
    (InvalidTransitionError, "err_transition"),
    (FeedbackAlreadyExistsError, "feedback_exists"),
    (AttachmentLimitError, "err_attachment_limit"),
    (ValidationError, "err_validation"),
]


class ErrorHandlerMiddleware(BaseMiddleware):
    """Friendly localized errors; internal details only into structured logs."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except DomainError as exc:
            lang = data.get("lang", "ru")
            from app.bot.i18n import t

            key = "err_internal"
            detail = ""
            types = ""
            for cls, k in ERROR_KEYS:
                if isinstance(exc, cls):
                    key, detail = k, str(exc)
                    break
            if key == "err_attachment_limit":
                svc = data.get("services")
                types = ",".join(sorted(svc.settings.mime_allowlist)) if svc else ""
            msg = t(lang, key, detail=detail, types=types)
            logger.info(
                "domain error type=%s update_id=%s", type(exc).__name__, data.get("update_id")
            )
            message = data.get("message")
            callback = data.get("callback_query")
            if callback is not None:
                await callback.answer(msg, show_alert=True)
            elif message is not None:
                await message.answer(msg)
            return None
        except Exception:
            logger.exception(
                "unhandled error while processing update update_id=%s",
                data.get("update_id"),
            )
            lang = data.get("lang", "ru")
            from app.bot.i18n import t

            msg = t(lang, "err_internal")
            callback = data.get("callback_query")
            message = data.get("message")
            if callback is not None:
                await callback.answer(msg, show_alert=True)
            elif message is not None:
                await message.answer(msg)
            return None
