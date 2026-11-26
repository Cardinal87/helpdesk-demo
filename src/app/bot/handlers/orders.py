"""Catalogue, order creation and workspace order list (single-screen UI)."""

import html
from datetime import UTC, datetime

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application import order_usecases as OU
from app.application import session_usecases as SU
from app.bot import callbacks as cb
from app.bot.fsm import NoteStates, OrderCreateStates
from app.bot.handlers.common import actor_id, lang, safe_callback, svc, t
from app.bot.keyboards import inline as kb
from app.bot.menu import render_menu
from app.bot.screen import push_screen, render_screen, reset_flow
from app.domain.order import OrderStatus, Priority
from app.domain.ticket import Role

router = Router(name="orders")


def _fmt_dt(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


# --------------------------------------------------------------------------- #
# Catalogue & order creation FSM
# --------------------------------------------------------------------------- #
@router.callback_query(cb.MenuCB.filter(F.action == "catalog"))
async def catalog(callback: CallbackQuery, state: FSMContext, data: dict, bot: Bot) -> None:
    services = await OU.list_services(svc(data))
    await safe_callback(callback)
    if callback.message:
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            t(lang(data), "catalog"),
            kb.services_kb(lang(data), services),
        )


@router.callback_query(cb.ServiceCB.filter())
async def select_service(
    callback: CallbackQuery,
    callback_data: cb.ServiceCB,
    state: FSMContext,
    data: dict,
    bot: Bot,
) -> None:
    await state.set_state(OrderCreateStates.description)
    await state.update_data(service_id=callback_data.service_id)
    await safe_callback(callback)
    if callback.message:
        await render_screen(
            bot, callback.message.chat.id, state, t(lang(data), "order_description")
        )


@router.message(OrderCreateStates.description, F.text & ~F.text.startswith("/"))
async def create_order(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    description = (message.text or "").strip()
    if not description:
        await push_screen(bot, message.chat.id, state, t(lang(data), "order_description"))
        return

    draft = await state.get_data()
    service_id = int(draft["service_id"])
    await reset_flow(state)

    order = await OU.create_order(svc(data), actor_id(data), service_id, description)
    await render_menu(
        message.chat.id,
        state,
        data,
        bot,
        notice=t(lang(data), "order_created", order_id=order.id),
        push=True,
    )


def _render_notes_text(language: str, notes: list) -> str:
    if not notes:
        return t(language, "notes_empty")
    lines = [t(language, "notes_title")]
    for n in notes[:10]:
        lines.append(
            t(
                language,
                "note_row",
                created_at=_fmt_dt(n.created_at),
                body=html.escape(n.body[:300]),
            )
        )
    return "\n".join(lines)


async def _render_notes_screen(
    chat_id: int,
    state: FSMContext,
    data: dict,
    bot: Bot,
    order_id: int,
    notice: str | None = None,
    push: bool = False,
) -> None:
    from app.domain import access

    ctx = await SU.get_actor_context(svc(data), actor_id(data))
    access.require_role(access.require_active_session(ctx.session, datetime.now(UTC)), Role.SUPPORT)
    notes = await svc(data).orders.list_notes(ctx.workspace.id, order_id)
    parts: list[str] = []
    if notice:
        parts.append(notice)
    parts.append(_render_notes_text(lang(data), notes))
    render = push_screen if push else render_screen
    await render(
        bot, chat_id, state, "\n\n".join(parts), kb.notes_kb(lang(data), "order", order_id)
    )


# --------------------------------------------------------------------------- #
# Order list & card
# --------------------------------------------------------------------------- #
@router.callback_query(cb.MenuCB.filter(F.action.in_({"my_orders", "orders"})))
async def list_orders(callback: CallbackQuery, state: FSMContext, data: dict, bot: Bot) -> None:
    orders = await OU.list_orders(svc(data), actor_id(data))
    await safe_callback(callback)
    if callback.message:
        text = t(lang(data), "orders_empty") if not orders else t(lang(data), "btn_orders")
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            text,
            kb.orders_kb(lang(data), orders),
        )


