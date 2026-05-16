from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Returned on successful login or token refresh."""
    access_token: str
    token_type: str = "bearer"
    # Refresh token is set as an HttpOnly cookie — NOT in this body.
    # Exposing it in the JSON response body would make it accessible to JS,
    # defeating the purpose of HttpOnly.


class TokenPayload(BaseModel):
    """Decoded JWT claims — used internally by the auth dependency."""
    sub: str      # user UUID
    type: str     # "access"