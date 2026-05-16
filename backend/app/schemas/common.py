from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Standard success message envelope used for operations with no body."""
    message: str


class ErrorResponse(BaseModel):
    """Standard error envelope — mirrors AppException.to_dict()."""
    error: str
    message: str