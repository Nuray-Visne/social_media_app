from src.db import init_db, insert_post


if __name__ == "__main__":
    print("📝 Initializing database...")
    init_db()
    print("✓ Database ready\n")
    

    posts = [
        {
            "username": "alex_explorer",
            "body": "Barcelona is amazing! The Gothic Quarter in the morning is stunning. Pro tip: go early before crowds. Best paella at Casa Calders near La Rambla.",
            "image_path": "./Testdata/Barcelona.jpg"
        },
        {
            "username": "backpacker_jane",
            "body": "Tokyo train system is incredibly efficient. Get a Suica card immediately at the airport. Shibuya crossing at night is worth the hype!",
            "image_path": "./Testdata/tokyo.jpg"
        },
        {
            "username": "wanderer_mike",
            "body": "Peru - Machu Picchu is breathtaking but crowded. Stay in Aguas Calientes village first. The 2-day hike is tougher than expected but unforgettable.",
            "image_path": "./Testdata/machu_picchu.jpg"
        },
        {
            "username": "desert_traveler",
            "body": "Morocco - Marrakech medina is a sensory overload in the best way. Bargain at souks but be respectful. Mint tea everywhere is a lifesaver in heat.",
            "image_path": "./Testdata/marrakech.jpg"
        },
        {
            "username": "island_hopper",
            "body": "Greece - Santorini sunsets live up to the hype. Skip the crowded Oia, try Akrotiri for sunset. Ferry to other islands cheap and easy.",
            "image_path": "./Testdata/santorini.jpg"
        },
    ]
    
    # Insert posts
 
    for i, post_data in enumerate(posts, 1):
        try:
            post_id = insert_post(
                username=post_data["username"],
                body=post_data["body"],
                image_path=post_data["image_path"]
            )
            print(f"✓ Post {i}: {post_data['username']}")
            print(f"  ID: {post_id}")
            print(f"  {post_data['body'][:60]}...\n")
        except Exception as e:
            print(f"Error creating post {i}: {e}\n")
    
    print("="*70)
    print("\n Ready to test with FastAPI!")
    print("   Run: uvicorn src.fast_api:app --reload\n")
