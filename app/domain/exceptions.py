class DomainError(Exception):
    """Base exception for domain rule violations."""


class ReservationRuleError(DomainError):
    """Raised when reservation invariants are violated."""


class ReservationConflictError(DomainError):
    """Raised when reservation timing conflicts with existing booking."""
