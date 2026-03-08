"""Authentication router with database-backed auth and API key management."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from api.database.supabase_manager import db
from metivta_eval.config.toml_config import config

router = APIRouter()


class UserCreate(BaseModel):
    """User registration request."""

    email: EmailStr
    name: str = Field(..., min_length=2, max_length=255)
    organization: str | None = Field(None, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """Ensure password meets minimum complexity requirements."""
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one digit")
        return value


class UserResponse(BaseModel):
    """User response model."""

    id: UUID
    email: str
    name: str
    organization: str | None
    role: str
    created_at: datetime


class LoginRequest(BaseModel):
    """Login request model."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Bearer token response model."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class APIKeyCreate(BaseModel):
    """API key create request model."""

    name: str = Field(..., min_length=1, max_length=255)
    scopes: list[str] = Field(default=["eval:read", "eval:write"])
    expires_in_days: int | None = Field(None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """API key metadata response model."""

    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None


class APIKeyCreatedResponse(BaseModel):
    """Response returned when a key is created."""

    id: UUID
    name: str
    key: str
    key_prefix: str
    scopes: list[str]
    created_at: datetime
    expires_at: datetime | None
    message: str = "Save this key securely - it will not be shown again!"


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> dict:
    """Resolve authenticated user from bearer token or API key."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        user = db.get_user_from_access_token(token)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
            )
        return user

    if x_api_key:
        if not x_api_key.startswith(config.security.api_keys.prefix):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key format",
            )
        principal = db.validate_api_key(x_api_key)
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

        user = db.get_user_by_id(principal["user_id"])
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown API key owner",
            )
        user["api_key_id"] = principal["api_key_id"]
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_admin(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    """Ensure user has admin role."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register_user(user_data: UserCreate) -> UserResponse:
    """Register a user account."""
    try:
        user = db.register_user(
            email=str(user_data.email),
            name=user_data.name,
            organization=user_data.organization,
            password=user_data.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from exc

    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        organization=user["organization"],
        role=user["role"],
        created_at=user["created_at"],
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get access token",
)
async def login(credentials: LoginRequest) -> TokenResponse:
    """Login with email/password and return session tokens."""
    result = db.login_user(email=str(credentials.email), password=credentials.password)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    tokens = result["tokens"]
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        expires_in=tokens["expires_in"],
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh_access_token(
    refresh_token: str = Header(..., alias="X-Refresh-Token"),
) -> TokenResponse:
    """Rotate refresh token and return a new session pair."""
    tokens = db.refresh_user_session(refresh_token)
    if tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        expires_in=tokens["expires_in"],
    )


@router.post(
    "/api-keys",
    response_model=APIKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API key",
)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> APIKeyCreatedResponse:
    """Create a new API key for the current user."""
    api_key = db.create_scoped_api_key(
        user_id=current_user["id"],
        name=key_data.name,
        scopes=key_data.scopes,
        expires_in_days=key_data.expires_in_days,
    )

    return APIKeyCreatedResponse(
        id=api_key["id"],
        name=api_key["name"],
        key=api_key["key"],
        key_prefix=api_key["key_prefix"],
        scopes=api_key["scopes"],
        created_at=api_key["created_at"],
        expires_at=api_key["expires_at"],
    )


@router.get(
    "/api-keys",
    response_model=list[APIKeyResponse],
    summary="List API keys",
)
async def list_api_keys(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> list[APIKeyResponse]:
    """List API keys for current user."""
    keys = db.list_user_api_keys(current_user["id"])
    return [
        APIKeyResponse(
            id=entry["id"],
            name=entry["name"],
            key_prefix=entry["key_prefix"],
            scopes=entry["scopes"],
            created_at=entry["created_at"],
            expires_at=entry["expires_at"],
            last_used_at=entry["last_used_at"],
        )
        for entry in keys
    ]


@router.delete(
    "/api-keys/{key_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
)
async def revoke_api_key(
    key_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    """Revoke one API key owned by the current user."""
    revoked = db.revoke_user_api_key(current_user["id"], str(key_id))
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
)
async def get_me(current_user: Annotated[dict, Depends(get_current_user)]) -> UserResponse:
    """Return profile of the current user."""
    created_at = current_user.get("created_at")
    if created_at is None:
        created_at = datetime.now(UTC)

    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        organization=current_user.get("organization"),
        role=current_user.get("role", "user"),
        created_at=created_at,
    )
