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
from typing import Any, Union, Dict, Optional, Set
import pickle

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS: Set[str] = {'.txt', '.pdf', '.doc', '.docx', '.zip', '.png', '.jpg', '.jpeg'}
USER_SUBSCRIPTIONS = {
    'basic': {'storage_limit': 75_000_000},  # 75MB
    'premium': {'storage_limit': 150_000_000}  # 150MB
}
# In-memory storage for user dictionaries
# Add to user_data structure
user_data: Dict[str, Dict[str, Any]] = {
    # user_id: {
    #    'files': {...},
    #    'subscription': 'basic',
    #    'storage_used': 0
    # }
}
# Add at top of app.py with other constants
MAX_USERS = 10
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

def check_user_limit():
    if len(user_data) >= MAX_USERS:
        raise HTTPException(
            status_code=400,
            detail=f"Server user limit reached (max {MAX_USERS} users)"
        )

@app.post("/user/{user_id}/ping")
async def ping(user_id: str):
    if user_id not in user_data:
        check_user_limit()  # Check before creating new user
        user_data[user_id] = {'files': {}, 'subscription': 'basic', 'storage_used': 0}
    return {"response": "PONG"}

@app.post("/user/{user_id}/echo")
async def echo(user_id: str, message: str):
    if user_id not in user_data:
        user_data[user_id] = {}
    return {"response": message}

@app.post("/user/{user_id}/set")
async def set_value(user_id: str, request: SetRequest):
    if user_id not in user_data:
        check_user_limit()  # Check before creating new user
        user_data[user_id] = {'files': {}, 'subscription': 'basic', 'storage_used': 0}
    
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
    if user_id not in user_data:
        check_user_limit()  # Check before creating new user
        user_data[user_id] = {'files': {}, 'subscription': 'basic', 'storage_used': 0}
    elif 'files' not in user_data[user_id]:
        user_data[user_id]['files'] = {}
    
    content = await file.read()
    file_size = len(content)
    
    # Check storage limit
    subscription = user_data[user_id].get('subscription', 'basic')
    storage_limit = USER_SUBSCRIPTIONS[subscription]['storage_limit']
    current_usage = user_data[user_id].get('storage_used', 0)
    
    if current_usage + file_size > storage_limit:
        raise HTTPException(
            status_code=400, 
            detail=f"Storage limit exceeded. Available: {storage_limit - current_usage} bytes"
        )
    
    # Store file data
    content_b64 = base64.b64encode(content).decode()
    user_data[user_id]['files'][key] = {
        "value": content_b64,
        "type": "binary",
        "content_type": file.content_type,
        "original_filename": file.filename,
        "expiry": datetime.utcnow() + timedelta(seconds=expiry) if expiry else None
    }
    
    user_data[user_id]['storage_used'] = current_usage + file_size
    return {"response": "OK"}

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
    
    # Get keys from both regular values and files
    regular_keys = set(user_data[user_id].keys()) - {'files', 'storage_used', 'subscription'}
    file_keys = set(user_data[user_id].get('files', {}).keys())
    
    return {"keys": list(regular_keys | file_keys)}

@app.get("/info")
async def get_info():
    info = {
        "server": "FastAPI Server",
        "version": "1.0.0",
        "users_count": len(user_data),
    }
    return info
@app.delete("/user/{user_id}/key/{key}")
async def delete_key(user_id: str, key: str):
    if user_id not in user_data:
        raise HTTPException(status_code=404, detail="User not found")
    if key not in user_data[user_id]:
        raise HTTPException(status_code=404, detail="Key not found")
    
    del user_data[user_id][key]
    return {"response": f"Key '{key}' deleted successfully"}

@app.delete("/user/{user_id}")
async def delete_user(user_id: str):
    if user_id not in user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    del user_data[user_id]
    return {"response": f"User '{user_id}' deleted successfully"}

@app.delete("/users")
async def delete_all_users():
    user_data.clear()
    return {"response": "All users deleted successfully"}

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

