import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_logs():
    client = AsyncIOMotorClient("mongodb://mongo:27017")
    db = client.agent_waf
    # Fetch latest 5 logs
    cursor = db.waf_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(5)
    docs = await cursor.to_list(length=None)
    print("Latest 5 WAF logs:")
    for doc in docs:
        print(f"Timestamp: {doc.get('timestamp')}")
        print(f"Agent ID: {doc.get('agent_id')}")
        print(f"Session ID: {doc.get('session_id')}")
        print(f"Tool Name: {doc.get('tool_name')}")
        print(f"Outcome: {doc.get('outcome')}")
        print(f"Final Disposition: {doc.get('final_disposition')}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(check_logs())
