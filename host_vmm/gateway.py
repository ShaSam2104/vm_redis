from fastapi import FastAPI
from models import Response, Message

app = FastAPI()

@app.post("/ping/")
async def ping():
    raise NotImplementedError()

@app.post("/echo/")
async def echo(message: Message):
    raise NotImplementedError()
