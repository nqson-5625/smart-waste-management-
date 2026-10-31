"""HTTP endpoints for /auth."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..core.security import current_user
from ..services import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


@router.post("/login")
def login(body: LoginIn):
    return auth_service.login(body.email, body.password)


@router.get("/me")
def me(user=Depends(current_user)):
    return auth_service.public_user(user)
