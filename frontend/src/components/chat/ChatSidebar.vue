<template>
  <div class="sidebar card-panel">
    <div class="sidebar-header">
      <span class="logo-emoji">🌱</span>
      <span class="app-name">MindEcho</span>
      <button class="theme-toggle" @click="toggle" :title="isNight ? '切换日间' : '切换夜间'">
        {{ isNight ? '☀️' : '🌙' }}
      </button>
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

    <div class="new-sessions-btn-group">
      <button class="new-session-btn" @click="$emit('create-session', false)" :disabled="isCreatingSession">
        ➕ 新建常规对话
      </button>
      <button class="new-session-btn incognito-btn" @click="$emit('create-session', true)" :disabled="isCreatingSession">
        🔒 新建无痕树洞
      </button>
    </div>

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
      <EmptyState v-if="sessions.length === 0" message="暂无对话，点击上方新建" icon="💬" />
    </div>

    <button class="logout-btn" @click="$emit('logout')">🚪 退出登录</button>
  </div>
</template>

<script setup>
import { useTheme } from '../../composables/useTheme'
import EmptyState from '../shared/EmptyState.vue'

const { isNight, toggle } = useTheme()

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
  width: 280px; display: flex; flex-direction: column; padding: 25px 15px;
  border-radius: var(--radius-lg); background: var(--panel-bg); flex-shrink: 0;
  box-shadow: 0 10px 30px var(--shadow-color); box-sizing: border-box;
}
.sidebar-header { display: flex; align-items: center; gap: 10px; font-size: 20px; font-weight: 600; margin-bottom: 20px; color: var(--primary); }
.logo-emoji { font-size: 24px; }
.app-name { flex: 1; }
.theme-toggle {
  background: var(--primary-light); border: 1px solid var(--border-color);
  border-radius: var(--radius-sm); padding: 4px 8px; font-size: 14px;
  cursor: pointer; transition: var(--transition-normal);
}
.theme-toggle:hover { background: var(--border-color); }
.user-info { display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--primary-light); border-radius: var(--radius-md); margin-bottom: 15px; }
.avatar-placeholder { width: 40px; height: 40px; border-radius: 50%; background: var(--panel-bg); display: flex; justify-content: center; align-items: center; font-size: 20px; }
.user-nickname { font-weight: 600; font-size: 15px; color: var(--primary-hover); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.user-role { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }

.new-sessions-btn-group { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
.new-session-btn {
  width: 100%; padding: 12px; background: var(--primary); color: white; border: none;
  border-radius: var(--radius-md); font-size: 13.5px; font-weight: 500; cursor: pointer;
  transition: var(--transition-normal); box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.new-session-btn:hover { background: var(--primary-hover); transform: translateY(-1px); }
.incognito-btn { background: var(--accent); }
.incognito-btn:hover { background: var(--accent-hover); }

.sessions-list { flex: 1; overflow-y: auto; margin-bottom: 20px; display: flex; flex-direction: column; gap: 8px; }
.session-item {
  display: flex; align-items: center; gap: 10px; padding: 12px 15px;
  border-radius: var(--radius-md); cursor: pointer; transition: var(--transition-normal);
  font-size: 14.5px; border: 1px solid transparent; color: var(--text-primary);
}
.session-item:hover { background: rgba(0,0,0,0.02); }
.session-item.active { background: var(--primary-light); color: var(--primary-hover); border-color: var(--primary); font-weight: 600; }
.session-title { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.incognito-badge { font-size: 10px; background: var(--accent); color: white; padding: 2px 6px; border-radius: 10px; }

.logout-btn {
  background: transparent; border: 1px solid var(--border-color); padding: 12px;
  border-radius: var(--radius-md); color: var(--text-primary); font-size: 14px;
  cursor: pointer; transition: var(--transition-normal);
}
.logout-btn:hover { background: var(--warning-light); border-color: var(--warning); color: #C0392B; }
</style>
