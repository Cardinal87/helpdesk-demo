"""SQLAlchemy 2.x async ORM models (PostgreSQL via asyncpg).

Notes:
- All timestamps are UTC (``DateTime(timezone=True)`` + server_default now()).
- Indexes required by AGENTS.md are declared below.
- Schema changes go through Alembic migrations; ``create_all`` is never used
  as a schema-update mechanism in production paths.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.ticket import Role, TicketStatus


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    tickets: Mapped[list[TicketModel]] = relationship(
        cascade="all, delete-orphan", back_populates="workspace"
    )
    role_sessions: Mapped[list[RoleSessionModel]] = relationship(
        cascade="all, delete-orphan", back_populates="workspace"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    language: Mapped[str] = mapped_column(String(5), default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RoleSessionModel(Base):
    __tablename__ = "role_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    owner_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(16))  # Role enum value
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="role_sessions")


class TicketModel(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    author_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    subject: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default=TicketStatus.NEW.value)
    assignee_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(64), default="general")
    priority: Mapped[str] = mapped_column(String(16), default="normal")

    workspace: Mapped[Workspace] = relationship(back_populates="tickets")
    messages: Mapped[list[TicketMessageModel]] = relationship(
        cascade="all, delete-orphan", order_by="TicketMessageModel.created_at"
    )
    attachments: Mapped[list[AttachmentModel]] = relationship(cascade="all, delete-orphan")
    feedback: Mapped[FeedbackModel | None] = relationship(
        back_populates="ticket", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_tickets_customer_status_updated", "author_telegram_id", "status", "updated_at"),
        Index("ix_tickets_assignee_status_updated", "assignee_telegram_id", "status", "updated_at"),
    )


class TicketMessageModel(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    author_telegram_id: Mapped[int] = mapped_column(BigInteger)
    author_role: Mapped[str] = mapped_column(String(16))  # Role enum value at send time
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    attachments: Mapped[list[AttachmentModel]] = relationship(
        cascade="all, delete-orphan", back_populates="message"
    )

    __table_args__ = (Index("ix_ticket_messages_ticket_created", "ticket_id", "created_at"),)


class AttachmentModel(Base):
    """Metadata only: Telegram file_id + validated info. Binaries are not stored."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("ticket_messages.id", ondelete="CASCADE"), nullable=True
    )
    file_id: Mapped[str] = mapped_column(String(512))
    file_name: Mapped[str] = mapped_column(String(255))  # untrusted display name
    mime_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    message: Mapped[TicketMessageModel | None] = relationship(back_populates="attachments")

    __table_args__ = (CheckConstraint("size_bytes > 0", name="ck_attachments_size_positive"),)


class FeedbackModel(Base):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), unique=True
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    author_telegram_id: Mapped[int] = mapped_column(BigInteger)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped[TicketModel] = relationship(back_populates="feedback")

    __table_args__ = (
        UniqueConstraint("ticket_id", name="uq_feedback_one_per_ticket"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_feedbacks_rating_range"),
    )


class AuditEventModel(Base):
    """Lightweight history for the demo: status changes, assignment, role exit."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    ticket_id: Mapped[int | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True, index=True
    )
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger)
    event: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text, default="{}")  # JSON string, no PII text
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ServiceModel(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    price_from: Mapped[str] = mapped_column(String(80), default="")
    is_active: Mapped[bool] = mapped_column(default=True)


class OrderModel(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    customer_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    service_title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="new")
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        Index("ix_orders_workspace_status_updated", "workspace_id", "status", "updated_at"),
    )


class InternalNoteModel(Base):
    __tablename__ = "internal_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    author_telegram_id: Mapped[int] = mapped_column(BigInteger)
    body: Mapped[str] = mapped_column(Text)
    ticket_id: Mapped[int | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True, index=True
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("ticket_id IS NOT NULL OR order_id IS NOT NULL", name="ck_note_target"),
    )


# Type aliases used by repositories/services when mapping to domain entities.
RoleEnum = Role
StatusEnum = TicketStatus
