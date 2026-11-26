"""Attachment validation: allowlist, per-file/per-ticket/per-workspace limits.

Called BEFORE any Attachment row is created (AGENTS.md): rejected files never
touch the DB. Telegram file_name is untrusted — only MIME and size decide.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.domain.errors import AttachmentLimitError


@dataclass(slots=True)
class IncomingFile:
    """Normalized view of a Telegram document/photo/video metadata."""

    file_id: str
    file_name: str
    mime_type: str
    size_bytes: int


def human_size(num: int) -> str:
    amount = float(num)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if amount < 1024 or unit == "GiB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.0f} B"


def validate_attachment(
    incoming: IncomingFile,
    *,
    settings: Settings,
    ticket_file_count: int,
    workspace_file_count: int,
    workspace_total_bytes: int,
) -> None:
    """Raise AttachmentLimitError with a user-safe detail string if over any limit."""
    if incoming.mime_type not in settings.mime_allowlist:
        raise AttachmentLimitError(f"mime type '{incoming.mime_type}' not allowed")
    if incoming.size_bytes <= 0:
        raise AttachmentLimitError("invalid file size")
    if incoming.size_bytes > settings.max_file_size_bytes:
        raise AttachmentLimitError(
            f"file too large ({human_size(incoming.size_bytes)}; "
            f"max {human_size(settings.max_file_size_bytes)})"
        )
    if ticket_file_count >= settings.max_files_per_ticket:
        raise AttachmentLimitError(f"ticket already has {settings.max_files_per_ticket} files")
    if workspace_file_count >= settings.max_workspace_total_files:
        raise AttachmentLimitError(
            f"workspace already has {settings.max_workspace_total_files} files"
        )
    if workspace_total_bytes + incoming.size_bytes > settings.max_workspace_total_size_bytes:
        raise AttachmentLimitError(
            f"workspace storage quota exceeded (max {human_size(settings.max_workspace_total_size_bytes)})"
        )


def sanitize_display_name(name: str) -> str:
    """Keep it short and free of control chars; never used for logic anyway."""
    cleaned = "".join(ch for ch in name if ch.isprintable()).strip() or "file"
    return cleaned[:255]
