"""Localization catalog: all user-facing strings live here, not in handlers.

Languages: ru / en (first release). Keys are stable identifiers; formatting
uses ``str.format`` placeholders so translators keep control of word order.
"""

from __future__ import annotations

SUPPORTED_LANGUAGES = ("ru", "en")

MESSAGES: dict[str, dict[str, str]] = {
    "ru": {
        # welcome & roles
        "welcome": (
            "👋 Добро пожаловать в демо Telegram CRM!\n\n"
            "Это изолированная песочница: вы создаёте тикеты как клиент и "
            "обслуживаете их же как сотрудник.\n\nВыберите язык и роль."
        ),
        "choose_language": "Выберите язык / Choose language:",
        "choose_role": "Кого вы хотите представить в этом демо?",
        "role_client": "🧑‍💼 Я клиент",
        "role_support": "🛠 Я сотрудник поддержки",
        "role_switched": "Вы теперь: {role}.",
        "menu": "Меню",
        "btn_my_tickets": "Мои тикеты",
        "btn_ticket_queue": "Очередь тикетов",
        "btn_new_ticket": "➕ Создать тикет",
        "btn_catalog": "🛍 Услуги",
        "btn_my_orders": "📦 Мои заказы",
        "btn_orders": "📦 Заказы workspace",
        "btn_priority": "⚑ Приоритет",
        "btn_note": "📝 Внутренняя заметка",
        "btn_ticket_for_order": "💬 Тикет по заказу",
        "ticket_category": "Выберите категорию: вопрос, ошибка или поддержка.",
        "note_prompt": "Введите внутреннюю заметку. Клиент её не увидит.",
        "note_saved": "Внутренняя заметка сохранена.",
        "catalog": "Выберите услугу:",
        "order_description": "Опишите задачу для заказа.",
        "order_created": "Заказ #{order_id} создан.",
        "orders_empty": "Заказов пока нет.",
        "order_card": "Заказ #{id}\nУслуга: {service}\nСтатус: {status}\nПриоритет: {priority}\n\n{description}",
        "order_new": "Новый",
        "order_clarification": "Уточнение",
        "order_accepted": "Принят",
        "order_in_progress": "В работе",
        "order_review": "Проверка",
        "order_completed": "Завершён",
        "order_cancelled": "Отменён",
        "priority_low": "Низкий",
        "priority_normal": "Обычный",
        "priority_high": "Высокий",
        "btn_switch_role": "🔄 Сменить роль",
        "btn_settings": "⚙️ Настройки",
        "btn_language": "🌐 Язык",
        "btn_exit": "Выйти из роли",
        "btn_new_workspace": "🗑 Новый workspace",
        "btn_reply": "💬 Ответить",
        "btn_feedback": "⭐ Оставить отзыв",
        "btn_back_menu": "⬅️ В меню",
        "exit_confirm": "Выйти из текущей роли? Данные workspace сохранятся.",
        "btn_yes": "Да",
        "btn_no": "Нет",
        "exited": "Вы вышли из роли. Выберите роль при следующем действии.",
        # ticket creation FSM
        "ticket_subject_prompt": "Опишите кратко тему тикета (до 200 символов).\n/cancel — отменить",
        "ticket_description_prompt": "Теперь подробно опишите проблему.\n/cancel — отменить",
        "ticket_attach_prompt": "Можно приложить файлы (до {max_files} шт., до {max_size}).\nОтправьте файлы или нажмите «Готово».",
        "btn_done_attachments": "✅ Готово",
        "ticket_created": "Тикет #{ticket_id} создан: «{subject}».",
        "ticket_cancelled": "Создание тикета отменено.",
        "cancel_not_in_form": "Сейчас нечего отменять.",
        # lists & cards
        "tickets_empty": "Пока нет тикетов. Создайте первый!",
        "tickets_title_client": "Ваши тикеты:",
        "tickets_title_support": "Тикеты вашего workspace:",
        "ticket_row": "#{id} {status_emoji} {subject}",
        "ticket_card": (
            "Тикет #{ticket_id}\n"
            "Тема: {subject}\n"
            "Категория: {category}\n"
            "Статус: {status}\n"
            "Приоритет: {priority}\n"
            "Заказ: {order}\n"
            "Создан: {created_at}\n\n"
            "Описание:\n{description}"
        ),
        "category_question": "Вопрос",
        "category_bug": "Ошибка",
        "category_support": "Поддержка",
        "category_general": "Общее",
        "ticket_order_none": "не привязан",
        "page_info": "Стр. {page}/{pages}",
        "btn_prev": "⬅️",
        "btn_next": "➡️",
        # messages & attachments
        "reply_prompt": "Введите сообщение для тикета #{ticket_id}.\n/cancel — отменить",
        "reply_sent": "Сообщение добавлено.",
        "attachment_saved": "📎 Вложение сохранено: {file_name} ({size})",
        "attachments_list": "Вложения: {items}",
        "no_attachments": "Вложений нет.",
        # statuses
        "status_new": "Новый",
        "status_in_progress": "В работе",
        "status_waiting_client": "Ждёт ответа клиента",
        "status_resolved": "Решён",
        "status_closed": "Закрыт",
        "status_changed": "Статус тикета #{ticket_id}: {status}",
        "close_confirm": "Закрыть тикет #{ticket_id}? После закрытия его нельзя изменить.",
        "ticket_closed": "Тикет #{ticket_id} закрыт.",
        # feedback
        "feedback_prompt_rating": "Оцените работу поддержки от 1 до 5 ⭐",
        "feedback_prompt_comment": "Напишите короткий отзыв (или /skip — без комментария).",
        "feedback_saved": "Спасибо за отзыв!",
        "feedback_not_closed": "Оставить отзыв можно только после закрытия тикета.",
        "feedback_exists": "Отзыв на этот тикет уже оставлен.",
        "feedback_skipped": "Отзыв сохранён без комментария.",
        # errors
        "err_access": "У вас нет доступа к этому действию.",
        "err_transition": "Такой переход статуса недопустим.",
        "err_session_expired": "Сессия роли истекла. Выберите роль заново.",
        "err_workspace_expired": "Workspace устарел и будет удалён. Начните с /start.",
        "err_validation": "Проверьте введённые данные: {detail}",
        "err_attachment_limit": ("Вложение отклонено: {detail}. Разрешённые типы: {types}"),
        "err_internal": "Что-то пошло не так. Попробуйте позже.",
        "err_rate_limited": "Слишком много действий. Подождите немного.",
        # notes
        "btn_view_notes": "📝 Заметки",
        "btn_add_note": "➕ Добавить заметку",
        "btn_back_card": "⬅️ К карточке",
        "notes_title": "Внутренние заметки (клиент их не видит):",
        "notes_empty": "Заметок пока нет.",
        "note_row": "[{created_at}] {body}",
        # workspace reset
        "new_workspace_confirm": (
            "Создать новый workspace? Текущий будет удалён безвозвратно "
            "(тикеты, сообщения, отзывы)."
        ),
        "workspace_reset": "Создан новый пустой workspace.",
    },
    "en": {
        "welcome": (
            "👋 Welcome to the Telegram CRM demo!\n\n"
            "This is an isolated sandbox: you create tickets as a client and "
            "handle them yourself as a support agent.\n\nPick a language and a role."
        ),
        "choose_language": "Choose language / Выберите язык:",
        "choose_role": "Whom do you want to play in this demo?",
        "role_client": "🧑‍💼 I'm a client",
        "role_support": "🛠 I'm a support agent",
        "role_switched": "You are now: {role}.",
        "menu": "Menu",
        "btn_my_tickets": "My tickets",
        "btn_ticket_queue": "Ticket queue",
        "btn_new_ticket": "➕ New ticket",
        "btn_catalog": "🛍 Services",
        "btn_my_orders": "📦 My orders",
        "btn_orders": "📦 Workspace orders",
        "btn_priority": "⚑ Priority",
        "btn_note": "📝 Internal note",
        "btn_ticket_for_order": "💬 Ticket for this order",
        "ticket_category": "Choose a category: question, bug, or support.",
        "note_prompt": "Type an internal note. The client cannot see it.",
        "note_saved": "Internal note saved.",
        "catalog": "Choose a service:",
        "order_description": "Describe the task for this order.",
        "order_created": "Order #{order_id} created.",
        "orders_empty": "No orders yet.",
        "order_card": "Order #{id}\nService: {service}\nStatus: {status}\nPriority: {priority}\n\n{description}",
        "order_new": "New",
        "order_clarification": "Clarification",
        "order_accepted": "Accepted",
        "order_in_progress": "In progress",
        "order_review": "Review",
        "order_completed": "Completed",
        "order_cancelled": "Cancelled",
        "priority_low": "Low",
        "priority_normal": "Normal",
        "priority_high": "High",
        "btn_switch_role": "🔄 Switch role",
        "btn_settings": "⚙️ Settings",
        "btn_language": "🌐 Language",
        "btn_exit": "Leave role",
        "btn_new_workspace": "🗑 New workspace",
        "btn_reply": "💬 Reply",
        "btn_feedback": "⭐ Feedback",
        "btn_back_menu": "⬅️ Menu",
        "exit_confirm": "Leave the current role? Workspace data will be kept.",
        "btn_yes": "Yes",
        "btn_no": "No",
        "exited": "You left the role. Pick a role again for your next action.",
        "ticket_subject_prompt": "Enter a short ticket subject (max 200 chars).\n/cancel to abort",
        "ticket_description_prompt": "Now describe the issue in detail.\n/cancel to abort",
        "ticket_attach_prompt": "Optionally attach files (up to {max_files}, {max_size} each).\nSend files or press “Done”.",
        "btn_done_attachments": "✅ Done",
        "ticket_created": "Ticket #{ticket_id} created: “{subject}”.",
        "ticket_cancelled": "Ticket creation cancelled.",
        "cancel_not_in_form": "Nothing to cancel right now.",
        "tickets_empty": "No tickets yet. Create the first one!",
        "tickets_title_client": "Your tickets:",
        "tickets_title_support": "Tickets in your workspace:",
        "ticket_row": "#{id} {status_emoji} {subject}",
        "ticket_card": (
            "Ticket #{ticket_id}\n"
            "Subject: {subject}\n"
            "Category: {category}\n"
            "Status: {status}\n"
            "Priority: {priority}\n"
            "Order: {order}\n"
            "Created: {created_at}\n\n"
            "Description:\n{description}"
        ),
        "category_question": "Question",
        "category_bug": "Bug",
        "category_support": "Support",
        "category_general": "General",
        "ticket_order_none": "not linked",
        "page_info": "Page {page}/{pages}",
        "btn_prev": "⬅️",
        "btn_next": "➡️",
        "reply_prompt": "Type a message for ticket #{ticket_id}.\n/cancel to abort",
        "reply_sent": "Message added.",
        "attachment_saved": "📎 Attachment saved: {file_name} ({size})",
        "attachments_list": "Attachments: {items}",
        "no_attachments": "No attachments.",
        "status_new": "New",
        "status_in_progress": "In progress",
        "status_waiting_client": "Waiting for client",
        "status_resolved": "Resolved",
        "status_closed": "Closed",
        "status_changed": "Ticket #{ticket_id} status: {status}",
        "close_confirm": "Close ticket #{ticket_id}? It becomes read-only after closing.",
        "ticket_closed": "Ticket #{ticket_id} closed.",
        "feedback_prompt_rating": "Rate the support experience, 1 to 5 ⭐",
        "feedback_prompt_comment": "Write a short review (or /skip for none).",
        "feedback_saved": "Thanks for your feedback!",
        "feedback_not_closed": "Feedback is possible only after the ticket is closed.",
        "feedback_exists": "Feedback for this ticket already exists.",
        "feedback_skipped": "Feedback saved without a comment.",
        "err_access": "You don't have access to this action.",
        "err_transition": "That status transition is not allowed.",
        "err_session_expired": "Your role session expired. Pick a role again.",
        "err_workspace_expired": "Workspace expired and will be removed. Start with /start.",
        "err_validation": "Check your input: {detail}",
        "err_attachment_limit": "Attachment rejected: {detail}. Allowed types: {types}",
        "err_internal": "Something went wrong. Please try again later.",
        "err_rate_limited": "Too many actions. Please wait a moment.",
        "btn_view_notes": "📝 Notes",
        "btn_add_note": "➕ Add note",
        "btn_back_card": "⬅️ Back to card",
        "notes_title": "Internal notes (hidden from the client):",
        "notes_empty": "No notes yet.",
        "note_row": "[{created_at}] {body}",
        "new_workspace_confirm": (
            "Create a new workspace? The current one (tickets, messages, reviews) "
            "will be deleted permanently."
        ),
        "workspace_reset": "A new empty workspace was created.",
    },
}

ROLE_NAMES: dict[str, dict[str, str]] = {
    "ru": {"client": "клиент", "support": "сотрудник"},
    "en": {"client": "client", "support": "support agent"},
}

STATUS_EMOJI: dict[str, str] = {
    "new": "🆕",
    "in_progress": "🔧",
    "waiting_client": "⏳",
    "resolved": "✅",
    "closed": "🔒",
}


def t(lang: str, key: str, **kwargs: object) -> str:
    """Translate ``key`` into ``lang`` and format with kwargs. Falls back to EN."""
    table = MESSAGES.get(lang) or MESSAGES["en"]
    template = table.get(key) or MESSAGES["en"].get(key) or key
    return template.format(**kwargs) if kwargs else template
