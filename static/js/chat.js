/**
 * 嵇康对话前端逻辑
 */

// DOM 元素
const chatMain = document.getElementById('chatMain');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const clearBtn = document.getElementById('clearBtn');
const aboutBtn = document.getElementById('aboutBtn');
const aboutModal = document.getElementById('aboutModal');
const closeModal = document.getElementById('closeModal');
const suggestions = document.querySelectorAll('.suggestion');

// 状态
let history = [];
let isLoading = false;

// 初始化
function init() {
    loadHistory();
    messageInput.focus();
}

// 绑定事件
sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

clearBtn.addEventListener('click', () => {
    if (confirm('确定要清空对话吗？')) {
        clearChat();
    }
});

aboutBtn.addEventListener('click', () => {
    aboutModal.classList.add('active');
});

closeModal.addEventListener('click', () => {
    aboutModal.classList.remove('active');
});

aboutModal.addEventListener('click', (e) => {
    if (e.target === aboutModal) {
        aboutModal.classList.remove('active');
    }
});

suggestions.forEach(btn => {
    btn.addEventListener('click', () => {
        messageInput.value = btn.dataset.text;
        sendMessage();
    });
});

// 发送消息
async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isLoading) return;

    // 添加用户消息
    addMessage('user', text);
    messageInput.value = '';
    
    // 移除欢迎界面（如果还在）
    const welcome = document.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    // 显示加载状态
    showLoading();
    isLoading = true;
    sendBtn.disabled = true;

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: text,
                history: history
            })
        });

        const data = await response.json();
        
        // 移除加载状态
        hideLoading();
        
        // 添加机器人回复
        addMessage('bot', data.reply);
        
        // 保存历史
        history.push({ user: text, bot: data.reply });
        saveHistory();
        
    } catch (error) {
        hideLoading();
        addMessage('bot', '……吾今日心神不宁，难以应答。子可稍后再试。');
        console.error('Error:', error);
    } finally {
        isLoading = false;
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

// 添加消息到界面
function addMessage(role, text) {
    const row = document.createElement('div');
    row.className = `message-row ${role}`;
    
    const time = new Date().toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
    });
    
    const avatarText = role === 'bot' ? '嵇' : '客';
    const nameText = role === 'bot' ? '嵇康' : '访客';
    
    // 处理文本中的换行
    const formattedText = escapeHtml(text).replace(/\n/g, '<br>');
    
    row.innerHTML = `
        <div class="message-content">
            <div class="message-avatar" title="${nameText}">${avatarText}</div>
            <div>
                <div class="message-bubble">${formattedText}</div>
                <div class="message-time">${time}</div>
            </div>
        </div>
    `;
    
    chatMain.appendChild(row);
    scrollToBottom();
}

// 显示加载状态
function showLoading() {
    const loading = document.createElement('div');
    loading.className = 'loading-row';
    loading.id = 'loadingIndicator';
    loading.innerHTML = `
        <div class="loading-avatar">嵇</div>
        <div class="loading-text">抚琴沉思中……</div>
    `;
    chatMain.appendChild(loading);
    scrollToBottom();
}

// 移除加载状态
function hideLoading() {
    const loading = document.getElementById('loadingIndicator');
    if (loading) loading.remove();
}

// 清空对话
function clearChat() {
    chatMain.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">🎋</div>
            <h2>松下风来，与君对坐</h2>
            <p>吾乃嵇康，字叔夜。子有何事，但说无妨。</p>
            <div class="suggested-questions">
                <button class="suggestion" data-text="请谈《广陵散》">《广陵散》</button>
                <button class="suggestion" data-text="何为声无哀乐？">声无哀乐</button>
                <button class="suggestion" data-text="与山巨源绝交，何故？">与山巨源绝交书</button>
                <button class="suggestion" data-text="君如何养生？">养生之道</button>
            </div>
        </div>
    `;
    
    // 重新绑定建议按钮事件
    document.querySelectorAll('.suggestion').forEach(btn => {
        btn.addEventListener('click', () => {
            messageInput.value = btn.dataset.text;
            sendMessage();
        });
    });
    
    history = [];
    saveHistory();
}

// 滚动到底部
function scrollToBottom() {
    chatMain.scrollTop = chatMain.scrollHeight;
}

// 保存历史到 localStorage
function saveHistory() {
    try {
        localStorage.setItem('jikang_history', JSON.stringify(history));
    } catch (e) {
        // 忽略存储错误
    }
}

// 加载历史
function loadHistory() {
    try {
        const saved = localStorage.getItem('jikang_history');
        if (saved) {
            history = JSON.parse(saved);
            if (history.length > 0) {
                // 移除欢迎界面
                const welcome = document.querySelector('.welcome-message');
                if (welcome) welcome.remove();
                
                // 恢复消息
                history.forEach(turn => {
                    addMessage('user', turn.user);
                    addMessage('bot', turn.bot);
                });
            }
        }
    } catch (e) {
        history = [];
    }
}

// HTML 转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 启动
init();
