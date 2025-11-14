from src.db import init_db, insert_post, get_post, get_image, get_latest_post
from uuid import UUID



def test_get_latest_post():
    init_db()

    # Insert some posts with an image
    insert_post(username="Chris P. Bacon", body="Time for my bi-annual pfp change", image_path="./Testdata/p1.png")

    insert_post(username="Amy Stake", body="Felt cute, might delete later", image_path="./Testdata/p2.png")
    
    insert_post(username="Joe King", body="Totally #nofilter", image_path="./Testdata/p3.png")
    
    latest = get_latest_post()
    assert latest is not None
    assert latest.username == "Joe King"
    assert "nofilter" in latest.body
    