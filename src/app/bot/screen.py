"""Single-screen UI.

render_screen: edit stored screen in place (button presses).
push_screen: retire old screen, send new below user's message (user input).
The screen id AND its last payload (text+markup) live in FSM data so any
unhandled input can replay the current screen (see handlers/fallback.py).
"""

from __future__ import annotations

import contextlib

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

SCREEN_KEY = "screen_msg_id"
PAYLOAD_KEY = "screen_payload"

_EMPTY_KB = InlineKeyboardMarkup(inline_keyboard=[])


def _is_not_modified(exc: TelegramBadRequest) -> bool:
    return "message is not modified" in str(exc)


def _payload(text: str, markup: InlineKeyboardMarkup) -> dict:
    return {"text": text, "markup": markup.model_dump()}


async def render_screen(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Edit the current screen in place (callback/button updates)."""
    markup = markup if markup is not None else _EMPTY_KB
    screen_id = (await state.get_data()).get(SCREEN_KEY)
    if screen_id:
        try:
            await bot.edit_message_text(
                text, chat_id=chat_id, message_id=int(screen_id), reply_markup=markup
            )
            await state.update_data(**{PAYLOAD_KEY: _payload(text, markup)})
            return
        except TelegramBadRequest as exc:
            if _is_not_modified(exc):
                return
    sent = await bot.send_message(chat_id, text, reply_markup=markup)
    await state.update_data(**{SCREEN_KEY: sent.message_id, PAYLOAD_KEY: _payload(text, markup)})


async def push_screen(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Retire the old screen, send a new one below the user's message."""
    markup = markup if markup is not None else _EMPTY_KB
    screen_id = (await state.get_data()).get(SCREEN_KEY)
    if screen_id:
        await _retire(bot, chat_id, int(screen_id))
    sent = await bot.send_message(chat_id, text, reply_markup=markup)
    await state.update_data(**{SCREEN_KEY: sent.message_id, PAYLOAD_KEY: _payload(text, markup)})


async def _retire(bot: Bot, chat_id: int, message_id: int) -> None:
    with contextlib.suppress(TelegramAPIError):
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=_EMPTY_KB,
        )


async def reset_flow(state: FSMContext, **draft: object) -> None:
    """FSM reset which keeps the screen (id + payload) across dialog resets."""
    data = await state.get_data()
    keep = {k: data[k] for k in (SCREEN_KEY, PAYLOAD_KEY) if k in data}
    await state.clear()
    keep.update(draft)
    await state.update_data(**keep)
