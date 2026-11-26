"""Shared handler helpers.

Handlers only: parse input -> call use case -> render result (AGENTS.md).
No SQL, no authorization decisions, no status-transition logic here.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.context import Services
from app.bot.i18n import t
from app.domain.errors import DomainError


def svc(data: dict[str, Any]) -> Services:
    services = data.get("services")
    if not isinstance(services, Services):
        raise DomainError("internal: services missing")
    return services


def lang(data: dict[str, Any]) -> str:
    value = data.get("lang", "ru")
    return value if isinstance(value, str) else "ru"


def actor_id(data: dict[str, Any]) -> int:
    tg_user = data.get("event_from_user")
    if tg_user is None:
        raise DomainError("internal: no user in update")
    telegram_id = getattr(tg_user, "id", None)
    if not isinstance(telegram_id, int):
        raise DomainError("internal: invalid user in update")
    return telegram_id


LOCALIZED_START_ALIASES = ("начало", "старт")


class LocalizedStart(Command):
    """Command filter for localized /start aliases."""

    def __init__(self) -> None:
        super().__init__(commands=list(LOCALIZED_START_ALIASES), prefix="/")


async def safe_callback(callback: CallbackQuery) -> None:
    """Acknowledge a callback query quietly; never leak errors into chat."""
    with suppress(Exception):  # pragma: no cover - acknowledgement is best effort
        await callback.answer()


async def clear_fsm_and_menu(state: FSMContext) -> None:
    await state.clear()


__all__ = [
    "CallbackQuery",
    "Command",
    "FSMContext",
    "LocalizedStart",
    "Message",
    "actor_id",
    "clear_fsm_and_menu",
    "lang",
    "safe_callback",
    "svc",
    "t",
]
