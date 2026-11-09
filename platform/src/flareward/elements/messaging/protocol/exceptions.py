"""
IEM Protocol Exceptions
"""


class IEMException(Exception):
    """Base exception for IEM protocol errors."""

    pass


class IEMTimeoutException(IEMException):
    """Raised when a request times out waiting for response."""

    pass


class IEMValidationException(IEMException):
    """Raised when packet validation fails."""

    pass


class IEMAdjacencyException(IEMException):
    """Raised when attempting to send to non-adjacent node."""

    pass


class IEMPermissionException(IEMException):
    """Raised when lacking permission for an action."""

    pass