@app.get("/user/{user_id}/getfile")
async def get_file(user_id: str, key: str):
    try:
        # Check if user and file exist
        if user_id not in user_data:
            raise HTTPException(status_code=404, detail="User not found")
        if 'files' not in user_data[user_id] or key not in user_data[user_id]['files']:
            raise HTTPException(status_code=404, detail="File not found")
        
        data = user_data[user_id]['files'][key]  # Changed this line to look in 'files'
        
        # Check expiry
        if data["expiry"] and data["expiry"] < datetime.utcnow():
            del user_data[user_id]['files'][key]  # Also update this line
            raise HTTPException(status_code=404, detail="File expired")
        
        # Decode file content
        try:
            content = base64.b64decode(data["value"])
            return StreamingResponse(
                io.BytesIO(content), 
                media_type=data.get("content_type", "application/octet-stream"),
                headers={
                    "Content-Disposition": f"attachment; filename={data.get('original_filename', key)}"
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving file: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error in get_file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/download_rdb/{user_id}")
async def download_user_rdb(user_id: str, path: Optional[str] = None):
    if user_id not in user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    rdb_data = {user_id: user_data[user_id]}
    rdb_bytes = pickle.dumps(rdb_data)
    
    if path:
        with open(path, 'wb') as f:
            f.write(rdb_bytes)
        return {"response": f"RDB file saved to {path}"}
    
    return StreamingResponse(io.BytesIO(rdb_bytes), media_type="application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename={user_id}_dump.rdb"
    })

@app.get("/download_rdb")
async def download_all_rdb(path: Optional[str] = None):
    rdb_bytes = pickle.dumps(user_data)
    
    if path:
        with open(path, 'wb') as f:
            f.write(rdb_bytes)
        return {"response": f"RDB file saved to {path}"}
    
    return StreamingResponse(io.BytesIO(rdb_bytes), media_type="application/octet-stream", headers={
        "Content-Disposition": "attachment; filename=all_users_dump.rdb"
    })

@app.post("/upload_rdb/{user_id}")
async def upload_user_rdb(user_id: str, file: Optional[UploadFile] = None, path: Optional[str] = None):
    try:
        if file:
            content = await file.read()
        elif path:
            with open(path, 'rb') as f:
                content = f.read()
        else:
            raise HTTPException(status_code=400, detail="Either file or path must be provided")
        
        rdb_data = pickle.loads(content)
        
        if user_id in rdb_data:
            user_data[user_id] = {**user_data.get(user_id, {}), **rdb_data[user_id]}
        else:
            raise HTTPException(status_code=400, detail="RDB file does not contain the specified user data")
        
        return {"response": "OK"}
    except Exception as e:
        logger.error(f"Error uploading RDB file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.post("/upload_rdb")
async def upload_all_rdb(file: Optional[UploadFile] = None, path: Optional[str] = None):
    try:
        if file:
            content = await file.read()
        elif path:
            with open(path, 'rb') as f:
                content = f.read()
        else:
            raise HTTPException(status_code=400, detail="Either file or path must be provided")
        
        rdb_data = pickle.loads(content)
        
        for user_id, data in rdb_data.items():
            if user_id in user_data:
                user_data[user_id] = {**user_data[user_id], **data}
            else:
                user_data[user_id] = data
        
        return {"response": "OK"}
    except Exception as e:
        logger.error(f"Error uploading RDB file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/user/{user_id}/usage")
async def get_user_usage(user_id: str):
    if user_id not in user_data:
        # Initialize user with default structure
        user_data[user_id] = {
            'files': {},
            'subscription': 'basic',
            'storage_used': 0
        }
    
    # Calculate storage from binary files
    storage_used = 0
    if 'files' in user_data[user_id]:
        storage_used = sum(
            len(base64.b64decode(data["value"]))
            for data in user_data[user_id]['files'].values()
            if data.get("type") == "binary"
        )
    
    subscription = user_data[user_id].get('subscription', 'basic')
    storage_limit = USER_SUBSCRIPTIONS[subscription]['storage_limit']
    
    return {
        "storage_used": storage_used,
        "storage_limit": storage_limit,
        "subscription": subscription
    }
@app.post("/user/{user_id}/subscription")
async def update_subscription(user_id: str, tier: str):
    if tier not in USER_SUBSCRIPTIONS:
        raise HTTPException(status_code=400, detail="Invalid subscription tier")
    
    if user_id not in user_data:
        check_user_limit()  # Check before creating new user
        user_data[user_id] = {'files': {}, 'subscription': 'basic', 'storage_used': 0}
    
    # Calculate current storage usage
    current_usage = user_data[user_id].get('storage_used', 0)
    target_limit = USER_SUBSCRIPTIONS[tier]['storage_limit']
    
    # Check if downgrading and storage exceeds new limit
    if (tier == 'basic' and 
        user_data[user_id].get('subscription') == 'premium' and 
        current_usage > target_limit):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot downgrade: Current storage usage ({current_usage/1024/1024:.2f}MB) exceeds {tier} tier limit ({target_limit/1024/1024:.2f}MB)"
        )
    
    user_data[user_id]['subscription'] = tier
    return {"status": "OK", "subscription": tier}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)