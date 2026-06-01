import os
import re
import json
import time
from typing import List, Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker

class ReActAgent:
    """
    An industry-grade ReAct Agent implementing the Thought-Action-Observation loop
    with advanced parsing, loop protection, fallback execution, and telemetry logging.
    Supports both a baseline direct chat mode and an agentic ReAct mode.
    """
    
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps

    def get_system_prompt(self) -> str:
        """
        Creates the ReAct system prompt explaining the available tools,
        the expected Thought-Action-Observation loop structure, and strict format guidelines.
        """
        tool_descriptions = "\n".join([f"- **{t['name']}**: {t['description']}" for t in self.tools])
        
        return f"""Bạn là một Trợ lý AI chuyên nghiệp phụ trách giải đáp thông tin về Công viên giải trí VinWonders Nam Hội An.
Bạn có quyền truy cập vào các công cụ (tools) dưới đây để phục vụ tra cứu dữ liệu thực tế. KHÔNG ĐƯỢC tự bịa đặt thông tin không có trong kết quả trả về của công cụ.

### CÁC CÔNG CỤ HIỆN CÓ:
{tool_descriptions}

### QUY TRÌNH SUY LUẬN (ReAct Loop):
Khi người dùng đặt câu hỏi, bạn phải suy luận từng bước theo định dạng sau:
Thought: Phân tích câu hỏi và suy nghĩ xem cần dùng công cụ nào tiếp theo (hoặc đưa ra câu trả lời trực tiếp nếu thông tin đã đầy đủ).
Action: tên_công_cụ(tên_tham_số="giá_trị") hoặc viết dưới dạng JSON: {{"name": "tên_công_cụ", "arguments": {{"tên_tham_số": "giá_trị"}}}}
Observation: Kết quả trả về của công cụ (Hệ thống sẽ tự động cung cấp kết quả này sau khi Action được thực thi).
... (Lặp lại cặp Thought - Action - Observation nếu cần thiết để thu thập đủ dữ liệu)
Thought: Tôi đã có đủ thông tin cần thiết.
Final Answer: Câu trả lời cuối cùng và hoàn chỉnh nhất dành cho người dùng bằng tiếng Việt, có kết hợp đề xuất/gợi ý 2-3 câu hỏi liên quan để khuyến khích tương tác.

### CÁC NGUYÊN TẮC BẮT BUỘC:
1. Bạn PHẢI viết đúng định dạng tiêu đề "Thought:", "Action:", "Observation:", "Final Answer:".
2. Trong mỗi lượt suy luận, bạn chỉ được gọi duy nhất 1 Action.
3. Không tự tạo ra dữ liệu Observation. Bạn chỉ ghi nhận Observation từ kết quả thực tế của công cụ.
4. Nếu kết quả công cụ trống hoặc không tìm thấy, hãy thông báo rõ ràng cho người dùng, đề xuất họ cung cấp thêm từ khóa hoặc kiểm tra lại thông số.
5. Câu trả lời cuối cùng (Final Answer) phải thân thiện, chu đáo và bao gồm các gợi ý câu hỏi tiếp theo (ví dụ: "Bạn có muốn kiểm tra điều kiện chiều cao cho bé không?").
"""

    def run_baseline(self, user_input: str) -> Dict[str, Any]:
        """
        Runs the direct LLM baseline without any tools or step-by-step reasoning.
        Demonstrates the limitations of a standard LLM.
        """
        start_time = time.time()
        logger.log_event("BASELINE_START", {"input": user_input, "model": self.llm.model_name})
        
        baseline_system_prompt = """Bạn là trợ lý AI giải đáp thông tin về VinWonders Nam Hội An. 
Bạn không có quyền truy cập công cụ trực tiếp để tra cứu dữ liệu thời gian thực mà chỉ dựa vào tri thức sẵn có. 
Hãy trả lời câu hỏi của người dùng một cách thân thiện và chu đáo nhất."""
        
        try:
            response = self.llm.generate(user_input, system_prompt=baseline_system_prompt)
            content = response.get("content", "Không thể tạo phản hồi.")
            usage = response.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
            latency_ms = response.get("latency_ms", int((time.time() - start_time) * 1000))
            
            # Track metrics
            tracker.track_request(
                provider=response.get("provider", "google"),
                model=self.llm.model_name,
                usage=usage,
                latency_ms=latency_ms
            )
            
            result = {
                "answer": content,
                "trace": [],
                "metrics": {
                    "latency_ms": latency_ms,
                    "steps": 0,
                    "tokens": usage.get("total_tokens", 0),
                    "status": "success"
                }
            }
            logger.log_event("BASELINE_END", {"status": "success", "latency_ms": latency_ms})
            return result
            
        except Exception as e:
            logger.error(f"Error in Baseline: {e}")
            return {
                "answer": f"Đã xảy ra lỗi hệ thống khi gọi Baseline: {str(e)}",
                "trace": [],
                "metrics": {
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "steps": 0,
                    "tokens": 0,
                    "status": "error"
                }
            }

    def run(self, user_input: str) -> Dict[str, Any]:
        """
        Executes the ReAct loop:
        1. Query LLM to generate Thought + Action (or Final Answer).
        2. Parse Action, handle potential formatting anomalies, execute associated tool.
        3. Push Observation back into prompt history.
        4. Loop until Final Answer is found or max_steps is reached.
        """
        start_time = time.time()
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})
        
        prompt_history = f"User: {user_input}\n"
        steps = 0
        trace = []
        total_tokens = 0
        action_history = set()  # To detect repeating action loops
        
        while steps < self.max_steps:
            steps += 1
            step_start = time.time()
            
            # 1. Call LLM with the prompt history accumulated so far
            try:
                system_prompt = self.get_system_prompt()
                response = self.llm.generate(prompt_history, system_prompt=system_prompt)
                content = response.get("content", "").strip()
                usage = response.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
                latency_ms = response.get("latency_ms", int((time.time() - step_start) * 1000))
                
                total_tokens += usage.get("total_tokens", 0)
                
                tracker.track_request(
                    provider=response.get("provider", "google"),
                    model=self.llm.model_name,
                    usage=usage,
                    latency_ms=latency_ms
                )
            except Exception as e:
                logger.error(f"LLM generation failed at step {steps}: {e}")
                trace.append({
                    "step": steps,
                    "thought": "Đã xảy ra lỗi khi gọi LLM.",
                    "action": "N/A",
                    "observation": f"Lỗi: {str(e)}"
                })
                break

            logger.log_event("AGENT_STEP_LLM", {"step": steps, "content": content})

            # 2. Parse Thought, Action and Final Answer from output
            thought, action_str, final_answer = self._parse_react_output(content)
            
            trace_step = {
                "step": steps,
                "thought": thought or "Đang phân tích dữ liệu...",
                "action": action_str or "N/A",
                "observation": ""
            }

            # 3. Check if Final Answer is ready
            if final_answer:
                trace_step["action"] = "Không cần gọi công cụ (Đã tìm ra câu trả lời)"
                trace_step["observation"] = "Hoàn thành vòng lặp ReAct."
                trace.append(trace_step)
                logger.log_event("AGENT_STEP_COMPLETE", {"step": steps, "type": "final_answer"})
                
                total_latency = int((time.time() - start_time) * 1000)
                logger.log_event("AGENT_END", {"status": "success", "steps": steps, "latency_ms": total_latency})
                
                return {
                    "answer": final_answer,
                    "trace": trace,
                    "metrics": {
                        "latency_ms": total_latency,
                        "steps": steps,
                        "tokens": total_tokens,
                        "status": "success"
                    }
                }

            # 4. Process Action if available
            if action_str:
                tool_name, tool_args = self._parse_action_details(action_str)
                
                # Check for loop detection: is the agent calling the exact same tool with the exact same args?
                action_fingerprint = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
                if action_fingerprint in action_history:
                    # Loop detected! Force fallback
                    warning_msg = f"Cảnh báo: Phát hiện vòng lặp vô hạn gọi công cụ '{tool_name}'."
                    logger.log_event("AGENT_LOOP_DETECTED", {"action": action_fingerprint})
                    trace_step["observation"] = f"Hệ thống: {warning_msg} Kết thúc vòng lặp để đưa ra kết quả tốt nhất."
                    trace.append(trace_step)
                    break
                
                action_history.add(action_fingerprint)

                # Execute tool
                observation = self._execute_tool(tool_name, tool_args)
                trace_step["observation"] = observation
                trace.append(trace_step)
                
                # Append thought, action, and observation to the history so LLM can read in the next loop
                prompt_history += f"\nThought: {thought}\nAction: {action_str}\nObservation: {observation}\n"
                logger.log_event("AGENT_STEP_COMPLETE", {"step": steps, "type": "tool_call", "tool": tool_name})
            else:
                # No action and no final answer found! Parser error fallback
                fallback_msg = "Không thể phân tách Action hoặc Final Answer từ đầu ra của LLM."
                trace_step["observation"] = f"Hệ thống: {fallback_msg}"
                trace.append(trace_step)
                logger.log_event("AGENT_PARSER_ERROR", {"content": content})
                
                # Append a hint for LLM to produce either a Final Answer or a valid Action
                prompt_history += f"\nThought: {thought or 'Tôi cần tiếp tục suy luận.'}\nHệ thống: Vui lòng đưa ra hành động 'Action: tên_công_cụ(tham_số)' hợp lệ hoặc 'Final Answer: câu trả lời'.\n"

        # 5. Handle fallback when maximum steps exceeded or loop terminated
        logger.log_event("AGENT_FALLBACK_TRIGGERED", {"steps": steps})
        
        # Run a fallback generation asking the LLM to summarize based on the history gathered so far
        fallback_prompt = prompt_history + "\nThought: Đã quá giới hạn bước hoặc gặp vòng lặp. Tôi phải tổng hợp các thông tin đã có thành câu trả lời hoàn chỉnh ngay lập tức.\nFinal Answer:"
        try:
            fallback_response = self.llm.generate(fallback_prompt, system_prompt=self.get_system_prompt())
            fallback_answer = fallback_response.get("content", "").strip()
            # If the output contains 'Final Answer:', strip it
            if "Final Answer:" in fallback_answer:
                fallback_answer = fallback_answer.split("Final Answer:")[-1].strip()
        except Exception as e:
            fallback_answer = f"Tôi xin lỗi, hệ thống đã đạt giới hạn suy luận nhưng không thể tổng hợp kết quả chính xác do lỗi: {str(e)}."

        total_latency = int((time.time() - start_time) * 1000)
        logger.log_event("AGENT_END", {"status": "fallback", "steps": steps, "latency_ms": total_latency})
        
        return {
            "answer": fallback_answer,
            "trace": trace,
            "metrics": {
                "latency_ms": total_latency,
                "steps": steps,
                "tokens": total_tokens,
                "status": "fallback"
            }
        }

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        Executes a tool dynamically by matching name and injecting unpacked arguments.
        Includes robust error trapping and argument fallback names.
        """
        for tool in self.tools:
            if tool["name"] == tool_name:
                try:
                    # Unpack arguments and match keys
                    func = tool["func"]
                    # Call function with dict unpacked as kwargs
                    # Catch cases where tool takes positional argument or keyword
                    # e.g., search_rides(query="...")
                    return str(func(**args))
                except TypeError as te:
                    # Catch wrong argument names and try to map them to the first parameter of the tool
                    logger.error(f"Type error executing tool {tool_name} with args {args}: {te}")
                    # Try fallback: if args contains values, pass the first value as a single parameter
                    if args:
                        first_val = list(args.values())[0]
                        try:
                            return str(func(first_val))
                        except Exception as inner_e:
                            return f"Lỗi tham số khi chạy công cụ '{tool_name}': {inner_e}"
                    return f"Lỗi tham số khi chạy công cụ '{tool_name}': {te}"
                except Exception as e:
                    logger.error(f"Exception executing tool {tool_name}: {e}")
                    return f"Lỗi hệ thống khi chạy công cụ '{tool_name}': {str(e)}"
                    
        return f"Không tìm thấy công cụ '{tool_name}'."

    def _parse_react_output(self, text: str) -> tuple:
        """
        Extracts Thought, Action, and Final Answer from the raw LLM output.
        Handles variations in capitalization and spacing.
        """
        thought = None
        action = None
        final_answer = None

        # Look for Thought
        thought_match = re.search(r"Thought:\s*(.*?)(?=(Action:|Final Answer:|$))", text, re.DOTALL | re.IGNORECASE)
        if thought_match:
            thought = thought_match.group(1).strip()

        # Look for Action
        action_match = re.search(r"Action:\s*(.*?)(?=(Observation:|Final Answer:|$))", text, re.DOTALL | re.IGNORECASE)
        if action_match:
            action = action_match.group(1).strip()

        # Look for Final Answer
        final_match = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL | re.IGNORECASE)
        if final_match:
            final_answer = final_match.group(1).strip()

        return thought, action, final_answer

    def _parse_action_details(self, action_str: str) -> tuple:
        """
        Advanced Dual Parser: Supports parsing tool calls from both:
        1. JSON strings: {"name": "tool_name", "arguments": {"arg1": "val"}}
        2. Standard Python calls: tool_name(arg_name="value", another_arg=5)
        """
        action_str = action_str.strip()
        
        # Check if action_str is/contains JSON
        json_match = re.search(r"(\{.*\})", action_str, re.DOTALL)
        if json_match:
            try:
                json_data = json.loads(json_match.group(1))
                tool_name = json_data.get("name", "").strip()
                tool_args = json_data.get("arguments", {})
                if tool_name:
                    return tool_name, tool_args
            except json.JSONDecodeError:
                pass # Fall back to regex parsing

        # Try parsing standard python style: tool_name(arg="val", arg2=12)
        py_match = re.match(r"^([\w_]+)\((.*)\)$", action_str, re.DOTALL)
        if py_match:
            tool_name = py_match.group(1).strip()
            args_str = py_match.group(2).strip()
            tool_args = {}
            
            if args_str:
                # Parse keyword arguments e.g., query="thần long", height_cm=135
                kwargs = re.findall(r"([\w_]+)\s*=\s*(.*?)(?:,\s*(?=[\w_]+\s*=)|$)", args_str, re.DOTALL)
                if kwargs:
                    for k, v in kwargs:
                        k = k.strip()
                        v = v.strip().strip("'\"") # strip quotes
                        # Try casting to numeric if applicable
                        try:
                            if "." in v:
                                tool_args[k] = float(v)
                            else:
                                tool_args[k] = int(v)
                        except ValueError:
                            tool_args[k] = v
                else:
                    # Positional fallback (if it's a single argument like "search_rides('thần long')")
                    val = args_str.strip().strip("'\"")
                    # Try detecting if we can map to the tool's signature
                    # By default, pass under a generic key 'query' or 'ride_name'
                    # We'll detect later in execution, but for now we put it in key 'query' and 'ride_name'
                    tool_args["query"] = val
                    tool_args["ride_name"] = val
                    try:
                        if "." in val:
                            tool_args["height_cm"] = float(val)
                        else:
                            tool_args["height_cm"] = int(val)
                    except ValueError:
                        pass
                        
            return tool_name, tool_args

        # Fallback if only the name is outputted e.g. "search_rides" without brackets
        return action_str, {}
