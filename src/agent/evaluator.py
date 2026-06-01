import os
import sys
import time
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.local_provider import LocalProvider
from src.agent.chatbot import BaselineChatbot
from src.agent.agent import ReActAgent
from src.telemetry.metrics import tracker

# Define test suite
TEST_CASES = [
    {
        "id": "Q1_SIMPLE",
        "query": "Tên chính xác của công viên chủ đề này là gì? Cho tôi biết các nguồn dữ liệu chính thống được sử dụng.",
        "desc": "Simple query testing baseline knowledge of park name and source urls."
    },
    {
        "id": "Q2_TICKET",
        "query": "Gia đình tôi gồm bố mẹ, 1 bé cao 0.9m và 1 bé cao 1.35m. Chúng tôi cần mua những loại vé nào theo quy định chiều cao?",
        "desc": "Single-step rule query requiring get_ticket_rules."
    },
    {
        "id": "Q3_MULTISTEP_SAFETY",
        "query": "Tôi cao 1.3m và nặng 60kg, có thể tham gia những trò chơi cảm giác mạnh nào ở Vùng đất phiêu lưu? Hãy kiểm tra chi tiết xem tôi có đủ điều kiện chơi trò Cú rơi thế kỷ hay không.",
        "desc": "Multi-step safety check requiring search_rides and check_ride_suitability."
    },
    {
        "id": "Q4_MULTISTEP_COMPARE",
        "query": "Tôi muốn tìm đường trượt ở Thế giới nước chơi bằng thiết bị phao cho nhóm 4 người chơi mỗi lượt. Có những trò nào như vậy và thời lượng của chúng?",
        "desc": "Complex comparison requiring search_rides and filtering by equipment/players."
    },
    {
        "id": "Q5_GENERAL_RULES",
        "query": "Tôi muốn mang đồ ăn nước uống và sử dụng điện thoại khi chơi các trò cảm giác mạnh ở công viên có được không? Quy định chung thế nào?",
        "desc": "General rule query requiring get_general_rules for thrill rides."
    }
]

def run_evaluator():
    load_dotenv()
    
    # Initialize Local Provider
    model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
    if not os.path.exists(model_path):
        print(f"❌ Error: Local model not found at {model_path}")
        return
        
    print("Initializing Local Llama Provider...")
    llm = LocalProvider(model_path=model_path)
    
    # Define Tools registry metadata for the Agent
    tools_metadata = [
        {
            "name": "get_ticket_rules",
            "description": "Lấy quy định chiều cao và phân loại giá vé của công viên.",
            "args_signature": ""
        },
        {
            "name": "get_general_rules",
            "description": "Lấy nội quy chung của công viên. Tham số category phải là 'water_park' hoặc 'thrill_rides'.",
            "args_signature": "category: str"
        },
        {
            "name": "search_rides",
            "description": "Tìm kiếm và lọc các trò chơi. Các tham số lọc tùy chọn gồm zone (Thế giới nước, Vùng đất phiêu lưu, Trò chơi trong nhà), category (Đường trượt, Sông hồ, Cảm giác mạnh, Thiếu nhi), name_query (tên trò chơi).",
            "args_signature": "zone: Optional[str] = None, category: Optional[str] = None, name_query: Optional[str] = None"
        },
        {
            "name": "check_ride_suitability",
            "description": "Kiểm tra xem chiều cao (m) và cân nặng (kg) của du khách có đủ điều kiện an toàn tham gia một trò chơi cụ thể hay không.",
            "args_signature": "ride_name: str, height_m: float, weight_kg: Optional[float] = None"
        }
    ]
    
    # Configurations to test
    configs = [
        {"name": "Chatbot Baseline", "type": "chatbot", "prompt_version": None},
        {"name": "ReAct Agent (Prompt v1)", "type": "agent", "prompt_version": "v1"},
        {"name": "ReAct Agent (Prompt v2)", "type": "agent", "prompt_version": "v2"}
    ]
    
    results = []
    
    print("\n==================================================")
    print("🚀 STARTING VINWONDERS CHATBOT VS AGENT BENCHMARK")
    print("==================================================\n")
    
    for config in configs:
        print(f"Running Configuration: {config['name']}...")
        
        # Instantiate correct handler
        if config["type"] == "chatbot":
            runner = BaselineChatbot(llm=llm)
        else:
            runner = ReActAgent(llm=llm, tools=tools_metadata, max_steps=6, prompt_version=config["prompt_version"])
            
        for case in TEST_CASES:
            print(f"  - Case {case['id']}: {case['query'][:50]}...")
            
            # Reset tracker metrics for this query run to isolate token count/latency
            tracker.session_metrics = []
            
            start_time = time.time()
            response = runner.run(case["query"])
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Accumulate metrics from tracker
            total_tokens = sum([m["total_tokens"] for m in tracker.session_metrics])
            prompt_tokens = sum([m["prompt_tokens"] for m in tracker.session_metrics])
            completion_tokens = sum([m["completion_tokens"] for m in tracker.session_metrics])
            total_cost = sum([m["cost_estimate"] for m in tracker.session_metrics])
            steps_taken = len(tracker.session_metrics) if config["type"] == "agent" else 1
            
            results.append({
                "config": config["name"],
                "case_id": case["id"],
                "query": case["query"],
                "response": response,
                "latency_ms": duration_ms,
                "steps": steps_taken,
                "tokens": total_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": total_cost
            })
            
            print(f"    Completed in {duration_ms}ms | Steps: {steps_taken} | Tokens: {total_tokens} | Cost: ${total_cost:.5f}")
            print(f"    Answer snippet: {response[:150].replace(chr(10), ' ')}...\n")
            
    # Output final summary markdown table
    print("\n" + "="*50)
    print("📊 BENCHMARK RESULTS SUMMARY")
    print("="*50 + "\n")
    
    print("| Configuration | Case ID | Steps | Latency (ms) | Tokens (P/C/T) | Cost ($) |")
    print("| :--- | :--- | :---: | :---: | :---: | :---: |")
    for r in results:
        tokens_str = f"{r['prompt_tokens']}/{r['completion_tokens']}/{r['tokens']}"
        print(f"| {r['config']} | {r['case_id']} | {r['steps']} | {r['latency_ms']:,} | {tokens_str} | {r['cost']:.5f} |")

    # Save evaluation summary to a file
    summary_path = "./logs/eval_summary.md"
    os.makedirs("./logs", exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# VinWonders Chatbot Benchmark Evaluation Results\n\n")
        f.write("| Configuration | Case ID | Steps | Latency (ms) | Tokens (P/C/T) | Cost ($) |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: |\n")
        for r in results:
            tokens_str = f"{r['prompt_tokens']}/{r['completion_tokens']}/{r['tokens']}"
            f.write(f"| {r['config']} | {r['case_id']} | {r['steps']} | {r['latency_ms']:,} | {tokens_str} | {r['cost']:.5f} |\n")
        
        f.write("\n\n## Detailed Responses\n\n")
        for r in results:
            f.write(f"### {r['config']} - {r['case_id']}\n")
            f.write(f"**Query**: {r['query']}\n\n")
            f.write(f"**Metrics**: Steps = {r['steps']} | Latency = {r['latency_ms']} ms | Tokens = {r['tokens']} | Cost = ${r['cost']:.5f}\n\n")
            f.write(f"**Response**:\n{r['response']}\n\n")
            f.write("---\n\n")
            
    print(f"\nSaved detailed evaluation results to {summary_path}")

if __name__ == "__main__":
    run_evaluator()
