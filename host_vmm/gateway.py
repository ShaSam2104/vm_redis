import auth
from typing import Union
from fastapi import FastAPI
from models import Response, User, Auth, Message

app = FastAPI()

@app.post("/signin/")
async def signIn(authMethod: Union[Auth, User]) -> Response:

    if isinstance(authMethod, Auth):

        await auth.verifyToken(authMethod.token)

    elif isinstance(authMethod, User):
        
        await auth.verifyUser(authMethod.userName, authMethod.password)

    raise NotImplementedError()

@app.post("/signup/")
async def signUp(message: Message) -> Response:
    raise NotImplementedError()

