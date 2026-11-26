"""Domain errors for the Telegram CRM demo."""


class DomainError(Exception):
    """Base class for all domain-level errors.

    Handlers must translate these into friendly, localized messages;
    internal details are never shown to the end user.
    """


class AccessDeniedError(DomainError):
    """Actor has no rights to the requested object (wrong role, foreign workspace...)."""


class InvalidTransitionError(DomainError):
    """Requested ticket status transition is not allowed by domain rules."""


class ValidationError(DomainError):
    """User input failed validation (too long, empty, bad format)."""


class AttachmentLimitError(ValidationError):
    """Attachment rejected by configured allowlist/size/count limits."""


class FeedbackAlreadyExistsError(DomainError):
    """Only one feedback per closed ticket is allowed."""


class WorkspaceExpiredError(DomainError):
    """Workspace TTL has elapsed; data is gone or going away."""


class NoActiveRoleError(DomainError):
    """The operation requires an active RoleSession, but none exists."""
