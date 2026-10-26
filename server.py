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
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


DB_BasePath_FoundTrash = Path(
    os.getenv("DATABASE_DIR", "/app/data/FoundTrashDatabases")
).resolve()
DB_BasePath_ImageDB = Path(
    os.getenv("DATABASE_DIR_IMAGES", "/app/data/Images")
).resolve()

DB_BasePath_FoundTrash.mkdir(parents=True, exist_ok=True)
DB_BasePath_ImageDB.mkdir(parents=True, exist_ok=True)

app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

if os.getenv("SetupCORS", "FALSE") == "TRUE":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://192.168.100.22",
            "http://localhost",
            "http://localhost:3000",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )


def safe_child_path(base: Path, name: str) -> Path:
    """Make the path safe, to stop traversing attacks"""
    if not name or Path(name).name != name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid name")
    path = (base / name).resolve()
    if not path.is_relative_to(base):
        raise HTTPException(status_code=400, detail="Invalid path")
    return path


def WaitForDatabase(db_path):
    """Open SQLite and acquire a write lock, retrying while another writer holds it."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            cursor.execute("BEGIN EXCLUSIVE TRANSACTION")
            return conn, cursor
        except sqlite3.OperationalError as exc:
            try:
                conn.close()
            except (UnboundLocalError, AttributeError):
                pass
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                time.sleep(0.25)
                continue
            raise


def require_api_key(api_key: str):
    """Check for the API key supplied, by raising the error"""
    if not CheckAPIKeyDatabase_sync(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


def CheckAPIKeyDatabase_sync(api):
    """Check the API key is correct / supplied"""
    configured_key = os.getenv("API_KEY", "HELLO")
    # quickly for testing
    #return bool(configured_key) and api == configured_key
    return True

def decode_database_name(filename: str) -> str:
    """Decode the base64 label prefix before the UUID suffix."""
    match = re.match(
        r"^(.*)_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:\\.db)?$", # this took WAY too long
        filename,
        flags=re.IGNORECASE,
    )
    if not match:
        return filename
    try:
        return base64.urlsafe_b64decode(match.group(1).encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return filename


def make_database_filename(display_name: str, suffix: str = "") -> str:
    """Encode the base64 string thingy"""
    encoded = base64.urlsafe_b64encode(display_name.encode("utf-8")).decode("ascii")
    return f"{encoded}_{uuid.uuid4()}{suffix}"


def image_storage_dir(database_name: str) -> Path:
    # Each image database has its own directory for its uploaded files.
    db_path = safe_child_path(DB_BasePath_ImageDB, database_name)
    folder = (DB_BasePath_ImageDB / f"{db_path.name}.files").resolve()
    if not folder.is_relative_to(DB_BasePath_ImageDB):
        raise HTTPException(status_code=400, detail="Invalid database name")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def get_image_db(database_name: str) -> Path:
    if not database_name.endswith(".db"):
        raise HTTPException(status_code=400, detail="Image database name must end in .db")
    return safe_child_path(DB_BasePath_ImageDB, database_name)


def initialize_image_table(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS found_images (
            ID TEXT PRIMARY KEY,
            image_name TEXT NOT NULL,
            database_name TEXT NOT NULL,
            image_path TEXT,
            media_type TEXT,
            date_added REAL NOT NULL
        )
    """)
    # Migrate databases created by the earlier version of this API.
    existing = {
        row[1] for row in connection.execute("PRAGMA table_info(found_images)").fetchall()
    }
    migrations = {
        "image_path": "ALTER TABLE found_images ADD COLUMN image_path TEXT",
        "media_type": "ALTER TABLE found_images ADD COLUMN media_type TEXT",
        "date_added": "ALTER TABLE found_images ADD COLUMN date_added REAL",
    }
    for column, sql in migrations.items():
        if column not in existing:
            connection.execute(sql)


