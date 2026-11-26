"""Inline keyboards factory. All labels come from the i18n catalog."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot import callbacks as cb
from app.bot.i18n import STATUS_EMOJI, t
from app.domain.entities import Order, Service, Ticket
from app.domain.order import ORDER_TRANSITIONS
from app.domain.ticket import Role, TicketStatus


def language_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data=cb.LangCB(code="ru").pack()),
                InlineKeyboardButton(text="🇬🇧 English", callback_data=cb.LangCB(code="en").pack()),
            ]
        ]
    )


def category_kb(lang: str) -> InlineKeyboardMarkup:
    labels = {"question": "❓ Question", "bug": "🐞 Bug", "support": "🛠 Support"}
    if lang == "ru":
        labels = {"question": "❓ Вопрос", "bug": "🐞 Ошибка", "support": "🛠 Поддержка"}
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=cb.CategoryCB(code=code).pack())]
            for code, label in labels.items()
        ]
    )


def role_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "role_client"), callback_data=cb.RoleCB(role="client").pack()
                )
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "role_support"), callback_data=cb.RoleCB(role="support").pack()
                )
            ],
        ]
    )


def menu_kb(lang: str, role: Role | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    # Ролевые кнопки
    if role is Role.CLIENT:
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_catalog"), callback_data=cb.MenuCB(action="catalog").pack()
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_my_orders"),
                    callback_data=cb.MenuCB(action="my_orders").pack(),
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_new_ticket"),
                    callback_data=cb.MenuCB(action="new_ticket").pack(),
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_my_tickets"),
                    callback_data=cb.MenuCB(action="my_tickets").pack(),
                )
            ]
        )
    elif role is Role.SUPPORT:
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_orders"), callback_data=cb.MenuCB(action="orders").pack()
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_ticket_queue"), callback_data=cb.MenuCB(action="queue").pack()
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=t(lang, "btn_switch_role"),
                callback_data=cb.MenuCB(action="switch_role").pack(),
            ),
            InlineKeyboardButton(
                text=t(lang, "btn_language"), callback_data=cb.MenuCB(action="settings").pack()
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=t(lang, "btn_exit"),
                callback_data=cb.ConfirmCB(action="exit_role", approve="ask").pack(),
            ),
            InlineKeyboardButton(
                text=t(lang, "btn_new_workspace"),
                callback_data=cb.ConfirmCB(action="reset_ws", approve="ask").pack(),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def services_kb(lang: str, services: list[Service]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{s.title} · {s.price_from}",
                callback_data=cb.ServiceCB(service_id=s.id).pack(),
            )
        ]
        for s in services
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text=t(lang, "btn_back_menu"), callback_data=cb.MenuCB(action="back_menu").pack()
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def orders_kb(lang: str, orders: list[Order]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"#{o.id} {o.service_title} · {o.status}",
                callback_data=cb.OrderCB(order_id=o.id).pack(),
            )
        ]
        for o in orders
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text=t(lang, "btn_back_menu"), callback_data=cb.MenuCB(action="back_menu").pack()
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_card_kb(lang: str, order: Order, role: Role) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if role is Role.SUPPORT:
        targets = ORDER_TRANSITIONS[order.status]
        if targets:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=t(lang, f"order_{x.value}"),
                        callback_data=cb.OrderStatusCB(order_id=order.id, target=x.value).pack(),
                    )
                    for x in targets
                ]
            )
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, f"priority_{p}"),
                    callback_data=cb.PriorityCB(
                        target_type="order", target_id=order.id, priority=p
                    ).pack(),
                )
                for p in ("low", "normal", "high")
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_note"),
                    callback_data=cb.NoteCB(target_type="order", target_id=order.id).pack(),
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_view_notes"),
                    callback_data=cb.NotesViewCB(target_type="order", target_id=order.id).pack(),
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_ticket_for_order"),
                    callback_data=cb.TicketForOrderCB(order_id=order.id).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=t(lang, "btn_back_menu"), callback_data=cb.MenuCB(action="back_menu").pack()
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb(lang: str, action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_yes"),
                    callback_data=cb.ConfirmCB(action=action, approve="yes").pack(),
                ),
                InlineKeyboardButton(
                    text=t(lang, "btn_no"),
                    callback_data=cb.ConfirmCB(action=action, approve="no").pack(),
                ),
            ]
        ]
    )


def tickets_list_kb(
    lang: str, tickets: list[Ticket], page: int, total: int
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for tk in tickets:
        label = t(
            lang,
            "ticket_row",
            id=tk.id,
            status_emoji=STATUS_EMOJI.get(tk.status.value, ""),
            subject=(tk.subject[:40] + "…" if len(tk.subject) > 40 else tk.subject),
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=label, callback_data=cb.TicketOpenCB(ticket_id=tk.id).pack()
                )
            ]
        )
    pages = max(1, (total + 4) // 5)
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text=t(lang, "btn_prev"), callback_data=cb.TicketPageCB(page=page - 1).pack()
            )
        )
    nav.append(
        InlineKeyboardButton(
            text=t(lang, "page_info", page=page + 1, pages=pages), callback_data="noop"
        )
    )
    if page + 1 < pages:
        nav.append(
            InlineKeyboardButton(
                text=t(lang, "btn_next"), callback_data=cb.TicketPageCB(page=page + 1).pack()
            )
        )
    rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(
                text=t(lang, "btn_back_menu"),
                callback_data=cb.MenuCB(action="back_menu").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ticket_card_kb(lang: str, ticket: Ticket, role: Role) -> InlineKeyboardMarkup:
    """Capability buttons are hints; services re-verify everything."""
    rows: list[list[InlineKeyboardButton]] = []
    if ticket.is_editable:
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_reply"),
                    callback_data=cb.ReplyCB(ticket_id=ticket.id).pack(),
                )
            ]
        )
    if role is Role.SUPPORT and ticket.is_editable:
        from app.domain.access import _support_targets

        btns = []
        for target in _support_targets(ticket.status):
            emoji = STATUS_EMOJI.get(target.value, "")
            btns.append(
                InlineKeyboardButton(
                    text=f"{emoji} {t(lang, f'status_{target.value}')}",
                    callback_data=(
                        cb.CloseConfirmCB(
                            ticket_id=ticket.id, approve="ask"
                        ).pack()  # <-- ИСПРАВЛЕНО ЗДЕСЬ
                        if target is TicketStatus.CLOSED
                        else cb.StatusCB(ticket_id=ticket.id, target=target.value).pack()
                    ),
                )
            )
        if btns:
            rows.append(btns)
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, f"priority_{p}"),
                    callback_data=cb.PriorityCB(
                        target_type="ticket", target_id=ticket.id, priority=p
                    ).pack(),
                )
                for p in ("low", "normal", "high")
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_note"),
                    callback_data=cb.NoteCB(target_type="ticket", target_id=ticket.id).pack(),
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_view_notes"),
                    callback_data=cb.NotesViewCB(target_type="ticket", target_id=ticket.id).pack(),
                )
            ]
        )
    if role is Role.CLIENT and ticket.status is TicketStatus.CLOSED:
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_feedback"),
                    callback_data=cb.FeedbackStartCB(ticket_id=ticket.id).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=t(lang, "btn_back_menu"),
                callback_data=cb.MenuCB(action="back_menu").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def close_confirm_kb(lang: str, ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_yes"),
                    callback_data=cb.CloseConfirmCB(ticket_id=ticket_id, approve="yes").pack(),
                ),
                InlineKeyboardButton(
                    text=t(lang, "btn_no"),
                    callback_data=cb.CloseConfirmCB(ticket_id=ticket_id, approve="no").pack(),
                ),
            ]
        ]
    )


def attach_done_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_done_attachments"), callback_data=cb.AttachDoneCB().pack()
                )
            ]
        ]
    )


def rating_kb(lang: str, ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐" * i,
                    callback_data=cb.FeedbackRatingCB(ticket_id=ticket_id, rating=i).pack(),
                )
                for i in range(1, 6)
            ]
        ]
    )


def back_only_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_back_menu"),
                    callback_data=cb.MenuCB(action="back_menu").pack(),
                )
            ]
        ]
    )


def notes_kb(lang: str, target_type: str, target_id: int) -> InlineKeyboardMarkup:
    back = (
        cb.TicketOpenCB(ticket_id=target_id)
        if target_type == "ticket"
        else cb.OrderCB(order_id=target_id)
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_add_note"),
                    callback_data=cb.NoteCB(target_type=target_type, target_id=target_id).pack(),
                )
            ],
            [InlineKeyboardButton(text=t(lang, "btn_back_card"), callback_data=back.pack())],
        ]
    )
