from src.db import init_db, insert_post, get_post, get_image, get_latest_post
from uuid import UUID



def test_get_latest_post():
    init_db()

    # Insert some posts with an image
    p1 = insert_post(username="Chris P. Bacon", body="Time for my bi-annual pfp change", image_path="./Testdata/p1.png")
    print("Inserted post with image:", p1)
    
    p2 = insert_post(username="Amy Stake", body="Felt cute, might delete later", image_path="./Testdata/p2.png")
    print("Inserted post with image:", p2)
    
    p3 = insert_post(username="Joe King", body="Totally #nofilter", image_path="./Testdata/p3.png")
    print("Inserted post with image:", p3)

    # Read back
    post = get_post(UUID(str(p2)))
    print("Got post:", post)

    # If it has an image, fetch it
    if post and post.image_id:
        img = get_image(post.image_id)
        print("Image mime:", img["mime_type"], "bytes:", len(img["data"]))
    
    latest = get_latest_post()
    assert latest is not None
    assert latest.username == "Joe King"
    assert "nofilter" in latest.body
