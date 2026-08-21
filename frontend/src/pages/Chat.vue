<template>
  <div class="chat-container">
    <!-- 侧边面板（双模式 + 画像入口） -->
    <ChatSidebar
      :nickname="nickname"
      :activeMode="activeMode"
      @switch-mode="switchMode"
      @show-profile="showProfile = true"
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
        <div class="session-name-tag">
          <span class="session-name-icon">{{ activeMode === 'incognito' ? '🔒' : '💬' }}</span>
          <span class="session-name-text">{{ sessions[activeMode]?.title || (activeMode === 'incognito' ? '无痕树洞' : '直接聊天') }}</span>
        </div>
        <div v-if="activeMode === 'incognito'" class="active-mode-tag incognito">
          🛡️ 无痕加密模式已开启
        </div>
      </div>

      <!-- 消息区 -->
      <MessageArea
        ref="messagesAreaRef"
        :messages="messages"
        :isGenerating="isGenerating"
        :isAnonymous="activeMode === 'incognito'"
        :nickname="nickname"
      />

      <!-- 底栏输入框 -->
      <ChatInput
        ref="chatInputRef"
        :isGenerating="isGenerating"
        @send-message="sendMessage"
      />
    </div>

    <!-- 用户画像可视化弹窗 -->
    <ProfilePanel v-if="showProfile" @close="showProfile = false" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { getPayload } from '../composables/useAuth'
import CapybaraSvg from '../components/CapybaraSvg.vue'
import ChatSidebar from '../components/chat/ChatSidebar.vue'
import MessageArea from '../components/chat/MessageArea.vue'
import ChatInput from '../components/chat/ChatInput.vue'
import ProfilePanel from '../components/chat/ProfilePanel.vue'

const router = useRouter()

// 状态定义
const nickname = ref('同学')
const token = ref('')
const messages = ref([])
const isGenerating = ref(false)
const showProfile = ref(false)

// 双模式：normal（直接聊天，落库） / incognito（无痕树洞，仅内存）
const activeMode = ref('normal')
const sessions = reactive({
  normal: null,       // 常规会话对象
  incognito: null     // 无痕会话对象
})
// 无痕会话消息缓存（内存，关闭页面即失）
const incognitoMessages = ref([])

// DOM / 组件引用
const messagesAreaRef = ref(null)
const chatInputRef = ref(null)

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

// 获取当前模式对应的 session_id
const activeSessionId = computed(() => sessions[activeMode.value]?.id || '')

// 加载/创建当前模式的固定会话（每个用户固定两个：直接聊天 / 无痕树洞）
async function ensureSession(mode) {
  const isIncognito = mode === 'incognito'
  const fixedTitle = isIncognito ? '无痕树洞' : '直接聊天'
  try {
    // 优先复用已存在的固定标题会话（注册时创建；存量用户首次进入时自动补齐）
    const res = await axios.get('/api/chat/sessions', {
      headers: { Authorization: `Bearer ${token.value}` }
    })
    if (res.data?.code === 200) {
      const list = res.data.data || []
      const fixed = list.find(s => s.is_anonymous === isIncognito && s.title === fixedTitle)
      if (fixed) {
        sessions[mode] = fixed
        return fixed
      }
    }
    // 未找到固定会话（存量用户）→ 创建
    const res2 = await axios.post('/api/chat/session', {
      title: fixedTitle,
      is_anonymous: isIncognito
    }, {
      headers: { Authorization: `Bearer ${token.value}` }
    })
    if (res2.data?.code === 200) {
      sessions[mode] = res2.data.data
      return sessions[mode]
    }
  } catch (e) {
    console.error('加载/创建会话失败:', e)
  }
  return null
}

// 切换模式（无痕树洞 / 直接聊天）
async function switchMode(mode) {
  if (activeMode.value === mode) return
  // 保存当前模式消息缓存
  if (activeMode.value === 'incognito') {
    incognitoMessages.value = [...messages.value]
  }
  activeMode.value = mode
  messages.value = []

  // 无痕：从内存读（无历史则建会话）
  if (mode === 'incognito') {
    if (!sessions.incognito) {
      await ensureSession('incognito')
    }
    messages.value = incognitoMessages.value
  } else {
    // 常规：从数据库加载最近对话
    if (!sessions.normal) {
      await ensureSession('normal')
    }
    await loadNormalHistory()
  }
  await scrollToBottom()
  nextTick(() => chatInputRef.value?.focus())
}

// 加载常规会话历史（最近 12 条窗口 + 标题）
async function loadNormalHistory() {
  const session = sessions.normal
  if (!session) return
  try {
    const res = await axios.get(`/api/chat/session/${session.id}/history`, {
      headers: { Authorization: `Bearer ${token.value}` }
    })
    if (res.data?.code === 200) {
      messages.value = res.data.data.map(msg => ({
        sender: msg.sender,
        content: msg.content,
        intent: msg.intent || '',
        reason: '',
        ragCards: []
      }))
    }
  } catch (e) {
    console.error('加载消息历史失败:', e)
    messages.value = []
  }
}

// 发送消息并流式 SSE 渲染
async function sendMessage(content) {
  if (isGenerating.value || !activeSessionId.value) return

  isGenerating.value = true

  // 1. 将用户输入追加到当前消息列表
  messages.value.push({ sender: 'user', content: content })

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
    // 2. 利用 fetch API 读取流式数据以注入 Header
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
    // 无痕模式：同步内存缓存
    if (activeMode.value === 'incognito') {
      incognitoMessages.value = [...messages.value]
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
onMounted(async () => {
  const localToken = localStorage.getItem('token')
  if (localToken) {
    token.value = localToken
    const payload = getPayload(localToken)
    if (payload) {
      nickname.value = payload.sub
    }
    // 默认进入常规模式（直接聊天）
    await ensureSession('normal')
    await loadNormalHistory()
    nextTick(() => chatInputRef.value?.focus())
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
  box-shadow: 0 10px 30px var(--shadow-color);
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
  background: var(--accent-light);
  color: var(--accent-hover);
  border: 1px solid var(--accent);
  animation: pulse-border 2s infinite;
}
.session-name-tag {
  margin-left: auto;
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  padding: 6px 14px;
}
.session-name-icon { font-size: 12px; }
.session-name-text { white-space: nowrap; }

@keyframes pulse-border {
  0% { border-color: rgba(200, 135, 129, 0.2); }
  50% { border-color: rgba(200, 135, 129, 0.5); }
  100% { border-color: rgba(200, 135, 129, 0.2); }
}
</style>
