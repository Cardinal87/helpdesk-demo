"""Order catalogue and intake use cases, reusable by a future Mini App."""

from datetime import UTC, datetime

from app.application.context import Services
from app.application.session_usecases import get_actor_context
from app.domain import access
from app.domain.entities import Order, Service
from app.domain.errors import AccessDeniedError, InvalidTransitionError, ValidationError
from app.domain.order import OrderStatus, Priority
from app.domain.ticket import Role


async def list_services(svc: Services) -> list[Service]:
    return await svc.orders.services()


async def create_order(svc: Services, telegram_id: int, service_id: int, description: str) -> Order:
    ctx = await get_actor_context(svc, telegram_id)
    access.require_role(access.require_active_session(ctx.session, datetime.now(UTC)), Role.CLIENT)
    description = description.strip()
    if not description or len(description) > svc.settings.text_max_length:
        raise ValidationError("order description must be non-empty and within the limit")
    service = await svc.orders.service(service_id)
    if service is None:
        raise AccessDeniedError("service unavailable")
    order = await svc.orders.create(ctx.workspace.id, telegram_id, service, description)
    await svc.workspaces.touch(ctx.workspace.id, svc.settings.workspace_ttl_seconds)
    await svc.audit.record(
        workspace_id=ctx.workspace.id,
        actor_telegram_id=telegram_id,
        event="order.created",
        payload=f'{{"order_id":{order.id}}}',
    )
    return order


async def list_orders(svc: Services, telegram_id: int) -> list[Order]:
    ctx = await get_actor_context(svc, telegram_id)
    session = access.require_active_session(ctx.session, datetime.now(UTC))
    return await svc.orders.list_page(
        ctx.workspace.id, telegram_id if session.role is Role.CLIENT else None
    )


async def change_order_status(
    svc: Services, telegram_id: int, order_id: int, target: OrderStatus
) -> Order:
    ctx = await get_actor_context(svc, telegram_id)
    session = access.require_active_session(ctx.session, datetime.now(UTC))
    access.require_role(session, Role.SUPPORT)
    order = await svc.orders.get(order_id, ctx.workspace.id)
    if order is None:
        raise AccessDeniedError("order not found")
    from app.domain.order import is_order_transition_allowed

    if not is_order_transition_allowed(order.status, target):
        raise InvalidTransitionError(f"{order.status.value} -> {target.value}")
    await svc.orders.set_status(order_id, ctx.workspace.id, target)
    return (await svc.orders.get(order_id, ctx.workspace.id)) or order


async def change_order_priority(
    svc: Services, telegram_id: int, order_id: int, priority: Priority
) -> Order:
    ctx = await get_actor_context(svc, telegram_id)
    session = access.require_active_session(ctx.session, datetime.now(UTC))
    access.require_role(session, Role.SUPPORT)
    order = await svc.orders.get(order_id, ctx.workspace.id)
    if order is None:
        raise AccessDeniedError("order not found")
    await svc.orders.set_priority(order_id, ctx.workspace.id, priority)
    return (await svc.orders.get(order_id, ctx.workspace.id)) or order


async def add_order_note(svc: Services, telegram_id: int, order_id: int, body: str) -> None:
    ctx = await get_actor_context(svc, telegram_id)
    access.require_role(access.require_active_session(ctx.session, datetime.now(UTC)), Role.SUPPORT)
    if not body.strip() or len(body) > svc.settings.text_max_length:
        raise ValidationError("invalid internal note")
    if await svc.orders.get(order_id, ctx.workspace.id) is None:
        raise AccessDeniedError("order not found")
    await svc.orders.add_note(ctx.workspace.id, telegram_id, order_id, body.strip())
