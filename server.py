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

# we are going to Transition to eveyrhitng in one file


DB_BasePath = Path(
    os.getenv("DATABASE_DIR", "/app/data/FoundTrashDatabases")
)
DB_BasePath.mkdir(parents=True, exist_ok=True)
app = FastAPI()
setup_CORS = False

if setup_CORS:
    origins = [
        "http://localhost:3000",      
        "https://myfrontendapp.com",  
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,            
        allow_credentials=True,           
        allow_methods=["GET", "POST", "PUT", "DELETE"], 
        allow_headers=["*"],              
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



@app.post("/api/DB_AddItem/{database_uuid}")
async def DB_AddItem(database_uuid:str, api_key:str,
                     image_path:str, latitude:float, longitude:float, 
                     source:str, confidence_score:float, trash_type:str):
    result = await CheckAPIKeyDatabase(api_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or missing API key")
    database_path = DB_BasePath / database_uuid
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

@app.delete("/api/DB_DeleteItem/{database_uuid}")
async def DB_DeleteItem(database_uuid:str, item_uuid:str, api_key:str):
    result = await CheckAPIKeyDatabase(api_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or missing API key")

    connection = None
    try:
        database_path = DB_BasePath / database_uuid
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

@app.put("/api/DB_EditItem/{database_uuid}")
async def DB_EditItem(database_uuid:str, api_key:str, item_uuid:str,
                     image_path:str, latitude:float, longitude:float, 
                     source:str, confidence_score:float, trash_type:str):
    result = await CheckAPIKeyDatabase(api_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or missing API key")

    connection = None
    try:
        database_path = DB_BasePath / database_uuid
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
async def DB_AddDatabase(api_key:str):
    result = await CheckAPIKeyDatabase(api_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or missing API key")
    connection = None
    try:
        database_uuid = str(uuid.uuid4())
        connection, cursor = WaitForDatabase(DB_BasePath / database_uuid)
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
                "DatabaseUUID": database_uuid}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Something has gone wrong: {e}")
    finally:
        if connection is not None:
            connection.close()  


@app.get("/api/DB_GetDatabase/{database_uuid}")
async def DB_GetDatabase(database_uuid:str, limit:int | None):
    """Fetch the data for the said database_uuid"""
    connection = None
    try:
        database_path = DB_BasePath / database_uuid
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
    databases = [
        database.name
        for database in DB_BasePath.iterdir()
        if database.is_file()
    ]
    return {"status": "successful", "Databases": databases}

@app.delete("/api/DB_DeleteDB/{database_uuid}")
async def DB_DeleteDB(database_uuid:str, api_key:str):
    result = await CheckAPIKeyDatabase(api_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or missing API key")
    database_path = DB_BasePath / database_uuid
    if not database_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database does not exist")
    try:
        database_path.unlink()
        return {"status": "successful", "DatabaseUUID": database_uuid}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Something has gone wrong: {e}")


###############

# ADMIN LOGIN SETUP
# it has to be implemented

login_database = "data/"
@app.post("/api/Login_MakeNewUser")
async def MakeNewUser():
    return {"status": "Not implemented"}



if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)