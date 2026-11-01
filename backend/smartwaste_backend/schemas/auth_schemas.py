"""Request/response models for /auth."""

from pydantic import BaseModel, Field, field_validator


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class UserPublic(BaseModel):
    id: str
    display_name: str
    roles: list[str]


class LoginOut(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserPublic


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def fits_bcrypt(cls, value):
        if len(value.encode()) > 72:
            raise ValueError("mật khẩu tối đa 72 byte")
        return value


class OkOut(BaseModel):
    ok: bool