async def _render_order_card(
    chat_id: int,
    state: FSMContext,
    data: dict,
    bot: Bot,
    order_id: int,
    notice: str | None = None,
    push: bool = False,
) -> None:
    """Single renderer for the order card; reused by status/priority/note flows."""
    ctx = await SU.get_actor_context(svc(data), actor_id(data))
    order = await svc(data).orders.get(order_id, ctx.workspace.id)
    if order is None:
        await render_screen(
            bot, chat_id, state, t(lang(data), "err_access"), kb.back_only_kb(lang(data))
        )
        return

    parts: list[str] = []
    if notice:
        parts.append(notice)
    parts.append(
        t(
            lang(data),
            "order_card",
            id=order.id,
            service=order.service_title,
            status=t(lang(data), f"order_{order.status.value}"),
            priority=t(lang(data), f"priority_{order.priority.value}"),
            description=html.escape(order.description),
        )
    )
    render = push_screen if push else render_screen
    await render(
        bot,
        chat_id,
        state,
        "\n\n".join(parts),
        kb.order_card_kb(lang(data), order, ctx.session.role if ctx.session else Role.CLIENT),
    )


@router.callback_query(cb.OrderCB.filter())
async def open_order(
    callback: CallbackQuery, callback_data: cb.OrderCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    await safe_callback(callback)
    if callback.message:
        await _render_order_card(callback.message.chat.id, state, data, bot, callback_data.order_id)


@router.callback_query(cb.NotesViewCB.filter(F.target_type == "order"))
async def view_order_notes(
    callback: CallbackQuery, callback_data: cb.NotesViewCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    await safe_callback(callback)
    if callback.message:
        await _render_notes_screen(
            callback.message.chat.id, state, data, bot, callback_data.target_id
        )


@router.callback_query(cb.OrderStatusCB.filter())
async def update_status(
    callback: CallbackQuery,
    callback_data: cb.OrderStatusCB,
    state: FSMContext,
    data: dict,
    bot: Bot,
) -> None:
    await OU.change_order_status(
        svc(data), actor_id(data), callback_data.order_id, OrderStatus(callback_data.target)
    )
    await safe_callback(callback)
    if callback.message:
        await _render_order_card(callback.message.chat.id, state, data, bot, callback_data.order_id)


@router.callback_query(cb.PriorityCB.filter(F.target_type == "order"))
async def update_priority(
    callback: CallbackQuery, callback_data: cb.PriorityCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    await OU.change_order_priority(
        svc(data), actor_id(data), callback_data.target_id, Priority(callback_data.priority)
    )
    await safe_callback(callback)
    if callback.message:
        await _render_order_card(
            callback.message.chat.id, state, data, bot, callback_data.target_id
        )


# --------------------------------------------------------------------------- #
# Internal notes for orders
# --------------------------------------------------------------------------- #
@router.callback_query(cb.NoteCB.filter(F.target_type == "order"))
async def start_note(
    callback: CallbackQuery, callback_data: cb.NoteCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    await state.set_state(NoteStates.body)
    await state.update_data(note_order_id=callback_data.target_id)
    await safe_callback(callback)
    if callback.message:
        await render_screen(bot, callback.message.chat.id, state, t(lang(data), "note_prompt"))


async def _note_for_order(message: Message, state: FSMContext) -> bool:
    """Route guard: this router handles only order notes."""
    return "note_order_id" in (await state.get_data())


@router.message(NoteStates.body, _note_for_order, F.text & ~F.text.startswith("/"))
async def save_note(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    draft = await state.get_data()
    text = (message.text or "").strip()
    if not text:
        await push_screen(bot, message.chat.id, state, t(lang(data), "note_prompt"))
        return

    order_id = int(draft["note_order_id"])
    await reset_flow(state)
    await OU.add_order_note(svc(data), actor_id(data), order_id, text)
    await _render_notes_screen(
        message.chat.id, state, data, bot, order_id, notice=t(lang(data), "note_saved"), push=True
    )
