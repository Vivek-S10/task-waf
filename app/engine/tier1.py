import time
from typing import Dict, List, Set, Tuple, Optional
from pydantic import BaseModel
from app.core.models import ToolCallPayload, RuleOutcome
class Tier1Engine:
    def __init__(self):
        # State stores (in-memory for "Walking Skeleton")
        self.call_history: Dict[str, List[float]] = {}
        self.session_state: Dict[str, Set[str]] = {}
        
        # Agent Registry cache
        self.agent_registry: Dict[str, dict] = {}
        
        # Global Configuration (Defaults)
        self.rate_limit_window = 60.0  # seconds
        self.rate_limit_max = 5        # max calls per window
        self.param_max_size = 2000     # characters
        self.blocklist = ["' OR 1=1", "<script>", "DROP TABLE"]
        self.global_sequence_rules = {
            "ExecuteWireTransfer": "VerifyUserIdentity",
            "ReadDatabase": "Authenticate"
        }
        
        # Shadow Mode Configs (True means it logs but DOES NOT block)
        self.shadow_mode_rate_limit = False
        self.shadow_mode_sequence = False
        self.shadow_mode_params = False

    def check_rate_limit(self, client_ip: str, agent_id: Optional[str]) -> Tuple[bool, str]:
        now = time.time()
        tracking_key = agent_id if agent_id else client_ip
        
        # Determine rate limit max: check registry first, then global default
        current_limit = self.rate_limit_max
        if agent_id and agent_id in self.agent_registry:
            registered_limit = self.agent_registry[agent_id].get("rate_limit_max")
            if registered_limit is not None:
                current_limit = registered_limit
        
        if tracking_key not in self.call_history:
            self.call_history[tracking_key] = []
            
        # Clean old history
        self.call_history[tracking_key] = [t for t in self.call_history[tracking_key] if now - t < self.rate_limit_window]
        
        if len(self.call_history[tracking_key]) >= current_limit:
            return True, f"Rate limit exceeded: {current_limit} calls per {self.rate_limit_window}s"
            
        self.call_history[tracking_key].append(now)
        return False, ""

    def check_sequence(self, tool_name: str, session_id: Optional[str], agent_id: Optional[str]) -> Tuple[bool, str]:
        if not session_id:
            return False, ""
            
        if session_id not in self.session_state:
            self.session_state[session_id] = set()
            
        # Determine sequence rules: registry override, else global defaults
        rules_to_use = self.global_sequence_rules
        if agent_id and agent_id in self.agent_registry:
            custom_rules = self.agent_registry[agent_id].get("sequence_rules")
            if custom_rules is not None:
                rules_to_use = custom_rules
            
        # Check prerequisite
        if tool_name in rules_to_use:
            prereq = rules_to_use[tool_name]
            if prereq not in self.session_state[session_id]:
                return True, f"Sequence violation: '{prereq}' must be called before '{tool_name}'"
                
        # Register this tool in the session
        self.session_state[session_id].add(tool_name)
        return False, ""

    def check_parameters(self, payload: ToolCallPayload) -> Tuple[bool, str]:
        params_str = str(payload.parameters)
        
        # Size limit
        if len(params_str) > self.param_max_size:
            return True, f"Parameter size exceeded limit of {self.param_max_size} chars"
            
        # Blocklist
        upper_params = params_str.upper()
        for banned in self.blocklist:
            if banned.upper() in upper_params:
                return True, f"Parameter matched blocklist signature: {banned}"
                
        return False, ""

    def evaluate(self, payload: ToolCallPayload, client_ip: str, agent_id: Optional[str], session_id: Optional[str], agent_scope_header: Optional[str] = None) -> RuleOutcome:
        shadow_violations = []
        
        # Determine resolved scope (Registry > Header)
        resolved_scope = agent_scope_header
        if agent_id and agent_id in self.agent_registry:
            registered_scope = self.agent_registry[agent_id].get("agent_scope")
            if registered_scope:
                resolved_scope = registered_scope
        
        # 1. Parameter Validation (Always on)
        param_violation, param_msg = self.check_parameters(payload)
        if param_violation:
            if self.shadow_mode_params:
                shadow_violations.append(param_msg)
            else:
                return RuleOutcome(is_blocked=True, reason=param_msg, shadow_violations=shadow_violations, resolved_scope=resolved_scope)
                
        # 2. Sequence Rules
        seq_violation, seq_msg = self.check_sequence(payload.tool_name, session_id, agent_id)
        if seq_violation:
            if self.shadow_mode_sequence:
                shadow_violations.append(seq_msg)
            else:
                return RuleOutcome(is_blocked=True, reason=seq_msg, shadow_violations=shadow_violations, resolved_scope=resolved_scope)
                
        # 3. Rate Limit
        rl_violation, rl_msg = self.check_rate_limit(client_ip, agent_id)
        if rl_violation:
            if self.shadow_mode_rate_limit:
                shadow_violations.append(rl_msg)
            else:
                return RuleOutcome(is_blocked=True, reason=rl_msg, shadow_violations=shadow_violations, resolved_scope=resolved_scope)

        return RuleOutcome(is_blocked=False, shadow_violations=shadow_violations, resolved_scope=resolved_scope)

# Singleton for the app to use
tier1_engine = Tier1Engine()
