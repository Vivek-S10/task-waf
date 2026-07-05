from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from app.api.routes import router as api_router
from app.services.database import db_instance
from app.engine.tier1 import tier1_engine

templates = Jinja2Templates(directory="app/templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_instance.connect()
    
    # Preload the agent registry from MongoDB
    if db_instance.db is not None:
        try:
            cursor = db_instance.db.waf_registry.find({}, {"_id": 0})
            docs = await cursor.to_list(length=None)
            for doc in docs:
                agent_id = doc.get("agent_id")
                if agent_id:
                    tier1_engine.agent_registry[agent_id] = doc
            print(f"Preloaded {len(docs)} agent configurations from registry.")
        except Exception as e:
            print(f"Failed to preload registry from DB: {e}")
            
    yield
    db_instance.disconnect()

app = FastAPI(
    title="Agent WAF",
    description="Web Application Firewall for AI Agents",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy"}

@app.get("/dashboard")
async def dashboard(request: Request):
    """Serve the real-time HTML dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})