class ImageDatabaseRequest(BaseModel):
    api_key: str
    database_name: str = Field(min_length=1, max_length=150)


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
    """Add an item to the selected database: Supply the following
       database_name: str,
        api_key: str,
        image_path: str,
        latitude: float,
        longitude: float,
        source: str,
        confidence_score: float,
        trash_type: str,
    """
    require_api_key(api_key)
    database_path = safe_child_path(DB_BasePath_FoundTrash, database_name)
    if not database_path.is_file():
        raise HTTPException(status_code=404, detail="Database does not exist")

    connection = None
    try:
        connection, cursor = WaitForDatabase(database_path)
        item_uuid = str(uuid.uuid4())
        timestamp = datetime.datetime.now(datetime.timezone.utc).timestamp()
        cursor.execute(
            """INSERT INTO found_trash
               (ID, type, date, confidence_score, image_path, latitude, longitude, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item_uuid, trash_type, timestamp, confidence_score, image_path,
                latitude, longitude, source,
            ),
        )
        connection.commit()
        return {"status": "successful", "item_uuid": item_uuid}
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


@app.delete("/api/DB_DeleteItem/{database_name}")
async def DB_DeleteItem(database_name: str, item_uuid: str, api_key: str):
    """Delete an Item from the database"""
    require_api_key(api_key)
    database_path = safe_child_path(DB_BasePath_FoundTrash, database_name)
    if not database_path.is_file():
        raise HTTPException(status_code=404, detail="Database does not exist")

    connection = None
    try:
        connection, cursor = WaitForDatabase(database_path)
        cursor.execute("DELETE FROM found_trash WHERE ID = ?", (item_uuid,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item does not exist")
        connection.commit()
        return {"status": "successful", "item_uuid": item_uuid}
    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


@app.put("/api/DB_EditItem/{database_name}")
async def DB_EditItem(
    database_name: str,
    api_key: str,
    item_uuid: str,
    image_path: str,
    latitude: float,
    longitude: float,
    source: str,
    confidence_score: float,
    trash_type: str,
):
    """Edit an item in the database. Supply the new parameters"""
    require_api_key(api_key)
    database_path = safe_child_path(DB_BasePath_FoundTrash, database_name)
    if not database_path.is_file():
        raise HTTPException(status_code=404, detail="Database does not exist")

    connection = None
    try:
        connection, cursor = WaitForDatabase(database_path)
        cursor.execute(
            """UPDATE found_trash
               SET type = ?, confidence_score = ?, image_path = ?,
                   latitude = ?, longitude = ?, source = ?
               WHERE ID = ?""",
            (
                trash_type, confidence_score, image_path,
                latitude, longitude, source, item_uuid,
            ),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item does not exist")
        connection.commit()
        return {"status": "successful", "item_uuid": item_uuid}
    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


@app.post("/api/DB_AddDatabase")
async def DB_AddDatabase(api_key: str, database_name: str):
    """Create a dataabase. it will be given a UUID string, and save the 
    name via the database_name. Limit the name to only 30 characters to save the size"""
    require_api_key(api_key)
    if not database_name.strip():
        raise HTTPException(status_code=400, detail="Database name cannot be empty")
    try:
        database_name = database_name[:30]
    except Exception as e:
        pass

    filename = make_database_filename(database_name.strip())
    database_path = safe_child_path(DB_BasePath_FoundTrash, filename)
    connection = None
    try:
        connection = sqlite3.connect(database_path)
        connection.execute("""
            CREATE TABLE found_trash (
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
        return {"status": "success", "DatabaseName": filename}
    except sqlite3.Error as exc:
        if database_path.exists():
            database_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


@app.get("/api/DB_GetDatabase/{database_name}")
async def DB_GetDatabase(database_name: str,limit: Optional[int] = Query(default=None, ge=1, le=10000)):
    """Get all the data in the selected database"""
    database_path = safe_child_path(DB_BasePath_FoundTrash, database_name)
    if not database_path.is_file():
        raise HTTPException(status_code=404, detail="Database does not exist")

    connection = None
    try:
        connection = sqlite3.connect(database_path, timeout=5)
        sql = """SELECT ID, type, date, confidence_score, image_path, latitude, longitude, source
                 FROM found_trash ORDER BY date DESC"""
        if limit is not None:
            sql += " LIMIT ?"
            rows = connection.execute(sql, (limit,)).fetchall()
        else:
            rows = connection.execute(sql).fetchall()

        found_data = [
            {
                "ID": row[0], "type": row[1], "date": row[2],
                "confidence_score": row[3], "image_path": row[4],
                "latitude": row[5], "longitude": row[6], "source": row[7],
            }
            for row in rows
        ]
        return {"status": "successful", "FoundData": found_data}
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


@app.get("/api/DB_FindDB")
async def DB_FindDB():
    """Find all the saved databases"""
    databases = []
    for path in DB_BasePath_FoundTrash.iterdir():
        if path.is_file() and path.suffix != "-journal" and not path.name.endswith(("-wal", "-shm")):
            databases.append({
                "Database_filename": path.name,
                "Database_Name": decode_database_name(path.name),
            })
    return {"status": "successful", "Databases": databases}


@app.delete("/api/DB_DeleteDB/{database_name}")
async def DB_DeleteDB(database_name: str, api_key: str):
    """Delete a database"""
    require_api_key(api_key)
    database_path = safe_child_path(DB_BasePath_FoundTrash, database_name)
    if not database_path.is_file():
        raise HTTPException(status_code=404, detail="Database does not exist")
    try:
        database_path.unlink()
        return {"status": "successful", "DatabaseUUID": database_name}
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not delete database: {exc}") from exc


@app.post("/api/ImageDB/SetupDB")
async def IMGDB_SetupDB(api_key: str, database_name: str):
    """Setup the Image Database"""
    require_api_key(api_key)
    if not database_name.strip():
        raise HTTPException(status_code=400, detail="Database name cannot be empty")

    filename = make_database_filename(database_name.strip(), ".db")
    database_path = get_image_db(filename)
    connection = None
    try:
        connection = sqlite3.connect(database_path)
        initialize_image_table(connection)
        connection.commit()
        image_storage_dir(filename).mkdir(parents=True, exist_ok=True)
        return {"status": "success", "DatabaseName": filename}
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


@app.post("/api/ImageDB/AddImage")
async def IMGDB_AddImage(
    api_key: str,
    database_name: str,
    image: UploadFile = File(...),
):
    """Upload one image and store its metadata in the selected image database."""
    require_api_key(api_key)
    database_path = get_image_db(database_name)
    if not database_path.is_file():
        raise HTTPException(status_code=404, detail="Image database does not exist")

    content_type = image.content_type or mimetypes.guess_type(image.filename or "")[0]
    if not content_type or not content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Only image uploads are accepted")

    max_bytes = int(os.getenv("MAX_IMAGE_SIZE_BYTES", str(10 * 1024 * 1024)))
    contents = await image.read(max_bytes + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Image exceeds the {max_bytes}-byte limit")

    original_name = Path(image.filename or "image").name
    suffix = Path(original_name).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,10}", suffix):
        suffix = mimetypes.guess_extension(content_type) or ".img"

    image_id = str(uuid.uuid4())
    stored_filename = f"{image_id}{suffix}"
    folder = image_storage_dir(database_name)
    stored_path = safe_child_path(folder, stored_filename)
    connection = None

    try:
        stored_path.write_bytes(contents)
        connection, cursor = WaitForDatabase(database_path)
        cursor.execute(
            """INSERT INTO found_images
               (ID, image_name, database_name, image_path, media_type, date_added)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                image_id, original_name, database_name, stored_filename,
                content_type, datetime.datetime.now(datetime.timezone.utc).timestamp(),
            ),
        )
        connection.commit()
        return {
            "status": "successful",
            "image_id": image_id,
            "image_name": original_name,
            "database_name": database_name,
            "image_url": f"/api/ImageDB/GetImage/{database_name}/{image_id}",
        }
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Could not save image: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()
        await image.close()


@app.get("/api/ImageDB/FindDB")
async def IMGDB_FindDB(limit: int = Query(default=-1, ge=-1, le=1000)):
    """Find all Image Databases"""
    databases = []
    for path in sorted(DB_BasePath_ImageDB.iterdir()):
        if path.is_file() and path.suffix == ".db":
            databases.append({
                "Database_filename": path.name,
                "Database_Name": decode_database_name(path.name),
            })
    if limit >= 0:
        databases = databases[:limit]
    return {"status": "successful", "Databases": databases}


@app.get("/api/ImageDB/FindImages/{database_name}")
async def IMGDB_FindImages(
    database_name: str,
    image_limit: int = Query(default=20, ge=1, le=1000),
):
    """List image metadata, with image_limit limiting the number returned."""
    database_path = get_image_db(database_name)
    if not database_path.is_file():
        raise HTTPException(status_code=404, detail="Image database does not exist")

    connection = None
    try:
        connection = sqlite3.connect(database_path, timeout=5)
        initialize_image_table(connection)
        connection.commit()
        rows = connection.execute(
            """SELECT ID, image_name, database_name, media_type, date_added
               FROM found_images ORDER BY date_added DESC LIMIT ?""",
            (image_limit,),
        ).fetchall()
        images = [
            {
                "image_id": row[0],
                "image_name": row[1],
                "database_name": row[2],
                "media_type": row[3],
                "date_added": row[4],
                "image_url": f"/api/ImageDB/GetImage/{database_name}/{row[0]}",
            }
            for row in rows
        ]
        return {"status": "successful", "count": len(images), "Images": images}
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


@app.get("/api/ImageDB/GetImage/{database_name}/{image_id}")
async def IMGDB_GetImage(database_name: str, image_id: str):
    """Fetch an image by its ID"""
    database_path = get_image_db(database_name)
    if not database_path.is_file():
        raise HTTPException(status_code=404, detail="Image database does not exist")

    connection = None
    try:
        connection = sqlite3.connect(database_path, timeout=5)
        row = connection.execute(
            "SELECT image_path, media_type FROM found_images WHERE ID = ?",
            (image_id,),
        ).fetchone()
        if row is None or not row[0]:
            raise HTTPException(status_code=404, detail="Image not found")

        folder = image_storage_dir(database_name)
        file_path = safe_child_path(folder, row[0])
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="Image file is missing")
        return FileResponse(
            path=file_path,
            media_type=row[1] or "application/octet-stream",
        )
    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


@app.delete("/api/ImageDB/DeleteImage/{database_name}/{image_id}")
async def IMGDB_DeleteImage(database_name: str, image_id: str, api_key: str):
    """Delete an image's metadata and its stored file."""
    require_api_key(api_key)
    database_path = get_image_db(database_name)
    if not database_path.is_file():
        raise HTTPException(status_code=404, detail="Image database does not exist")

    connection = None
    stored_path = None
    try:
        connection, cursor = WaitForDatabase(database_path)
        row = cursor.execute(
            "SELECT image_path FROM found_images WHERE ID = ?", (image_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Image not found")

        if row[0]:
            stored_path = safe_child_path(image_storage_dir(database_name), row[0])
        cursor.execute("DELETE FROM found_images WHERE ID = ?", (image_id,))
        connection.commit()
        if stored_path is not None:
            stored_path.unlink(missing_ok=True)
        return {"status": "successful", "image_id": image_id}
    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8010, reload=True)

