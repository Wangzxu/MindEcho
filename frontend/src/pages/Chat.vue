<template>
  <div class="chat-container">
    <!-- 侧边会话面板 -->
    <ChatSidebar
      :sessions="sessions"
      :activeSessionId="activeSessionId"
      :isCreatingSession="isCreatingSession"
      :nickname="nickname"
      @select-session="selectSession"
      @create-session="createSession"
      @logout="handleLogout"
    />

    <!-- 聊天主窗口 -->
    <div class="chat-main card-panel">
      <div class="chat-header">
        <div class="avatar-pic-svg">
          <CapybaraSvg size="50px" />
        </div>
        <div class="ai-details">
          <h3>小影 • AI 心理委员</h3>
          <span class="status-indicator">● 温柔包容，非批判性陪伴</span>
        </div>
        <div v-if="activeSession?.is_anonymous" class="active-mode-tag incognito">
          🛡️ 无痕加密模式已开启
        </div>
      </div>

      <!-- 消息区 -->
      <MessageArea
        ref="messagesAreaRef"
        :messages="messages"
        :isGenerating="isGenerating"
        :isAnonymous="activeSession?.is_anonymous || false"
        :nickname="nickname"
      />

      <!-- 底栏输入框 -->
      <ChatInput
        ref="chatInputRef"
        :isGenerating="isGenerating"
        @send-message="sendMessage"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import CapybaraSvg from '../components/CapybaraSvg.vue'
import ChatSidebar from '../components/chat/ChatSidebar.vue'
import MessageArea from '../components/chat/MessageArea.vue'
import ChatInput from '../components/chat/ChatInput.vue'

const router = useRouter()

// 状态定义
const nickname = ref('同学')
const token = ref('')
const sessions = ref([])
const activeSessionId = ref('')
const messages = ref([])
const isGenerating = ref(false)

// 会话创建相关状态
const isCreatingSession = ref(false)

// 内存版无痕会话历史消息记录字典
const sessionMessagesMap = reactive({})

// DOM / 组件引用
const messagesAreaRef = ref(null)
const chatInputRef = ref(null)

// 计算属性：当前激活的会话对象
const activeSession = computed(() => {
  return sessions.value.find(s => s.id === activeSessionId.value)
})

// 原生 Base64 令牌负载解析
function getPayload(tokenStr) {
  try {
    return JSON.parse(atob(tokenStr.split('.')[1]));
  } catch (e) {
    return null;
  }
}

// 自动滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (messagesAreaRef.value) {
    messagesAreaRef.value.scrollToBottom()
  }
}

// 监听消息列表变化并滚动
watch(messages, () => {
  scrollToBottom()
}, { deep: true })

// 加载用户所有会话列表
async function fetchSessions() {
  try {
    const res = await axios.get('/api/chat/sessions', {
      headers: { Authorization: `Bearer ${token.value}` }
    })
    if (res.data && res.data.code === 200) {
      sessions.value = res.data.data
      
      // 如果没有激活会话，且列表不为空，默认选中第一个
      if (!activeSessionId.value && sessions.value.length > 0) {
        await selectSession(sessions.value[0].id)
      }
    }
  } catch (e) {
    console.error("加载会话列表失败:", e)
  }
}

// 选择会话
async function selectSession(sessionId) {
  activeSessionId.value = sessionId
  const session = sessions.value.find(s => s.id === sessionId)
  if (!session) return

  // A. 若是无痕会话，在内存 Map 中维护
  if (session.is_anonymous) {
    if (!sessionMessagesMap[sessionId]) {
      sessionMessagesMap[sessionId] = []
    }
    messages.value = sessionMessagesMap[sessionId]
  } 
  // B. 若是常规会话，从后端 MySQL 载入历史记录，并缓存至 Map
  else {
    try {
      const res = await axios.get(`/api/chat/session/${sessionId}/history`, {
        headers: { Authorization: `Bearer ${token.value}` }
      })
      if (res.data && res.data.code === 200) {
        const dbMsgs = res.data.data.map(msg => ({
          sender: msg.sender,
          content: msg.content,
          intent: msg.intent,
          reason: msg.reason || '',
          ragCards: []
        }))
        sessionMessagesMap[sessionId] = dbMsgs
        messages.value = sessionMessagesMap[sessionId]
      }
    } catch (e) {
      console.error("加载消息历史失败:", e)
      messages.value = []
    }
  }
  
  await scrollToBottom()
  nextTick(() => {
    if (chatInputRef.value) {
      chatInputRef.value.focus()
    }
  })
}

