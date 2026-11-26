"""Access rules: role + workspace ownership checks.

Everything here is pure and receives already-loaded entities. Application
services load Workspace/RoleSession/Ticket from DB and call these helpers —
callback data is *never* treated as proof of rights (AGENTS.md requirement).
"""

from __future__ import annotations

from datetime import datetime

from app.domain.entities import RoleSession, Ticket, Workspace
from app.domain.errors import AccessDeniedError, NoActiveRoleError, WorkspaceExpiredError
from app.domain.ticket import Role, TicketStatus, is_transition_allowed


def require_active_workspace(workspace: Workspace, now: datetime) -> None:
    if workspace.is_expired(now):
        raise WorkspaceExpiredError("workspace expired")


def require_active_session(session: RoleSession | None, now: datetime) -> RoleSession:
    """Every action must have a live RoleSession for the acting Telegram user."""
    if session is None or not session.is_active(now):
        raise NoActiveRoleError("no active role session")
    return session


def require_workspace_owner(workspace: Workspace, telegram_id: int) -> None:
    if workspace.owner_telegram_id != telegram_id:
        # Same message as "not found": do not leak existence of foreign workspaces.
        raise AccessDeniedError("not your workspace")


def require_ticket_in_workspace(ticket: Ticket, workspace_id: int) -> None:
    """Cross-workspace guard: ticket must belong to the actor's own workspace."""
    if ticket.workspace_id != workspace_id:
        raise AccessDeniedError("ticket does not belong to this workspace")


def require_role(session: RoleSession, role: Role) -> None:
    if session.role is not role:
        raise AccessDeniedError(f"role {session.role.value} cannot perform this action")


def can_view_ticket_list(session: RoleSession) -> bool:
    """Both roles see tickets, but through different lenses (own vs workspace queue)."""
    return True  # filtering happens in repositories by role; kept for explicitness


def ticket_actions(ticket: Ticket, role: Role) -> frozenset[str]:
    """UI-level capability hints for keyboards. Authoritative checks stay in services."""
    actions: set[str] = {"open", "reply"}
    if not ticket.is_editable:
        return frozenset({"open"})
    if role is Role.CLIENT:
        actions.add("cancel_creation")
        if ticket.status is TicketStatus.CLOSED:
            actions.discard("reply")
    if role is Role.SUPPORT and ticket.status is not TicketStatus.CLOSED:
        for target in _support_targets(ticket.status):
            actions.add(f"transition:{target.value}")
    return frozenset(actions)


def _support_targets(current: TicketStatus) -> list[TicketStatus]:
    return sorted(
        (t for t in TicketStatus if is_transition_allowed(current, t)),
        key=lambda s: list(TicketStatus).index(s),
    )


def assert_support_transition(ticket: Ticket, target: TicketStatus, session: RoleSession) -> None:
    """Support-only transition gate used by the status-change use case."""
    require_role(session, Role.SUPPORT)
    if not is_transition_allowed(ticket.status, target):
        from app.domain.errors import InvalidTransitionError

        raise InvalidTransitionError(f"{ticket.status.value} -> {target.value} is not allowed")
