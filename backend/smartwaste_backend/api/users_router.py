"""HTTP endpoints for /users: the admin manages admin and collector accounts."""

from typing import Literal

from fastapi import APIRouter, Depends, Request

from ..core.common import Limit
from ..core.security import require_roles
from ..schemas.users_schemas import Role, UserCreate, UserOut, UserUpdate
from ..services import users_service


router = APIRouter(prefix="/users", tags=["users"])
admin_only = require_roles("admin")


@router.post("", status_code=201, response_model=UserOut)
def create_user(body: UserCreate, request: Request, user=Depends(admin_only)):
    return users_service.create_user(body, user, request.state.request_id)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, request: Request, user=Depends(admin_only)):
    """Partial update; also how the admin resets a forgotten password or disables an account."""
    return users_service.update_user(user_id, body, user, request.state.request_id)


@router.get("")
def list_users(
    role: Role | None = None,
    status: Literal["pending", "active", "disabled"] | None = None,
    limit: int = Limit,
    cursor: str | None = None,
    user=Depends(admin_only),
):
    return users_service.list_users(role, status, limit, cursor)
