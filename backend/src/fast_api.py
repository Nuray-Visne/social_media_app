
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline
from typing import Optional
import uuid
import os
import json
from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi import Query, Body
import pika
import re
import time
from src.db import (
    insert_post,
    list_posts,
    init_db,
    insert_image_from_upload,
    insert_image_from_path,
    get_image,
    get_image_thumbnail,
    search_posts_combined
)   

app = FastAPI()

# Load sentiment analysis pipeline
sentiment_analyzer = pipeline("sentiment-analysis")

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
QUEUE_NAME = "image_resize_queue"



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


def send_resize_message(image_id: uuid.UUID):
    """Send a message to RabbitMQ to process image resize."""
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials,
            connection_attempts=3,
            retry_delay=2
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # Declare queue (idempotent)
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        
        # Send message
        message = json.dumps({"image_id": str(image_id), "action": "resize"})
        channel.basic_publish(
            exchange='',
            routing_key=QUEUE_NAME,
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
        )
        
        connection.close()
        print(f"Sent resize message for image: {image_id}")
    except Exception as e:
        print(f"Failed to send resize message: {e}")
        # Don't fail the upload if RabbitMQ is down


@app.on_event("startup")
def startup_event():
    try:
        init_db()
    except Exception:
        raise RuntimeError("Database initialization failed")


@app.get("/posts/")
def get_posts(
    keyword: str = Query(None, description="Keyword to search in post body"),
    sentiment: str = Query(None, description="Sentiment label, e.g., POSITIVE or NEGATIVE"),
    limit: int = 20,
    offset: int = 0
):
    """
    Retrieve a list of posts, optionally filtered by keyword and/or sentiment.
    Returns all fields, including sentiment_label and sentiment_score.
    """
    posts = search_posts_combined(keyword, sentiment, limit, offset)
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

    # Sentiment analysis
    sentiment = sentiment_analyzer(body_val)[0]
    sentiment_label = sentiment["label"]
    sentiment_score = float(sentiment["score"])

    # Send image to resize queue if we have an image
    if image_id:
        send_resize_message(image_id)

    post_id = insert_post(username_val, body_val, image_id, None, sentiment_label, sentiment_score)
    return {"post_id": str(post_id), "image_id": str(image_id) if image_id else None, "sentiment": sentiment_label, "sentiment_score": sentiment_score}



