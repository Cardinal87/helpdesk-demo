"""Ticket use cases: creation, listing, card, replies, status transitions.

Transaction boundary: each public function is called inside an outer transaction
managed by the DB session middleware (session.begin()). Handlers must not call
Telegram API side effects while a long DB transaction is open — file metadata
is validated from the already-received message object before entering here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.application.context import Services
from app.application.session_usecases import get_actor_context
from app.domain import access
from app.domain.entities import Ticket
from app.domain.errors import AccessDeniedError, ValidationError
from app.domain.order import Priority
from app.domain.ticket import Role, TicketStatus, is_transition_allowed


def _now() -> datetime:
    return datetime.now(UTC)


async def create_ticket(
    svc: Services,
    telegram_id: int,
    subject: str,
    description: str,
    *,
    category: str = "general",
    order_id: int | None = None,
) -> Ticket:
    subject = subject.strip()
    description = description.strip()
    if not subject or len(subject) > 200:
        raise ValidationError("subject must be 1..200 chars")
    if not description:
        raise ValidationError("description required")
    if len(description) > svc.settings.text_max_length:
        raise ValidationError("description too long")

    ctx = await get_actor_context(svc, telegram_id)
    session = access.require_active_session(ctx.session, _now())
    access.require_role(session, Role.CLIENT)

    if order_id is not None and await svc.orders.get(order_id, ctx.workspace.id) is None:
        raise AccessDeniedError("order not found in your workspace")

    ticket = await svc.tickets.create(
        workspace_id=ctx.workspace.id,
        author_telegram_id=telegram_id,
        subject=subject,
        description=description,
        category=category,
        order_id=order_id,
    )
    # Description becomes the first client message for a uniform timeline.
    await svc.tickets.add_message(
        ticket_id=ticket.id,
        workspace_id=ctx.workspace.id,
        author_telegram_id=telegram_id,
        author_role=Role.CLIENT,
        text=description,
        attachments=[],
    )
    await svc.workspaces.touch(ctx.workspace.id, svc.settings.workspace_ttl_seconds)
    await svc.audit.record(
        workspace_id=ctx.workspace.id,
        actor_telegram_id=telegram_id,
        event="ticket.created",
        ticket_id=ticket.id,
    )
    full = await svc.tickets.get_with_messages(ticket.id, ctx.workspace.id)
    assert full is not None
    return full


async def list_tickets(svc: Services, telegram_id: int, page: int) -> tuple[list[Ticket], int]:
    ctx = await get_actor_context(svc, telegram_id)
    session = access.require_active_session(ctx.session, _now())
    if page < 0:
        raise ValidationError("bad page")
    author_only = telegram_id if session.role is Role.CLIENT else None
    tickets, total = await svc.tickets.list_page(
        workspace_id=ctx.workspace.id, page=page, author_only=author_only
    )
    await svc.workspaces.touch(ctx.workspace.id, svc.settings.workspace_ttl_seconds)
    return tickets, total


async def get_ticket_card(svc: Services, telegram_id: int, ticket_id: int) -> Ticket:
    """Fetch + authorize. Foreign/other-workspace ids look identical to 'not found'."""
    ctx = await get_actor_context(svc, telegram_id)
    access.require_active_session(ctx.session, _now())
    ticket = await svc.tickets.get_with_messages(ticket_id, ctx.workspace.id)
    if ticket is None:
        raise AccessDeniedError("ticket not found in your workspace")
    await svc.workspaces.touch(ctx.workspace.id, svc.settings.workspace_ttl_seconds)
    return ticket


async def add_reply(
    svc: Services,
    telegram_id: int,
    ticket_id: int,
    text: str,
    attachments: list[dict],
) -> Ticket:
    text = text.strip()
    if not text and not attachments:
        raise ValidationError("empty reply")
    if len(text) > svc.settings.text_max_length:
        raise ValidationError("reply too long")

    ctx = await get_actor_context(svc, telegram_id)
    session = access.require_active_session(ctx.session, _now())
    ticket = await svc.tickets.get_with_messages(ticket_id, ctx.workspace.id)
    if ticket is None:
        raise AccessDeniedError("ticket not found in your workspace")
    if not ticket.is_editable:
        raise AccessDeniedError("closed ticket is read-only")

    await svc.tickets.add_message(
        ticket_id=ticket.id,
        workspace_id=ctx.workspace.id,
        author_telegram_id=telegram_id,
        author_role=session.role,
        text=text or "(attachment)",
        attachments=attachments,
    )
    # Client answering a waiting_client ticket moves it back into progress.
    new_status: TicketStatus | None = None
    if (
        session.role is Role.CLIENT
        and ticket.status is TicketStatus.WAITING_CLIENT
        or session.role is Role.SUPPORT
        and ticket.status
        in (
            TicketStatus.NEW,
            TicketStatus.WAITING_CLIENT,
        )
    ):
        new_status = TicketStatus.IN_PROGRESS
    if new_status is not None and is_transition_allowed(ticket.status, new_status):
        await svc.tickets.set_status(
            ticket.id,
            ctx.workspace.id,
            new_status,
            assignee=telegram_id if new_status is TicketStatus.IN_PROGRESS else None,
        )
    await svc.workspaces.touch(ctx.workspace.id, svc.settings.workspace_ttl_seconds)
    await svc.audit.record(
        workspace_id=ctx.workspace.id,
        actor_telegram_id=telegram_id,
        event="ticket.replied",
        ticket_id=ticket.id,
    )
    full = await svc.tickets.get_with_messages(ticket_id, ctx.workspace.id)
    assert full is not None
    return full


async def change_status(
    svc: Services, telegram_id: int, ticket_id: int, target: TicketStatus
) -> Ticket:
    ctx = await get_actor_context(svc, telegram_id)
    session = access.require_active_session(ctx.session, _now())
    ticket = await svc.tickets.get_with_messages(ticket_id, ctx.workspace.id)
    if ticket is None:
        raise AccessDeniedError("ticket not found in your workspace")

    if target is TicketStatus.CLOSED:
        # Closing is support-side; only allowed from resolved.
        access.assert_support_transition(ticket, target, session)
    else:
        access.assert_support_transition(ticket, target, session)

    await svc.tickets.set_status(
        ticket.id,
        ctx.workspace.id,
        target,
        assignee=telegram_id if target is TicketStatus.IN_PROGRESS else None,
        closed_at=_now() if target is TicketStatus.CLOSED else None,
    )
    await svc.workspaces.touch(ctx.workspace.id, svc.settings.workspace_ttl_seconds)
    await svc.audit.record(
        workspace_id=ctx.workspace.id,
        actor_telegram_id=telegram_id,
        event=f"ticket.status.{target.value}",
        ticket_id=ticket.id,
        payload=f'{{"from":"{ticket.status.value}"}}',
    )
    full = await svc.tickets.get_with_messages(ticket_id, ctx.workspace.id)
    assert full is not None
    return full


async def change_priority(
    svc: Services, telegram_id: int, ticket_id: int, priority: Priority
) -> Ticket:
    ctx = await get_actor_context(svc, telegram_id)
    access.require_role(access.require_active_session(ctx.session, _now()), Role.SUPPORT)
    ticket = await svc.tickets.get_with_messages(ticket_id, ctx.workspace.id)
    if ticket is None:
        raise AccessDeniedError("ticket not found")
    await svc.tickets.set_priority(ticket_id, ctx.workspace.id, priority)
    return (await svc.tickets.get_with_messages(ticket_id, ctx.workspace.id)) or ticket
