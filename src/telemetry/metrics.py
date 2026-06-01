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
        Calculates the actual API cost based on the model name and usage metrics (input vs output tokens).
        Rates are based on current official industry pricing (per 1,000,000 tokens).
        """
        model_lower = model.lower()
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        
        # 1. Gemini Models (gemini-1.5-flash, gemini-1.5-pro, etc.)
        if "gemini" in model_lower:
            if "pro" in model_lower:
                # Gemini 1.5 Pro: $1.25 / 1M input, $5.00 / 1M output
                cost = (prompt_tokens * 1.25 + completion_tokens * 5.00) / 1_000_000
            else:
                # Gemini 1.5 Flash: $0.075 / 1M input, $0.30 / 1M output
                cost = (prompt_tokens * 0.075 + completion_tokens * 0.30) / 1_000_000
                
        # 2. OpenAI GPT-4o / GPT-4o-mini
        elif "gpt-4o-mini" in model_lower:
            # GPT-4o-mini: $0.150 / 1M input, $0.600 / 1M output
            cost = (prompt_tokens * 0.150 + completion_tokens * 0.600) / 1_000_000
        elif "gpt-4" in model_lower:
            # GPT-4o: $2.50 / 1M input, $10.00 / 1M output
            cost = (prompt_tokens * 2.50 + completion_tokens * 10.00) / 1_000_000
            
        # 3. Local model / fallback
        else:
            # Assume a very minimal free/local rate or generic cheap LLM API rate
            cost = 0.0
            
        return cost

# Global tracker instance
tracker = PerformanceTracker()