"""Ticket status machine.

Allowed chain (per AGENTS.md): new -> in_progress -> waiting_client -> resolved -> closed.

Transitions and the role allowed to perform them are defined here, in the domain
layer — never in aiogram handlers or repositories.
"""

from enum import StrEnum


class TicketStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_CLIENT = "waiting_client"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Role(StrEnum):
    CLIENT = "client"
    SUPPORT = "support"


# status -> set of statuses it may move to
TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.NEW: frozenset({TicketStatus.IN_PROGRESS}),
    TicketStatus.IN_PROGRESS: frozenset({TicketStatus.WAITING_CLIENT, TicketStatus.RESOLVED}),
    TicketStatus.WAITING_CLIENT: frozenset({TicketStatus.IN_PROGRESS}),
    TicketStatus.RESOLVED: frozenset({TicketStatus.CLOSED}),
    TicketStatus.CLOSED: frozenset(),  # terminal; reopening is a separate task
}

# Transitions that the support employee may trigger while working on a ticket.
SUPPORT_TRANSITIONS: frozenset[tuple[TicketStatus, TicketStatus]] = frozenset(
    {
        (TicketStatus.NEW, TicketStatus.IN_PROGRESS),
        (TicketStatus.IN_PROGRESS, TicketStatus.WAITING_CLIENT),
        (TicketStatus.WAITING_CLIENT, TicketStatus.IN_PROGRESS),
        (TicketStatus.RESOLVED, TicketStatus.CLOSED),
    }
)


def is_transition_allowed(current: TicketStatus, target: TicketStatus) -> bool:
    """Pure graph check: is ``current -> target`` on the allowed chain?"""
    return target in TRANSITIONS[current]


def can_close(current: TicketStatus) -> bool:
    """A ticket can be closed only from ``resolved``."""
    return TicketStatus.CLOSED in TRANSITIONS[current]
