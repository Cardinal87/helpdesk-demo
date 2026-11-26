from datetime import UTC, datetime, timedelta

import pytest

from app.application.attachment_rules import IncomingFile, validate_attachment
from app.config import Settings
from app.domain.access import assert_support_transition
from app.domain.entities import (
    FeedbackAllowed,
    FeedbackAuthorMismatch,
    RoleSession,
    Ticket,
    Workspace,
    feedback_allowed,
)
from app.domain.errors import AttachmentLimitError, InvalidTransitionError
from app.domain.ticket import Role, TicketStatus


def test_workspace_touch_extends_expiry() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    workspace = Workspace(1, 10, now, now, now + timedelta(hours=1))

    workspace.touch(now + timedelta(minutes=5), ttl_seconds=3600)

    assert workspace.last_activity_at == now + timedelta(minutes=5)
    assert workspace.expires_at == now + timedelta(minutes=65)


def test_support_cannot_skip_ticket_statuses() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    ticket = Ticket(1, 1, 10, "Subject", "Description", TicketStatus.NEW, None, now, now, None)
    session = RoleSession(1, 1, 10, Role.SUPPORT, now, now + timedelta(hours=1))

    with pytest.raises(InvalidTransitionError):
        assert_support_transition(ticket, TicketStatus.RESOLVED, session)


def test_workspace_attachment_quota_rejects_overflow() -> None:
    settings = Settings(
        BOT_TOKEN="test-token",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/test",
        REDIS_URL="redis://localhost/0",
        max_workspace_total_size_bytes=100,
    )
    incoming = IncomingFile("file", "test.txt", "text/plain", 51)

    with pytest.raises(AttachmentLimitError):
        validate_attachment(
            incoming,
            settings=settings,
            ticket_file_count=0,
            workspace_file_count=1,
            workspace_total_bytes=50,
        )


def test_feedback_is_available_once_only_to_ticket_author() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    ticket = Ticket(1, 1, 10, "Subject", "Description", TicketStatus.CLOSED, None, now, now, now)

    assert feedback_allowed(ticket, has_feedback=False, actor_telegram_id=10) is FeedbackAllowed.YES
    assert (
        feedback_allowed(ticket, has_feedback=True, actor_telegram_id=10)
        is FeedbackAllowed.ALREADY_GIVEN
    )
    with pytest.raises(FeedbackAuthorMismatch):
        feedback_allowed(ticket, has_feedback=False, actor_telegram_id=11)
