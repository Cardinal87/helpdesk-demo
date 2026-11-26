"""Feedback FSM handlers: rating keyboard -> optional comment -> save once.

All steps render into the single chat screen.
"""

from __future__ import annotations

import re

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application import feedback_usecases as FU
from app.bot import callbacks as cb
from app.bot.fsm import FeedbackStates
from app.bot.handlers.common import actor_id, lang, safe_callback, svc, t
from app.bot.keyboards import inline as kb
from app.bot.menu import render_menu
from app.bot.screen import push_screen, render_screen, reset_flow

router = Router(name="feedback")


@router.callback_query(cb.FeedbackStartCB.filter())
async def cb_feedback_start(
    callback: CallbackQuery,
    callback_data: cb.FeedbackStartCB,
    state: FSMContext,
    data: dict,
    bot: Bot,
) -> None:
    # Gate: author + closed + no feedback yet (raises friendly DomainError otherwise).
    ticket = await FU.start_feedback(svc(data), actor_id(data), callback_data.ticket_id)
    await reset_flow(state, feedback_ticket_id=ticket.id)
    await state.set_state(FeedbackStates.waiting_rating)
    await safe_callback(callback)
    if callback.message:
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            t(lang(data), "feedback_prompt_rating"),
            kb.rating_kb(lang(data), ticket.id),
        )


@router.callback_query(FeedbackStates.waiting_rating, cb.FeedbackRatingCB.filter())
async def cb_feedback_rating(
    callback: CallbackQuery,
    callback_data: cb.FeedbackRatingCB,
    state: FSMContext,
    data: dict,
    bot: Bot,
) -> None:
    draft = await state.get_data()
    if callback_data.ticket_id != draft.get("feedback_ticket_id"):
        await safe_callback(callback)
        return
    await state.update_data(rating=callback_data.rating)
    await state.set_state(FeedbackStates.waiting_comment)
    await safe_callback(callback)
    if callback.message:
        # step without buttons: rating keyboard is removed
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            t(lang(data), "feedback_prompt_comment"),
        )


@router.message(FeedbackStates.waiting_comment, F.text & ~F.text.startswith("/"))
async def fb_comment(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    text = (message.text or "").strip()
    if not text:
        # invalid input: same screen, same state
        await push_screen(bot, message.chat.id, state, t(lang(data), "feedback_prompt_comment"))
        return
    await _finish(message, state, data, bot, comment=text)


@router.message(FeedbackStates.waiting_comment, F.text.regexp(r"^/skip\b", flags=re.IGNORECASE))
async def fb_skip(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    await _finish(message, state, data, bot, comment="")


async def _finish(message: Message, state: FSMContext, data: dict, bot: Bot, comment: str) -> None:
    draft = await state.get_data()
    ticket_id = draft["feedback_ticket_id"]
    rating = int(draft.get("rating") or 0)

    # DomainError (double feedback, not author, not closed) propagates to the
    # error middleware; state is kept so the user can retry or /cancel.
    await FU.save_feedback(svc(data), actor_id(data), ticket_id, rating, comment)

    await reset_flow(state)
    key = "feedback_saved" if comment else "feedback_skipped"
    await render_menu(message.chat.id, state, data, bot, notice=t(lang(data), key), push=True)
