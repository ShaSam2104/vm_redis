from typing import Any
from pydantic import BaseModel

class Response(BaseModel):
    error: str | None
    status: dict[str, int | str]

class Message(BaseModel):
    
    key: str | None
    value: Any
    type: str | None

class Auth(BaseModel):

    pk: str
    hash: str
    salt: str
