/**
 * 嵇康对话 - Frontend Application
 * Vanilla JavaScript, no frameworks.
 */

// ==================== STATE ====================
const state = {
  sessionId: null,
  currentScreen: 'launch',
  isWriting: false,
  heartVoiceEnabled: false,
  selectedMode: null,       // 'xingqing' | 'wenda'
  selectedIdentity: null,   // for xingqing
  selectedSubtype: null,    // for wenda
  scene: 'bamboo',          // 'bamboo' | 'prison' | 'death'
  eventSource: null,
  currentJiKangMessage: null, // DOM element being filled
  currentHeartVoice: null,    // stored heart voice text
};

// ==================== DOM REFERENCES ====================
const dom = {
  screens: {
    launch: document.getElementById('screen-launch'),
    chat: document.getElementById('screen-chat'),
  },
  modeCards: document.querySelectorAll('.mode-card'),
  step2: document.getElementById('step-2'),
  optionsXingqing: document.getElementById('options-xingqing'),
  optionsWenda: document.getElementById('options-wenda'),
  heartVoiceToggle: document.getElementById('heart-voice-toggle'),
  btnEnter: document.getElementById('btn-enter'),
  modeTags: document.getElementById('mode-tags'),
  chatHistory: document.getElementById('chat-history'),
  emptyState: document.getElementById('empty-state'),
  chatInput: document.getElementById('chat-input'),
  btnSend: document.getElementById('btn-send'),
  btnNewChat: document.getElementById('btn-new-chat'),
  btnHistory: document.getElementById('btn-history'),
  writingIndicator: document.getElementById('writing-indicator'),
  // History panel
  historyPanel: document.getElementById('history-panel'),
  historyOverlay: document.getElementById('history-overlay'),
  historyList: document.getElementById('history-list'),
  btnCloseHistory: document.getElementById('btn-close-history'),
  // Launch screen history button
  btnLaunchHistory: document.getElementById('btn-launch-history'),
  // New chat modal (step 1)
  newChatModal: document.getElementById('new-chat-modal'),
  btnCancelNew: document.getElementById('btn-cancel-new'),
  btnConfirmNew: document.getElementById('btn-confirm-new'),
  // Save chat modal (step 2)
  saveChatModal: document.getElementById('save-chat-modal'),
  saveChatDesc: document.getElementById('save-chat-desc'),
  btnNoSave: document.getElementById('btn-no-save'),
  btnYesSave: document.getElementById('btn-yes-save'),
  btnCancelSave: document.getElementById('btn-cancel-save'),
};

// ==================== SCREEN NAVIGATION ====================
function showScreen(screenName) {
  state.currentScreen = screenName;
  Object.values(dom.screens).forEach((el) => el.classList.remove('active'));
  if (dom.screens[screenName]) {
    dom.screens[screenName].classList.add('active');
  }
}

// ==================== MODE SELECTION (Launch Screen) ====================
function selectMode(mode) {
  state.selectedMode = mode;

  // Update card visuals
  dom.modeCards.forEach((card) => {
    const isSelected = card.dataset.mode === mode;
    card.classList.toggle('active', isSelected);
    card.setAttribute('aria-pressed', String(isSelected));
  });

  // Show step 2
  dom.step2.hidden = false;
  dom.optionsXingqing.hidden = mode !== 'xingqing';
  dom.optionsWenda.hidden = mode !== 'wenda';

  // Reset defaults
  if (mode === 'xingqing') {
    const firstIdentity = dom.optionsXingqing.querySelector('input[name="identity"]');
    if (firstIdentity) firstIdentity.checked = true;
  } else {
    const firstSubtype = dom.optionsWenda.querySelector('input[name="subtype"]');
    if (firstSubtype) firstSubtype.checked = true;
  }

  dom.btnEnter.disabled = false;
}

dom.modeCards.forEach((card) => {
  card.addEventListener('click', () => selectMode(card.dataset.mode));
});

