class ApplicationError(Exception):
    """Base exception for application layer."""


class NotFoundError(ApplicationError):
    """Raised when requested resource is not found."""


class ConflictError(ApplicationError):
    """Raised when command conflicts with existing state."""


class ValidationError(ApplicationError):
    """Raised when input breaks business or validation rules."""
