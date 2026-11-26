"""Shared menu renderer: the menu is a screen like everything else."""

from __future__ import annotations

from aiogram import Bot
from aiogram.fsm.context import FSMContext

from app.application import session_usecases as SU
from app.bot.handlers.common import actor_id, lang, svc, t
from app.bot.keyboards import inline as kb
from app.bot.screen import push_screen, render_screen
from app.domain.errors import DomainError


async def render_menu(
    chat_id: int,
    state: FSMContext,
    data: dict,
    bot: Bot,
    notice: str | None = None,
    push: bool = False,
) -> None:
    language = lang(data)
    try:
        ctx = await SU.get_actor_context(svc(data), actor_id(data))
        role = ctx.session.role if ctx.session else None
    except DomainError:
        role = None

    parts: list[str] = []
    if notice:
        parts.append(notice)
    if role:
        role_name = t(language, f"role_{role.value}").strip("🧑‍🛠 ").strip()
        parts.append(f"👤 {role_name}")
    parts.append(t(language, "menu"))

    render = push_screen if push else render_screen
    await render(bot, chat_id, state, "\n\n".join(parts), kb.menu_kb(language, role))