// ==================== SESSION INITIALIZATION ====================
async function initSession() {
  // Gather form data
  let identity = null;
  let subtype = null;
  state.heartVoiceEnabled = false;

  if (state.selectedMode === 'xingqing') {
    const checked = document.querySelector('input[name="identity"]:checked');
    identity = checked ? checked.value : '好友';
    state.heartVoiceEnabled = dom.heartVoiceToggle.checked;
    state.selectedIdentity = identity;
  } else if (state.selectedMode === 'wenda') {
    const checked = document.querySelector('input[name="subtype"]:checked');
    subtype = checked ? checked.value : '原始版';
    state.selectedSubtype = subtype;
  }

  const payload = {
    mode: state.selectedMode,
    identity: identity,
    subtype: subtype,
    heart_voice: state.heartVoiceEnabled,
  };

  try {
    const res = await fetch('/api/init', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`初始化失败: ${res.status}`);
    }

    const data = await res.json();
    state.sessionId = data.session_id || data.sessionId || null;

    if (!state.sessionId) {
      throw new Error('服务器未返回会话ID');
    }

    // Initialize scene from backend
    state.scene = data.scene || 'bamboo';

    // Update mode tags
    updateModeTags();

    // Switch to chat
    showScreen('chat');

    // Show initial scene notice in chat box
    const initialSceneName = data.scene_name || '竹林';
    appendSystemNotice('场景', `当前场景：${initialSceneName}`);
  } catch (err) {
    console.error('initSession error:', err);
    alert('会话初始化失败，请稍后重试。');
  }
}

dom.btnEnter.addEventListener('click', initSession);

function updateModeTags() {
  const tags = [];

  if (state.selectedMode === 'xingqing') {
    tags.push('性情版');
    tags.push(state.selectedIdentity || '好友');
    if (state.heartVoiceEnabled) tags.push('心声');
    // Show scene tag for personality mode (only when not in default bamboo)
    const sceneName = state.scene === 'prison' ? '狱中' : state.scene === 'death' ? '临刑前' : '';
    if (sceneName) tags.push(sceneName);
  } else if (state.selectedMode === 'wenda') {
    tags.push('问答版');
    tags.push(state.selectedSubtype || '原始版');
  }

  dom.modeTags.innerHTML = tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join(' \u00b7 ');
}

