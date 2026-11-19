"""Request/response models for /users."""

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
Role = Literal["admin", "collector"]  # the team dropped the dispatcher role; admin does it
UserStatus = Literal["active", "disabled"]


def _unique_roles(roles):
    if roles is not None and len(set(roles)) != len(roles):
        raise ValueError("roles không được lặp")
    return roles


def _fits_bcrypt(password):
    if password is not None and len(password.encode()) > 72:
        raise ValueError("mật khẩu tối đa 72 byte")
    return password


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=254, pattern=EMAIL_PATTERN)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=72)
    roles: list[Role] = Field(min_length=1, max_length=2)
    phone: str | None = Field(None, min_length=1, max_length=30)

    @field_validator("roles")
    @classmethod
    def roles_unique(cls, value):
        return _unique_roles(value)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value):
        return _fits_bcrypt(value)


class UserUpdate(BaseModel):
    """Partial update: only fields present in the request are changed."""

    model_config = ConfigDict(str_strip_whitespace=True)

    display_name: str | None = Field(None, min_length=1, max_length=120)
    roles: list[Role] | None = Field(None, min_length=1, max_length=2)
    status: UserStatus | None = None
    phone: str | None = Field(None, min_length=1, max_length=30)
    password: str | None = Field(None, min_length=8, max_length=72)

    NOT_NULL: ClassVar[tuple[str, ...]] = ("display_name", "roles", "status", "password")

    @field_validator("roles")
    @classmethod
    def roles_unique(cls, value):
        return _unique_roles(value)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value):
        return _fits_bcrypt(value)

    @model_validator(mode="after")
    def required_fields_not_null(self):
        for field in self.NOT_NULL:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} không được để trống")
        return self


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    roles: list[str]
    status: str
    phone: str | None
    last_login_at: str | None
    created_at: str
