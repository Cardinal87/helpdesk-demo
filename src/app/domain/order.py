"""Order intake domain: catalogue services, priorities and order lifecycle."""

from enum import StrEnum


class OrderStatus(StrEnum):
    NEW = "new"
    CLARIFICATION = "clarification"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.NEW: frozenset(
        {OrderStatus.CLARIFICATION, OrderStatus.ACCEPTED, OrderStatus.CANCELLED}
    ),
    OrderStatus.CLARIFICATION: frozenset({OrderStatus.ACCEPTED, OrderStatus.CANCELLED}),
    OrderStatus.ACCEPTED: frozenset({OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED}),
    OrderStatus.IN_PROGRESS: frozenset({OrderStatus.REVIEW, OrderStatus.CANCELLED}),
    OrderStatus.REVIEW: frozenset({OrderStatus.COMPLETED, OrderStatus.IN_PROGRESS}),
    OrderStatus.COMPLETED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


def is_order_transition_allowed(current: OrderStatus, target: OrderStatus) -> bool:
    return target in ORDER_TRANSITIONS[current]
