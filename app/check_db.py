import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_db():
    client = AsyncIOMotorClient("mongodb://mongo:27017")
    db = client.agent_waf
    cursor = db.waf_registry.find({}, {"_id": 0})
    docs = await cursor.to_list(length=None)
    print("MongoDB WAF Registry inside container:")
    for doc in docs:
        print(doc)

if __name__ == "__main__":
    asyncio.run(check_db())
