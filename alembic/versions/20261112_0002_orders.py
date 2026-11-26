"""Add catalogue, orders, ticket linkage and internal notes."""

import sqlalchemy as sa

from alembic import op

revision = "20261112_0002"
down_revision = "20261110_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_from", sa.String(80), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("customer_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("service_title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_orders_workspace_id", "orders", ["workspace_id"])
    op.create_index("ix_orders_customer_telegram_id", "orders", ["customer_telegram_id"])
    op.create_index(
        "ix_orders_workspace_status_updated", "orders", ["workspace_id", "status", "updated_at"]
    )
    op.add_column("tickets", sa.Column("order_id", sa.Integer(), nullable=True))
    op.add_column(
        "tickets", sa.Column("category", sa.String(64), nullable=False, server_default="general")
    )
    op.add_column(
        "tickets", sa.Column("priority", sa.String(16), nullable=False, server_default="normal")
    )
    op.create_foreign_key(
        "fk_tickets_order", "tickets", "orders", ["order_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_tickets_order_id", "tickets", ["order_id"])
    op.create_table(
        "internal_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("ticket_id IS NOT NULL OR order_id IS NOT NULL", name="ck_note_target"),
    )
    op.create_index("ix_internal_notes_workspace_id", "internal_notes", ["workspace_id"])
    op.create_index("ix_internal_notes_ticket_id", "internal_notes", ["ticket_id"])
    op.create_index("ix_internal_notes_order_id", "internal_notes", ["order_id"])
    op.bulk_insert(
        sa.table(
            "services",
            sa.column("code"),
            sa.column("title"),
            sa.column("description"),
            sa.column("price_from"),
        ),
        [
            {
                "code": "telegram_bot",
                "title": "Telegram-бот",
                "description": "Разработка бота под ключ.",
                "price_from": "от 2 500 ₽",
            },
            {
                "code": "vps_setup",
                "title": "Настройка VPS",
                "description": "Развёртывание, Docker и базовая настройка сервера.",
                "price_from": "от 2 000 ₽",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("internal_notes")
    op.drop_index("ix_tickets_order_id", table_name="tickets")
    op.drop_constraint("fk_tickets_order", "tickets", type_="foreignkey")
    op.drop_column("tickets", "priority")
    op.drop_column("tickets", "category")
    op.drop_column("tickets", "order_id")
    op.drop_table("orders")
    op.drop_table("services")
