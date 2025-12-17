from typing import Optional
import uuid
from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi import Query
from src.db import (
    insert_post,
    list_posts,
    search_posts,
    init_db,
    insert_image_from_upload,
    insert_image_from_path,
    get_image,
)

app = FastAPI()

# CORS for local frontend dev (Vite on 5173)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    try:
        init_db()
    except Exception:
        raise RuntimeError("Database initialization failed")


@app.get("/posts/")
def get_posts(search: str = None, limit: int = 20, offset: int = 0):

    """
    Retrieve a list of posts.

    - If a search keyword is provided, filters posts by matching
      the keyword in the `username` or `body` (case-insensitive).
    - If no search is provided, returns the latest posts.

    Query Parameters:
    - search: Optional string to filter posts.
    - limit: Number of posts to return (default: 20).
    - offset: Offset for pagination (default: 0).

    Returns:
    - A dictionary containing a list of posts, where each post includes:
      id, username, body, image_id, and created_at.
    """
    if search:
        posts = search_posts(search, limit, offset)
    else:
        posts = list_posts(limit, offset)
    return {"posts": [post.__dict__ for post in posts]}



@app.post("/posts/")
async def create_post(
    username: str | None = Form(None),
    body: str | None = Form(None),
    image: UploadFile = File(None),
    image_path: str | None = Query(None, description="Optional path to an existing image on server"),
    username_q: str | None = Query(None, alias="username"),
    body_q: str | None = Query(None, alias="body"),
):
    """
    Create a post.

    - Normal use: frontend sends form fields `username`, `body`, optional file `image`.
    - Test/demo use: can pass `username` and `body` as query params and `image_path` to load a local file.
    """
    if image and image_path:
        raise HTTPException(status_code=400, detail="Provide either image or image_path, not both")

    # Accept username/body from either form (frontend) or query (tests)
    username_val = username or username_q
    body_val = body or body_q
    if not username_val or not body_val:
        raise HTTPException(status_code=422, detail="username and body are required")

    image_id = None

    if image_path:
        image_id = insert_image_from_path(image_path)
    elif image:
        data = await image.read()
        image_id = insert_image_from_upload(data, image.content_type, image.filename)

    post_id = insert_post(username_val, body_val, image_id)
    return {"post_id": str(post_id), "image_id": str(image_id) if image_id else None}


@app.get("/images/{image_id}")
def get_image_endpoint(image_id: uuid.UUID):
    img = get_image(image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    return Response(
        content=img["data"],
        media_type=img["mime_type"],
        headers={"Content-Disposition": f"inline; filename={img['filename']}"}
    )
