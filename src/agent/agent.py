import os
import re
import time
from typing import List, Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker
from src.tools.vinwonders_tools import (
    get_ticket_rules,
    get_general_rules,
    search_rides,
    check_ride_suitability
)

class ReActAgent:
    """
    A ReAct-style Agent that follows the Thought-Action-Observation loop.
    Supports Prompt V1 and V2, dynamically executes custom tools, tracks performance,
    and handles parser errors elegantly.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5, prompt_version: str = "v2"):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []
        self.prompt_version = prompt_version

    def get_system_prompt(self) -> str:
        """
        Generates the system prompt based on the chosen prompt version.
        Supports V1 (Standard) and V2 (Improved with strict rules and few-shots).
        """
        tool_descriptions = "\n".join([f"- {t['name']}: {t['description']}. Signature: {t['name']}({t.get('args_signature', '')})" for t in self.tools])
        
        if self.prompt_version == "v1":
            return f"""
            Bạn là trợ lý AI thông minh của VinWonders Nam Hội An. Bạn có quyền truy cập các công cụ sau:
            {tool_descriptions}

            Hãy sử dụng đúng định dạng sau:
            Thought: suy nghĩ của bạn.
            Action: tên_công_cụ(tham_số)
            Observation: kết quả từ công cụ.
            ... (lặp lại Thought/Action/Observation nếu cần)
            Final Answer: câu trả lời cuối cùng bằng tiếng Việt.
            """
            # Prompt V2: Chuẩn nghiệp, rõ ràng, có ràng buộc chặt chẽ và few-shot examples
            return f"""
            Bạn là Agent AI chuyên gia hỏi đáp về VinWonders Nam Hội An. Nhiệm vụ của bạn là trả lời chính xác các câu hỏi bằng cách sử dụng các công cụ có sẵn.
            
            CÁC CÔNG CỤ CÓ SẴN:
            {tool_descriptions}
            
            QUY TẪC BẮT BUỘC:
            1. Bạn PHẢI luôn tuân theo chu trình Thought → Action → Observation.
            2. Mỗi lượt chỉ viết MỘT Thought và MỘT Action, HOẶC MỘT Thought và MỘT Final Answer. Không viết cả Action lẫn Final Answer trong cùng một lượt.
            3. Không được tự đặt ra công cụ. Chỉ dùng các công cụ đã liệt kê ở trên.
            4. Cú pháp gọi công cụ: Action: tên_công_cụ(tham_số="giá_trị"). Chuỗi phải đặt trong dấu ngoặc kép.
            5. Nếu công cụ lỗi hoặc không có dữ liệu, phân tích lỗi và thử truy vấn khác. Không lặp lại hành động đã thất bại.
            6. Khi đã có đủ thông tin, viết "Final Answer:" kèm câu trả lời đầy đủ và lịch sự bằng tiếng Việt.
            7. Giới hạn chiều cao rất quan trọng. Hãy kiểm tra bằng công cụ check_ride_suitability.
            
            FEW-SHOT EXAMPLES:
            
            Example 1 (Multi-step query):
            User: Tôi cao 1.3m, có chơi được trò Cú rơi thế kỷ không?
            Thought: Người dùng muốn biết có thể chơi trò Cú rơi thế kỷ với chiều cao 1.3m không. Tôi cần sử dụng công cụ check_ride_suitability để kiểm tra.
            Action: check_ride_suitability(ride_name="Cú rơi thế kỷ", height_m=1.3)
            Observation: === ĐÁNH GIÁ SỰ PHÙ HỢP CHO TRÒ CHƠI: Cú rơi thế kỷ ===
            Độ tuổi/thông số của bạn: Chiều cao: 1.3m | Cân nặng: Không cung cấp
            Trạng thái: ✅ PHÙ HỢP / ĐỦ ĐIỀU KIỆN THAM GIA
            Chi tiết lý do:
            - Bạn thỏa mãn tất cả các điều kiện an toàn về chiều cao và cân nặng.
            Thought: Công cụ xác nhận người dùng cao 1.3m đủ điều kiện tham gia trò Cú rơi thế kỷ. Tôi sẽ cung cấp câu trả lời cuối cùng cho người dùng.
            Final Answer: Chào bạn, với chiều cao 1.3m, bạn hoàn toàn đủ điều kiện để tham gia trò chơi "Cú rơi thế kỷ" (Swiss Tower) tại VinWonders Nam Hội An. Chúc bạn có những trải nghiệm tuyệt vời!
            
            Example 2 (Ticket calculation):
            User: Nhà tôi có 2 người lớn và 1 trẻ em cao 1.2m thì giá vé thế nào?
            Thought: Tôi cần kiểm tra quy định giá vé theo chiều cao để tính toán.
            Action: get_ticket_rules()
            Observation: === QUY ĐỊNH CHIỀU CAO VÀ GIÁ VÉ - VinWonders Nam Hội An ===
            - Under 1m: Miễn phí
            - From 1m to under 1.4m: Vé trẻ em
            - From 1.4m: Vé người lớn
            Thought: Theo quy định: trẻ em cao 1.2m thuộc nhóm "từ 1m đến dưới 1.4m" nên sẽ mua vé trẻ em. Hai người lớn cao trên 1.4m sẽ mua 2 vé người lớn. Tôi sẽ tổng hợp câu trả lời.
            Final Answer: Chào bạn, theo quy định giá vé tại VinWonders Nam Hội An:
            - Bé cao 1.2m (nằm trong khoảng từ 1m đến dưới 1.4m) sẽ được áp dụng mức giá **Vé trẻ em**.
            - 2 người lớn sẽ áp dụng mức giá **Vé người lớn**.
            Tổng cộng gia đình mình cần mua **2 vé người lớn** và **1 vé trẻ em**. Bé dưới 1m sẽ được miễn phí hoàn toàn.
            """

    def run(self, user_input: str) -> str:
        """
        Runs the ReAct loop: Thought -> Action -> Observation -> Thought...
        """
        logger.log_event("AGENT_START", {
            "input": user_input, 
            "model": self.llm.model_name, 
            "prompt_version": self.prompt_version
        })
        
        current_prompt = user_input
        steps = 0
        total_latency_ms = 0
        
        while steps < self.max_steps:
            logger.log_event("AGENT_STEP", {"step": steps + 1, "max_steps": self.max_steps})
            
            # 1. Generate response from LLM
            start_time = time.time()
            result_dict = self.llm.generate(current_prompt, system_prompt=self.get_system_prompt())
            latency_ms = result_dict.get("latency_ms", int((time.time() - start_time) * 1000))
            total_latency_ms += latency_ms
            
            usage = result_dict.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
            
            # Track request telemetry
            tracker.track_request(
                provider=result_dict.get("provider", "local"),
                model=self.llm.model_name,
                usage=usage,
                latency_ms=latency_ms
            )
            
            content = result_dict.get("content", "").strip()
            logger.log_event("LLM_RESPONSE", {"content": content, "step": steps + 1})
            
            # Append LLM output to prompt
            current_prompt += f"\n{content}"
            
            # 2. Check for Final Answer (ends loop)
            final_answer_match = re.search(r"Final\s*Answer:\s*(.*)", content, re.DOTALL | re.IGNORECASE)
            if final_answer_match:
                final_answer = final_answer_match.group(1).strip()
                logger.log_event("AGENT_END", {
                    "status": "success",
                    "steps": steps + 1,
                    "total_latency_ms": total_latency_ms,
                    "final_answer": final_answer
                })
                return final_answer
                
            # 3. Parse Action: tool_name(arguments)
            action_match = re.search(r"Action:\s*(\w+)\((.*)\)", content, re.IGNORECASE)
            if action_match:
                tool_name = action_match.group(1).strip()
                tool_args = action_match.group(2).strip()
                
                # Execute tool
                observation = self._execute_tool(tool_name, tool_args)
                
                logger.log_event("AGENT_OBSERVATION", {"tool": tool_name, "observation": observation})
                
                # Append Observation to prompt
                current_prompt += f"\nObservation: {observation}"
            else:
                # Failure handling: If model outputs a thought but no action or final answer,
                # guide it back using a structured observation error.
                error_msg = "Error: System could not parse an Action or Final Answer from your output. Please follow the format 'Action: tool_name(args)' or 'Final Answer: your response' strictly."
                logger.log_event("PARSER_ERROR", {"content": content})
                current_prompt += f"\nObservation: {error_msg}"
                
            steps += 1
            
        logger.log_event("AGENT_END", {
            "status": "timeout",
            "steps": steps,
            "total_latency_ms": total_latency_ms
        })
        
        # Timeout fallback
        return "Xin lỗi bạn, hệ thống đã vượt quá số bước suy luận tối đa cho phép để trả lời câu hỏi này."

    def _execute_tool(self, tool_name: str, args_str: str) -> str:
        """
        Executes a registered tool by name with parsed arguments.
        """
        tool_funcs = {
            "get_ticket_rules": get_ticket_rules,
            "get_general_rules": get_general_rules,
            "search_rides": search_rides,
            "check_ride_suitability": check_ride_suitability
        }
        
        if tool_name not in tool_funcs:
            return f"Error: Tool '{tool_name}' not found. Available tools: {list(tool_funcs.keys())}"
            
        try:
            parsed_args = self._parse_args(args_str)
            logger.log_event("TOOL_EXECUTE_START", {"tool": tool_name, "args": parsed_args})
            start_time = time.time()
            
            func = tool_funcs[tool_name]
            if isinstance(parsed_args, dict):
                result = func(**parsed_args)
            elif isinstance(parsed_args, list):
                result = func(*parsed_args)
            else:
                result = func()
                
            latency_ms = int((time.time() - start_time) * 1000)
            logger.log_event("TOOL_EXECUTE_END", {"tool": tool_name, "latency_ms": latency_ms})
            
            return str(result)
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {str(e)}")
            return f"Error executing tool '{tool_name}': {str(e)}"

    def _parse_args(self, args_str: str) -> Any:
        """
        Robustly parses a tool argument string into Python keywords or positional arguments.
        Supports:
        - Keyword arguments: arg1="value", arg2=1.35, arg3=None
        - Positional arguments: "value", 1.35, None
        """
        args_str = args_str.strip()
        if not args_str:
            return {}
            
        if args_str.startswith("(") and args_str.endswith(")"):
            args_str = args_str[1:-1].strip()
            
        if "=" in args_str:
            kwargs = {}
            # Match key="value" or key='value' or key=value (word or float or special terms)
            pattern = r"(\w+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([a-zA-Z0-9.\-_/<>]+))"
            matches = re.findall(pattern, args_str)
            for key, val_double, val_single, val_raw in matches:
                val = val_double or val_single or val_raw
                if val == "None" or val == "null":
                    kwargs[key] = None
                elif val == "True" or val == "true":
                    kwargs[key] = True
                elif val == "False" or val == "false":
                    kwargs[key] = False
                else:
                    try:
                        if "." in val:
                            kwargs[key] = float(val)
                        else:
                            kwargs[key] = int(val)
                    except ValueError:
                        kwargs[key] = val
            return kwargs
        else:
            args_list = []
            # Split by comma that is not inside quotes
            parts = re.split(r",(?=(?:[^\"']*[\"'][^\"']*[\"'])*[^\"']*$)", args_str)
            for part in parts:
                part = part.strip().strip("'\"")
                if not part:
                    continue
                if part == "None" or part == "null":
                    args_list.append(None)
                elif part == "True" or part == "true":
                    args_list.append(True)
                elif part == "False" or part == "false":
                    args_list.append(False)
                else:
                    try:
                        if "." in part:
                            args_list.append(float(part))
                        else:
                            args_list.append(int(part))
                    except ValueError:
                        args_list.append(part)
            return args_list