// ==================== CHAT FLOW ====================
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function createMessageBubble(role, text = '') {
  const wrapper = document.createElement('div');
  wrapper.className = `message-wrapper ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.innerHTML = text ? escapeHtml(text).replace(/\n/g, '<br>') : '<span class="placeholder"></span>';

  wrapper.appendChild(bubble);
  return { wrapper, bubble };
}

function appendToChat(role, text) {
  if (dom.emptyState) {
    dom.emptyState.remove();
    dom.emptyState = null;
  }

  const { wrapper, bubble } = createMessageBubble(role, text);
  dom.chatHistory.appendChild(wrapper);
  scrollToBottom();
  return bubble;
}

function scrollToBottom() {
  dom.chatHistory.scrollTop = dom.chatHistory.scrollHeight;
}

function showWriting() {
  dom.writingIndicator.hidden = false;
  scrollToBottom();
}

function hideWriting() {
  dom.writingIndicator.hidden = true;
}

function sendMessage() {
  const text = dom.chatInput.value.trim();
  if (!text || state.isWriting) return;

  if (!state.sessionId) {
    alert('会话未初始化，请重新开始。');
    showScreen('launch');
    return;
  }

  // Append user message
  appendToChat('user', text);
  dom.chatInput.value = '';
  dom.chatInput.rows = 1;

  // Create Ji Kang container
  state.currentJiKangMessage = appendToChat('jikang', '');
  state.currentHeartVoice = null;
  state.isWriting = true;

  // Start SSE
  startStream(text);
}

dom.btnSend.addEventListener('click', sendMessage);

dom.chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.ctrlKey && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Auto-resize textarea
dom.chatInput.addEventListener('input', () => {
  dom.chatInput.rows = 1;
  const rows = Math.min(5, Math.ceil(dom.chatInput.scrollHeight / 24));
  dom.chatInput.rows = Math.max(1, rows);
});

// ==================== SSE STREAMING ====================
function startStream(userInput) {
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }

  const url = new URL('/chat/stream', window.location.origin);
  url.searchParams.set('session_id', state.sessionId);
  url.searchParams.set('user_input', userInput);

  const es = new EventSource(url.toString());
  state.eventSource = es;

  es.addEventListener('writing', () => {
    showWriting();
  });

  es.addEventListener('scene_change', (e) => {
    const data = safeJsonParse(e.data);
    const sceneName = data && data.scene_name ? data.scene_name : '';
    const text = data && data.text ? data.text : '场景已转移';
    if (sceneName) {
      state.scene = data.scene;
      updateModeTags();
      appendSystemNotice('场景转移', text);
    }
  });

  es.addEventListener('identity_change', (e) => {
    const data = safeJsonParse(e.data);
    const identity = data && data.identity ? data.identity : '';
    const identityNameCn = data && data.identity_name_cn ? data.identity_name_cn : '';
    const personName = data && data.person_name ? data.person_name : '';
    const text = data && data.text ? data.text : '身份已转换';
    if (identity) {
      // 更新前端状态
      state.selectedIdentity = identityNameCn;
      updateModeTags();
      appendSystemNotice('身份转换', text);
    }
  });

  es.addEventListener('token', (e) => {
    hideWriting();
    const data = safeJsonParse(e.data);
    const char = data && data.text ? data.text : e.data;
    if (state.currentJiKangMessage) {
      const placeholder = state.currentJiKangMessage.querySelector('.placeholder');
      if (placeholder) placeholder.remove();
      appendTextToBubble(state.currentJiKangMessage, char);
      scrollToBottom();
    }
  });

  es.addEventListener('heart_voice', (e) => {
    const data = safeJsonParse(e.data);
    const text = data && data.text ? data.text : e.data;
    state.currentHeartVoice = text;
    if (state.currentJiKangMessage) {
      ensureHeartVoiceSection(state.currentJiKangMessage, text);
    }
  });

  es.addEventListener('filtered', (e) => {
    const data = safeJsonParse(e.data);
    const replacement = data && data.text ? data.text : '';
    appendSystemNotice('后世典故已拦截', replacement);
  });

  es.addEventListener('rejection', (e) => {
    const data = safeJsonParse(e.data);
    const message = data && data.text ? data.text : e.data;
    appendSystemNotice('嵇康拒绝回应', message);
    state.isWriting = false;
    hideWriting();
  });

  es.addEventListener('error', (e) => {
    const data = safeJsonParse(e.data);
    const message = data && data.text ? data.text : '连接出错';
    appendSystemNotice('错误', message);
    state.isWriting = false;
    hideWriting();
    es.close();
    state.eventSource = null;

    // Session expired check
    if (message.includes('session') || message.includes('过期') || message.includes('expired')) {
      alert('会话已过期，请重新开始。');
      showScreen('launch');
    }
  });

  es.addEventListener('done', () => {
    state.isWriting = false;
    hideWriting();
    es.close();
    state.eventSource = null;
  });

  es.onerror = () => {
    if (state.isWriting) {
      state.isWriting = false;
      hideWriting();
      appendSystemNotice('连接中断', '与服务器的连接已中断，请重试。');
    }
    es.close();
    state.eventSource = null;
  };
}

function safeJsonParse(str) {
  try {
    return JSON.parse(str);
  } catch {
    return null;
  }
}

function appendTextToBubble(bubble, text) {
  const lines = text.split('\n');
  lines.forEach((line, idx) => {
    if (idx > 0) bubble.appendChild(document.createElement('br'));
    bubble.appendChild(document.createTextNode(line));
  });
}

function appendSystemNotice(title, detail) {
  if (dom.emptyState) {
    dom.emptyState.remove();
    dom.emptyState = null;
  }
  const wrapper = document.createElement('div');
  wrapper.className = 'message-wrapper system';
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble system-bubble';
  bubble.innerHTML = `<strong>${escapeHtml(title)}</strong>` +
    (detail ? `<p>${escapeHtml(detail)}</p>` : '');
  wrapper.appendChild(bubble);
  dom.chatHistory.appendChild(wrapper);
  scrollToBottom();
}

// ==================== HEART VOICE ====================
function ensureHeartVoiceSection(bubble, text) {
  let section = bubble.parentElement.querySelector('.heart-voice-section');
  if (!section) {
    section = document.createElement('div');
    section.className = 'heart-voice-section';
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'heart-toggle-btn';
    toggle.innerHTML = '心声 <span class="arrow">▼</span>';
    toggle.addEventListener('click', () => toggleHeartVoice(section, toggle));

    const content = document.createElement('div');
    content.className = 'heart-voice-content';

    section.appendChild(toggle);
    section.appendChild(content);
    bubble.parentElement.appendChild(section);
  }
  const content = section.querySelector('.heart-voice-content');
  content.textContent = text;
}

function toggleHeartVoice(section, toggleBtn) {
  const content = section.querySelector('.heart-voice-content');
  const isExpanded = content.classList.contains('expanded');
  content.classList.toggle('expanded', !isExpanded);
  toggleBtn.classList.toggle('expanded', !isExpanded);
  const arrow = isExpanded ? '▼' : '▲';
  toggleBtn.innerHTML = `心声 <span class="arrow">${arrow}</span>`;
  scrollToBottom();
}

// ==================== CONVERSATION STORAGE ====================
const STORAGE_KEY = 'jikang_chat_history';

function loadSavedConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveConversations(list) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

function extractConversationFromDOM() {
  const messages = [];
  const wrappers = dom.chatHistory.querySelectorAll('.message-wrapper');
  wrappers.forEach((wrapper) => {
    const role = wrapper.classList.contains('user') ? 'user'
      : wrapper.classList.contains('jikang') ? 'jikang'
      : wrapper.classList.contains('system') ? 'system' : 'other';
    const bubble = wrapper.querySelector('.message-bubble');
    if (!bubble) return;
    // Get text content, preserving line breaks
    const text = bubble.innerText.trim();
    if (!text) return;
    const msg = { role, text };
    // Extract heart voice if present (for jikang messages)
    if (role === 'jikang') {
      const heartVoiceSection = wrapper.querySelector('.heart-voice-section');
      if (heartVoiceSection) {
        const heartVoiceContent = heartVoiceSection.querySelector('.heart-voice-content');
        if (heartVoiceContent) {
          const heartText = heartVoiceContent.textContent.trim();
          if (heartText) {
            msg.heart_voice = heartText;
          }
        }
      }
    }
    messages.push(msg);
  });
  return messages;
}

function getConversationTitle(messages) {
  const firstUser = messages.find((m) => m.role === 'user');
  if (firstUser) {
    const t = firstUser.text.replace(/\s+/g, ' ').trim();
    return t.length > 20 ? t.slice(0, 20) + '…' : t;
  }
  return '未命名对话';
}

function saveCurrentConversation() {
  const messages = extractConversationFromDOM();
  if (messages.length === 0) {
    alert('当前对话为空，无需保存。');
    return false;
  }

  const list = loadSavedConversations();
  const record = {
    id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random(),
    title: getConversationTitle(messages),
    mode: state.selectedMode === 'xingqing' ? '性情版' : '问答版',
    identity: state.selectedIdentity || '',
    subtype: state.selectedSubtype || '',
    heart_voice: state.heartVoiceEnabled,
    timestamp: Date.now(),
    messages: messages,
  };

  list.unshift(record); // newest first
  // Keep max 50 records
  if (list.length > 50) list.length = 50;
  saveConversations(list);
  return true;
}

// ==================== HISTORY PANEL ====================
function openHistoryPanel() {
  renderHistoryList();
  dom.historyPanel.hidden = false;
  dom.historyOverlay.hidden = false;
  // Trigger reflow for transition
  requestAnimationFrame(() => {
    dom.historyPanel.classList.add('active');
    dom.historyOverlay.classList.add('active');
  });
}

function closeHistoryPanel() {
  dom.historyPanel.classList.remove('active');
  dom.historyOverlay.classList.remove('active');
  setTimeout(() => {
    dom.historyPanel.hidden = true;
    dom.historyOverlay.hidden = true;
  }, 300);
}

function isModeCompatible(item) {
  // 只检查大模式（性情版 / 问答版），子类型不同也允许引用
  if (state.selectedMode === 'xingqing') {
    return item.mode === '性情版';
  }
  if (state.selectedMode === 'wenda') {
    return item.mode === '问答版';
  }
  return false;
}

function getSubTypeDiff(item) {
  // 返回子类型差异描述，无差异返回空字符串
  if (state.selectedMode === 'xingqing') {
    if (state.selectedIdentity !== item.identity) {
      return `此对话身份为「${item.identity || '好友'}」，当前为「${state.selectedIdentity || '好友'}」`;
    }
  } else if (state.selectedMode === 'wenda') {
    if (state.selectedSubtype !== item.subtype) {
      return `此对话为「${item.subtype || '原始版'}」，当前为「${state.selectedSubtype || '原始版'}」`;
    }
  }
  return '';
}

function renderHistoryList() {
  const list = loadSavedConversations();
  if (list.length === 0) {
    dom.historyList.innerHTML = '<p class="history-empty">暂无保存的对话</p>';
    return;
  }

  const inChat = state.currentScreen === 'chat' && state.sessionId;

  dom.historyList.innerHTML = list.map((item) => {
    const date = new Date(item.timestamp);
    const dateStr = `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
    const modeTag = item.mode || '问答版';
    const extra = item.identity || item.subtype || '';
    const compatible = inChat && isModeCompatible(item);
    const quoteClass = compatible ? 'quote' : 'quote disabled';
    const quoteTitle = compatible ? '引用此对话' : '模式不同，无法引用';
    return `
      <div class="history-item" data-id="${escapeHtml(item.id)}">
        <div class="history-item-header">
          <div class="history-item-title">${escapeHtml(item.title)}</div>
          <div class="history-item-actions">
            <button class="history-btn continue" data-id="${escapeHtml(item.id)}" data-action="continue" title="继续此对话">续</button>
            <button class="history-btn ${quoteClass}" data-id="${escapeHtml(item.id)}" data-action="quote" title="${quoteTitle}">引</button>
            <button class="history-btn delete" data-id="${escapeHtml(item.id)}" data-action="delete" title="删除">×</button>
          </div>
        </div>
        <div class="history-item-meta">
          <span class="history-item-mode">${escapeHtml(modeTag)}${extra ? ' · ' + escapeHtml(extra) : ''}</span>
          <span>${dateStr}</span>
        </div>
      </div>
    `;
  }).join('');

  // Click item body to show detail
  dom.historyList.querySelectorAll('.history-item').forEach((el) => {
    el.addEventListener('click', (e) => {
      if (e.target.closest('.history-btn')) return;
      const id = el.dataset.id;
      showHistoryDetail(id);
    });
  });

  // Continue buttons
  dom.historyList.querySelectorAll('.history-btn[data-action="continue"]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      continueConversation(btn.dataset.id);
    });
  });

  // Delete buttons
  dom.historyList.querySelectorAll('.history-btn[data-action="delete"]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteConversation(btn.dataset.id);
    });
  });

  // Quote buttons
  dom.historyList.querySelectorAll('.history-btn[data-action="quote"]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      quoteConversation(btn.dataset.id);
    });
  });
}

