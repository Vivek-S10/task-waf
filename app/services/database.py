from motor.motor_asyncio import AsyncIOMotorClient
import os

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    def connect(cls):
        # We will set MONGO_URL in docker-compose.yml
        mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        cls.client = AsyncIOMotorClient(mongo_url)
        cls.db = cls.client.agent_waf
        print(f"Connected to MongoDB at {mongo_url}")

    @classmethod
    def disconnect(cls):
        if cls.client:
            cls.client.close()

db_instance = Database()
