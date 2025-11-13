from __future__ import annotations
import os
import uuid
import mimetypes
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
     
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


# -----------------------------
# Environment & connection pool
# -----------------------------
def _make_conninfo() -> str:
    """
    Build a psycopg connection string from .env (DATABASE_URL has priority).
    """
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5445")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "")
    database = os.getenv("PGDATABASE", "postgres")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


# Create a small global pool (safe for simple apps / scripts)
_POOL = ConnectionPool(
    conninfo=_make_conninfo(),
    min_size=1,
    max_size=5,
    kwargs={"autocommit": False}  # we'll control transactions explicitly
)


# -----------------------------
# Schema initialization
# -----------------------------
def init_db() -> None:
    """
    Creates tables if they don't exist. Uses UUIDs from Python (no extension needed).
    """
    ddl = """
    CREATE TABLE IF NOT EXISTS images (
        id UUID PRIMARY KEY,
        data BYTEA NOT NULL,
        mime_type TEXT,
        filename TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS posts (
        id UUID PRIMARY KEY,
        username TEXT NOT NULL,
        body TEXT NOT NULL,
        image_id UUID NULL REFERENCES images(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts (created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_posts_username ON posts (username);
    """
    with _POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()


# -----------------------------
# Data models (lightweight)
# -----------------------------
@dataclass
class Post:
    id: uuid.UUID
    username: str
    body: str
    image_id: Optional[uuid.UUID]
    created_at: str  # ISO string returned from Postgres


@dataclass
class ImageMeta:
    id: uuid.UUID
    mime_type: Optional[str]
    filename: Optional[str]
    created_at: str


# -----------------------------
# Insert helpers
# -----------------------------
def _guess_mime_type(path: str) -> Optional[str]:
    mt, _ = mimetypes.guess_type(path)
    return mt


def insert_image_from_path(path: str, mime_type: Optional[str] = None) -> uuid.UUID:
    """
    Reads a file from disk and inserts it into the images table as BYTEA.
    Returns the image_id (UUID).
    """
    image_id = uuid.uuid4()
    if mime_type is None:
        mime_type = _guess_mime_type(path)

    with open(path, "rb") as f:
        data = f.read()

    with _POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO images (id, data, mime_type, filename)
                VALUES (%s, %s, %s, %s)
                """,
                (image_id, psycopg.Binary(data), mime_type, os.path.basename(path))
            )
        conn.commit()

    return image_id


def insert_post(username: str, body: str, image_path: Optional[str] = None) -> uuid.UUID:
    """
    Inserts a post; if image_path is provided, stores the image first and links it.
    Returns the post_id (UUID).
    """
    post_id = uuid.uuid4()
    image_id = None

    with _POOL.connection() as conn:
        try:
            if image_path:
                image_id = uuid.uuid4()
                mime_type = _guess_mime_type(image_path)
                with open(image_path, "rb") as f:
                    data = f.read()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO images (id, data, mime_type, filename)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (image_id, psycopg.Binary(data), mime_type, os.path.basename(image_path))
                    )

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO posts (id, username, body, image_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (post_id, username, body, image_id)
                )

            conn.commit()
            return post_id
        except Exception:
            conn.rollback()
            raise


# -----------------------------
# Retrieve helpers
# -----------------------------
def get_post(post_id: uuid.UUID) -> Optional[Post]:
    """
    Returns a single Post (without image data) or None if not found.
    """
    with _POOL.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, username, body, image_id, created_at
            FROM posts
            WHERE id = %s
            """,
            (post_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return Post(
            id=row["id"],
            username=row["username"],
            body=row["body"],
            image_id=row["image_id"],
            created_at=row["created_at"].isoformat()
        )


def list_posts(limit: int = 20, offset: int = 0) -> List[Post]:
    """
    Returns posts ordered by newest first (without image bytes).
    """
    with _POOL.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, username, body, image_id, created_at
            FROM posts
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset)
        )
        rows = cur.fetchall()

    return [
        Post(
            id=r["id"],
            username=r["username"],
            body=r["body"],
            image_id=r["image_id"],
            created_at=r["created_at"].isoformat()
        )
        for r in rows
    ]


def get_image(image_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """
    Returns {'data': bytes, 'mime_type': str | None, 'filename': str | None, 'created_at': iso}
    or None if not found.
    """
    with _POOL.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT data, mime_type, filename, created_at
            FROM images
            WHERE id = %s
            """,
            (image_id,)
        )
        row = cur.fetchone()

    if not row:
        return None

    return {
        "data": bytes(row["data"]),
        "mime_type": row["mime_type"],
        "filename": row["filename"],
        "created_at": row["created_at"].isoformat()
    }


# -----------------------------
# Utilities we might want
# -----------------------------
def delete_post(post_id: uuid.UUID) -> bool:
    """
    Deletes a post. If it referenced an image that no other posts use,
    you may want to GC that image separately (not implemented here).
    Returns True if deleted, False if not found.
    """
    with _POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM posts WHERE id = %s", (post_id,))
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted


def count_posts() -> int:
    with _POOL.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM posts")
        return cur.fetchone()[0]