function deleteConversation(id) {
  const list = loadSavedConversations();
  const item = list.find((x) => x.id === id);
  if (!item) return;
  if (!confirm(`确定要删除对话「${item.title}」吗？\n此操作不可恢复。`)) return;

  const newList = list.filter((x) => x.id !== id);
  saveConversations(newList);
  renderHistoryList();
}

async function quoteConversation(id) {
  const list = loadSavedConversations();
  const item = list.find((x) => x.id === id);
  if (!item) return;

  // Must be in an active chat session
  if (state.currentScreen !== 'chat' || !state.sessionId) {
    alert('请先进入对话，再引用历史记录。');
    return;
  }

  // Check mode compatibility (大模式必须一致)
  if (!isModeCompatible(item)) {
    const currentMode = state.selectedMode === 'xingqing' ? '性情版' : '问答版';
    const currentExtra = state.selectedIdentity || state.selectedSubtype || '';
    const itemExtra = item.identity || item.subtype || '';
    alert(`模式不同，无法引用。\n\n此对话：${item.mode}${itemExtra ? ' · ' + itemExtra : ''}\n当前：${currentMode}${currentExtra ? ' · ' + currentExtra : ''}\n\n请切换至相同模式后再引用。`);
    return;
  }

  // Check subtype difference
  const diff = getSubTypeDiff(item);

  // Confirm
  const hasMessages = dom.chatHistory.querySelectorAll('.message-wrapper').length > 0;
  let confirmMsg = '引用将把历史消息追加到当前对话末尾，嵇康也能看到这些内容';
  if (diff) {
    confirmMsg += '\n\n注意：' + diff + '，嵇康的语气可能略有不同。';
  }
  confirmMsg += '\n\n是否继续？';

  if (hasMessages || diff) {
    if (!confirm(confirmMsg)) {
      return;
    }
  }

  // 1. Send to backend so Ji Kang can see the context
  try {
    const res = await fetch('/api/import_history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        messages: item.messages,
      }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      alert('引用失败：' + (errData.error || res.statusText));
      return;
    }
    const result = await res.json();
    if (!result.success) {
      alert('引用失败：后端未确认');
      return;
    }
  } catch (err) {
    alert('引用失败：网络错误');
    console.error(err);
    return;
  }

  // 2. Render on frontend
  closeHistoryPanel();
  renderQuotedMessages(item.messages, item.title);
}

