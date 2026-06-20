<template>
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
    
    <!-- 新建对话按钮组 -->
    <div class="new-sessions-btn-group">
      <button class="new-session-btn" @click="$emit('create-session', false)" :disabled="isCreatingSession">
        ➕ 新建常规对话
      </button>
      <button class="new-session-btn incognito-btn" @click="$emit('create-session', true)" :disabled="isCreatingSession">
        🔒 新建无痕树洞
      </button>
    </div>

    <!-- 会话列表 -->
    <div class="sessions-list">
      <div 
        v-for="session in sessions" 
        :key="session.id" 
        :class="['session-item', activeSessionId === session.id ? 'active' : '']"
        @click="$emit('select-session', session.id)"
      >
        <span class="session-icon">{{ session.is_anonymous ? '🔒' : '💬' }}</span>
        <span class="session-title" :title="session.title">{{ session.title }}</span>
        <span v-if="session.is_anonymous" class="incognito-badge">无痕</span>
      </div>
      <div v-if="sessions.length === 0" class="empty-sessions">
        暂无对话，点击上方新建
      </div>
    </div>
    
    <button class="logout-btn" @click="$emit('logout')">
      🚪 退出登录
    </button>
  </div>
</template>

<script setup>
defineProps({
  sessions: { type: Array, default: () => [] },
  activeSessionId: { type: String, default: '' },
  isCreatingSession: { type: Boolean, default: false },
  nickname: { type: String, default: '同学' }
})

defineEmits(['select-session', 'create-session', 'logout'])
</script>

<style scoped>
.sidebar {
  width: 280px;
  display: flex;
  flex-direction: column;
  padding: 25px 15px;
  border-radius: var(--radius-lg);
  background-color: var(--panel-bg);
  flex-shrink: 0;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
  box-sizing: border-box;
}
.sidebar-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 20px;
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
  margin-bottom: 15px;
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
  font-weight: 600;
  font-size: 15px;
  color: var(--primary-hover);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.user-role {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* 新建对话 */
.new-sessions-btn-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}
.new-session-btn {
  width: 100%;
  padding: 12px;
  background-color: var(--primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition-normal);
  box-shadow: 0 4px 12px rgba(46, 125, 50, 0.2);
}
.new-session-btn:hover {
  background-color: var(--primary-hover);
  transform: translateY(-1px);
}
.incognito-btn {
  background-color: #7D3C98;
  box-shadow: 0 4px 12px rgba(125, 60, 152, 0.2);
}
.incognito-btn:hover {
  background-color: #6C3483;
}

.sessions-list {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 15px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: var(--transition-normal);
  font-size: 14.5px;
  border: 1px solid transparent;
  color: var(--text-primary);
}
.session-item:hover {
  background-color: rgba(0, 0, 0, 0.02);
}
.session-item.active {
  background-color: var(--primary-light);
  color: var(--primary-hover);
  border-color: rgba(46, 125, 50, 0.15);
  font-weight: 600;
}
.session-title {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.incognito-badge {
  font-size: 10px;
  background-color: #7D3C98;
  color: white;
  padding: 2px 6px;
  border-radius: 10px;
  transform: scale(0.9);
}
.empty-sessions {
  font-size: 13px;
  color: var(--text-secondary);
  text-align: center;
  padding: 30px 0;
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
</style>
