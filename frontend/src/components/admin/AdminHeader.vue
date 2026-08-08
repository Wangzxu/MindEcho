<template>
  <header class="admin-header card-panel">
    <div class="header-left">
      <span class="logo-emoji">🌱</span>
      <h1 class="app-name">MindEcho 教师端后台</h1>
      <span class="badge">管理系统</span>
    </div>
    <div class="header-right">
      <button class="mode-toggle-btn" @click="toggle" :title="isNight ? '切换为日间燕麦色' : '切换为夜间暖灰蓝'">
        <span v-if="isNight">☀️ 日间</span>
        <span v-else>🌙 夜间</span>
      </button>
      <div class="admin-info">
        <span class="avatar-placeholder">🔑</span>
        <span class="admin-name">{{ adminName }} (管理员)</span>
      </div>
      <button class="logout-btn" @click="$emit('logout')">🚪 退出登录</button>
    </div>
  </header>
</template>

<script setup>
import { useTheme } from '../../composables/useTheme'

defineProps({ adminName: { type: String, default: '管理员' } })
defineEmits(['logout'])

const { isNight, toggle } = useTheme()
</script>

<style scoped>
.admin-header { display: flex; justify-content: space-between; align-items: center; padding: 15px 30px; background-color: var(--panel-bg); border-radius: var(--radius-md); }
.header-left { display: flex; align-items: center; gap: 12px; }
.logo-emoji { font-size: 28px; }
.app-name { font-size: 20px; font-weight: 600; color: var(--text-primary); }
.badge { font-size: 11px; background-color: var(--primary-light); color: var(--primary); padding: 3px 8px; border-radius: var(--radius-sm); font-weight: 500; border: 1px solid var(--primary); }
.header-right { display: flex; align-items: center; gap: 20px; }
.mode-toggle-btn { background-color: var(--primary-light); border: 1px solid var(--border-color); padding: 6px 12px; font-size: 12px; border-radius: var(--radius-sm); color: var(--text-primary); cursor: pointer; transition: var(--transition-normal); }
.mode-toggle-btn:hover { background-color: var(--border-color); }
.admin-info { display: flex; align-items: center; gap: 8px; }
.avatar-placeholder { font-size: 20px; }
.admin-name { font-size: 14px; font-weight: 500; color: var(--text-primary); }
.logout-btn { background: transparent; border: 1px solid var(--border-color); padding: 8px 16px; border-radius: var(--radius-md); color: var(--text-primary); font-size: 13px; cursor: pointer; transition: var(--transition-normal); }
.logout-btn:hover { background-color: var(--warning-light); border-color: var(--warning); color: #C0392B; }
</style>
