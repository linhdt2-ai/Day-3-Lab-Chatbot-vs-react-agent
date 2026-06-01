import time
from typing import Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker

class BaselineChatbot:
    """
    A standard LLM Chatbot that answers questions based on pre-trained knowledge or a simple prompt.
    It does not have access to external tools, simulating the baseline chatbot behavior.
    """
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def get_system_prompt(self) -> str:
        return """
        Bạn là trợ lý ảo thân thiện và hữu ích của VinWonders Nam Hội An.
        Nhiệm vụ của bạn là trả lời các câu hỏi của khách du lịch về công viên, giá vé và các trò chơi một cách tốt nhất có thể.
        Vì bạn không có công cụ tra cứu dữ liệu trực tiếp, hãy trả lời dựa trên kiến thức của bạn.
        Hãy luôn trả lời lịch sự, rõ ràng và có cấu trúc bằng tiếng Việt.
        """

    def run(self, user_input: str) -> str:
        """
        Thực thi chatbot cơ sở bằng cách gửi câu hỏi trực tiếp tới mô hình LLM (không có công cụ).
        """
        logger.log_event("CHATBOT_START", {"input": user_input, "model": self.llm.model_name})
        
        start_time = time.time()
        
        # Generate the response
        response = self.llm.generate(prompt=user_input, system_prompt=self.get_system_prompt())
        
        latency_ms = response.get("latency_ms", int((time.time() - start_time) * 1000))
        usage = response.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        
        # Log to telemetry
        tracker.track_request(
            provider=response.get("provider", "local"),
            model=self.llm.model_name,
            usage=usage,
            latency_ms=latency_ms
        )
        
        logger.log_event("CHATBOT_END", {"latency_ms": latency_ms, "tokens": usage.get("total_tokens", 0)})
        
        return response.get("content", "Xin lỗi, tôi không thể tạo câu trả lời cho câu hỏi này.")
