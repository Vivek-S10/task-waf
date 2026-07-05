import asyncio
import httpx
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from typing import Optional
from app.core.models import ToolCallPayload, AgentRegistryPayload, RegistryResponse
from app.engine.tier1 import tier1_engine
from app.services.logger import log_tool_call
from app.services.database import db_instance

router = APIRouter()

@router.post("/proxy")
async def tool_proxy(
    payload: ToolCallPayload, 
    request: Request, 
    x_target_url: Optional[str] = Header(None),
    x_agent_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None),
    x_agent_scope: Optional[str] = Header(None)
):
    """
    True HTTP Reverse Proxy endpoint that evaluates rules via Tier 1/2 and forwards the request.
    """
    if not x_target_url:
        raise HTTPException(
            status_code=400,
            detail="Missing 'X-Target-URL' header. Please provide the destination API URL (e.g., X-Target-URL: https://mock.internal.tool)."
        )
        
    client_ip = request.client.host if request.client else "unknown_ip"
    mode = "Stateful" if x_agent_id else "Stateless"

    # Evaluate Tier 1 Rules
    outcome = tier1_engine.evaluate(
        payload=payload, 
        client_ip=client_ip, 
        agent_id=x_agent_id, 
        session_id=x_session_id,
        agent_scope_header=x_agent_scope
    )
    
    # Evaluate Tier 2 Rules (Semantic Engine)
    if not outcome.is_blocked and outcome.resolved_scope:
        from app.engine.tier2 import tier2_engine
        score, zone = tier2_engine.evaluate(outcome.resolved_scope, payload.parameters)
        outcome.semantic_score = score
        outcome.semantic_zone = zone
        
        if zone == "block":
            outcome.is_blocked = True
            outcome.reason = f"Semantic drift detected (Score: {score:.2f}). Parameters deviated significantly from agent scope."
        elif zone == "warn":
            outcome.shadow_violations.append(f"Semantic drift warning (Score: {score:.2f}). Parameters partially deviated from agent scope.")
            
    final_disposition = "blocked" if outcome.is_blocked else "allowed"
    
    # Use asyncio.create_task so logging runs in the background
    asyncio.create_task(
        log_tool_call(
            payload=payload.model_dump(),
            outcome=outcome.model_dump(),
            final_disposition=final_disposition,
            client_ip=client_ip,
            agent_id=x_agent_id,
            session_id=x_session_id,
            agent_scope=x_agent_scope,
            mode=mode
        )
    )
    
    if outcome.is_blocked:
        raise HTTPException(
            status_code=403, 
            detail={"status": "error", "action": "blocked", "reason": outcome.reason, "shadow_violations": outcome.shadow_violations}
        )
    
    # Path A: Testing Mode
    if x_target_url == "https://mock.internal.tool":
        return {
            "status": "success",
            "message": "Mock tool executed successfully.",
            "echo_params": payload.parameters
        }
        
    # Path B: Live Mode
    async with httpx.AsyncClient() as client:
        try:
            # Forward the exact JSON payload to the X-Target-URL
            response = await client.post(
                x_target_url,
                json=payload.model_dump(),
                headers={"Content-Type": "application/json"}
            )
            try:
                return response.json()
            except ValueError:
                return JSONResponse(status_code=response.status_code, content=response.text)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Bad Gateway: Failed to reach external API. {str(e)}")

import datetime

@router.get("/logs")
async def get_logs(
    limit: int = 50, 
    skip: int = 0, 
    filter_disposition: Optional[str] = None,
    filter_time: Optional[str] = None,
    filter_tool: Optional[str] = None,
    filter_shadow: Optional[str] = None
):
    """Fetch the most recent logs for the dashboard with pagination and extensive filtering."""
    if db_instance.db is None:
        return {"logs": [], "total": 0}
    
    query = {}
    
    # 1. Action Disposition Filter
    if filter_disposition and filter_disposition != "all":
        query["final_disposition"] = filter_disposition
        
    # 2. Time Filter
    if filter_time and filter_time != "all":
        now = datetime.datetime.utcnow()
        if filter_time == "5m":
            query["timestamp"] = {"$gte": now - datetime.timedelta(minutes=5)}
        elif filter_time == "1h":
            query["timestamp"] = {"$gte": now - datetime.timedelta(hours=1)}
        elif filter_time == "24h":
            query["timestamp"] = {"$gte": now - datetime.timedelta(hours=24)}
            
    # 3. Tool Name Filter (Case Insensitive Regex)
    if filter_tool:
        query["tool_name"] = {"$regex": filter_tool, "$options": "i"}
        
    # 4. Shadow Warnings Filter
    if filter_shadow and filter_shadow != "all":
        if filter_shadow == "has_warnings":
            query["rule_evaluation.shadow_violations.0"] = {"$exists": True}
        elif filter_shadow == "no_warnings":
            query["rule_evaluation.shadow_violations.0"] = {"$exists": False}
        
    total = await db_instance.db.waf_logs.count_documents(query)
    cursor = db_instance.db.waf_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit)
    logs = await cursor.to_list(length=limit)
    return {"logs": logs, "total": total}

@router.post("/registry", response_model=RegistryResponse)
async def register_agent(payload: AgentRegistryPayload):
    """
    Register an agent's configuration overrides (sequence rules, rate limits, scope).
    """
    config_dict = payload.model_dump(exclude_unset=True)
    
    # 1. Update in-memory cache for fast zero-latency access
    tier1_engine.agent_registry[payload.agent_id] = config_dict
    
    # 2. Persist to MongoDB in the background
    if db_instance.db is not None:
        async def save_to_db(agent_id: str, cfg: dict):
            try:
                # Upsert
                await db_instance.db.waf_registry.update_one(
                    {"agent_id": agent_id},
                    {"$set": cfg},
                    upsert=True
                )
            except Exception as e:
                print(f"Failed to save registry to DB: {e}")
                
        asyncio.create_task(save_to_db(payload.agent_id, config_dict))
        
    return RegistryResponse(
        status="success",
        message="Agent configuration registered successfully.",
        agent_id=payload.agent_id
    )