@app.get("/images/{image_id}")
def get_image_endpoint(image_id: uuid.UUID):
    """Get full-size image."""
    img = get_image(image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    return Response(
        content=img["data"],
        media_type=img["mime_type"],
        headers={"Content-Disposition": f"inline; filename={img['filename']}"}
    )


@app.get("/images/{image_id}/thumbnail")
def get_thumbnail_endpoint(image_id: uuid.UUID):
    """Get thumbnail version of image. Falls back to full image if thumbnail not ready."""
    img = get_image_thumbnail(image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    # If thumbnail is not yet generated and we're serving the full image as a fallback,
    # instruct browsers NOT to cache the response. Otherwise they may cache the full-size
    # image and never re-fetch the thumbnail once it is ready.
    is_thumb = bool(img.get("is_thumbnail", False))
    headers = {
        "Content-Disposition": f"inline; filename=thumb_{img['filename']}",
        "X-Is-Thumbnail": str(is_thumb)
    }
    if is_thumb:
        # Safe to cache aggressively once the real thumbnail exists
        headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        # Prevent caching the temporary fallback
        headers["Cache-Control"] = "no-store"

    return Response(
        content=img["data"],
        media_type=img["mime_type"],
        headers=headers
    )


# Trip planner request model
class TripPlanRequest(BaseModel):
    city: str
    concept: str
    budget: str
    days: int
    people: int=1


@app.post("/plan-trip/")
async def plan_trip(request: TripPlanRequest):
    start_time = time.time()
    print("[TripPlanner] Start /plan-trip/")

    if request.days < 1:
        raise HTTPException(status_code=400, detail="'days' must be a positive integer")
    if request.people < 1:
        raise HTTPException(status_code=400, detail="'people' must be a positive integer")

    prompt = f'''
        YOU MUST FOLLOW THESE RULES EXACTLY:
        1. Output MUST be valid JSON.
        2. The JSON MUST contain ONLY one key: "days".
        3. "days" MUST be an array with EXACTLY {request.days} items.
        4. Each item MUST have:
             - "day": number (starting from 1)
             - "summary": 1–2 short sentences only, and MUST mention budget tips or estimated costs for that day.
        5. The plan MUST fit within a total budget of {request.budget} euros for the whole trip.
        6. Do NOT add extra days.
        7. Do NOT add explanations or text outside JSON.

        Example for 1 day:
        {{
            "days": [
                {{ "day": 1, "summary": "Explore the old town and visit a local art gallery. Keep costs under 30 euros by using public transport and free museum entry." }}
            ]
        }}

        Now generate the plan.

        City: {request.city}
        People: {request.people}
        Concept: {request.concept}
        Budget: {request.budget} euros
        '''
    print(f"[TripPlanner] Prompt built in {time.time() - start_time:.2f}s")

    ollama_url = "http://ollama:11434/api/chat"

    data = {
        "model": "phi3:mini",
        "stream": False,   
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful trip advisor. Give friendly, and practical travel plans. Limit your answer to 5 short sentences per day."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    try:
        ollama_start = time.time()
        response = httpx.post(
            ollama_url,
            json=data,
            timeout=300  
        )
        print(f"[TripPlanner] Ollama call took {time.time() - ollama_start:.2f}s")
        response.raise_for_status()

        result = response.json()

        plan_raw = result["message"]["content"]
        print("[TripPlanner] Raw LLM output:", plan_raw)

        # Strip Markdown code block markers if present
        
        cleaned = re.sub(r'^```[a-zA-Z]*\s*', '', plan_raw.strip())
        cleaned = re.sub(r'```$', '', cleaned.strip())

        # Try to parse JSON
        try:
            parsed = json.loads(cleaned)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM did not return valid JSON: {plan_raw}")

        # Validate and correct days
        days_requested = int(request.days)
        days = parsed.get("days", [])
        # Only keep the requested number of days
        days = days[:days_requested]
        # Only keep 'day' and 'summary' fields
        cleaned_days = []
        for d in days:
            if "day" in d and "summary" in d:
                cleaned_days.append({"day": d["day"], "summary": d["summary"]})
        # If not enough valid days, raise error
        if len(cleaned_days) != days_requested:
            raise HTTPException(status_code=500, detail=f"Model returned {len(cleaned_days)} valid days instead of {days_requested}")

        # Convert to frontend format
        plan_lines = [f"Day {d['day']}: {d['summary']}" for d in cleaned_days]
        plan_text = "\n".join(plan_lines)

        print(f"[TripPlanner] Total /plan-trip/ time: {time.time() - start_time:.2f}s")
        return {"plan": plan_text}

    except httpx.HTTPError as e:
        print(f"[TripPlanner] HTTPError after {time.time() - start_time:.2f}s: {e}")
        raise HTTPException(status_code=502, detail=f"Ollama HTTP error: {str(e)}")
    except KeyError as e:
        print(f"[TripPlanner] KeyError after {time.time() - start_time:.2f}s: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected Ollama response: {str(response.json())}")
    except Exception as e:
        print(f"[TripPlanner] Exception after {time.time() - start_time:.2f}s: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Update /test-ollama/ endpoint to use the correct model name
@app.get("/test-ollama/")
def test_ollama():
    try:
        response = httpx.post("http://ollama:11434/api/chat", json={
            "model": "phi3:mini",
            "stream": False,
            "messages": [{"role": "user", "content": "Hello!"}]
        })
        response.raise_for_status()
        return {"result": response.json()}
    except Exception as e:
        return {"error": str(e)}

    