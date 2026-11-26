"""Entry-point handlers: /start, language, role choice, menu, exit, reset."""

from __future__ import annotations

import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application import session_usecases as SU
from app.bot import callbacks as cb
from app.bot.fsm import ConfirmStates, StartStates
from app.bot.handlers.common import LocalizedStart, actor_id, lang, safe_callback, svc, t
from app.bot.i18n import SUPPORTED_LANGUAGES
from app.bot.i18n import t as translate
from app.bot.keyboards import inline as kb
from app.bot.menu import render_menu
from app.bot.screen import push_screen, render_screen, reset_flow
from app.domain.ticket import Role

router = Router(name="start")


# --------------------------------------------------------------------------- #
# /start, /menu, /help, /cancel
# --------------------------------------------------------------------------- #
@router.message(LocalizedStart())
async def cmd_start_localized(message: Message, state: FSMContext, bot: Bot) -> None:
    await _begin(message, state, bot)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot) -> None:
    await _begin(message, state, bot)


@router.message(F.text.regexp(r"^/(menu|меню)$", flags=re.IGNORECASE))
async def msg_menu_alias(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    """Plain-text '/menu' shortcut to the main menu."""
    await reset_flow(state)
    await _render_menu_to(message, state, data, bot, push=True)


@router.message(Command("help"))
async def cmd_help(message: Message, data: dict) -> None:
    language = lang(data)
    text = (
        translate(language, "welcome")
        + "\n\n/start — "
        + ("начать заново" if language == "ru" else "restart the flow")
        + "\n/cancel — "
        + ("отменить текущее действие" if language == "ru" else "cancel current action")
        + "\n/menu — "
        + ("главное меню" if language == "ru" else "main menu")
    )
    await message.answer(text)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    if await state.get_state() is None:
        await message.answer(t(lang(data), "cancel_not_in_form"))
        return
    await reset_flow(state)
    await _render_menu_to(
        message, state, data, bot, notice=t(lang(data), "ticket_cancelled"), push=True
    )


async def _begin(message: Message, state: FSMContext, bot: Bot) -> None:
    await reset_flow(state)
    await state.set_state(StartStates.choose_language)
    await push_screen(
        bot,
        message.chat.id,
        state,
        "Выберите язык / Choose language:",
        kb.language_kb(),
    )


# --------------------------------------------------------------------------- #
# Language & role
# --------------------------------------------------------------------------- #
@router.callback_query(StartStates.choose_language, cb.LangCB.filter())
async def cb_language(
    callback: CallbackQuery, callback_data: cb.LangCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    code = callback_data.code if callback_data.code in SUPPORTED_LANGUAGES else "ru"
    await svc(data).users.set_language(actor_id(data), code)
    data["lang"] = code  # reflect immediately for downstream rendering
    await state.set_state(StartStates.choose_role)
    await safe_callback(callback)
    if callback.message:
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            t(code, "welcome") + "\n\n" + t(code, "choose_role"),
            kb.role_kb(code),
        )


async def _render_role_choice(
    chat_id: int, state: FSMContext, data: dict, bot: Bot, notice: str | None = None
) -> None:
    """Helper to show the role selection screen, optionally with a notice."""
    await state.set_state(StartStates.choose_role)
    language = lang(data)
    text = t(language, "welcome") + "\n\n" + t(language, "choose_role")
    if notice:
        text = notice + "\n\n" + text
    await render_screen(bot, chat_id, state, text, kb.role_kb(language))


@router.callback_query(cb.RoleCB.filter())
async def cb_role(
    callback: CallbackQuery, callback_data: cb.RoleCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    try:
        role = Role(callback_data.role)
    except ValueError:
        await safe_callback(callback)
        return
    await SU.choose_role(svc(data), actor_id(data), role)
    await reset_flow(state)
    await safe_callback(callback)
    if callback.message:
        await _render_menu_to(callback.message, state, data, bot)


@router.callback_query(cb.MenuCB.filter(F.action == "switch_role"))
async def cb_switch_role(callback: CallbackQuery, state: FSMContext, data: dict, bot: Bot) -> None:
    await reset_flow(state)
    await safe_callback(callback)
    if callback.message:
        await _render_role_choice(callback.message.chat.id, state, data, bot)


@router.callback_query(cb.MenuCB.filter(F.action == "settings"))
async def cb_settings(callback: CallbackQuery, state: FSMContext, data: dict, bot: Bot) -> None:
    await state.set_state(StartStates.choose_language)
    await safe_callback(callback)
    if callback.message:
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            t(lang(data), "choose_language"),
            kb.language_kb(),
        )


# --------------------------------------------------------------------------- #
# Back to menu
# --------------------------------------------------------------------------- #
@router.callback_query(cb.MenuCB.filter(F.action == "back_menu"))
async def cb_back_menu(callback: CallbackQuery, state: FSMContext, data: dict, bot: Bot) -> None:
    await safe_callback(callback)
    if callback.message:
        await _render_menu_to(callback.message, state, data, bot)


# --------------------------------------------------------------------------- #
# Confirms: exit role / reset workspace
# --------------------------------------------------------------------------- #
@router.callback_query(cb.ConfirmCB.filter((F.action == "exit_role") & (F.approve == "ask")))
async def cb_exit_ask(callback: CallbackQuery, state: FSMContext, data: dict, bot: Bot) -> None:
    await state.update_data(pending="exit_role")
    await state.set_state(ConfirmStates.pending)
    await safe_callback(callback)
    if callback.message:
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            t(lang(data), "exit_confirm"),
            kb.confirm_kb(lang(data), "exit_role"),
        )


@router.callback_query(cb.ConfirmCB.filter((F.action == "reset_ws") & (F.approve == "ask")))
async def cb_reset_ask(callback: CallbackQuery, state: FSMContext, data: dict, bot: Bot) -> None:
    await state.update_data(pending="reset_ws")
    await state.set_state(ConfirmStates.pending)
    await safe_callback(callback)
    if callback.message:
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            t(lang(data), "new_workspace_confirm"),
            kb.confirm_kb(lang(data), "reset_ws"),
        )


@router.callback_query(
    cb.ConfirmCB.filter(F.action.in_({"exit_role", "reset_ws"}) & F.approve.in_({"yes", "no"}))
)
async def cb_confirm_resolved(
    callback: CallbackQuery, callback_data: cb.ConfirmCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    await reset_flow(state)
    approved = callback_data.approve == "yes"
    await safe_callback(callback)
    if not callback.message:
        return

    if not approved:
        await _render_menu_to(callback.message, state, data, bot)
        return

    if callback_data.action == "exit_role":
        await SU.leave_role(svc(data), actor_id(data))
        await _render_role_choice(
            callback.message.chat.id, state, data, bot, notice=t(lang(data), "exited")
        )
    else:
        await SU.reset_workspace(svc(data), actor_id(data))
        await _render_role_choice(
            callback.message.chat.id, state, data, bot, notice=t(lang(data), "workspace_reset")
        )


# --------------------------------------------------------------------------- #
# Menu rendering (single screen)
# --------------------------------------------------------------------------- #
async def _render_menu_to(
    target: Message,
    state: FSMContext,
    data: dict,
    bot: Bot,
    notice: str | None = None,
    push: bool = False,
) -> None:
    """Delegate to the shared render_menu, which handles role/notice formatting."""
    await render_menu(target.chat.id, state, data, bot, notice=notice, push=push)
