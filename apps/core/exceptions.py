class DomainError(Exception):
    """
    Base exception for business/domain errors.
    """
    def __init__(self, message: str, code: str = "domain_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationError(DomainError):
    """
    Business validation failed.
    """
    def __init__(self, message: str, code: str = "validation_failed"):
        super().__init__(message, code)


class PermissionDenied(DomainError):
    """
    Actor is not allowed to perform the operation.
    """
    def __init__(self, message: str, code: str = "permission_not_allowed"):
        super().__init__(message, code)


class ConflictError(DomainError):
    """
    Operation conflicts with existing system state.
    """
    def __init__(self, message: str, code: str = "state_conflict"):
        super().__init__(message, code)


class NotFoundError(DomainError):
    """
    Required domain object does not exist.
    """
    def __init__(self, message: str, code: str = "not_found"):
        super().__init__(message, code)