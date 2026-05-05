from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
import os
from typing import Callable

security = HTTPBearer()

class CurrentUser(BaseModel):
    id: str
    email: str
    role: str

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> CurrentUser:
    """
    Verifies the JWT token from the Authorization header and returns the current user.
    Designed for Supabase JWTs.
    """
    token = credentials.credentials
    secret = os.getenv("SUPABASE_JWT_SECRET")
    
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret not configured on server"
        )

    try:
        payload = jwt.decode(
            token, 
            secret, 
            algorithms=["HS256"], 
            audience="authenticated"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    # Extract claims based on Supabase JWT structure
    user_id = payload.get("sub")
    email = payload.get("email")
    user_metadata = payload.get("user_metadata", {})
    role = user_metadata.get("role")

    if not user_id or not email or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required user claims"
        )

    return CurrentUser(id=user_id, email=email, role=role)

def require_role(required_role: str) -> Callable:
    """
    Dependency factory that ensures the current user has the required role.
    """
    def role_checker(current_user: CurrentUser = Depends(get_current_user)):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {required_role}"
            )
        return current_user
    
    return role_checker
