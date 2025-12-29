from __future__ import annotations
import os
import uuid
import mimetypes
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row


# -----------------------------
# Environment & connection helper
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
    port = os.getenv("PGPORT", "5432")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "")
    database = os.getenv("PGDATABASE", "postgres")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def get_conn():
    """Create and return a new psycopg connection."""
    conninfo = _make_conninfo()
    return psycopg.connect(conninfo)


# -----------------------------
# Schema initialization
# -----------------------------
def init_db() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS images (
        id UUID PRIMARY KEY,
        data BYTEA NOT NULL,
        mime_type TEXT,
        filename TEXT,
        thumbnail_data BYTEA NULL,
        thumbnail_generated BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS posts (
        id UUID PRIMARY KEY,
        username TEXT NOT NULL,
        body TEXT NOT NULL,
        image_id UUID NULL REFERENCES images(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        sentiment_label TEXT,
        sentiment_score FLOAT
    );

    CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts (created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_posts_username ON posts (username);
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()


# -----------------------------
# Data models
# -----------------------------
@dataclass
class Post:
    id: uuid.UUID
    username: str
    body: str
    image_id: Optional[uuid.UUID]
    created_at: str


# -----------------------------
# Insert helpers
# -----------------------------
def _guess_mime_type(path: str) -> Optional[str]:
    mt, _ = mimetypes.guess_type(path)
    return mt


def insert_image_from_upload(data: bytes, mime_type: str, filename: str) -> uuid.UUID:
    image_id = uuid.uuid4()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO images (id, data, mime_type, filename)
                VALUES (%s, %s, %s, %s)
                """,
                (image_id, psycopg.Binary(data), mime_type, filename)
            )
        conn.commit()

    return image_id


# for demo_setup file, which uses local image paths
def insert_image_from_path(path: str, mime_type: Optional[str] = None) -> uuid.UUID:
    image_id = uuid.uuid4()
    if mime_type is None:
        mime_type = _guess_mime_type(path)

    with open(path, "rb") as f:
        data = f.read()

    with get_conn() as conn:
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


def insert_post(
    username: str,
    body: str,
    image_id: Optional[uuid.UUID] = None,
    image_path: Optional[str] = None,
    sentiment_label: Optional[str] = None,
    sentiment_score: Optional[float] = None,
) -> uuid.UUID:
    """Insert a post; optionally create image from an existing file path.

    image_path is used in tests/demo data to attach a local image.
    """
    if image_id and image_path:
        raise ValueError("Provide either image_id or image_path, not both")

    if image_path:
        image_id = insert_image_from_path(image_path)

    post_id = uuid.uuid4()

    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO posts (id, username, body, image_id, sentiment_label, sentiment_score)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (post_id, username, body, image_id, sentiment_label, sentiment_score)
                )

            conn.commit()
            return post_id
        except Exception:
            conn.rollback()
            raise


# Combined search: keyword, sentiment, or both (or neither)
def search_posts_combined(keyword: str = None, sentiment_label: str = None, limit: int = 20, offset: int = 0) -> List[Post]:
    query = "SELECT id, username, body, image_id, created_at FROM posts"
    conditions = []
    params = []
    if keyword:
        conditions.append("body ILIKE %s")
        params.append(f"%{keyword}%")
    if sentiment_label:
        conditions.append("sentiment_label = %s")
        params.append(sentiment_label)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, tuple(params))
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



# -----------------------------
# Retrieve helpers
# -----------------------------
def get_post(post_id: uuid.UUID) -> Optional[Post]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
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
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
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


def get_latest_post() -> Optional[Post]:
    posts = list_posts(limit=1)
    return posts[0] if posts else None



def get_image(image_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
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
# Thumbnail helpers
# -----------------------------
def get_image_thumbnail(image_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """
    Get thumbnail version of an image. Falls back to full image if thumbnail not ready.
    """
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT thumbnail_data, thumbnail_generated, data, mime_type, filename, created_at
            FROM images
            WHERE id = %s
            """,
            (image_id,)
        )
        row = cur.fetchone()

    if not row:
        return None

    # Use thumbnail if available, otherwise use full image
    image_data = bytes(row["thumbnail_data"]) if row["thumbnail_generated"] and row["thumbnail_data"] else bytes(row["data"])

    return {
        "data": image_data,
        "mime_type": row["mime_type"],
        "filename": row["filename"],
        "created_at": row["created_at"].isoformat(),
        "is_thumbnail": row["thumbnail_generated"]
    }


def store_thumbnail(image_id: uuid.UUID, thumbnail_data: bytes) -> None:
    """
    Store the resized thumbnail for an image.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE images
                SET thumbnail_data = %s, thumbnail_generated = TRUE
                WHERE id = %s
                """,
                (psycopg.Binary(thumbnail_data), image_id)
            )
        conn.commit()