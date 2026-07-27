from pydantic import BaseModel


class LoginRequest(BaseModel):
    password: str


class SetPasswordRequest(BaseModel):
    password: str