function renderQuotedMessages(messages, title) {
  appendSystemNotice('引用历史对话', `从"${title}"导入 ${messages.length} 条消息作为上下文`);
  messages.forEach((msg) => {
    if (msg.role === 'user') {
      appendToChat('user', msg.text);
    } else if (msg.role === 'jikang') {
      const bubble = appendToChat('jikang', msg.text);
      // Restore heart voice if present
      if (msg.heart_voice) {
        ensureHeartVoiceSection(bubble, msg.heart_voice);
      }
    }
  });
}

function showHistoryDetail(id) {
  const list = loadSavedConversations();
  const item = list.find((x) => x.id === id);
  if (!item) return;

  const date = new Date(item.timestamp);
  const dateStr = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;

  const inChat = state.currentScreen === 'chat' && state.sessionId;
  const compatible = inChat && isModeCompatible(item);

  // Build detail HTML
  const msgsHtml = item.messages.map((m) => {
    const roleLabel = m.role === 'user' ? '你' : m.role === 'jikang' ? '嵇康' : m.role === 'system' ? '系统' : '其他';
    const roleClass = m.role === 'user' ? 'user-role' : '';
    let html = `<div class="msg-role ${roleClass}">${escapeHtml(roleLabel)}</div><div class="msg-text">${escapeHtml(m.text)}</div>`;
    // Show heart voice if present
    if (m.heart_voice) {
      html += `<div class="msg-role" style="color:var(--ink-light);">心声</div><div class="msg-text" style="color:var(--ink-light);font-style:italic;border-left:2px solid var(--border);padding-left:0.6rem;">${escapeHtml(m.heart_voice)}</div>`;
    }
    return html;
  }).join('');

  const detailBox = document.createElement('div');
  detailBox.className = 'history-detail';
  detailBox.innerHTML = `
    <div class="history-detail-header">
      <h4>${escapeHtml(item.title)} <span style="font-size:0.85rem;color:var(--ink-light);font-weight:normal;">— ${dateStr}</span></h4>
      <button type="button" class="btn-icon" id="btn-close-detail" aria-label="关闭">×</button>
    </div>
    <div class="history-detail-body">${msgsHtml}</div>
    <div class="history-detail-footer" style="padding:0.8rem 1.2rem;border-top:1px solid var(--border);display:flex;gap:0.6rem;justify-content:flex-end;">
      <button type="button" class="modal-btn secondary" id="btn-detail-delete">删除</button>
      <button type="button" class="modal-btn primary" id="btn-detail-continue">继续对话</button>
      <button type="button" class="modal-btn primary" id="btn-detail-quote" ${compatible ? '' : 'disabled'}>${compatible ? '引用此对话' : '模式不同，无法引用'}</button>
    </div>
  `;

  document.body.appendChild(detailBox);

  document.getElementById('btn-close-detail').addEventListener('click', () => {
    detailBox.remove();
  });

  document.getElementById('btn-detail-delete').addEventListener('click', () => {
    detailBox.remove();
    deleteConversation(id);
  });

  document.getElementById('btn-detail-continue').addEventListener('click', () => {
    detailBox.remove();
    continueConversation(id);
  });

  document.getElementById('btn-detail-quote').addEventListener('click', () => {
    if (!compatible) return;
    detailBox.remove();
    quoteConversation(id);
  });

  // Close on click outside
  const closeOnOutside = (e) => {
    if (!detailBox.contains(e.target)) {
      detailBox.remove();
      document.removeEventListener('click', closeOnOutside);
    }
  };
  // Delay to avoid immediate close
  setTimeout(() => document.addEventListener('click', closeOnOutside), 50);
}

