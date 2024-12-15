from fastapi import Header
from pydantic import BaseModel
from typing import Any, Annotated

class Response(BaseModel):
    error: str | None
    status: dict[str, int | str]

class Message(BaseModel):
    
    key: str
    value: Any | None
    type: str | None
    expiry: int | None
    salt: str | None

class User(BaseModel):

    userName: str
    password: str

class Auth(BaseModel):

    token: Annotated[str, Header()]
