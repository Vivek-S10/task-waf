from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

class ToolCallPayload(BaseModel):
    tool_name: str = Field(..., description="The name of the tool to invoke")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="The parameters for the tool call")

class RuleOutcome(BaseModel):
    is_blocked: bool
    reason: Optional[str] = None
    shadow_violations: List[str] = []
    resolved_scope: Optional[str] = None
    semantic_score: Optional[float] = None
    semantic_zone: Optional[str] = None

class AgentRegistryPayload(BaseModel):
    agent_id: str = Field(..., description="Unique identifier for the agent")
    agent_scope: Optional[str] = Field(None, description="Natural language boundary constraint for the agent")
    sequence_rules: Optional[Dict[str, str]] = Field(
        None, 
        description="Custom sequence rules. Key: Target Tool, Value: Prerequisite Tool (e.g., {'ExecuteWireTransfer': 'VerifyUserIdentity'})"
    )
    rate_limit_max: Optional[int] = Field(None, description="Custom rate limit for this agent (calls per minute)")

class RegistryResponse(BaseModel):
    status: str
    message: str
    agent_id: str