dom.btnHistory.addEventListener('click', openHistoryPanel);
dom.btnCloseHistory.addEventListener('click', closeHistoryPanel);
dom.historyOverlay.addEventListener('click', closeHistoryPanel);

// ==================== NEW CONVERSATION (Two-step confirmation) ====================
function showNewChatModal() {
  dom.newChatModal.hidden = false;
  requestAnimationFrame(() => {
    dom.newChatModal.classList.add('active');
  });
}

function hideNewChatModal() {
  dom.newChatModal.classList.remove('active');
  setTimeout(() => {
    dom.newChatModal.hidden = true;
  }, 250);
}

function showSaveChatModal() {
  // Update description with message count
  const msgCount = dom.chatHistory.querySelectorAll('.message-wrapper').length;
  if (dom.saveChatDesc) {
    dom.saveChatDesc.textContent = `当前对话有 ${msgCount} 条消息记录，是否保存？`;
  }
  dom.saveChatModal.hidden = false;
  requestAnimationFrame(() => {
    dom.saveChatModal.classList.add('active');
  });
}

function hideSaveChatModal() {
  dom.saveChatModal.classList.remove('active');
  setTimeout(() => {
    dom.saveChatModal.hidden = true;
  }, 250);
}

function doStartNewChat() {
  // Close any active SSE
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
  // Reset state
  state.sessionId = null;
  state.isWriting = false;
  state.selectedMode = null;
  state.selectedIdentity = null;
  state.selectedSubtype = null;
  state.heartVoiceEnabled = false;
  state.currentJiKangMessage = null;
  state.currentHeartVoice = null;
  state.scene = 'bamboo';
  // Reset UI
  dom.chatHistory.innerHTML = '<div class="empty-state" id="empty-state"><p class="empty-text">请输入问题...</p><p class="empty-hint">知识边界截止景元三年</p></div>';
  dom.emptyState = document.getElementById('empty-state');
  dom.step2.hidden = true;
  dom.optionsXingqing.hidden = true;
  dom.optionsWenda.hidden = true;
  dom.modeCards.forEach((c) => {
    c.classList.remove('active');
    c.setAttribute('aria-pressed', 'false');
  });
  dom.btnEnter.disabled = true;
  dom.heartVoiceToggle.checked = false;
  dom.modeTags.innerHTML = '<span class="tag tag-mode">性情版</span>';
  showScreen('launch');
}

