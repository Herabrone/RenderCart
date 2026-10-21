from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    turnstile_token: str | None = Field(default=None, max_length=2048)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    totp_code: str | None = Field(default=None, min_length=6, max_length=64)


class EmailRequest(BaseModel):
    email: EmailStr


class TokenRequest(BaseModel):
    token: str


class MagicSignInRequest(BaseModel):
    token: str
    totp_code: str | None = Field(default=None, min_length=6, max_length=64)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=256)


class TotpConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=64)


class UserResponse(BaseModel):
    id: str
    email: str
    email_verified: bool
    display_name: str | None
    staff_role: str
    totp_enabled: bool = False
    mfa_verified: bool = True
