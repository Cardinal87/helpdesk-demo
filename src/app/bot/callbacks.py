"""Callback data scheme: short stable prefixes + validated payloads.

aiogram's FilterData validates structure before the handler runs; rights are
still re-checked against DB in services (callback data is never proof).
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class LangCB(CallbackData, prefix="lang"):
    code: str


class RoleCB(CallbackData, prefix="role"):
    role: str  # client | support


class MenuCB(CallbackData, prefix="menu"):
    action: str  # my_tickets | queue | new_ticket | switch_role | settings | exit | new_ws


class TicketPageCB(CallbackData, prefix="tpage"):
    page: int


class TicketOpenCB(CallbackData, prefix="tk"):
    ticket_id: int


class ReplyCB(CallbackData, prefix="reply"):
    ticket_id: int


class StatusCB(CallbackData, prefix="st"):
    ticket_id: int
    target: str  # TicketStatus value


class CloseConfirmCB(CallbackData, prefix="close"):
    ticket_id: int
    approve: str  # yes | no


class FeedbackStartCB(CallbackData, prefix="fb"):
    ticket_id: int


class FeedbackRatingCB(CallbackData, prefix="fbr"):
    ticket_id: int
    rating: int


class ConfirmCB(CallbackData, prefix="cfm"):
    action: str  # exit_role | reset_ws
    approve: str  # yes | no


class AttachDoneCB(CallbackData, prefix="adone"):
    pass


class ServiceCB(CallbackData, prefix="svc"):
    service_id: int


class OrderCB(CallbackData, prefix="ord"):
    order_id: int


class OrderStatusCB(CallbackData, prefix="ost"):
    order_id: int
    target: str


class PriorityCB(CallbackData, prefix="prio"):
    target_type: str  # ticket | order
    target_id: int
    priority: str


class NoteCB(CallbackData, prefix="note"):
    target_type: str  # ticket | order
    target_id: int


class TicketForOrderCB(CallbackData, prefix="tford"):
    order_id: int


class CategoryCB(CallbackData, prefix="cat"):
    code: str


class NotesViewCB(CallbackData, prefix="notes"):
    target_type: str  # ticket | order
    target_id: int