// 创建新会话
async function createSession(isIncognito = false) {
  if (isCreatingSession.value) return
  isCreatingSession.value = true
  try {
    const defaultTitle = isIncognito ? '无痕新对话' : '新对话'
    const res = await axios.post('/api/chat/session', {
      title: defaultTitle,
      is_anonymous: isIncognito
    }, {
      headers: { Authorization: `Bearer ${token.value}` }
    })
    
    if (res.data && res.data.code === 200) {
      const newSession = res.data.data
      await fetchSessions()
      await selectSession(newSession.id)
    }
  } catch (e) {
    console.error("创建会话失败:", e)
  } finally {
    isCreatingSession.value = false
  }
}

// 发送消息并流式 SSE 渲染
async function sendMessage(content) {
  if (isGenerating.value || !activeSessionId.value) return
  
  isGenerating.value = true

  // 1. 将用户输入追加到当前消息列表和缓存中
  const userMsg = { sender: 'user', content: content }
  messages.value.push(userMsg)
  
  // 初始化一个空的 AI 响应占位符
  const aiMsg = reactive({
    sender: 'ai',
    content: '',
    intent: '',
    reason: '',
    ragCards: []
  })
  
  messages.value.push(aiMsg)
  await scrollToBottom()

  try {
    // 2. 利用 fetch API 读取流式数据以注入 Header - 修改为直连后端绝对地址
    const response = await fetch('http://localhost:5000/api/chat/message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token.value}`
      },
      body: JSON.stringify({
        session_id: activeSessionId.value,
        content: content
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP 异常! 状态码: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      
      const events = buffer.split(/\r?\n\r?\n/)
      buffer = events.pop()

      for (const rawEvent of events) {
        const line = rawEvent.trim()
        if (!line.startsWith('data:')) continue

        const dataStr = line.substring(5).trim()
        if (dataStr === '[DONE]') {
          break
        }

        try {
          const parsed = JSON.parse(dataStr)
          
          if (parsed.intent) {
            aiMsg.intent = parsed.intent
            aiMsg.reason = parsed.reason || ''
            aiMsg.ragCards = parsed.rag_cards || []
            
            // 捕获自动生成的会话标题并更新侧边栏
            if (parsed.new_title) {
              const sess = sessions.value.find(s => s.id === activeSessionId.value)
              if (sess) {
                sess.title = parsed.new_title
              }
            }
          } else if (parsed.content) {
            aiMsg.content += parsed.content
          } else if (parsed.error) {
            aiMsg.content += `\n⚠️ [系统提示: ${parsed.message || '模型推理异常'}]`
          }
        } catch (pe) {
          console.warn("解析流数据分块出错:", pe, dataStr)
        }
      }
    }
  } catch (error) {
    console.error("流式读取异常:", error)
    aiMsg.content += `\n⚠️ [网络通讯发生异常，请检查网络连接]`
  } finally {
    isGenerating.value = false
    if (activeSession.value?.is_anonymous) {
      sessionMessagesMap[activeSessionId.value] = [...messages.value]
    }
    await scrollToBottom()
  }
}

// 退出登录
function handleLogout() {
  localStorage.removeItem('token')
  router.push('/login')
}

// 初始化
onMounted(() => {
  const localToken = localStorage.getItem('token')
  if (localToken) {
    token.value = localToken
    const payload = getPayload(localToken)
    if (payload) {
      nickname.value = payload.sub
    }
    fetchSessions()
  } else {
    router.push('/login')
  }
})
</script>

<style scoped>
.chat-container {
  display: flex;
  height: 100vh;
  padding: 20px;
  gap: 20px;
  background-color: var(--bg-color);
  box-sizing: border-box;
}

/* 聊天主界面 */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: var(--panel-bg);
  border-radius: var(--radius-lg);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
  overflow: hidden;
}
.chat-header {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 20px 25px;
  border-bottom: 1px solid var(--border-color);
}
.avatar-pic-svg {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
}
.ai-details h3 {
  font-size: 17px;
  font-weight: 600;
}
.status-indicator {
  font-size: 11px;
  color: var(--primary);
  margin-top: 3px;
  display: inline-block;
}
.active-mode-tag {
  margin-left: auto;
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 20px;
  font-weight: 500;
}
.active-mode-tag.incognito {
  background-color: #F4ECF7;
  color: #7D3C98;
  border: 1px solid #E8DAEF;
  animation: pulse-border 2s infinite;
}

@keyframes pulse-border {
  0% { border-color: rgba(125, 60, 152, 0.2); }
  50% { border-color: rgba(125, 60, 152, 0.6); }
  100% { border-color: rgba(125, 60, 152, 0.2); }
}
</style>
