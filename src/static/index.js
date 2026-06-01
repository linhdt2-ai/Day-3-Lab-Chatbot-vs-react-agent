// ==========================================================================
// STATE MANAGEMENT & GLOBALS
// ==========================================================================
let currentSessionId = "";
let currentProvider = "google";
let currentMode = "react";
let activeTab = "chat";
let theme = "dark";

// ==========================================================================
// ON INITIALIZATION
// ==========================================================================
document.addEventListener("DOMContentLoaded", () => {
    // Generate or retrieve session ID
    startNewChat();
    // Load historical sessions in sidebar
    fetchSessions();
    // Fetch initial analytics
    fetchDashboardData();
    
    // Auto-scroll log stream on load
    const logBox = document.getElementById("terminal-log-container");
    logBox.scrollTop = logBox.scrollHeight;
});

// ==========================================================================
// THEME & VIEW CONFIGURATION
// ==========================================================================
function toggleTheme() {
    const body = document.body;
    const themeIndicator = document.getElementById("theme-indicator");
    
    if (theme === "dark") {
        theme = "light";
        body.classList.remove("dark-theme");
        body.classList.add("light-theme");
        themeIndicator.className = "fa-solid fa-sun theme-icon";
        themeIndicator.style.color = "var(--color-amber)";
        addLogLine("SYSTEM", "Chuyển sang Giao diện Sáng (Light Theme).");
    } else {
        theme = "dark";
        body.classList.remove("light-theme");
        body.classList.add("dark-theme");
        themeIndicator.className = "fa-solid fa-moon theme-icon";
        themeIndicator.style.color = "var(--color-amber)";
        addLogLine("SYSTEM", "Chuyển sang Giao diện Tối (Dark Theme).");
    }
}

function switchTab(tab) {
    if (activeTab === tab) return;
    
    activeTab = tab;
    
    // Manage tab buttons classes
    document.getElementById("tab-btn-chat").classList.toggle("active", tab === 'chat');
    document.getElementById("tab-btn-dashboard").classList.toggle("active", tab === 'dashboard');
    
    // Manage view panels classes
    document.getElementById("view-chat").classList.toggle("active", tab === 'chat');
    document.getElementById("view-dashboard").classList.toggle("active", tab === 'dashboard');
    
    if (tab === 'dashboard') {
        fetchDashboardData();
        addLogLine("SYSTEM", "Đã tải dữ liệu Dashboard Telemetry.");
    }
}

function switchMode(mode) {
    if (currentMode === mode) return;
    
    currentMode = mode;
    document.getElementById("mode-btn-react").classList.toggle("active", mode === 'react');
    document.getElementById("mode-btn-baseline").classList.toggle("active", mode === 'baseline');
    
    // Update indicator status text
    updateStatusIndicator();
    addLogLine("SYSTEM", `Chuyển chế độ hoạt động sang: ${mode === 'react' ? 'ReAct Agent (Truy cập công cụ)' : 'Baseline Chatbot (LLM thông thường)'}`);
}

function onConfigChange() {
    currentProvider = document.getElementById("provider-select").value;
    updateStatusIndicator();
    addLogLine("SYSTEM", `Thay đổi nhà cung cấp mô hình: ${currentProvider.toUpperCase()}`);
}

function updateStatusIndicator() {
    const statusText = document.getElementById("status-model-text");
    const providerLabel = currentProvider === 'google' ? 'Gemini 2.5' : (currentProvider === 'openai' ? 'GPT-4o' : 'Phi-3 CPU');
    const modeLabel = currentMode === 'react' ? 'ReAct Loop Active' : 'Direct baseline';
    statusText.innerText = `${providerLabel} - ${modeLabel}`;
}

// ==========================================================================
// SESSION MANAGEMENT (HISTORY MODULE)
// ==========================================================================
function preserveThinkingIndicator() {
    const indicator = document.getElementById("thinking-indicator");
    const container = document.getElementById("chat-messages-container");
    if (indicator && container && indicator.parentNode === container) {
        // Move it back as a sibling of container to preserve it from innerHTML clearing
        container.parentNode.appendChild(indicator);
        indicator.style.display = "none";
    }
}

