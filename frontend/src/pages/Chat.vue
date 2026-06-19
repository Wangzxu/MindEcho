<template>
  <div class="chat-container">
    <!-- 侧边会话面板 -->
    <div class="sidebar card-panel">
      <div class="sidebar-header">
        <span class="logo-emoji">🌱</span>
        <span class="app-name">MindEcho</span>
      </div>
      <div class="user-info">
        <div class="avatar-container">
          <div class="avatar-placeholder">👤</div>
        </div>
        <div class="user-details">
          <p class="user-nickname">{{ nickname }}</p>
          <p class="user-role">学生账户</p>
        </div>
      </div>
      <div class="sessions-list">
        <div class="session-item active">
          <span class="session-icon">💬</span>
          <span class="session-title">与水豚豚的温泉树洞</span>
        </div>
      </div>
      <button class="logout-btn" @click="handleLogout">
        🚪 退出登录
      </button>
    </div>

    <!-- 聊天主窗口 -->
    <div class="chat-main card-panel">
      <div class="chat-header">
        <div class="avatar-pic-svg">
          <CapybaraSvg size="50px" />
        </div>
        <div class="ai-details">
          <h3>水豚委员 • 豚豚</h3>
          <span class="status-indicator">● 保持松弛，听你倾诉</span>
        </div>
      </div>

      <div class="messages-area">
        <!-- AI 消息 (鼠尾草绿背景) -->
        <div class="msg-row ai">
          <div class="msg-avatar-svg"><CapybaraSvg size="38px" /></div>
          <div class="msg-bubble ai-bubble">
            <p>你好呀，{{ nickname }}。我是你的 AI 心理委员豚豚。就像我和小鸭子在温泉里泡澡一样，希望你在这里也能感受到温暖和彻底的松弛。不管是学习压力、人际交往，还是个人情感，你都可以在这和我说说。这是一个绝对私密的树洞，我会像水豚一样情绪稳定地陪伴着你。🌿</p>
          </div>
        </div>

        <!-- 模拟用户消息 (落日粉背景) -->
        <div class="msg-row user">
          <div class="msg-bubble user-bubble">
            <p>豚豚，这两天快期末考试了，我有点焦虑睡不好觉...</p>
          </div>
          <div class="msg-avatar">👤</div>
        </div>

        <!-- AI 回复 -->
        <div class="msg-row ai">
          <div class="msg-avatar-svg"><CapybaraSvg size="38px" /></div>
          <div class="msg-bubble ai-bubble">
            <p>听起来快到期末了，各科的备考确实让你感觉到了很大的压力。晚上睡不好会让人白天更加疲惫焦虑，这很正常，不用因此责怪自己。我们试着像水豚一样做一个缓慢的深呼吸，或者试试“五感着陆法”来放松一下大脑，你觉得可以吗？</p>
          </div>
        </div>
      </div>

      <!-- 情绪呼吸灯输入框 -->
      <div class="input-area">
        <input 
          type="text" 
          class="input-field" 
          placeholder="把你的烦恼写在这里，我会一直倾听... (焦点时将开启呼吸调节引导)"
        />
        <button class="btn-primary send-btn">发送</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import CapybaraSvg from '../components/CapybaraSvg.vue'

const router = useRouter()
const nickname = ref('同学')

// 原生 Base64 令牌负载解析
function getPayload(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch (e) {
    return null;
  }
}

onMounted(() => {
  const token = localStorage.getItem('token')
  if (token) {
    const payload = getPayload(token)
    if (payload) {
      nickname.value = payload.sub
    }
  }
})

function handleLogout() {
  localStorage.removeItem('token')
  router.push('/login')
}
</script>

<style scoped>
.chat-container {
  display: flex;
  height: 100vh;
  padding: 20px;
  gap: 20px;
  background-color: var(--bg-color);
}

/* 侧边栏 */
.sidebar {
  width: 260px;
  display: flex;
  flex-direction: column;
  padding: 25px 15px;
  border-radius: var(--radius-lg);
  background-color: var(--panel-bg);
}
.sidebar-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 30px;
  color: var(--primary);
}
.logo-emoji {
  font-size: 24px;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background-color: var(--primary-light);
  border-radius: var(--radius-md);
  margin-bottom: 25px;
}
.avatar-placeholder {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: var(--panel-bg);
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 20px;
}
.user-nickname {
  font-weight: 500;
  font-size: 15px;
}
.user-role {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.sessions-list {
  flex: 1;
}
.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 15px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-normal);
  font-size: 14px;
}
.session-item.active {
  background-color: var(--primary-light);
  color: var(--primary-hover);
  font-weight: 500;
}
.logout-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  padding: 12px;
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
  transition: var(--transition-normal);
}
.logout-btn:hover {
  background-color: var(--warning-light);
  border-color: var(--warning);
  color: #C0392B;
}

/* 聊天主界面 */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: var(--panel-bg);
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
.avatar-pic {
  font-size: 32px;
  width: 45px;
  height: 45px;
  background-color: var(--primary-light);
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
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
.messages-area {
  flex: 1;
  padding: 25px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  max-width: 80%;
}
.msg-row.ai {
  align-self: flex-start;
}
.msg-row.user {
  align-self: flex-end;
}
.msg-avatar-svg {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
}
.msg-avatar {
  font-size: 24px;
  width: 36px;
  height: 36px;
  background-color: var(--primary-light);
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
}
.msg-bubble {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  font-size: 14.5px;
  line-height: 1.5;
  box-shadow: 0 4px 15px rgba(0,0,0,0.02);
}
.ai-bubble {
  background-color: var(--primary-light);
  border-top-left-radius: 4px;
  border: 1px solid var(--border-color);
}
.user-bubble {
  background-color: var(--accent-light);
  border-top-right-radius: 4px;
  border: 1px solid var(--accent);
}
.input-area {
  padding: 20px 25px;
  border-top: 1px solid var(--border-color);
  display: flex;
  gap: 15px;
}
.send-btn {
  padding: 10px 24px;
}
</style>
