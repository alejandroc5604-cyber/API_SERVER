"""New file meant to replace the old server.py"""
import base64
import binascii
import datetime
import mimetypes
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated
from fastapi import FastAPI, File, Form, UploadFile, Depends
from pydantic import BaseModel, Field
from fastapi.security import APIKeyHeader
import random


app = FastAPI()

# API
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

Data_Base_Path = Path(os.getenv("DATABASE_DIR", "/app/data/FoundTrashDatabases"))

API_KEY = "bjwhZPQ2bZmB3PaLj9OM3JnKenAzuamNDngaBF13twM="
async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials"
        )
    return api_key


# CLASSES
class RecordItem(BaseModel):
    trash_type: str = Field(..., description="Trash Type: Give a name of the detected trash", examples=["ceramic", "plastic", "metal", "paper"])
    latitude: float = Field(..., description="Latitude: Give the latitude of the found trash")
    longitude: float = Field(..., description="Latitude: Give the longitude of the found trash")
    source: str = Field(..., description="Source: A unique identifier to find which model found the data")
    confidence_score: float = Field(..., gt=0, lt=100, examples=[75.5, 89.2, 94.1],description="Confidence_Score: A score, from an AI model, about how confident it is from sorting this trash into one of the categories", )

class DatabaseItem(BaseModel):
    DatabaseName: str = Field(..., description="Name: the name given to the database", maxlength=30, )#pattern=r"^(?!.*[\*\?\[\]\{\}~\$\!&\|;<>\/\\\x00]).*$")

class DatabaseItemResponse(BaseModel):
    completed_time: float
    DatabaseFilename: str
    DatabaseName: str
    

class DatabaseSearchResponse(BaseModel):
    completed_time: float
    foundAmount: int
    foundData: list[DatabaseItemResponse]
    

class DatabaseDeleteResponse(BaseModel):
    completed_time: float
    success: bool

class DatabaseFetchResponse(BaseModel):
    completed_time: float
    foundAmount: int
    foundData: list[RecordItem]
class DatabaseAddResponse(BaseModel):
    completed_time: float
    success: bool

# HELPERS



# ENDPOINTS

@app.post("/api/CreateDatabase", response_model=DatabaseItemResponse, status_code=201) # FINISHED THE PYDANTIC THINGY
async def CreateDatabase(
    item: DatabaseItem,
    api_key: str = Depends(verify_api_key)
):
    """Create a database"""
    pass

@app.delete("/api/DeleteDatabase/{database}", response_model=DatabaseDeleteResponse, status_code=201) # FINISHED THE PYDANTIC THINGY
async def DeleteDatabase(
    database: str,
    api_key: str = Depends(verify_api_key)
):
    """Delete a database"""
    pass

@app.get("/api/FindDatabase", response_model=DatabaseSearchResponse, status_code=201) # FINISHED THE PYDANTIC THINGY
async def FindDatabase():
    """Get a list of databases available"""
    pass

@app.get("/api/FetchDatabase/{database}", response_model=DatabaseFetchResponse, status_code=201) # FINISHED THE PYDANTIC THINGY
async def FetchDatabase(
    database: str
):
    """Get records in the selected database"""
    pass

@app.post("/api/AddItem/{database}", response_model=DatabaseAddResponse, status_code=201) # NOT FINISHED THE PYDANTIC THINGY
async def AddItem(
    item: Annotated[RecordItem, Form()],
    image: UploadFile = File(..., description="The image file of the detected trash"),
    api_key: str = Depends(verify_api_key)
):
    """Add an item to the selected database"""
    pass

@app.delete("/api/DeleteItem/{database}")
async def DeleteItem(
    api_key: str = Depends(verify_api_key)
):
    pass

@app.get("/api/FindItem/{database}")
async def FindItems():
    pass

