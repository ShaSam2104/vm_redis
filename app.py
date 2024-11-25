from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Dict, Optional, Union, Set
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime, timedelta
import logging
import base64
import mimetypes
import os
from fastapi.middleware.cors import CORSMiddleware
import io
import json
from typing import Any, Union,Dict, Optional, Set

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS: Set[str] = {'.txt', '.pdf', '.doc', '.docx', '.zip', '.png', '.jpg', '.jpeg'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit
# In-memory storage for user dictionaries
user_data: Dict[str, Dict[str, Dict[str, Union[str, bytes, Optional[datetime]]]]] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to specific IPs in production
    allow_credentials=True,
    allow_methods=["*"],
)

config = {
    "dir": "/tmp",
    "dbfilename": "dump.rdb",
    "port": "6379",
    "replicaof": "",
    "master_replid": "8371b4fb1155b71f4a04d3e1bc3e18c4a990aeeb",
    "master_repl_offset": "0",
}

class SetRequest(BaseModel):
    key: str
    value: Any
    type: Optional[str] = None  # Add type field
    expiry: Optional[int] = None  # Expiry time in seconds

@app.post("/user/{user_id}/ping")
async def ping(user_id: str):
    if user_id not in user_data:
        user_data[user_id] = {}
    return {"response": "PONG"}

@app.post("/user/{user_id}/echo")
async def echo(user_id: str, message: str):
    if user_id not in user_data:
        user_data[user_id] = {}
    return {"response": message}

@app.post("/user/{user_id}/set")
async def set_value(user_id: str, request: SetRequest):
    if user_id not in user_data:
        user_data[user_id] = {}
    
    try:
        # Convert value based on specified type
        converted_value = request.value
        if request.type:
            if request.type == "int":
                converted_value = int(request.value)
            elif request.type == "float":
                converted_value = float(request.value)
            elif request.type == "bool":
                converted_value = bool(request.value)
            elif request.type == "list":
                converted_value = json.loads(request.value) if isinstance(request.value, str) else request.value
            elif request.type == "dict":
                converted_value = json.loads(request.value) if isinstance(request.value, str) else request.value
        
        value_type = request.type or type(converted_value).__name__
        expiry_time = datetime.utcnow() + timedelta(seconds=request.expiry) if request.expiry else None
        
        user_data[user_id][request.key] = {
            "value": converted_value,
            "expiry": expiry_time,
            "type": value_type
        }
        return {"response": "OK", "type": value_type}
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Type conversion error: {str(e)}")

@app.post("/user/{user_id}/setfile")
async def set_file(user_id: str, key: str = Form(...), file: UploadFile = File(...), expiry: Optional[int] = Form(None)):
    try:
        if user_id not in user_data:
            user_data[user_id] = {}
        
        file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ''
        content_type = file.content_type or mimetypes.guess_type(file.filename)[0]
        
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File size exceeds {MAX_FILE_SIZE/1024/1024}MB limit")
        
        expiry_time = datetime.utcnow() + timedelta(seconds=expiry) if expiry else None
        encoded_content = base64.b64encode(content).decode('utf-8')
        
        user_data[user_id][key] = {
            "value": encoded_content,
            "expiry": expiry_time,
            "type": "binary",
            "content_type": content_type,
            "extension": file_ext,
            "original_filename": file.filename
        }
        return {"response": "OK"}
        
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/user/{user_id}/get")
async def get_value(user_id: str, key: str):
    if user_id not in user_data:
        raise HTTPException(status_code=404, detail="User not found")
    if key not in user_data[user_id]:
        raise HTTPException(status_code=404, detail="Key not found")
    
    data = user_data[user_id][key]
    if data["expiry"] and data["expiry"] < datetime.utcnow():
        del user_data[user_id][key]
        raise HTTPException(status_code=404, detail="Key expired")
    
    return {"value": data["value"], "type": data.get("type", "text")}

@app.get("/user/{user_id}/keys")
async def get_keys(user_id: str):
    if user_id not in user_data:
        raise HTTPException(status_code=404, detail="User not found")
    return {"keys": list(user_data[user_id].keys())}

@app.get("/info")
async def get_info():
    info = {
        "server": "FastAPI Server",
        "version": "1.0.0",
        "users_count": len(user_data),
    }
    return info

@app.post("/config")
async def config_command(command: str, value: str):
    if command.lower() == "set":
        config[command] = value
        return {"response": "OK"}
    else:
        raise HTTPException(status_code=400, detail="Invalid CONFIG command")

@app.post("/psync")
async def psync_command(replica_id: str, offset: int):
    # Simulate PSYNC command handling
    return {"response": f"FULLRESYNC {replica_id} {offset}"}

@app.get("/users")
async def get_all_users():
    return user_data

@app.post("/user/{user_id}/getfile")
async def get_file(user_id: str, key: str):
    try:
        # Check if user and key exist
        if user_id not in user_data:
            raise HTTPException(status_code=404, detail="User not found")
        if key not in user_data[user_id]:
            raise HTTPException(status_code=404, detail="File not found")
        
        data = user_data[user_id][key]
        
        # Check expiry
        if data["expiry"] and data["expiry"] < datetime.utcnow():
            del user_data[user_id][key]
            raise HTTPException(status_code=404, detail="File expired")
        
        # Decode file content
        try:
            content = base64.b64decode(data["value"])
            return StreamingResponse(io.BytesIO(content), media_type=data.get("content_type", "application/octet-stream"), headers={
                "Content-Disposition": f"attachment; filename={data.get('original_filename', key)}"
            })
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving file: {str(e)}"
            )
            
    except Exception as e:
        logger.error(f"Error in get_file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}"
        )   

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)