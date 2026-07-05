import json
import numpy as np
from typing import Dict, Any, Tuple
from fastembed import TextEmbedding

class Tier2Engine:
    def __init__(self):
        # We use a lightweight, fast model for CPU inference via ONNX
        self.model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        
        # Thresholds (Tuned for BGE-small dense embedding space)
        self.ALLOW_THRESHOLD = 0.70
        self.WARN_THRESHOLD = 0.60

    def flatten_parameters(self, parameters: Dict[str, Any]) -> str:
        """Convert the JSON parameters into a flat string for embedding."""
        if not parameters:
            return "No parameters provided."
        try:
            # Sort keys to ensure consistent strings
            return json.dumps(parameters, sort_keys=True)
        except Exception:
            return str(parameters)

    def cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Calculate cosine similarity between two numpy vectors."""
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
        return float(dot_product / (norm_v1 * norm_v2))

    def evaluate(self, scope: str, parameters: Dict[str, Any]) -> Tuple[float, str]:
        """
        Evaluate the parameters against the agent's scope.
        Returns a tuple: (similarity_score, zone_name)
        """
        param_string = self.flatten_parameters(parameters)
        
        # FastEmbed returns a generator of embeddings. We use list() to exhaust it.
        embeddings = list(self.model.embed([scope, param_string]))
        scope_embedding = embeddings[0]
        param_embedding = embeddings[1]
        
        score = self.cosine_similarity(scope_embedding, param_embedding)
        
        if score >= self.ALLOW_THRESHOLD:
            zone = "allow"
        elif score >= self.WARN_THRESHOLD:
            zone = "warn"
        else:
            zone = "block"
            
        return score, zone

# Singleton
tier2_engine = Tier2Engine()
