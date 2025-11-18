from fastapi.testclient import TestClient
from src.fast_api import app

client = TestClient(app)

def test_create_and_get_post():
    # Create a new post
    response = client.post(
        "/posts/",
        params={
            "username": "testuser",
            "body": "This is a test post",
            "image_path": None
        }
    )
    assert response.status_code == 200
    post_id = response.json()["post_id"]

    # Retrieve the list of posts
    response = client.get("/posts/")
    assert response.status_code == 200
    posts = response.json()["posts"]

    # Check that the created post is in the list
    assert any(post["id"] == post_id and post["username"] == "testuser" and post["body"] == "This is a test post" for post in posts)