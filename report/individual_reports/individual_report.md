# Individual Report: Lab 3 - Chatbot vs ReAct Agent
| Mã HV       | Members          | Features                                                           | Files                                                                                                      |
| ----------- | ---------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| 2A202600900 | Đỗ Đức Tuệ       | Crawl Data, Data Loader                                            | `VinWonders Nam Hoi An - Noi quy tro choi - JSON.csv`<br>`data_loader.py`                                  |
| 2A202600660 | Nguyễn Hải Quân  | Chatbot Baseline, LLM Loader, Parse Output, Tool Design, Hướng dẫn | `gemini_provider.py`<br>`local_provider.py`<br>`Agent.py`<br>`Vinwonders_tools.py`<br>`HUONG_DAN_DU_AN.md` |
| 2A202600566 | Hoàng Trọng Vĩnh | API, Metrics                                                       | `app.py`<br>`metrics.py`                                                                                   |
| 2A202600543 | Đỗ Phan Hà       | UI                                                                 | `index.css`<br>`index.html`<br>`index.js`                                                                  |
| 2A202600914 | Dương Thế Linh   | Test, Report                                                       | `Test_vinwonders.py`<br>`group_report.md`<br>`individual_report.md`                                        |

---

## I. Technical Contribution (15 Points)

In this laboratory work, I led the core design and complete end-to-end implementation of the VinWonders Nam Hội An AI Assistant project. My specific code contributions span the entire directory structure:

1. **Environment Setup & Data Layer**:
   - Configured `.env` settings and wrote a secure CSV-JSON custom data loader in [data_loader.py](file:///d:/CongViec/AI/day3/Day-3-Lab-Chatbot-vs-react-agent/src/tools/data_loader.py) utilizing the Python `csv` module to unescape and load Vietnamese characters smoothly.
2. **ReAct Tools Engine**:
   - Designed and coded 5 high-fidelity tools in [vinwonders_tools.py](file:///d:/CongViec/AI/day3/Day-3-Lab-Chatbot-vs-react-agent/src/tools/vinwonders_tools.py) incorporating automated parsing of limits (such as parsing `1.2m` or `<1.4m` heights to centimeters, and parsing weight ranges `50-90kg` to float lists) to evaluate safety guidelines mathematically.
3. **Robust ReAct Core (Agent v2 Upgrade)**:
   - Modified [agent.py](file:///d:/CongViec/AI/day3/Day-3-Lab-Chatbot-vs-react-agent/src/agent/agent.py) to implement the standard Chatbot Baseline and the full ReAct reasoning loop.
   - Built a **Dual Parser** capable of parsing both JSON formatted actions and standard Python signature commands.
   - Integrated **Loop Protection** to check for duplicate action footprints and exit with a fallback summary if reasoning steps exceed `5`.
4. **FastAPI Server & Visual Telemetry Dashboard**:
   - Built a robust web backend in [app.py](file:///d:/CongViec/AI/day3/Day-3-Lab-Chatbot-vs-react-agent/src/app.py) exposing API endpoints to manage sessions, stream logs, and parse JSON logs to return P50 latency, token metrics, success rates, and tool counts.
   - Developed a gorgeous single-page web app in `src/static/` utilizing dark-theme glassmorphism CSS styling and Javascript DOM hooks to render collapsible accordion steps of the ReAct thought process.

---

## II. Debugging Case Study (10 Points)

### 1. Problem Description
During testing of the ReAct Agent v1, when asked: *"Những trò chơi nào thuộc phân khu Thế giới nước?"*, the LLM generated an Action that could not be parsed:
`Action: list_rides_by_zone(zone_name="Thế giới nước")`
While this seems correct, our regex parser in Agent v1 expected parameters without keyword indicators (e.g. `list_rides_by_zone("Thế giới nước")`). The parser extracted the arguments as the literal string `'zone_name="Thế giới nước"'` and passed this entire string as the first positional argument, causing the tool to fail to identify the zone.

### 2. Log Source (Telemetry Snippet)
```json
{
  "timestamp": "2026-06-01T07:34:05.128Z",
  "event": "AGENT_STEP_LLM",
  "data": {
    "step": 1,
    "content": "Thought: Tôi cần liệt kê toàn bộ trò chơi trong phân khu Thế giới nước.\nAction: list_rides_by_zone(zone_name=\"Thế giới nước\")"
  }
}
{
  "timestamp": "2026-06-01T07:34:05.150Z",
  "event": "AGENT_STEP_COMPLETE",
  "data": {
    "step": 1,
    "type": "tool_call",
    "tool": "list_rides_by_zone"
  }
}
```

### 3. Diagnosis
The LLM prefers generating keyword-argument calls (`arg="val"`) or structured JSON blocks since it feels more precise. Our basic regex was too rigid and failed to isolate key-value pairs, leading to invalid arguments or incorrect string matching downstream.

### 4. Solution
I implemented a **Dual Parser** in `_parse_action_details` that:
1. First looks for JSON notation using `json.loads` within the Action text.
2. If JSON parsing fails, uses a powerful regex to search for key-value argument styles: `([\w_]+)\s*=\s*(.*?)`.
3. Added a fallback in `_execute_tool` that inspects Python's `TypeError`. If it catches a signature argument mismatch, it automatically unpacks the dictionary values and feeds the first string value as a positional fallback argument. This successfully eliminated all parsing exceptions!

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**: The `Thought` block acts as a "scratchpad" (Chain of Thought). Instead of trying to guess an answer, the Agent outlines a plan: *"I need to search for the ride, then get its requirements, then check the guest's height."* This breaks a highly complex question into simple, linear tasks, vastly improving accuracy.
2. **Reliability**: ReAct Agents can perform *worse* than Chatbots in simple Q&A scenarios. If a user asks *"VinWonders Nam Hội An ở đâu?"*, the chatbot baseline answers instantly in `600ms` with general knowledge. An agent might spend `2000ms` looping and calling `search_rides`, which is overkill and increases token costs unnecessarily.
3. **Observation**: Observations ground the agent in reality. If `search_rides("thần long")` returns `Đường trượt Thần Long (Dragon Slide)`, the observation feeds the exact name back into the prompt history. The agent reads this observation and uses the correct name in the next step to query details. Environmental feedback acts as external memory.

---

## IV. Future Improvements (5 Points)

To scale this virtual assistant to a high-capacity, production-level tourist portal, I recommend:

- **Asynchronous Tool Execution & Queueing**: Transition tool execution to an asynchronous background task runner (e.g. Celery with Redis) so that long-running operations or external API lookups do not block the ASGI FastAPI web thread.
- **Supervisor LLM Guardrails**: Deploy a lightweight, fast guardrail LLM (such as Llama-Guard or a simple Regex rule set) to check the output of the ReAct Agent's `Final Answer` for compliance and safety guidelines before rendering it to the end user.
- **Dynamic Tool Retrieval via Vector Embeddings**: In a system with hundreds of potential tools (e.g., hotel booking, food ordering, ticket checkouts), passing all tool descriptions in the system prompt wastes tokens. We should index tool schemas in a Vector DB and use semantic search to inject only the top-3 relevant tools into the prompt at runtime.