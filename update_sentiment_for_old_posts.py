
from backend.src.db import get_conn
from transformers import pipeline

# Load sentiment analysis pipeline
sentiment_analyzer = pipeline("sentiment-analysis")

def update_old_posts_sentiment():
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Fetch posts with NULL sentiment_label
            cur.execute("SELECT id, body FROM posts WHERE sentiment_label IS NULL")
            posts = cur.fetchall()
            print(f"Found {len(posts)} posts to update.")
            for post_id, body in posts:
                sentiment = sentiment_analyzer(body)[0]
                label = sentiment["label"]
                score = float(sentiment["score"])
                cur.execute(
                    """
                    UPDATE posts SET sentiment_label = %s, sentiment_score = %s WHERE id = %s
                    """,
                    (label, score, post_id)
                )
            conn.commit()
            print("Sentiment updated for all old posts.")

if __name__ == "__main__":
    update_old_posts_sentiment()
