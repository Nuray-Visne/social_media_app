"""
Image Processor Microservice
Listens to RabbitMQ queue for image resize requests and processes them.
"""
import os
import sys
import time
import json
import uuid
from io import BytesIO

import pika
import psycopg
from psycopg.rows import dict_row
from PIL import Image


# Configuration from environment
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
DATABASE_URL = os.getenv("DATABASE_URL")
THUMBNAIL_MAX_WIDTH = int(os.getenv("THUMBNAIL_MAX_WIDTH", "400"))
THUMBNAIL_QUALITY = int(os.getenv("THUMBNAIL_QUALITY", "85"))

QUEUE_NAME = "image_resize_queue"


def get_db_conn():
    """Create database connection."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is required")
    return psycopg.connect(DATABASE_URL)


def get_image_from_db(image_id: str):
    """Fetch full image data from database."""
    with get_db_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT data, mime_type FROM images WHERE id = %s",
                (uuid.UUID(image_id),)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "data": bytes(row["data"]),
                "mime_type": row["mime_type"]
            }


def store_thumbnail_in_db(image_id: str, thumbnail_data: bytes):
    """Store thumbnail back to database."""
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE images 
                SET thumbnail_data = %s, thumbnail_generated = TRUE 
                WHERE id = %s
                """,
                (psycopg.Binary(thumbnail_data), uuid.UUID(image_id))
            )
        conn.commit()


def resize_image(image_data: bytes, max_width: int = 400, quality: int = 85) -> bytes:
    """
    Resize image to thumbnail maintaining aspect ratio.
    """
    try:
        # Open image from bytes
        img = Image.open(BytesIO(image_data))
        
        # Convert RGBA to RGB if needed (for JPEG compatibility)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        # Calculate new dimensions maintaining aspect ratio
        width, height = img.size
        if width > max_width:
            ratio = max_width / width
            new_width = max_width
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save to bytes with compression
        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        return output.getvalue()
    
    except Exception as e:
        print(f"❌ Error resizing image: {e}")
        raise


def process_message(message_body: str):
    """Process a single resize message."""
    try:
        # Parse message
        data = json.loads(message_body)
        image_id = data.get("image_id")
        action = data.get("action")
        
        if action != "resize":
            print(f"⚠️  Unknown action: {action}")
            return
        
        print(f"📸 Processing image: {image_id}")
        
        # Fetch image from database
        image_data = get_image_from_db(image_id)
        if not image_data:
            print(f"❌ Image not found: {image_id}")
            return
        
        # Resize image
        thumbnail = resize_image(
            image_data["data"],
            max_width=THUMBNAIL_MAX_WIDTH,
            quality=THUMBNAIL_QUALITY
        )
        
        # Store thumbnail
        store_thumbnail_in_db(image_id, thumbnail)
        
        original_size = len(image_data["data"])
        thumbnail_size = len(thumbnail)
        reduction = 100 - (thumbnail_size / original_size * 100)
        
        print(f"✅ Thumbnail created: {image_id}")
        print(f"   Original: {original_size:,} bytes → Thumbnail: {thumbnail_size:,} bytes ({reduction:.1f}% reduction)")
    
    except Exception as e:
        print(f"❌ Error processing message: {e}")
        raise


def wait_for_rabbitmq(max_retries=30, delay=2):
    """Wait for RabbitMQ to be ready."""
    print(f"🔄 Waiting for RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT}...")
    
    for attempt in range(max_retries):
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            parameters = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=credentials,
                connection_attempts=1,
                retry_delay=1
            )
            connection = pika.BlockingConnection(parameters)
            connection.close()
            print("✅ RabbitMQ is ready!")
            return
        except Exception as e:
            print(f"⏳ Attempt {attempt + 1}/{max_retries}: {e}")
            time.sleep(delay)
    
    raise RuntimeError("Failed to connect to RabbitMQ")


def main():
    """Main consumer loop."""
    print("🚀 Image Processor Microservice starting...")
    print(f"   RabbitMQ: {RABBITMQ_HOST}:{RABBITMQ_PORT}")
    print(f"   Database: {DATABASE_URL[:50]}...")
    print(f"   Thumbnail max width: {THUMBNAIL_MAX_WIDTH}px")
    print(f"   Thumbnail quality: {THUMBNAIL_QUALITY}%")
    
    # Wait for RabbitMQ to be ready
    wait_for_rabbitmq()
    
    # Connect to RabbitMQ
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300
    )
    
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    # Declare queue (create if doesn't exist)
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    
    print(f"👂 Listening for messages on queue: {QUEUE_NAME}")
    print("   Press CTRL+C to exit")
    
    def callback(ch, method, properties, body):
        """Handle incoming message."""
        try:
            process_message(body.decode())
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"❌ Failed to process message: {e}")
            # Reject and requeue the message
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    # Set QoS to process one message at a time
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
    
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        channel.stop_consuming()
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