function startNewChat() {
    preserveThinkingIndicator();
    currentSessionId = "session_" + Math.random().toString(36).substring(2, 15);
    
    // Clear chat container and re-render welcome screen
    const container = document.getElementById("chat-messages-container");
    container.innerHTML = `
        <div class="welcome-screen" id="welcome-screen">
            <div class="welcome-icon"><i class="fa-solid fa-robot"></i></div>
            <h2>Xin chào! Tôi có thể giúp gì cho bạn hôm nay?</h2>
            <p>Tôi là trợ lý AI được tích hợp hệ thống suy luận ReAct Agent có khả năng truy cập các công cụ tra cứu thông tin thực tế về VinWonders Nam Hội An.</p>
            <div class="suggestion-section">
                <div class="suggestion-title">Đề xuất câu hỏi tra cứu nhanh:</div>
                <div class="suggestion-grid">
                    <div class="suggestion-card" onclick="useSuggestion('Có những trò chơi nào trong phân khu Thế giới nước?')">
                        <i class="fa-solid fa-water"></i>
                        <span>Trò chơi trong Thế giới nước</span>
                    </div>
                    <div class="suggestion-card" onclick="useSuggestion('Bé nhà mình cao 1m3 và nặng 35kg có được chơi trò Đường trượt Siêu tốc không?')">
                        <i class="fa-solid fa-person-running"></i>
                        <span>Kiểm tra điều kiện chơi cho bé</span>
                    </div>
                    <div class="suggestion-card" onclick="useSuggestion('Giá vé vào cổng được tính thế nào dựa vào chiều cao?')">
                        <i class="fa-solid fa-ticket"></i>
                        <span>Tra cứu giá vé vào cổng</span>
                    </div>
                    <div class="suggestion-card" onclick="useSuggestion('Tìm thông tin chi tiết về trò chơi Cơn lốc sa mạc')">
                        <i class="fa-solid fa-magnifying-glass"></i>
                        <span>Chi tiết trò Cơn lốc sa mạc</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove active styles from sidebar sessions
    const sessionItems = document.querySelectorAll(".history-item");
    sessionItems.forEach(item => item.classList.remove("active"));
    
    updateStatusIndicator();
    addLogLine("SYSTEM", `Khởi tạo phiên hội thoại mới: ${currentSessionId}`);
}

async function fetchSessions() {
    try {
        const response = await fetch("/api/history");
        const sessions = await response.json();
        const listContainer = document.getElementById("sessions-list");
        
        if (sessions.length === 0) {
            listContainer.innerHTML = `<div class="loading-history">Không có lịch sử hội thoại.</div>`;
            return;
        }
        
        listContainer.innerHTML = "";
        sessions.forEach(session => {
            const dateObj = new Date(session.created_at);
            const dateStr = dateObj.toLocaleDateString("vi-VN") + " " + dateObj.toLocaleTimeString("vi-VN", {hour: '2-digit', minute:'2-digit'});
            
            const activeClass = session.session_id === currentSessionId ? "active" : "";
            
            const item = document.createElement("div");
            item.className = `history-item ${activeClass}`;
            item.id = `session-item-${session.session_id}`;
            item.setAttribute("onclick", `loadSession('${session.session_id}')`);
            
            item.innerHTML = `
                <div class="history-info">
                    <span class="history-title">${escapeHTML(session.title)}</span>
                    <span class="history-date">${dateStr}</span>
                </div>
                <button class="action-icon-btn delete-session-btn" onclick="deleteSession(event, '${session.session_id}')" title="Xóa phiên này">
                    <i class="fa-regular fa-trash-can"></i>
                </button>
            `;
            listContainer.appendChild(item);
        });
    } catch (e) {
        console.error("Error loading sessions: ", e);
    }
}

async function loadSession(sessionId) {
    if (currentSessionId === sessionId) return;
    
    preserveThinkingIndicator();
    currentSessionId = sessionId;
    addLogLine("SYSTEM", `Đang tải phiên hội thoại: ${sessionId}`);
    
    // Update sidebar active class
    const sessionItems = document.querySelectorAll(".history-item");
    sessionItems.forEach(item => item.classList.remove("active"));
    const activeItem = document.getElementById(`session-item-${sessionId}`);
    if (activeItem) activeItem.classList.add("active");
    
    try {
        const response = await fetch(`/api/history/${sessionId}`);
        if (!response.ok) throw new Error("Failed to fetch session messages");
        
        const messages = await response.json();
        const container = document.getElementById("chat-messages-container");
        container.innerHTML = ""; // Clear current messages
        
        messages.forEach(msg => {
            if (msg.role === "user") {
                appendUserMessage(msg.content);
            } else {
                appendAssistantMessage(msg.content, msg.trace, msg.metrics);
                // Sync settings indicators with loaded assistant provider/mode
                if (msg.provider) {
                    document.getElementById("provider-select").value = msg.provider;
                    currentProvider = msg.provider;
                }
                if (msg.mode) {
                    currentMode = msg.mode;
                    document.getElementById("mode-btn-react").classList.toggle("active", msg.mode === 'react');
                    document.getElementById("mode-btn-baseline").classList.toggle("active", msg.mode === 'baseline');
                }
            }
        });
        
        updateStatusIndicator();
        scrollChatToBottom();
    } catch (e) {
        console.error("Failed to load session messages: ", e);
        addLogLine("ERROR", `Lỗi khi tải tin nhắn: ${e.message}`);
    }
}

async function deleteSession(event, sessionId) {
    event.stopPropagation(); // Avoid triggering loadSession
    if (!confirm("Bạn có chắc chắn muốn xóa hội thoại này không?")) return;
    
    addLogLine("SYSTEM", `Đang xóa phiên hội thoại: ${sessionId}`);
    try {
        const response = await fetch(`/api/history/${sessionId}`, { method: "DELETE" });
        if (response.ok) {
            if (currentSessionId === sessionId) {
                startNewChat();
            }
            fetchSessions();
        }
    } catch (e) {
        console.error("Failed to delete session: ", e);
    }
}

async function clearAllHistory() {
    if (!confirm("Cảnh báo: Bạn có chắc chắn muốn XÓA TOÀN BỘ lịch sử hội thoại trên hệ thống không?")) return;
    
    addLogLine("SYSTEM", "Đang tiến hành xóa toàn bộ lịch sử...");
    try {
        const response = await fetch("/api/history", { method: "DELETE" });
        if (response.ok) {
            startNewChat();
            fetchSessions();
        }
    } catch (e) {
        console.error("Failed to clear history: ", e);
    }
}

// ==========================================================================
// CHAT OPERATIONS
// ==========================================================================
function useSuggestion(text) {
    const input = document.getElementById("user-input-field");
    input.value = text;
    // Auto-focus input
    input.focus();
    // Submit form
    document.getElementById("chat-form").dispatchEvent(new Event("submit"));
}

async function handleChatSubmit(event) {
    event.preventDefault();
    
    const inputField = document.getElementById("user-input-field");
    const query = inputField.value.trim();
    if (!query) return;
    
    // Clear input
    inputField.value = "";
    
    // Remove welcome screen if it exists
    const welcome = document.getElementById("welcome-screen");
    if (welcome) welcome.remove();
    
    // 1. Render User Message
    appendUserMessage(query);
    scrollChatToBottom();
    
    // 2. Show thinking loader
    showThinkingIndicator();
    scrollChatToBottom();
    
    const startTime = Date.now();
    addLogLine("USER", `Gửi truy vấn: "${query}" (Chế độ: ${currentMode.toUpperCase()}, Model: ${currentProvider.toUpperCase()})`);
    
    try {
        // 3. Post Chat API request
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: query,
                session_id: currentSessionId,
                provider: currentProvider,
                mode: currentMode
            })
        });
        
        hideThinkingIndicator();
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Server error occurred");
        }
        
        const data = await response.json();
        const latencySec = ((Date.now() - startTime) / 1000).toFixed(2);
        
        // 4. Render Assistant response with accordion trace
        appendAssistantMessage(data.answer, data.trace, data.metrics);
        scrollChatToBottom();
        
        // 5. Write to logs stream and sync
        addLogLine("AGENT", `Nhận phản hồi trong ${latencySec}s. Số bước ReAct: ${data.metrics.steps}. Trạng thái: ${data.metrics.status.toUpperCase()}`);
        
        // Refresh sidebar sessions to capture any new titles
        fetchSessions();
        
        // If dashboard tab is opened, update dashboard immediately
        if (activeTab === "dashboard") {
            fetchDashboardData();
        }
        
    } catch (e) {
        hideThinkingIndicator();
        appendAssistantMessage(`❌ **Lỗi Hệ thống:** Không thể kết nối tới mô hình AI.\n\nChi tiết lỗi: *${e.message}*.\n\nVui lòng cấu hình API key trong tệp cấu hình `.env` hoặc thử lại sau.`);
        scrollChatToBottom();
        addLogLine("ERROR", `Lỗi chạy truy vấn: ${e.message}`);
    }
}

function appendUserMessage(text) {
    const container = document.getElementById("chat-messages-container");
    
    const bubble = document.createElement("div");
    bubble.className = "chat-message-bubble user";
    bubble.innerHTML = `
        <div class="avatar"><i class="fa-solid fa-user"></i></div>
        <div class="bubble-content">
            <div class="bubble-text-wrapper">${escapeHTML(text)}</div>
        </div>
    `;
    container.appendChild(bubble);
}

function appendAssistantMessage(text, trace = [], metrics = {}) {
    const container = document.getElementById("chat-messages-container");
    
    const bubble = document.createElement("div");
    bubble.className = "chat-message-bubble assistant";
    
    // Parse markdown basics (headings, lists, bold)
    const formattedText = parseMarkdown(text);
    
    let traceHtml = "";
    // Only render ReAct Trace accordion if we have ReAct mode and steps
    if (currentMode === "react" && trace && trace.length > 0) {
        const accordionId = "accordion-" + Math.random().toString(36).substring(2, 9);
        
        let stepsHtml = "";
        trace.forEach(step => {
            stepsHtml += `
                <div class="react-step">
                    <div class="step-number">Bước ${step.step} - Suy luận</div>
                    <div class="step-thought">Thought: ${escapeHTML(step.thought)}</div>
                    ${step.action && step.action !== "N/A" ? `<div class="step-action-box">${escapeHTML(step.action)}</div>` : ""}
                    ${step.observation ? `<div class="step-obs-box">${escapeHTML(step.observation)}</div>` : ""}
                </div>
            `;
        });
        
        const metricsLabel = metrics.latency_ms ? `[Latency: ${(metrics.latency_ms/1000).toFixed(2)}s | Steps: ${metrics.steps} | Tokens: ${metrics.tokens}]` : '';
        
        traceHtml = `
            <div class="react-steps-accordion" id="${accordionId}">
                <div class="accordion-header" onclick="toggleAccordion('${accordionId}')">
                    <span><i class="fa-solid fa-circle-nodes"></i> Xem tiến trình suy luận (ReAct Steps) ${metricsLabel}</span>
                    <i class="fa-solid fa-chevron-down chevron"></i>
                </div>
                <div class="accordion-content">
                    ${stepsHtml}
                </div>
            </div>
        `;
    }
    
    bubble.innerHTML = `
        <div class="avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="bubble-content" style="max-width: 95%;">
            <div class="bubble-text-wrapper">${formattedText}</div>
            ${traceHtml}
        </div>
    `;
    
    container.appendChild(bubble);
}

function toggleAccordion(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.toggle("open");
        scrollChatToBottom();
    }
}

function showThinkingIndicator() {
    const indicator = document.getElementById("thinking-indicator");
    const container = document.getElementById("chat-messages-container");
    
    // Move indicator to the end of chat messages list
    container.appendChild(indicator);
    indicator.style.display = "flex";
    
    // Randomize thinking texts for a high fidelity vibe
    const thinkingPhrases = [
        "Agent đang phân tích câu hỏi...",
        "Agent đang chọn công cụ phù hợp...",
        "Đang thực thi công cụ và phân tích Observation...",
        "Đang tổng hợp thông tin VinWonders Nam Hội An...",
        "Đang cấu trúc lại kết quả phản hồi cuối cùng..."
    ];
    let idx = 0;
    
    // Reset any previous interval on indicator
    if (window.thinkingInterval) clearInterval(window.thinkingInterval);
    
    document.getElementById("thinking-text").innerText = thinkingPhrases[0];
    
    window.thinkingInterval = setInterval(() => {
        idx = (idx + 1) % thinkingPhrases.length;
        const txtEl = document.getElementById("thinking-text");
        if (txtEl) txtEl.innerText = thinkingPhrases[idx];
    }, 2000);
}

function hideThinkingIndicator() {
    document.getElementById("thinking-indicator").style.display = "none";
    if (window.thinkingInterval) {
        clearInterval(window.thinkingInterval);
        window.thinkingInterval = null;
    }
}

function scrollChatToBottom() {
    const container = document.getElementById("chat-messages-container");
    container.scrollTop = container.scrollHeight;
}

// ==========================================================================
// TELEMETRY DASHBOARD DYNAMIC METRICS
// ==========================================================================
async function fetchDashboardData() {
    try {
        const response = await fetch("/api/dashboard");
        if (!response.ok) throw new Error("Dashboard fetch failed");
        
        const data = await response.json();
        
        // 1. Map KPI card values
        document.getElementById("kpi-total-chats").innerText = data.total_chats;
        document.getElementById("kpi-latency").innerText = `${data.avg_latency_s.toFixed(2)}s`;
        document.getElementById("kpi-success-rate").innerText = `${data.success_rate}%`;
        document.getElementById("kpi-cost").innerText = `$${data.estimated_cost_usd.toFixed(5)}`;
        
        // 2. Map status splits
        document.getElementById("status-cnt-success").innerText = data.success_count;
        document.getElementById("status-cnt-fallback").innerText = data.fallback_count;
        document.getElementById("status-cnt-error").innerText = data.error_count;
        document.getElementById("status-cnt-tokens").innerText = data.total_tokens.toLocaleString();
        
        // 3. Render Tool frequency bars dynamically
        const barsContainer = document.getElementById("tools-chart-bars");
        barsContainer.innerHTML = "";
        
        // Find max call count to calculate percentages
        const counts = Object.values(data.tool_usage);
        const maxVal = Math.max(...counts, 1);
        
        // Sort tools by calls descending
        const sortedTools = Object.entries(data.tool_usage).sort((a, b) => b[1] - a[1]);
        
        sortedTools.forEach(([tname, count]) => {
            const pct = (count / maxVal) * 100;
            
            const barItem = document.createElement("div");
            barItem.className = "tool-bar-item";
            barItem.innerHTML = `
                <div class="tool-bar-info">
                    <span class="tool-bar-label">${tname}</span>
                    <span class="tool-bar-count">${count} lượt gọi</span>
                </div>
                <div class="tool-bar-track">
                    <div class="tool-bar-fill" style="width: 0%"></div>
                </div>
            `;
            barsContainer.appendChild(barItem);
            
            // Trigger animation on width
            setTimeout(() => {
                const fill = barItem.querySelector(".tool-bar-fill");
                if (fill) fill.style.width = `${pct}%`;
            }, 100);
        });
        
    } catch (e) {
        console.error("Dashboard error: ", e);
        addLogLine("ERROR", `Không thể tải dữ liệu Dashboard: ${e.message}`);
    }
}

// Helper to stream logs into the visual console logstream panel
function addLogLine(source, message) {
    const container = document.getElementById("terminal-log-container");
    if (!container) return;
    
    const timeStr = new Date().toLocaleTimeString("vi-VN");
    const logLine = document.createElement("div");
    
    let sourceClass = "system";
    if (source === "USER") sourceClass = "system";
    else if (source === "ERROR") sourceClass = "error";
    else if (source === "AGENT") sourceClass = "";
    
    logLine.className = `log-line ${sourceClass}`;
    logLine.innerText = `[${timeStr}] [${source}] ${message}`;
    
    container.appendChild(logLine);
    
    // Auto scroll to bottom
    container.scrollTop = container.scrollHeight;
}

// ==========================================================================
// STRING & HTML UTILITIES
// ==========================================================================
function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

function parseMarkdown(text) {
    if (!text) return '';
    let parsed = text;
    
    // Escape HTML before parsing markdown tags (except paragraphs/lists)
    parsed = escapeHTML(parsed);
    
    // Bold tag replacement: **text** -> <strong>text</strong>
    parsed = parsed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Italic tag replacement: *text* -> <em>text</em>
    parsed = parsed.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Headings replacement: ### text -> <h3>text</h3>
    parsed = parsed.replace(/^###\s*(.*)$/gm, '<h3>$1</h3>');
    parsed = parsed.replace(/^##\s*(.*)$/gm, '<h2>$1</h2>');
    
    // Lists replacement: - text or * text -> <li>text</li> inside <ul>
    // Using a basic replacement for visual display in bubbles
    parsed = parsed.replace(/^\s*-\s*(.*)$/gm, '<li>$1</li>');
    
    // Bullet replacement formatting
    parsed = parsed.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    
    // Replace double linebreaks with paragraphs
    parsed = parsed.replace(/\n\n/g, '<br><br>');
    // Replace simple linebreaks
    parsed = parsed.replace(/\n/g, '<br>');
    
    return parsed;
}
