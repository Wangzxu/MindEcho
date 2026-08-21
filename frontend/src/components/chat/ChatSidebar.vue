<template>
  <div class="sidebar card-panel">
    <div class="sidebar-header">
      <span class="logo-emoji">🌱</span>
      <span class="app-name">MindEcho</span>
      <button class="theme-toggle" @click="toggle" :title="isNight ? '切换日间' : '切换夜间'">
        {{ isNight ? '☀️' : '🌙' }}
      </button>
    </div>

    <!-- 用户信息 -->
    <div class="user-info">
      <div class="avatar-container">
        <div class="avatar-placeholder">👤</div>
      </div>
      <div class="user-details">
        <p class="user-nickname">{{ nickname }}</p>
        <p class="user-role">学生账户</p>
      </div>
    </div>

    <!-- 双模式切换（仅两种固定会话：直接聊天 / 无痕树洞） -->
    <div class="mode-switch">
      <button
        class="mode-btn"
        :class="{ active: activeMode === 'normal' }"
        @click="$emit('switch-mode', 'normal')"
      >
        <span class="mode-icon">💬</span>
        <span class="mode-label">直接聊天</span>
        <span class="mode-desc">陪伴倾诉 · 记录存档</span>
      </button>
      <button
        class="mode-btn incognito"
        :class="{ active: activeMode === 'incognito' }"
        @click="$emit('switch-mode', 'incognito')"
      >
        <span class="mode-icon">🔒</span>
        <span class="mode-label">无痕树洞</span>
        <span class="mode-desc">阅后即焚 · 不落库</span>
      </button>
    </div>

    <!-- 会话信息（固定名称：直接聊天 / 无痕树洞） -->
    <div class="session-status">
      <p class="session-status-title">{{ activeMode === 'incognito' ? '🔒 无痕树洞' : '💬 直接聊天' }}</p>
      <p class="session-status-desc">
        {{ activeMode === 'incognito'
          ? '该模式下的对话仅保存在内存中，关闭页面即物理清除，绝不写入数据库。'
          : '该模式下的对话会持久化保存，重新打开页面仍可继续。' }}
      </p>
    </div>

    <!-- 画像可视化入口 -->
    <button class="profile-btn" @click="$emit('show-profile')">
      🧠 我的心理画像
    </button>

    <button class="logout-btn" @click="$emit('logout')">🚪 退出登录</button>
  </div>
</template>

<script setup>
import { useTheme } from '../../composables/useTheme'

const { isNight, toggle } = useTheme()

defineProps({
  nickname: { type: String, default: '同学' },
  activeMode: { type: String, default: 'normal' }   // 'normal' | 'incognito'
})

defineEmits(['switch-mode', 'show-profile', 'logout'])
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

/* 双模式切换 */
.mode-switch { display: flex; flex-direction: column; gap: 10px; margin-bottom: 15px; }
.mode-btn {
  width: 100%; display: flex; flex-direction: column; align-items: flex-start; gap: 2px;
  padding: 13px 15px; border: 1px solid var(--border-color); border-radius: var(--radius-md);
  background: var(--bg-color); color: var(--text-primary); cursor: pointer; transition: var(--transition-normal);
}
.mode-btn:hover { background: var(--primary-light); }
.mode-btn.active { background: var(--primary-light); border-color: var(--primary); color: var(--primary-hover); box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.mode-btn.incognito.active { border-color: var(--accent); background: var(--accent-light); color: var(--accent-hover); }
.mode-icon { font-size: 15px; }
.mode-label { font-weight: 600; font-size: 14px; }
.mode-desc { font-size: 11px; color: var(--text-secondary); }

.session-status { padding: 10px 12px; background: var(--bg-color); border-radius: var(--radius-md); margin-bottom: 15px; }
.session-status-title { font-size: 12.5px; font-weight: 600; color: var(--text-primary); margin-bottom: 3px; }
.session-status-desc { font-size: 11px; color: var(--text-secondary); line-height: 1.5; }

/* 画像入口 */
.profile-btn {
  width: 100%; padding: 12px; margin-bottom: 15px;
  background: linear-gradient(135deg, var(--primary-light), var(--accent-light));
  border: 1px solid var(--border-color); border-radius: var(--radius-md);
  color: var(--primary-hover); font-size: 13.5px; font-weight: 500; cursor: pointer;
  transition: var(--transition-normal);
}
.profile-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.08); }

.logout-btn {
  margin-top: auto;
  background: transparent; border: 1px solid var(--border-color); padding: 12px;
  border-radius: var(--radius-md); color: var(--text-primary); font-size: 14px;
  cursor: pointer; transition: var(--transition-normal);
}
.logout-btn:hover { background: var(--warning-light); border-color: var(--warning); color: #C0392B; }
</style>
