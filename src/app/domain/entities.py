"""Pure domain entities.

These dataclasses are storage-agnostic: SQLAlchemy models in
``infrastructure.db`` map rows to/from them, and application services operate
only on these types and the rules below. No ORM imports here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.errors import DomainError
from app.domain.order import OrderStatus, Priority
from app.domain.ticket import Role, TicketStatus


class FeedbackAllowed(StrEnum):
    YES = "yes"
    NOT_CLOSED = "not_closed"
    ALREADY_GIVEN = "already_given"


@dataclass(slots=True)
class Workspace:
    """Isolated demo sandbox owned by one Telegram ID."""

    id: int
    owner_telegram_id: int
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at <= now

    def touch(self, now: datetime, ttl_seconds: float) -> None:
        """Register activity and push the TTL deadline forward."""
        self.last_activity_at = now
        from datetime import timedelta

        self.expires_at = now + timedelta(seconds=ttl_seconds)


@dataclass(slots=True)
class User:
    id: int
    telegram_id: int
    display_name: str
    created_at: datetime


@dataclass(slots=True)
class RoleSession:
    """Active role of a Telegram user inside their workspace (temporary context)."""

    id: int
    workspace_id: int
    owner_telegram_id: int
    role: Role
    started_at: datetime
    expires_at: datetime
    ended_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        return self.ended_at is None and self.expires_at > now


@dataclass(slots=True)
class AttachmentMeta:
    """Validated metadata only — binaries stay on Telegram servers (file_id)."""

    id: int
    workspace_id: int
    ticket_id: int
    message_id: int | None
    file_id: str
    file_name: str  # untrusted display name, never used for logic
    mime_type: str
    size_bytes: int
    created_at: datetime
    expires_at: datetime


@dataclass(slots=True)
class TicketMessage:
    id: int
    ticket_id: int
    author_telegram_id: int
    author_role: Role
    text: str
    created_at: datetime
    attachments: list[AttachmentMeta] = field(default_factory=list)


@dataclass(slots=True)
class Ticket:
    id: int
    workspace_id: int
    author_telegram_id: int
    subject: str
    description: str
    status: TicketStatus
    assignee_telegram_id: int | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    order_id: int | None = None
    category: str = "general"
    priority: Priority = Priority.NORMAL
    messages: list[TicketMessage] = field(default_factory=list)

    @property
    def is_editable(self) -> bool:
        """Closed tickets are frozen (feedback aside — see Feedback rules)."""
        return self.status is not TicketStatus.CLOSED


@dataclass(slots=True)
class Service:
    id: int
    code: str
    title: str
    description: str
    price_from: str
    is_active: bool


@dataclass(slots=True)
class Order:
    id: int
    workspace_id: int
    customer_telegram_id: int
    service_id: int
    service_title: str
    description: str
    status: OrderStatus
    priority: Priority
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class InternalNote:
    id: int
    workspace_id: int
    author_telegram_id: int
    body: str
    ticket_id: int | None
    order_id: int | None
    created_at: datetime


@dataclass(slots=True)
class Feedback:
    id: int
    ticket_id: int
    workspace_id: int
    author_telegram_id: int
    rating: int  # 1..5
    comment: str
    created_at: datetime


class FeedbackAuthorMismatch(DomainError):
    """Only the ticket author (client side) may leave feedback."""


def feedback_allowed(
    ticket: Ticket, *, has_feedback: bool, actor_telegram_id: int
) -> FeedbackAllowed:
    """Domain rule: exactly one feedback per closed ticket, author-only, after close.

    Raises ``FeedbackAuthorMismatch`` when a non-author tries to give feedback —
    callers must translate it into a friendly localized message.
    """
    if actor_telegram_id != ticket.author_telegram_id:
        raise FeedbackAuthorMismatch("feedback is only for the ticket author")
    if ticket.status is not TicketStatus.CLOSED:
        return FeedbackAllowed.NOT_CLOSED
    if has_feedback:
        return FeedbackAllowed.ALREADY_GIVEN
    return FeedbackAllowed.YES
