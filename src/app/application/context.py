"""Shared service context: DI-lite container passed to use cases.

Handlers build this from aiogram workflow_data/middleware and call use cases.
Services own the transaction boundary; repositories own SQL; handlers own UX.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.infrastructure.db.repositories import (
    AuditRepo,
    OrderRepo,
    RoleSessionRepo,
    TicketRepo,
    UserRepo,
    WorkspaceRepo,
)


@dataclass(slots=True)
class Services:
    """All use-case dependencies for one request/update."""

    session: AsyncSession
    settings: Settings

    @property
    def workspaces(self) -> WorkspaceRepo:
        return WorkspaceRepo(self.session)

    @property
    def users(self) -> UserRepo:
        return UserRepo(self.session)

    @property
    def roles(self) -> RoleSessionRepo:
        return RoleSessionRepo(self.session)

    @property
    def tickets(self) -> TicketRepo:
        return TicketRepo(self.session)

    @property
    def audit(self) -> AuditRepo:
        return AuditRepo(self.session)

    @property
    def orders(self) -> OrderRepo:
        return OrderRepo(self.session)
