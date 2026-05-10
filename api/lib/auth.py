from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from uuid import UUID as PythonUUID
from jwt import PyJWKClient
import jwt
import os
from typing import Callable

security = HTTPBearer()


class CurrentUser(BaseModel):
    """Represent the authenticated user context."""
    id: PythonUUID
    email: str
    role: str
    first_name: str | None = None
    last_name: str | None = None


_supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
# Initialise at module level so PyJWKClient can cache the public key across requests.
_jwks_client = PyJWKClient(
    f"{_supabase_url}/auth/v1/.well-known/jwks.json"
) if _supabase_url else None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    """Verify the Supabase ES256 JWT and return the authenticated user."""
    if _jwks_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_URL not configured on server",
        )

    token = credentials.credentials

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
            # Allow 60 seconds of clock skew between Supabase and this server.
            leeway=60,
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    email = payload.get("email")
    user_metadata = payload.get("user_metadata", {})
    role = user_metadata.get("role")
    first_name = user_metadata.get("first_name")
    last_name = user_metadata.get("last_name")

    if not user_id or not email or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required user claims",
        )

    return CurrentUser(
        id=user_id,
        email=email,
        role=role,
        first_name=first_name,
        last_name=last_name,
    )


def require_role(required_role: str) -> Callable:
    """Return a dependency that enforces the required role on the current user."""
    def role_checker(current_user: CurrentUser = Depends(get_current_user)):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {required_role}",
            )
        return current_user

    return role_checker