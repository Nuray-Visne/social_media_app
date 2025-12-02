from typing import Optional
from fastapi import FastAPI
from src.db import insert_post, list_posts, search_posts, init_db

app = FastAPI()


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
def create_post(username: str, body: str, image_path: Optional[str] = None):
    """
    Create a new post.

    Parameters:
    - username: Name of the user creating the post.
    - body: Content of the post.
    - image_path: Optional path to an image to attach to the post.

    Returns:
    - A dictionary with the generated post_id (UUID).
    """
    post_id = insert_post(username, body, image_path)
    return {"post_id": str(post_id)}