function resetConversation() {
  // Check if there's actual conversation content (user or jikang messages)
  // System notices (like the initial scene notice) don't count
  const hasMessages = dom.chatHistory.querySelectorAll('.message-wrapper.user, .message-wrapper.jikang').length > 0;
  if (!hasMessages) {
    doStartNewChat();
    return;
  }
  // Step 1: ask if user wants to start a new conversation
  showNewChatModal();
}

// Step 1 handlers
dom.btnCancelNew.addEventListener('click', () => {
  hideNewChatModal();
});

dom.btnConfirmNew.addEventListener('click', () => {
  hideNewChatModal();
  // Step 2: ask if user wants to save the chat history
  showSaveChatModal();
});

// Step 2 handlers
dom.btnCancelSave.addEventListener('click', () => {
  hideSaveChatModal();
});

dom.btnNoSave.addEventListener('click', () => {
  hideSaveChatModal();
  doStartNewChat();
});

dom.btnYesSave.addEventListener('click', () => {
  hideSaveChatModal();
  if (saveCurrentConversation()) {
    doStartNewChat();
  }
});

// Click overlay background to close modals
dom.newChatModal.addEventListener('click', (e) => {
  if (e.target === dom.newChatModal) {
    hideNewChatModal();
  }
});

dom.saveChatModal.addEventListener('click', (e) => {
  if (e.target === dom.saveChatModal) {
    hideSaveChatModal();
  }
});

