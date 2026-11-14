"""HTTP endpoints for /auth."""

from fastapi import APIRouter, Depends, Request

from ..core.security import current_user
from ..schemas.auth_schemas import ChangePasswordIn, LoginIn, LoginOut, OkOut, UserPublic
from ..services import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn):
    return auth_service.login(body.email, body.password)


@router.get("/me", response_model=UserPublic)
def me(user=Depends(current_user)):
    return auth_service.public_user(user)


@router.post("/change-password", response_model=OkOut)
def change_password(body: ChangePasswordIn, request: Request, user=Depends(current_user)):
    return auth_service.change_password(user, body.current_password, body.new_password,
                                        request.state.request_id)
