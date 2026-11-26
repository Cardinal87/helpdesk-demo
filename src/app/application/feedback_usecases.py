"""Feedback use case: exactly one rating+comment per closed ticket, author-only."""

from __future__ import annotations

from datetime import UTC, datetime

from app.application.context import Services
from app.application.session_usecases import get_actor_context
from app.domain import access
from app.domain import entities as E
from app.domain.errors import (
    FeedbackAlreadyExistsError,
    ValidationError,
)
from app.domain.ticket import Role


def _now() -> datetime:
    return datetime.now(UTC)


async def start_feedback(svc: Services, telegram_id: int, ticket_id: int) -> E.Ticket:
    """Gate before entering the feedback FSM: must be author + closed + no feedback yet."""
    ctx = await get_actor_context(svc, telegram_id)
    session = access.require_active_session(ctx.session, _now())
    # Feedback is a client-side action about *their* ticket.
    access.require_role(session, Role.CLIENT)
    ticket = await svc.tickets.get_with_messages(ticket_id, ctx.workspace.id)
    if ticket is None:
        from app.domain.errors import AccessDeniedError

        raise AccessDeniedError("ticket not found in your workspace")
    verdict = E.feedback_allowed(
        ticket,
        has_feedback=await svc.tickets.has_feedback(ticket_id),
        actor_telegram_id=telegram_id,
    )
    if verdict is E.FeedbackAllowed.NOT_CLOSED:
        from app.domain.errors import DomainError

        raise DomainError("feedback_not_closed")
    if verdict is E.FeedbackAllowed.ALREADY_GIVEN:
        raise FeedbackAlreadyExistsError("feedback exists")
    return ticket


async def save_feedback(
    svc: Services, telegram_id: int, ticket_id: int, rating: int, comment: str
) -> E.Feedback:
    if not 1 <= rating <= 5:
        raise ValidationError("rating must be 1..5")
    comment = comment.strip()
    if len(comment) > svc.settings.text_max_length:
        raise ValidationError("comment too long")

    ctx = await get_actor_context(svc, telegram_id)
    session = access.require_active_session(ctx.session, _now())
    access.require_role(session, Role.CLIENT)
    ticket = await svc.tickets.get_with_messages(ticket_id, ctx.workspace.id)
    if ticket is None:
        from app.domain.errors import AccessDeniedError

        raise AccessDeniedError("ticket not found in your workspace")

    verdict = E.feedback_allowed(
        ticket,
        has_feedback=await svc.tickets.has_feedback(ticket_id),
        actor_telegram_id=telegram_id,
    )
    if verdict is E.FeedbackAllowed.NOT_CLOSED:
        from app.domain.errors import DomainError

        raise DomainError("feedback_not_closed")
    if verdict is E.FeedbackAllowed.ALREADY_GIVEN:
        raise FeedbackAlreadyExistsError("feedback exists")

    fb = await svc.tickets.add_feedback(
        ticket_id=ticket_id,
        workspace_id=ctx.workspace.id,
        author_telegram_id=telegram_id,
        rating=rating,
        comment=comment,
    )
    await svc.workspaces.touch(ctx.workspace.id, svc.settings.workspace_ttl_seconds)
    await svc.audit.record(
        workspace_id=ctx.workspace.id,
        actor_telegram_id=telegram_id,
        event="feedback.saved",
        ticket_id=ticket_id,
        payload=f'{{"rating":{rating}}}',
    )
    return fb
