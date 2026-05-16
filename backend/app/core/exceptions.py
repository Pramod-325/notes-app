"""
Custom exception hierarchy.

All application exceptions inherit from AppException.
A single FastAPI exception handler in main.py catches every AppException
and converts it to a structured JSON response — no scattered HTTPException
calls throughout the codebase.

Hierarchy:
    AppException (base)
    ├── NotFoundError         → 404
    ├── ConflictError         → 409
    ├── GoneError             → 410  (soft-deleted resource)
    ├── UnauthorizedError     → 401
    ├── ForbiddenError        → 403
    ├── ValidationError       → 422
    └── PayloadTooLargeError  → 413
"""


class AppException(Exception):
    """Base class for all application-level exceptions."""

    status_code: int = 500
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, detail: str | None = None) -> None:
        self.message = message or self.default_message
        # `detail` carries extra diagnostic info (logged server-side, NOT sent to client)
        self.detail = detail
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Serialise to the standard error envelope sent to clients."""
        return {"error": self.__class__.__name__, "message": self.message}


class NotFoundError(AppException):
    status_code = 404
    default_message = "The requested resource was not found."


class ConflictError(AppException):
    status_code = 409
    default_message = "A conflict occurred with the current state of the resource."


class GoneError(AppException):
    """
    Returned when a resource existed but was soft-deleted.
    Distinguishes a 'never existed' (404) from a 'was deleted' (410),
    which directly handles the Delete/Update collision edge case.
    """

    status_code = 410
    default_message = "This resource has been permanently deleted."


class UnauthorizedError(AppException):
    """
    Authentication failure — missing or invalid credentials.
    Always returns a generic message to prevent user enumeration.
    """

    status_code = 401
    default_message = "Authentication required."


class ForbiddenError(AppException):
    """
    Authorisation failure — authenticated but not permitted.
    Returns 403, NOT 404, so the caller knows the resource exists
    but they don't have access (better UX, same security posture).
    """

    status_code = 403
    default_message = "You do not have permission to perform this action."


class ValidationError(AppException):
    status_code = 422
    default_message = "Request validation failed."


class PayloadTooLargeError(AppException):
    status_code = 413
    default_message = "The request payload exceeds the allowed size limit."


class ServiceUnavailableError(AppException):
    """Raised when an upstream dependency (e.g. DB) is unreachable."""

    status_code = 503
    default_message = "The service is temporarily unavailable. Please try again later."