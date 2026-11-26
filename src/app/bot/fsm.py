"""FSM states for the multi-step flows. Every state supports /cancel."""

from aiogram.fsm.state import State, StatesGroup


class StartStates(StatesGroup):
    choose_language = State()
    choose_role = State()


class TicketCreateStates(StatesGroup):
    category = State()
    subject = State()
    description = State()
    attachments = State()  # optional files; "Done" finishes creation


class OrderCreateStates(StatesGroup):
    description = State()


class NoteStates(StatesGroup):
    body = State()


class ReplyStates(StatesGroup):
    waiting_message = State()


class FeedbackStates(StatesGroup):
    waiting_rating = State()
    waiting_comment = State()


class ConfirmStates(StatesGroup):
    """Dangerous operations: exit role, close ticket, reset workspace."""

    pending = State()
