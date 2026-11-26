"""Initial demo CRM schema.

Revision ID: 20261110_0001
Revises:
Create Date: 2026-11-10 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20261110_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspaces_owner_telegram_id", "workspaces", ["owner_telegram_id"])
    op.create_index("ix_workspaces_last_activity_at", "workspaces", ["last_activity_at"])
    op.create_index("ix_workspaces_expires_at", "workspaces", ["expires_at"])
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("language", sa.String(5), nullable=False, server_default="ru"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_table(
        "role_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_role_sessions_workspace_id", "role_sessions", ["workspace_id"])
    op.create_index("ix_role_sessions_owner_telegram_id", "role_sessions", ["owner_telegram_id"])
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("assignee_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tickets_workspace_id", "tickets", ["workspace_id"])
    op.create_index("ix_tickets_author_telegram_id", "tickets", ["author_telegram_id"])
    op.create_index(
        "ix_tickets_customer_status_updated",
        "tickets",
        ["author_telegram_id", "status", "updated_at"],
    )
    op.create_index(
        "ix_tickets_assignee_status_updated",
        "tickets",
        ["assignee_telegram_id", "status", "updated_at"],
    )
    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("author_role", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_ticket_messages_ticket_id", "ticket_messages", ["ticket_id"])
    op.create_index(
        "ix_ticket_messages_ticket_created", "ticket_messages", ["ticket_id", "created_at"]
    )
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("ticket_messages.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("file_id", sa.String(512), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size_bytes > 0", name="ck_attachments_size_positive"),
    )
    op.create_index("ix_attachments_workspace_id", "attachments", ["workspace_id"])
    op.create_index("ix_attachments_ticket_id", "attachments", ["ticket_id"])
    op.create_index("ix_attachments_expires_at", "attachments", ["expires_at"])
    op.create_table(
        "feedbacks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("ticket_id", name="uq_feedback_one_per_ticket"),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_feedbacks_rating_range"),
    )
    op.create_index("ix_feedbacks_workspace_id", "feedbacks", ["workspace_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_events_workspace_id", "audit_events", ["workspace_id"])
    op.create_index("ix_audit_events_ticket_id", "audit_events", ["ticket_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("feedbacks")
    op.drop_table("attachments")
    op.drop_table("ticket_messages")
    op.drop_table("tickets")
    op.drop_table("role_sessions")
    op.drop_table("users")
    op.drop_table("workspaces")
