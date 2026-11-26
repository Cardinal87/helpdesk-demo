"""Repositories: the only place where SQL/ORM queries live.

Handlers and application services never touch the ORM directly; they receive
domain entities back. Every ticket query is filtered by ``workspace_id`` —
cross-workspace access is impossible by construction (defense in depth on top
of domain checks).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain import entities as E
from app.domain.order import OrderStatus, Priority
from app.domain.ticket import Role, TicketStatus
from app.infrastructure.db import models as m


def _utcnow() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Mapping ORM <-> domain dataclasses
# --------------------------------------------------------------------------- #
def ws_to_domain(row: m.Workspace) -> E.Workspace:
    return E.Workspace(
        id=row.id,
        owner_telegram_id=row.owner_telegram_id,
        created_at=row.created_at,
        last_activity_at=row.last_activity_at,
        expires_at=row.expires_at,
    )


def rs_to_domain(row: m.RoleSessionModel) -> E.RoleSession:
    return E.RoleSession(
        id=row.id,
        workspace_id=row.workspace_id,
        owner_telegram_id=row.owner_telegram_id,
        role=Role(row.role),
        started_at=row.started_at,
        expires_at=row.expires_at,
        ended_at=row.ended_at,
    )


def att_to_domain(row: m.AttachmentModel) -> E.AttachmentMeta:
    return E.AttachmentMeta(
        id=row.id,
        workspace_id=row.workspace_id,
        ticket_id=row.ticket_id,
        message_id=row.message_id,
        file_id=row.file_id,
        file_name=row.file_name,
        mime_type=row.mime_type,
        size_bytes=row.size_bytes,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


def msg_to_domain(row: m.TicketMessageModel) -> E.TicketMessage:
    return E.TicketMessage(
        id=row.id,
        ticket_id=row.ticket_id,
        author_telegram_id=row.author_telegram_id,
        author_role=Role(row.author_role),
        text=row.text,
        created_at=row.created_at,
        attachments=[att_to_domain(a) for a in row.attachments],
    )


def ticket_to_domain(row: m.TicketModel) -> E.Ticket:
    return E.Ticket(
        id=row.id,
        workspace_id=row.workspace_id,
        author_telegram_id=row.author_telegram_id,
        subject=row.subject,
        description=row.description,
        status=TicketStatus(row.status),
        assignee_telegram_id=row.assignee_telegram_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        closed_at=row.closed_at,
        order_id=row.order_id,
        category=row.category,
        priority=Priority(row.priority),
        messages=[msg_to_domain(x) for x in row.messages],
    )


def fb_to_domain(row: m.FeedbackModel) -> E.Feedback:
    return E.Feedback(
        id=row.id,
        ticket_id=row.ticket_id,
        workspace_id=row.workspace_id,
        author_telegram_id=row.author_telegram_id,
        rating=row.rating,
        comment=row.comment,
        created_at=row.created_at,
    )


def service_to_domain(row: m.ServiceModel) -> E.Service:
    return E.Service(row.id, row.code, row.title, row.description, row.price_from, row.is_active)


def order_to_domain(row: m.OrderModel) -> E.Order:
    return E.Order(
        row.id,
        row.workspace_id,
        row.customer_telegram_id,
        row.service_id,
        row.service_title,
        row.description,
        OrderStatus(row.status),
        Priority(row.priority),
        row.created_at,
        row.updated_at,
    )


def note_to_domain(row: m.InternalNoteModel) -> E.InternalNote:
    return E.InternalNote(
        id=row.id,
        workspace_id=row.workspace_id,
        author_telegram_id=row.author_telegram_id,
        body=row.body,
        created_at=row.created_at,
        ticket_id=row.ticket_id,
        order_id=row.order_id,
    )


# --------------------------------------------------------------------------- #
# Workspace repository
# --------------------------------------------------------------------------- #
class WorkspaceRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_owner(self, telegram_id: int) -> E.Workspace | None:
        row = await self._s.scalar(
            select(m.Workspace).where(m.Workspace.owner_telegram_id == telegram_id)
        )
        return ws_to_domain(row) if row else None

    async def get(self, workspace_id: int) -> E.Workspace | None:
        row = await self._s.get(m.Workspace, workspace_id)
        return ws_to_domain(row) if row else None

    async def get_or_create(self, telegram_id: int, ttl_seconds: float) -> tuple[E.Workspace, bool]:
        existing = await self.get_by_owner(telegram_id)
        now = _utcnow()
        if existing:
            return existing, False
        ws = m.Workspace(
            owner_telegram_id=telegram_id,
            last_activity_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self._s.add(ws)
        await self._s.flush()
        return ws_to_domain(ws), True

    async def touch(self, workspace_id: int, ttl_seconds: float) -> None:
        row = await self._s.get(m.Workspace, workspace_id)
        if row:
            now = _utcnow()
            row.last_activity_at = now
            row.expires_at = now + timedelta(seconds=ttl_seconds)
            await self._s.flush()

    async def delete(self, workspace_id: int) -> None:
        """Cascade removes tickets/messages/attachments/feedback via FK ON DELETE CASCADE."""
        await self._s.execute(delete(m.Workspace).where(m.Workspace.id == workspace_id))

    async def purge_expired(self, now: datetime | None = None) -> int:
        """Idempotent TTL cleanup used by the background task."""
        now = now or _utcnow()
        count = await self._s.scalar(
            select(func.count()).select_from(m.Workspace).where(m.Workspace.expires_at <= now)
        )
        await self._s.execute(delete(m.Workspace).where(m.Workspace.expires_at <= now))
        return int(count or 0)


# --------------------------------------------------------------------------- #
# User repository (profile & language)
# --------------------------------------------------------------------------- #
class UserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, telegram_id: int) -> m.User | None:
        return await self._s.scalar(select(m.User).where(m.User.telegram_id == telegram_id))

    async def get_or_create(self, telegram_id: int, display_name: str, language: str) -> m.User:
        user = await self.get(telegram_id)
        if user is None:
            user = m.User(telegram_id=telegram_id, display_name=display_name, language=language)
            self._s.add(user)
            await self._s.flush()
        elif display_name and user.display_name != display_name:
            user.display_name = display_name
            await self._s.flush()
        return user

    async def set_language(self, telegram_id: int, language: str) -> None:
        user = await self.get(telegram_id)
        if user:
            user.language = language
            await self._s.flush()


# --------------------------------------------------------------------------- #
# Role session repository
# --------------------------------------------------------------------------- #
class RoleSessionRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def active_for(self, telegram_id: int) -> E.RoleSession | None:
        row = await self._s.scalar(
            select(m.RoleSessionModel)
            .where(
                m.RoleSessionModel.owner_telegram_id == telegram_id,
                m.RoleSessionModel.ended_at.is_(None),
                m.RoleSessionModel.expires_at > _utcnow(),
            )
            .order_by(m.RoleSessionModel.started_at.desc())
            .limit(1)
        )
        return rs_to_domain(row) if row else None

    async def start(
        self, workspace_id: int, telegram_id: int, role: Role, ttl_seconds: float
    ) -> E.RoleSession:
        """Replace any active session: end old rows, insert a new one."""
        now = _utcnow()
        old_rows = (
            await self._s.scalars(
                select(m.RoleSessionModel).where(
                    m.RoleSessionModel.owner_telegram_id == telegram_id,
                    m.RoleSessionModel.ended_at.is_(None),
                )
            )
        ).all()
        for row in old_rows:
            row.ended_at = now
        new = m.RoleSessionModel(
            workspace_id=workspace_id,
            owner_telegram_id=telegram_id,
            role=role.value,
            started_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self._s.add(new)
        await self._s.flush()
        return rs_to_domain(new)

    async def end_active(self, telegram_id: int) -> None:
        now = _utcnow()
        rows = (
            await self._s.scalars(
                select(m.RoleSessionModel).where(
                    m.RoleSessionModel.owner_telegram_id == telegram_id,
                    m.RoleSessionModel.ended_at.is_(None),
                )
            )
        ).all()
        for row in rows:
            row.ended_at = now
        await self._s.flush()


# --------------------------------------------------------------------------- #
# Ticket repository
# --------------------------------------------------------------------------- #
PAGE_SIZE = 5


class TicketRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(
        self,
        *,
        workspace_id: int,
        author_telegram_id: int,
        subject: str,
        description: str,
        category: str = "general",
        order_id: int | None = None,
    ) -> E.Ticket:
        row = m.TicketModel(
            workspace_id=workspace_id,
            author_telegram_id=author_telegram_id,
            subject=subject,
            description=description,
            category=category,
            order_id=order_id,
            status=TicketStatus.NEW.value,
            messages=[],  # mark collection as loaded; async ORM must not lazy-load it in mapper
        )
        self._s.add(row)
        await self._s.flush()
        return ticket_to_domain(row)

    async def get_with_messages(self, ticket_id: int, workspace_id: int) -> E.Ticket | None:
        """Always scoped by workspace: foreign ids simply resolve to None."""
        row = await self._s.scalar(
            select(m.TicketModel)
            .options(
                selectinload(m.TicketModel.messages).selectinload(m.TicketMessageModel.attachments)
            )
            .options(selectinload(m.TicketModel.feedback))
            .where(m.TicketModel.id == ticket_id, m.TicketModel.workspace_id == workspace_id)
        )
        return ticket_to_domain(row) if row else None

    async def list_page(
        self, *, workspace_id: int, page: int, author_only: int | None = None
    ) -> tuple[list[E.Ticket], int]:
        conds = [m.TicketModel.workspace_id == workspace_id]
        if author_only is not None:
            conds.append(m.TicketModel.author_telegram_id == author_only)
        total = await self._s.scalar(select(func.count()).select_from(m.TicketModel).where(*conds))
        rows = (
            await self._s.scalars(
                select(m.TicketModel)
                .options(
                    selectinload(m.TicketModel.messages).selectinload(
                        m.TicketMessageModel.attachments
                    )
                )
                .options(selectinload(m.TicketModel.feedback))
                .where(*conds)
                .order_by(m.TicketModel.updated_at.desc(), m.TicketModel.id.desc())
                .offset(page * PAGE_SIZE)
                .limit(PAGE_SIZE)
            )
        ).all()
        return [ticket_to_domain(r) for r in rows], total or 0

    async def list_notes(self, workspace_id: int, ticket_id: int) -> list[E.InternalNote]:
        rows = (
            await self._s.scalars(
                select(m.InternalNoteModel)
                .where(
                    m.InternalNoteModel.workspace_id == workspace_id,
                    m.InternalNoteModel.ticket_id == ticket_id,
                )
                .order_by(m.InternalNoteModel.created_at.desc())
                .limit(20)
            )
        ).all()
        return [note_to_domain(r) for r in rows]

    async def set_status(
        self,
        ticket_id: int,
        workspace_id: int,
        status: TicketStatus,
        *,
        assignee: int | None = None,
        closed_at: datetime | None = None,
    ) -> None:
        row = await self._s.scalar(
            select(m.TicketModel).where(
                m.TicketModel.id == ticket_id, m.TicketModel.workspace_id == workspace_id
            )
        )
        if row is None:
            from app.domain.errors import AccessDeniedError

            raise AccessDeniedError("ticket not found in workspace")
        row.status = status.value
        row.updated_at = _utcnow()
        if assignee is not None:
            row.assignee_telegram_id = assignee
        if status is TicketStatus.CLOSED:
            row.closed_at = closed_at or _utcnow()
        await self._s.flush()

    async def add_message(
        self,
        *,
        ticket_id: int,
        workspace_id: int,
        author_telegram_id: int,
        author_role: Role,
        text: str,
        attachments: list[
            dict
        ],  # validated dicts: file_id/file_name/mime_type/size_bytes/expires_at
    ) -> E.TicketMessage:
        """Atomic: message + attachment rows flush in the caller's transaction."""
        msg = m.TicketMessageModel(
            ticket_id=ticket_id,
            author_telegram_id=author_telegram_id,
            author_role=author_role.value,
            text=text,
        )
        self._s.add(msg)
        await self._s.flush()
        for a in attachments:
            self._s.add(
                m.AttachmentModel(
                    workspace_id=workspace_id,
                    ticket_id=ticket_id,
                    message_id=msg.id,
                    **a,
                )
            )
        # bump ticket.updated_at so ordering reflects activity
        ticket_row = await self._s.get(m.TicketModel, ticket_id)
        if ticket_row:
            ticket_row.updated_at = _utcnow()
        await self._s.flush()
        await self._s.refresh(msg, ["attachments"])
        return msg_to_domain(msg)

    async def has_feedback(self, ticket_id: int) -> bool:
        count = await self._s.scalar(
            select(func.count())
            .select_from(m.FeedbackModel)
            .where(m.FeedbackModel.ticket_id == ticket_id)
        )
        return bool(count)

    async def add_feedback(
        self,
        *,
        ticket_id: int,
        workspace_id: int,
        author_telegram_id: int,
        rating: int,
        comment: str,
    ) -> E.Feedback:
        row = m.FeedbackModel(
            ticket_id=ticket_id,
            workspace_id=workspace_id,
            author_telegram_id=author_telegram_id,
            rating=rating,
            comment=comment,
        )
        self._s.add(row)
        await self._s.flush()
        return fb_to_domain(row)

    # --- attachment accounting (workspace-level quota) ------------------------
    async def workspace_attachment_stats(self, workspace_id: int) -> tuple[int, int]:
        """(file_count, total_bytes) currently stored for the workspace."""
        row = (
            await self._s.execute(
                select(
                    func.count(), func.coalesce(func.sum(m.AttachmentModel.size_bytes), 0)
                ).where(m.AttachmentModel.workspace_id == workspace_id)
            )
        ).one()
        return int(row[0]), int(row[1])

    async def ticket_attachment_count(self, ticket_id: int) -> int:
        return int(
            await self._s.scalar(
                select(func.count())
                .select_from(m.AttachmentModel)
                .where(m.AttachmentModel.ticket_id == ticket_id)
            )
            or 0
        )

    async def set_priority(self, ticket_id: int, workspace_id: int, priority: Priority) -> None:
        row = await self._s.scalar(
            select(m.TicketModel).where(
                m.TicketModel.id == ticket_id, m.TicketModel.workspace_id == workspace_id
            )
        )
        if row is None:
            from app.domain.errors import AccessDeniedError

            raise AccessDeniedError("ticket not found")
        row.priority = priority.value
        await self._s.flush()

    async def add_note(self, workspace_id: int, author_id: int, ticket_id: int, body: str) -> None:
        ticket = await self._s.scalar(
            select(m.TicketModel).where(
                m.TicketModel.id == ticket_id,
                m.TicketModel.workspace_id == workspace_id,
            )
        )
        if ticket is None:
            from app.domain.errors import AccessDeniedError

            raise AccessDeniedError("ticket not found in workspace")
        self._s.add(
            m.InternalNoteModel(
                workspace_id=workspace_id,
                author_telegram_id=author_id,
                ticket_id=ticket_id,
                body=body,
            )
        )
        await self._s.flush()


class OrderRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def services(self) -> list[E.Service]:
        rows = (
            await self._s.scalars(
                select(m.ServiceModel)
                .where(m.ServiceModel.is_active.is_(True))
                .order_by(m.ServiceModel.id)
            )
        ).all()
        return [service_to_domain(row) for row in rows]

    async def service(self, service_id: int) -> E.Service | None:
        row = await self._s.scalar(
            select(m.ServiceModel).where(
                m.ServiceModel.id == service_id, m.ServiceModel.is_active.is_(True)
            )
        )
        return service_to_domain(row) if row else None

    async def create(
        self, workspace_id: int, customer_id: int, service: E.Service, description: str
    ) -> E.Order:
        row = m.OrderModel(
            workspace_id=workspace_id,
            customer_telegram_id=customer_id,
            service_id=service.id,
            service_title=service.title,
            description=description,
            status=OrderStatus.NEW.value,
            priority=Priority.NORMAL.value,
        )
        self._s.add(row)
        await self._s.flush()
        return order_to_domain(row)

    async def get(self, order_id: int, workspace_id: int) -> E.Order | None:
        row = await self._s.scalar(
            select(m.OrderModel).where(
                m.OrderModel.id == order_id, m.OrderModel.workspace_id == workspace_id
            )
        )
        return order_to_domain(row) if row else None

    async def list_page(self, workspace_id: int, customer_id: int | None = None) -> list[E.Order]:
        filters = [m.OrderModel.workspace_id == workspace_id]
        if customer_id is not None:
            filters.append(m.OrderModel.customer_telegram_id == customer_id)
        rows = (
            await self._s.scalars(
                select(m.OrderModel)
                .where(*filters)
                .order_by(m.OrderModel.updated_at.desc())
                .limit(PAGE_SIZE)
            )
        ).all()
        return [order_to_domain(row) for row in rows]

    async def list_notes(self, workspace_id: int, order_id: int) -> list[E.InternalNote]:
        rows = (
            await self._s.scalars(
                select(m.InternalNoteModel)
                .where(
                    m.InternalNoteModel.workspace_id == workspace_id,
                    m.InternalNoteModel.order_id == order_id,
                )
                .order_by(m.InternalNoteModel.created_at.desc())
                .limit(20)
            )
        ).all()
        return [note_to_domain(r) for r in rows]

    async def set_status(self, order_id: int, workspace_id: int, status: OrderStatus) -> None:
        row = await self._s.scalar(
            select(m.OrderModel).where(
                m.OrderModel.id == order_id, m.OrderModel.workspace_id == workspace_id
            )
        )
        if row is None:
            from app.domain.errors import AccessDeniedError

            raise AccessDeniedError("order not found")
        row.status = status.value
        row.updated_at = _utcnow()
        await self._s.flush()

    async def set_priority(self, order_id: int, workspace_id: int, priority: Priority) -> None:
        row = await self._s.scalar(
            select(m.OrderModel).where(
                m.OrderModel.id == order_id, m.OrderModel.workspace_id == workspace_id
            )
        )
        if row is None:
            from app.domain.errors import AccessDeniedError

            raise AccessDeniedError("order not found")
        row.priority = priority.value
        row.updated_at = _utcnow()
        await self._s.flush()

    async def add_note(self, workspace_id: int, author_id: int, order_id: int, body: str) -> None:
        ok = await self._s.scalar(
            select(m.OrderModel.id).where(
                m.OrderModel.id == order_id,
                m.OrderModel.workspace_id == workspace_id,
            )
        )
        if ok is None:
            from app.domain.errors import AccessDeniedError

            raise AccessDeniedError("order not found in workspace")
        self._s.add(
            m.InternalNoteModel(
                workspace_id=workspace_id,
                author_telegram_id=author_id,
                order_id=order_id,
                body=body,
            )
        )
        await self._s.flush()


# --------------------------------------------------------------------------- #
# Audit repository
# --------------------------------------------------------------------------- #
class AuditRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def record(
        self,
        *,
        workspace_id: int,
        actor_telegram_id: int,
        event: str,
        ticket_id: int | None = None,
        payload: str = "{}",
    ) -> None:
        self._s.add(
            m.AuditEventModel(
                workspace_id=workspace_id,
                ticket_id=ticket_id,
                actor_telegram_id=actor_telegram_id,
                event=event,
                payload=payload,
            )
        )
        await self._s.flush()