// Bind new chat button
dom.btnNewChat.addEventListener('click', resetConversation);

// Bind launch screen history button (click + keyboard for div[tabindex])
dom.btnLaunchHistory.addEventListener('click', openHistoryPanel);
dom.btnLaunchHistory.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    openHistoryPanel();
  }
});

// ==================== CONTINUE CONVERSATION ====================
async function continueConversation(id) {
  const list = loadSavedConversations();
  const item = list.find((x) => x.id === id);
  if (!item) return;

  // 映射前端 mode 值到后端
  const modeMapReverse = { '性情版': 'xingqing', '问答版': 'wenda' };

  const payload = {
    mode: modeMapReverse[item.mode] || item.mode,
    identity: item.identity || null,
    subtype: item.subtype || null,
    heart_voice: item.heart_voice || false,
    messages: item.messages || [],
  };

  try {
    const res = await fetch('/api/resume_session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error || `恢复会话失败: ${res.status}`);
    }

    const data = await res.json();

    // 恢复前端状态
    state.sessionId = data.session_id || data.sessionId;
    state.selectedMode = data.mode === 'personality' ? 'xingqing' : 'wenda';
    state.selectedIdentity = data.identity_name_cn || item.identity || '';
    state.selectedSubtype = data.qna_subtype_name_cn || item.subtype || '';
    state.heartVoiceEnabled = data.heart_voice;
    state.scene = data.scene || 'bamboo';

    // 更新模式标签
    updateModeTags();

    // 关闭历史面板
    closeHistoryPanel();

    // 切换到对话页
    showScreen('chat');

    // 渲染历史消息到聊天区
    renderMessagesToChat(item.messages);

    // 添加系统提示
    appendSystemNotice('继续对话', `已恢复「${item.title}」的上下文，共 ${data.imported_count || item.messages.length} 条消息，可直接继续发问`);

  } catch (err) {
    console.error('continueConversation error:', err);
    alert('恢复对话失败：' + err.message);
  }
}

function renderMessagesToChat(messages) {
  if (!messages || messages.length === 0) return;

  messages.forEach((msg) => {
    if (msg.role === 'user') {
      appendToChat('user', msg.text);
    } else if (msg.role === 'jikang') {
      const bubble = appendToChat('jikang', msg.text);
      // 恢复心声
      if (msg.heart_voice) {
        ensureHeartVoiceSection(bubble, msg.heart_voice);
      }
    } else if (msg.role === 'system') {
      // 系统消息不渲染到聊天区，避免重复
    }
  });
}

// ==================== INIT ====================
showScreen('launch');
