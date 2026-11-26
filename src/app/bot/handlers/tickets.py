"""Ticket flow handlers: creation FSM, lists with pagination, card, replies,
statuses — all rendered into the single chat screen."""

from __future__ import annotations

import html
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application import session_usecases as SU
from app.application import ticket_usecases as TU
from app.application.attachment_rules import (
    IncomingFile,
    human_size,
    sanitize_display_name,
    validate_attachment,
)
from app.bot import callbacks as cb
from app.bot.fsm import ConfirmStates, NoteStates, ReplyStates, TicketCreateStates
from app.bot.handlers.common import actor_id, lang, safe_callback, svc, t
from app.bot.i18n import STATUS_EMOJI
from app.bot.keyboards import inline as kb
from app.bot.screen import push_screen, render_screen, reset_flow
from app.domain.entities import Ticket
from app.domain.errors import AttachmentLimitError, DomainError
from app.domain.order import Priority
from app.domain.ticket import Role, TicketStatus

router = Router(name="tickets")

_CATEGORY_ALIASES = {
    "вопрос": "question",
    "ошибка": "bug",
    "поддержка": "support",
}


def _fmt_dt(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


# --------------------------------------------------------------------------- #
# Shared screen renderers
# --------------------------------------------------------------------------- #
async def _render_ticket_card(
    chat_id: int,
    state: FSMContext,
    data: dict,
    bot: Bot,
    ticket: Ticket,
    role: Role,
    notice: str | None = None,
    push: bool = False,
) -> None:
    """Single renderer for the ticket card; reused by every ticket flow."""
    parts: list[str] = []
    if notice:
        parts.append(notice)
    parts.append(_render_card(lang(data), ticket))
    render = push_screen if push else render_screen
    await render(
        bot,
        chat_id,
        state,
        "\n\n".join(parts),
        kb.ticket_card_kb(lang(data), ticket, role),
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
    ticket_id: int,
    notice: str | None = None,
    push: bool = False,
) -> None:
    from app.domain import access

    ctx = await SU.get_actor_context(svc(data), actor_id(data))
    access.require_role(access.require_active_session(ctx.session, datetime.now(UTC)), Role.SUPPORT)
    notes = await svc(data).tickets.list_notes(ctx.workspace.id, ticket_id)
    parts: list[str] = []
    if notice:
        parts.append(notice)
    parts.append(_render_notes_text(lang(data), notes))
    render = push_screen if push else render_screen
    await render(
        bot, chat_id, state, "\n\n".join(parts), kb.notes_kb(lang(data), "ticket", ticket_id)
    )


def _attach_prompt(data: dict) -> str:
    s = svc(data).settings
    return t(
        lang(data),
        "ticket_attach_prompt",
        max_files=s.max_files_per_ticket,
        max_size=human_size(s.max_file_size_bytes),
    )


async def _current_role(data: dict) -> Role | None:
    try:
        ctx = await SU.get_actor_context(svc(data), actor_id(data))
        return ctx.session.role if ctx.session else None
    except DomainError:
        return None


async def _ws_id(data: dict) -> int:
    ctx = await SU.get_actor_context(svc(data), actor_id(data))
    return ctx.workspace.id


def _extract_incoming_file(message: Message) -> IncomingFile | None:
    """Normalize Telegram document/photo/video metadata; never trust file names."""
    if message.document:
        d = message.document
        return IncomingFile(
            file_id=d.file_id,
            file_name=sanitize_display_name(d.file_name or "document"),
            mime_type=d.mime_type or "application/octet-stream",
            size_bytes=d.file_size or 0,
        )
    if message.video:
        v = message.video
        return IncomingFile(
            file_id=v.file_id,
            file_name=sanitize_display_name(v.file_name or "video.mp4"),
            mime_type=v.mime_type or "video/mp4",
            size_bytes=v.file_size or 0,
        )
    if message.photo:
        best = max(message.photo, key=lambda p: p.width * p.height)
        return IncomingFile(
            file_id=best.file_id,
            file_name="photo.jpg",
            mime_type="image/jpeg",
            size_bytes=best.file_size or 0,
        )
    return None


def _render_card(language: str, ticket: Ticket) -> str:
    status_line = (
        f"{STATUS_EMOJI.get(ticket.status.value, '')} "
        f"{t(language, f'status_{ticket.status.value}')}"
    )
    priority_text = t(language, f"priority_{ticket.priority.value}")
    category_text = t(language, f"category_{ticket.category}")
    order_label = (
        f"#{ticket.order_id}" if ticket.order_id is not None else t(language, "ticket_order_none")
    )
    parts = [
        t(
            language,
            "ticket_card",
            ticket_id=ticket.id,
            subject=html.escape(ticket.subject),
            category=category_text,
            status=status_line,
            priority=priority_text,
            order=order_label,
            created_at=_fmt_dt(ticket.created_at),
            description=html.escape(ticket.description[:500]),
        )
    ]
    timeline = ticket.messages[-3:]
    if len(timeline) > 1 or (timeline and timeline[0].text != ticket.description):
        parts.append(
            "\n---\n"
            + "\n".join(
                f"[{_fmt_dt(m.created_at)}] ({m.author_role.value}): {html.escape(m.text[:200])}"
                for m in timeline
            )
        )
    atts = [a for m in ticket.messages for a in m.attachments]
    if atts:
        items = ", ".join(
            f"{html.escape(a.file_name)} ({human_size(a.size_bytes)})" for a in atts[:10]
        )
        parts.append(t(language, "attachments_list", items=items))
    else:
        parts.append(t(language, "no_attachments"))
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Menu entries -> lists
# --------------------------------------------------------------------------- #
@router.callback_query(cb.MenuCB.filter(F.action == "new_ticket"))
async def cb_new_ticket(callback: CallbackQuery, state: FSMContext, data: dict, bot: Bot) -> None:
    await reset_flow(state, pending_files=[])
    await state.set_state(TicketCreateStates.category)
    await safe_callback(callback)
    if callback.message:
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            t(lang(data), "ticket_category"),
            kb.category_kb(lang(data)),
        )


