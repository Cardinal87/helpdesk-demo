"""Use cases: workspace & role lifecycle.

Every entry point here performs the full verification chain from AGENTS.md:
owner check -> active workspace check -> (session ops) — and never trusts
callback data as proof of rights.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC

from app.application.context import Services
from app.domain import access
from app.domain.entities import RoleSession, Workspace
from app.domain.ticket import Role


@dataclass(slots=True)
class SessionContext:
    """Result of verifying an actor: what services hand to handlers."""

    workspace: Workspace
    session: RoleSession | None  # None => role not chosen yet


async def ensure_workspace(svc: Services, telegram_id: int) -> tuple[Workspace, bool]:
    ws, created = await svc.workspaces.get_or_create(
        telegram_id, ttl_seconds=svc.settings.workspace_ttl_seconds
    )
    return ws, created


async def get_actor_context(svc: Services, telegram_id: int) -> SessionContext:
    """Load workspace + active role session for the acting Telegram user."""
    from datetime import datetime

    ws = await svc.workspaces.get_by_owner(telegram_id)
    if ws is None:
        # No workspace yet: caller should route through /start flow.
        from app.domain.errors import NoActiveRoleError

        raise NoActiveRoleError("workspace missing; run /start")
    now = datetime.now(UTC)
    access.require_active_workspace(ws, now)
    session = await svc.roles.active_for(telegram_id)
    return SessionContext(workspace=ws, session=session)


async def choose_role(svc: Services, telegram_id: int, role: Role) -> RoleSession:
    """Start or replace the active RoleSession in the user's own workspace.

    FSM clearing is the bot layer's responsibility (it owns aiogram state).
    """
    ws = await svc.workspaces.get_by_owner(telegram_id)
    if ws is None:
        ws, _ = await ensure_workspace(svc, telegram_id)
    access.require_workspace_owner(ws, telegram_id)
    session = await svc.roles.start(
        ws.id, telegram_id, role, ttl_seconds=svc.settings.role_session_ttl_seconds
    )
    await svc.workspaces.touch(ws.id, svc.settings.workspace_ttl_seconds)
    await svc.audit.record(
        workspace_id=ws.id, actor_telegram_id=telegram_id, event=f"role.start.{role.value}"
    )
    return session


async def leave_role(svc: Services, telegram_id: int) -> None:
    """Exit role: clears session only; workspace data preserved until TTL."""
    ws = await svc.workspaces.get_by_owner(telegram_id)
    if ws is None:
        return
    access.require_workspace_owner(ws, telegram_id)
    await svc.roles.end_active(telegram_id)
    await svc.audit.record(workspace_id=ws.id, actor_telegram_id=telegram_id, event="role.exit")


async def reset_workspace(svc: Services, telegram_id: int) -> Workspace:
    """Explicit 'New workspace' with confirmation handled at the bot layer."""
    old = await svc.workspaces.get_by_owner(telegram_id)
    if old is not None:
        await svc.workspaces.delete(old.id)
    ws, _ = await ensure_workspace(svc, telegram_id)
    await svc.audit.record(
        workspace_id=ws.id, actor_telegram_id=telegram_id, event="workspace.reset"
    )
    return ws
