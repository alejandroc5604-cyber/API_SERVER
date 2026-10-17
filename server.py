import sqlite3
import uuid
import datetime
import uvicorn
import time
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, status
import base64



DB_BasePath = Path(
    os.getenv("DATABASE_DIR", "/app/data/FoundTrashDatabases")
)


DB_BasePath.mkdir(parents=True, exist_ok=True)
app = FastAPI(docs_url="/api/docs", openapi_url = "/api/openapi.json")

setup_CORS = False
if os.getenv("SetupCORS", "FALSE") == "TRUE":
    setup_CORS = True

if setup_CORS:
    origins = [
        "http://192.168.100.22", # local testing
        "http://localhost",
        "http://localhost:3000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )



def WaitForDatabase(db_path):
    while True:
        try:
            conn = sqlite3.connect(db_path, timeout=0.5)
            cursor = conn.cursor()
            
            cursor.execute("BEGIN EXCLUSIVE TRANSACTION;")
            return conn, cursor
            
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                time.sleep(1)
            else:
                raise e

async def CheckAPIKeyDatabase(api):
    key = os.getenv("API_KEY", "HELLO")
    return api == key



@app.post("/api/DB_AddItem/{database_name}")
async def DB_AddItem(
    database_name: str,
    api_key: str,
    image_path: str,
    latitude: float,
    longitude: float,
    source: str,
    confidence_score: float,
    trash_type: str,
):
    result = await CheckAPIKeyDatabase(api_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or missing API key")
    database_path = DB_BasePath / database_name
    connection = None
    try:
        if not database_path.exists():
            raise FileNotFoundError("Database does not exist")
        connection, cursor = WaitForDatabase(database_path)
        item_uuid = str(uuid.uuid4())
        date = datetime.datetime.now().timestamp()
        data = [
            item_uuid,
            str(trash_type),
            float(date),
            float(confidence_score),
            str(image_path),
            float(latitude),
            float(longitude),
            str(source),
        ]
        cursor.execute("""INSERT INTO found_trash
                (ID,type,date,confidence_score,image_path,latitude,longitude,source)
                VALUES (?,?,?,?,?,?,?,?)
        """, data)
        connection.commit()
        connection.close()
        return {"status": "successful",
                "item_uuid": item_uuid}


    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Something has gone wrong: {e}")
    finally:
        if connection is not None:
            connection.close()

@app.delete("/api/DB_DeleteItem/{database_name}")
async def DB_DeleteItem(database_name:str, item_uuid:str, api_key:str):
    result = await CheckAPIKeyDatabase(api_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or missing API key")

    connection = None
    try:
        database_path = DB_BasePath / database_name
        if not database_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database does not exist")
        connection, cursor = WaitForDatabase(database_path)
        cursor.execute("DELETE FROM found_trash WHERE ID = ?", (item_uuid,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item does not exist")
        connection.commit()
        return {"status": "successful", "item_uuid": item_uuid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Something has gone wrong: {e}")
    finally:
        if connection is not None:
            connection.close()

@app.put("/api/DB_EditItem/{database_name}")
async def DB_EditItem(
    database_name:str, 
    api_key:str,
    item_uuid:str,      
    image_path:str,
    latitude:float, 
    longitude:float, 
    source:str, 
    confidence_score:float, 
    trash_type:str
):
    result = await CheckAPIKeyDatabase(api_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or missing API key")

    connection = None
    try:
        database_path = DB_BasePath / database_name
        if not database_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database does not exist")
        connection, cursor = WaitForDatabase(database_path)
        cursor.execute("""
            UPDATE found_trash
            SET type = ?, confidence_score = ?, image_path = ?,
                latitude = ?, longitude = ?, source = ?
            WHERE ID = ?
        """, (
            str(trash_type),
            float(confidence_score),
            str(image_path),
            float(latitude),
            float(longitude),
            str(source),
            item_uuid,
        ))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item does not exist")
        connection.commit()
        return {"status": "successful", "item_uuid": item_uuid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Something has gone wrong: {e}")
    finally:
        if connection is not None:
            connection.close()

@app.post("/api/DB_AddDatabase")
async def DB_AddDatabase(
    api_key:str,
    database_name:str):
    result = await CheckAPIKeyDatabase(api_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or missing API key")
    connection = None
    try:
        base_64_name = base64.urlsafe_b64encode(database_name.encode("utf-8")).decode()
        database_name = f"{base_64_name}_{str(uuid.uuid4())}"
        connection, cursor = WaitForDatabase(DB_BasePath / database_name)
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS found_trash (
                ID TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                date REAL NOT NULL,
                confidence_score REAL NOT NULL,
                image_path TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                source TEXT NOT NULL
            )
        """)
        connection.commit()
        connection.close()
        return {"status": "success",
                "DatabaseName": database_name}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Something has gone wrong: {e}")
    finally:
        if connection is not None:
            connection.close()  


@app.get("/api/DB_GetDatabase/{database_name}")
async def DB_GetDatabase(database_name:str, limit:int | None):
    """Fetch the data for the said database_name"""
    connection = None
    try:
        database_path = DB_BasePath / database_name
        if not database_path.exists():
            raise FileNotFoundError("Database does not exist")
        connection, cursor = WaitForDatabase(database_path)
        if limit is None:
            result = cursor.execute("""
            SELECT ID, type, date, confidence_score, image_path, latitude, longitude, source
            FROM found_trash
            ORDER BY date DESC
            """).fetchall()
        else:
            result = cursor.execute("""
            SELECT ID, type, date, confidence_score, image_path, latitude, longitude, source
            FROM found_trash
            ORDER BY date DESC
            LIMIT ?
            """, (limit,)).fetchall()
            print(result)

        found_data = [
            {
                "ID": item_id,
                "type": trash_type,
                "date": date,
                "confidence_score": confidence_score,
                "image_path": image_path,
                "latitude": latitude,
                "longitude": longitude,
                "source": source
            }
            for item_id, trash_type, date, confidence_score, image_path, latitude, longitude, source in result
        ]
        return {"status": "successful", "FoundData": found_data}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Something has gone wrong: {e}")
    finally:
        if connection is not None:
            connection.close()


@app.get("/api/DB_FindDB")
async def DB_FindDB():
    """Find the databases in the DB_BasePath"""
    databases = []
    for database_filename in DB_BasePath.iterdir():
        if database_filename.is_file():
            safe_string = str(database_filename.stem.split("_"))
            safe_bytes = safe_string.encode("utf-8")
            decoded_bytes = base64.urlsafe_b64decode(safe_bytes)
            database_name = decoded_bytes.decode("utf-8")
            databases.append({
                "Database_filename": str(Path(database_filename).stem), 
                "Database_Name": database_name
            }) # when using anything, use the filename

    
    return {"status": "successful", "Databases": databases}

@app.delete("/api/DB_DeleteDB/{database_name}")
async def DB_DeleteDB(database_name:str, api_key:str):
    result = await CheckAPIKeyDatabase(api_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or missing API key")
    database_path = DB_BasePath / database_name
    if not database_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database does not exist")
    try:
        database_path.unlink()
        return {"status": "successful", "DatabaseUUID": database_name}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Something has gone wrong: {e}")
# Now we are going to add an image database, with the reqests and storage in base64, 
# We will also give a UUID to all of the images, which will replace the image path
#

@app.post("/ImageDB/AddImage")
async def IMGDB_AddImage(key:str, image:str):
    """Add Image, formatted in base64 URLSafe. Return an error if the image base
    64 does not meet the criteria"""
    result = await CheckAPIKeyDatabase(key)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or missing API key")
    
    



if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)