@router.callback_query(cb.TicketForOrderCB.filter())
async def ticket_for_order(
    callback: CallbackQuery,
    callback_data: cb.TicketForOrderCB,
    state: FSMContext,
    data: dict,
    bot: Bot,
) -> None:
    await reset_flow(state, pending_files=[], order_id=callback_data.order_id)
    await state.set_state(TicketCreateStates.category)
    await safe_callback(callback)
    if callback.message:
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            t(lang(data), "ticket_category"),
            kb.category_kb(lang(data)),
        )


@router.callback_query(cb.NotesViewCB.filter(F.target_type == "ticket"))
async def view_ticket_notes(
    callback: CallbackQuery, callback_data: cb.NotesViewCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    await safe_callback(callback)
    if callback.message:
        await _render_notes_screen(
            callback.message.chat.id, state, data, bot, callback_data.target_id
        )


@router.callback_query(TicketCreateStates.category, cb.CategoryCB.filter())
async def create_category_button(
    callback: CallbackQuery,
    callback_data: cb.CategoryCB,
    state: FSMContext,
    data: dict,
    bot: Bot,
) -> None:
    if callback_data.code not in {"question", "bug", "support"}:
        await safe_callback(callback)
        return
    await state.update_data(category=callback_data.code)
    await state.set_state(TicketCreateStates.subject)
    await safe_callback(callback)
    if callback.message:
        # step without buttons: category keyboard is removed
        await render_screen(
            bot, callback.message.chat.id, state, t(lang(data), "ticket_subject_prompt")
        )


@router.message(TicketCreateStates.category, F.text & ~F.text.startswith("/"))
async def create_category(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    raw = (message.text or "").strip().lower()
    category = _CATEGORY_ALIASES.get(raw, raw)
    if category not in {"question", "bug", "support"}:
        # invalid input: same screen, same keyboard, state untouched
        await push_screen(
            bot,
            message.chat.id,
            state,
            t(lang(data), "ticket_category"),
            kb.category_kb(lang(data)),
        )
        return
    await state.update_data(category=category)
    await state.set_state(TicketCreateStates.subject)
    await push_screen(bot, message.chat.id, state, t(lang(data), "ticket_subject_prompt"))


@router.callback_query(cb.MenuCB.filter(F.action.in_({"my_tickets", "queue"})))
async def cb_open_list(
    callback: CallbackQuery, callback_data: cb.MenuCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    await safe_callback(callback)
    await _render_list(callback, state, data, bot, page=0)


@router.callback_query(cb.TicketPageCB.filter())
async def cb_list_page(
    callback: CallbackQuery, callback_data: cb.TicketPageCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    await safe_callback(callback)
    await _render_list(callback, state, data, bot, page=callback_data.page)


async def _render_list(
    callback: CallbackQuery, state: FSMContext, data: dict, bot: Bot, page: int
) -> None:
    language = lang(data)
    tickets, total = await TU.list_tickets(svc(data), actor_id(data), page)

    if not tickets and page == 0:
        if callback.message:
            await render_screen(
                bot,
                callback.message.chat.id,
                state,
                t(language, "tickets_empty"),
                kb.back_only_kb(language),
            )
        return

    title_key = "tickets_title_support"
    try:
        ctx = await SU.get_actor_context(svc(data), actor_id(data))
        if ctx.session and ctx.session.role is Role.CLIENT:
            title_key = "tickets_title_client"
    except DomainError:
        pass

    if callback.message:
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            t(language, title_key),
            kb.tickets_list_kb(language, tickets, page, total),
        )


# --------------------------------------------------------------------------- #
# Ticket creation FSM (subject -> description -> attachments)
# --------------------------------------------------------------------------- #
@router.message(TicketCreateStates.subject, F.text & ~F.text.startswith("/"))
async def create_subject(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    subject = (message.text or "").strip()
    if not subject or len(subject) > 200:
        await push_screen(
            bot,
            message.chat.id,
            state,
            t(lang(data), "err_validation", detail=t(lang(data), "ticket_subject_prompt")),
        )
        return
    await state.update_data(subject=subject)
    await state.set_state(TicketCreateStates.description)
    await push_screen(bot, message.chat.id, state, t(lang(data), "ticket_description_prompt"))


@router.message(TicketCreateStates.description, F.text & ~F.text.startswith("/"))
async def create_description(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    description = (message.text or "").strip()
    if not description:
        await push_screen(bot, message.chat.id, state, t(lang(data), "ticket_description_prompt"))
        return
    await state.update_data(description=description)
    await state.set_state(TicketCreateStates.attachments)
    await push_screen(
        bot,
        message.chat.id,
        state,
        _attach_prompt(data),
        kb.attach_done_kb(lang(data)),
    )


@router.message(TicketCreateStates.attachments, F.document | F.photo | F.video)
async def create_attachment(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    incoming = _extract_incoming_file(message)
    if incoming is None:
        return
    s = svc(data)
    draft = await state.get_data()
    files: list[dict] = list(draft.get("pending_files") or [])
    try:
        workspace_id = await _ws_id(data)
        workspace_file_count, workspace_total_bytes = await s.tickets.workspace_attachment_stats(
            workspace_id
        )
        validate_attachment(
            incoming,
            settings=s.settings,
            ticket_file_count=len(files),
            workspace_file_count=workspace_file_count + len(files),
            workspace_total_bytes=workspace_total_bytes
            + sum(int(file["size_bytes"]) for file in files),
        )
    except AttachmentLimitError as exc:
        # limit hit: same screen, same Done button, error shown as notice
        await push_screen(
            bot,
            message.chat.id,
            state,
            "\n\n".join(
                [
                    t(
                        lang(data),
                        "err_attachment_limit",
                        detail=str(exc),
                        types=",".join(sorted(s.settings.mime_allowlist)),
                    ),
                    _attach_prompt(data),
                ]
            ),
            kb.attach_done_kb(lang(data)),
        )
        return

    files.append(asdict(incoming))
    await state.update_data(pending_files=files)
    await push_screen(
        bot,
        message.chat.id,
        state,
        "\n\n".join(
            [
                t(
                    lang(data),
                    "attachment_saved",
                    file_name=incoming.file_name,
                    size=human_size(incoming.size_bytes),
                ),
                _attach_prompt(data),
            ]
        ),
        kb.attach_done_kb(lang(data)),
    )


@router.callback_query(TicketCreateStates.attachments, cb.AttachDoneCB.filter())
async def create_finish(callback: CallbackQuery, state: FSMContext, data: dict, bot: Bot) -> None:
    draft = await state.get_data()
    await safe_callback(callback)
    ticket = await TU.create_ticket(
        svc(data),
        actor_id(data),
        draft["subject"],
        draft["description"],
        category=draft.get("category", "general"),
        order_id=draft.get("order_id"),
    )
    pending_files: list[dict] = draft.get("pending_files") or []
    if pending_files:
        now = datetime.now(UTC)
        expires = now + timedelta(seconds=svc(data).settings.workspace_ttl_seconds)
        att_dicts = [
            {
                "file_id": f["file_id"],
                "file_name": f["file_name"],
                "mime_type": f["mime_type"],
                "size_bytes": f["size_bytes"],
                "expires_at": expires,
            }
            for f in pending_files
        ]
        # Atomic: first message of the ticket gets the attachments attached.
        await TU.add_reply(svc(data), actor_id(data), ticket.id, "", att_dicts)
        ticket = await TU.get_ticket_card(svc(data), actor_id(data), ticket.id)

    await reset_flow(state)
    if callback.message:
        await _render_ticket_card(
            callback.message.chat.id,
            state,
            data,
            bot,
            ticket,
            Role.CLIENT,
            notice=t(lang(data), "ticket_created", ticket_id=ticket.id, subject=ticket.subject),
        )


@router.callback_query(TicketCreateStates.attachments, F.data == "adone")
async def create_finish_fallback(
    callback: CallbackQuery, state: FSMContext, data: dict, bot: Bot
) -> None:
    """Accept the field-less callback even on aiogram versions that do not parse it."""
    await create_finish(callback, state, data, bot)


# --------------------------------------------------------------------------- #
# Ticket card
# --------------------------------------------------------------------------- #
@router.callback_query(cb.TicketOpenCB.filter())
async def cb_open_ticket(
    callback: CallbackQuery,
    callback_data: cb.TicketOpenCB,
    state: FSMContext,
    data: dict,
    bot: Bot,
) -> None:
    role = await _current_role(data) or Role.CLIENT
    ticket = await TU.get_ticket_card(svc(data), actor_id(data), callback_data.ticket_id)
    await safe_callback(callback)
    if callback.message:
        await _render_ticket_card(callback.message.chat.id, state, data, bot, ticket, role)


# --------------------------------------------------------------------------- #
# Reply FSM
# --------------------------------------------------------------------------- #
@router.callback_query(cb.ReplyCB.filter())
async def cb_reply_start(
    callback: CallbackQuery,
    callback_data: cb.ReplyCB,
    state: FSMContext,
    data: dict,
    bot: Bot,
) -> None:
    # Gate early so the prompt only appears when the action is actually allowed.
    ticket = await TU.get_ticket_card(svc(data), actor_id(data), callback_data.ticket_id)
    if not ticket.is_editable:
        await callback.answer(t(lang(data), "err_access"), show_alert=True)
        return
    await reset_flow(state, reply_ticket_id=ticket.id)
    await state.set_state(ReplyStates.waiting_message)
    await safe_callback(callback)
    if callback.message:
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            t(lang(data), "reply_prompt", ticket_id=ticket.id),
        )


@router.message(ReplyStates.waiting_message, F.text & ~F.text.startswith("/"))
async def reply_text(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    draft = await state.get_data()
    ticket_id = draft["reply_ticket_id"]
    text = (message.text or "").strip()
    if not text:
        await push_screen(
            bot, message.chat.id, state, t(lang(data), "reply_prompt", ticket_id=ticket_id)
        )
        return
    await TU.add_reply(svc(data), actor_id(data), ticket_id, text, [])
    await reset_flow(state)
    role = await _current_role(data) or Role.CLIENT
    ticket = await TU.get_ticket_card(svc(data), actor_id(data), ticket_id)
    await _render_ticket_card(
        message.chat.id,
        state,
        data,
        bot,
        ticket,
        role,
        notice=t(lang(data), "reply_sent"),
        push=True,
    )


@router.message(ReplyStates.waiting_message, F.document | F.photo | F.video)
async def reply_file(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    incoming = _extract_incoming_file(message)
    if incoming is None:
        return
    draft = await state.get_data()
    ticket_id = draft["reply_ticket_id"]
    s = svc(data)
    now = datetime.now(UTC)
    try:
        ws_count, ws_bytes = await s.tickets.workspace_attachment_stats(await _ws_id(data))
        validate_attachment(
            incoming,
            settings=s.settings,
            ticket_file_count=await s.tickets.ticket_attachment_count(ticket_id),
            workspace_file_count=ws_count,
            workspace_total_bytes=ws_bytes,
        )
    except AttachmentLimitError as exc:
        await push_screen(
            bot,
            message.chat.id,
            state,
            "\n\n".join(
                [
                    t(
                        lang(data),
                        "err_attachment_limit",
                        detail=str(exc),
                        types=",".join(sorted(s.settings.mime_allowlist)),
                    ),
                    t(lang(data), "reply_prompt", ticket_id=ticket_id),
                ]
            ),
        )
        return

    await TU.add_reply(
        s,
        actor_id(data),
        ticket_id,
        message.caption or "(attachment)",
        [
            {
                "file_id": incoming.file_id,
                "file_name": incoming.file_name,
                "mime_type": incoming.mime_type,
                "size_bytes": incoming.size_bytes,
                "expires_at": now + timedelta(seconds=s.settings.workspace_ttl_seconds),
            }
        ],
    )
    await reset_flow(state)
    role = await _current_role(data) or Role.CLIENT
    ticket = await TU.get_ticket_card(svc(data), actor_id(data), ticket_id)
    await _render_ticket_card(
        message.chat.id,
        state,
        data,
        bot,
        ticket,
        role,
        notice=t(
            lang(data),
            "attachment_saved",
            file_name=incoming.file_name,
            size=human_size(incoming.size_bytes),
        ),
        push=True,
    )


# --------------------------------------------------------------------------- #
# Status transitions + close confirmation
# --------------------------------------------------------------------------- #
@router.callback_query(cb.StatusCB.filter())
async def cb_status_change(
    callback: CallbackQuery, callback_data: cb.StatusCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    try:
        target = TicketStatus(callback_data.target)
    except ValueError:
        await safe_callback(callback)
        return
    ticket = await TU.change_status(svc(data), actor_id(data), callback_data.ticket_id, target)
    role = await _current_role(data) or Role.SUPPORT
    await safe_callback(callback)
    if callback.message:
        await _render_ticket_card(
            callback.message.chat.id,
            state,
            data,
            bot,
            ticket,
            role,
            notice=t(
                lang(data),
                "status_changed",
                ticket_id=ticket.id,
                status=f"{STATUS_EMOJI.get(target.value, '')} {t(lang(data), f'status_{target.value}')}",
            ),
        )


@router.callback_query(cb.CloseConfirmCB.filter(F.approve == "ask"))
async def cb_close_ask(
    callback: CallbackQuery,
    callback_data: cb.CloseConfirmCB,
    state: FSMContext,
    data: dict,
    bot: Bot,
) -> None:
    ticket_id = callback_data.ticket_id
    await TU.get_ticket_card(svc(data), actor_id(data), ticket_id)
    await reset_flow(state, close_ticket_id=ticket_id)
    await state.set_state(ConfirmStates.pending)
    await safe_callback(callback)
    if callback.message:
        await render_screen(
            bot,
            callback.message.chat.id,
            state,
            t(lang(data), "close_confirm", ticket_id=ticket_id),
            kb.close_confirm_kb(lang(data), ticket_id),
        )


@router.callback_query(cb.CloseConfirmCB.filter(F.approve.in_({"yes", "no"})))
async def cb_close_resolved(
    callback: CallbackQuery,
    callback_data: cb.CloseConfirmCB,
    state: FSMContext,
    data: dict,
    bot: Bot,
) -> None:
    ticket_id = callback_data.ticket_id
    await safe_callback(callback)
    if not callback.message:
        return

    if callback_data.approve == "no":
        await reset_flow(state)
        ticket = await TU.get_ticket_card(svc(data), actor_id(data), ticket_id)
        role = await _current_role(data) or Role.SUPPORT
        await _render_ticket_card(callback.message.chat.id, state, data, bot, ticket, role)
        return

    ticket = await TU.change_status(svc(data), actor_id(data), ticket_id, TicketStatus.CLOSED)
    await reset_flow(state)
    await _render_ticket_card(
        callback.message.chat.id,
        state,
        data,
        bot,
        ticket,
        Role.SUPPORT,
        notice=t(lang(data), "ticket_closed", ticket_id=ticket.id),
    )


@router.callback_query(cb.PriorityCB.filter(F.target_type == "ticket"))
async def ticket_priority(
    callback: CallbackQuery, callback_data: cb.PriorityCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    ticket = await TU.change_priority(
        svc(data), actor_id(data), callback_data.target_id, Priority(callback_data.priority)
    )
    await safe_callback(callback)
    if callback.message:
        await _render_ticket_card(callback.message.chat.id, state, data, bot, ticket, Role.SUPPORT)


# --------------------------------------------------------------------------- #
# Internal notes for tickets
# --------------------------------------------------------------------------- #
@router.callback_query(cb.NoteCB.filter(F.target_type == "ticket"))
async def ticket_note(
    callback: CallbackQuery, callback_data: cb.NoteCB, state: FSMContext, data: dict, bot: Bot
) -> None:
    await state.set_state(NoteStates.body)
    await state.update_data(note_ticket_id=callback_data.target_id)
    await safe_callback(callback)
    if callback.message:
        await render_screen(bot, callback.message.chat.id, state, t(lang(data), "note_prompt"))


async def _note_for_ticket(message: Message, state: FSMContext) -> bool:
    """Route guard: this router handles only ticket notes."""
    return "note_ticket_id" in (await state.get_data())


@router.message(NoteStates.body, _note_for_ticket, F.text & ~F.text.startswith("/"))
async def save_ticket_note(message: Message, state: FSMContext, data: dict, bot: Bot) -> None:
    draft = await state.get_data()
    text = (message.text or "").strip()
    if not text:
        # invalid input: same screen, state untouched
        await push_screen(bot, message.chat.id, state, t(lang(data), "note_prompt"))
        return

    from app.domain import access

    ctx = await SU.get_actor_context(svc(data), actor_id(data))
    access.require_role(access.require_active_session(ctx.session, datetime.now(UTC)), Role.SUPPORT)

    ticket_id = int(draft["note_ticket_id"])
    await svc(data).tickets.add_note(ctx.workspace.id, actor_id(data), ticket_id, text)
    await reset_flow(state)
    await _render_notes_screen(
        message.chat.id, state, data, bot, ticket_id, notice=t(lang(data), "note_saved"), push=True
    )
