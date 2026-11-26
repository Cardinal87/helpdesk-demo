"""Catch-all: any unhandled user input replays the current screen."""

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, Message

from app.bot.menu import render_menu
from app.bot.screen import PAYLOAD_KEY, push_screen

router = Router(name="fallback")


@router.message()
async def on_unhandled(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    payload = (await state.get_data()).get(PAYLOAD_KEY)
    if payload:
        await push_screen(
            bot,
            message.chat.id,
            state,
            payload["text"],
            InlineKeyboardMarkup.model_validate(payload["markup"]),
        )
    else:
        await render_menu(message.chat.id, state, data, bot, push=True)
