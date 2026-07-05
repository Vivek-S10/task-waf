from app.services.database import db_instance
import datetime
from typing import Dict, Any, Optional

async def log_tool_call(
    payload: dict,
    outcome: dict,
    final_disposition: str,
    client_ip: str,
    agent_id: Optional[str],
    session_id: Optional[str],
    agent_scope: Optional[str],
    mode: str
):
    """
    Asynchronously logs the tool call, extracted headers, and its evaluation outcome to MongoDB.
    """
    log_entry = {
        "timestamp": datetime.datetime.utcnow(),
        "client_ip": client_ip,
        "agent_id": agent_id,
        "session_id": session_id,
        "agent_scope": agent_scope,
        "mode": mode,
        "tool_name": payload.get("tool_name"),
        "parameters": payload.get("parameters"),
        "semantic_score": outcome.get("semantic_score"),
        "semantic_zone": outcome.get("semantic_zone"),
        "rule_evaluation": outcome,
        "final_disposition": final_disposition
    }
    
    if db_instance.db is not None:
        try:
            await db_instance.db.waf_logs.insert_one(log_entry)
        except Exception as e:
            # Fail-open logging: Do not crash the app if logging fails
            print(f"Failed to write log to MongoDB: {e}")
    else:
        print("Warning: Database not initialized, skipping log write.")
