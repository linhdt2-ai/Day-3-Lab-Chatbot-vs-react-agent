import time
from typing import Dict, Any, List
from src.telemetry.logger import logger

class PerformanceTracker:
    """
    Tracking industry-standard metrics for LLMs.
    """
    def __init__(self):
        self.session_metrics = []

    def track_request(self, provider: str, model: str, usage: Dict[str, int], latency_ms: int):
        """
        Logs a single request metric to our telemetry.
        """
        metric = {
            "provider": provider,
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "latency_ms": latency_ms,
            "cost_estimate": self._calculate_cost(model, usage) # Mock cost calculation
        }
        self.session_metrics.append(metric)
        logger.log_event("LLM_METRIC", metric)

    def _calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """
        Calculates estimated API costs based on model and token count.
        - local: $0.00 (Free local CPU execution)
        - gpt-4o (openai): Input $0.005 / 1K tokens, Output $0.015 / 1K tokens
        - gemini-1.5-flash (google): Input $0.000075 / 1K tokens, Output $0.0003 / 1K tokens
        """
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        
        model_lower = model.lower()
        if "phi" in model_lower or "gguf" in model_lower:
            # Local models are free to run
            return 0.0
        elif "gpt-4" in model_lower or "openai" in model_lower:
            return (prompt_tokens / 1000) * 0.005 + (completion_tokens / 1000) * 0.015
        elif "gemini" in model_lower or "google" in model_lower:
            return (prompt_tokens / 1000) * 0.000075 + (completion_tokens / 1000) * 0.0003
        else:
            # Fallback default commercial rate
            return (usage.get("total_tokens", 0) / 1000) * 0.002

# Global tracker instance
tracker = PerformanceTracker()

