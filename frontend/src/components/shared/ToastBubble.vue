<template>
  <transition name="toast-fade">
    <div v-if="visible" :class="['toast-bubble', type]">
      <span class="toast-icon">{{ iconMap[type] || '🔵' }}</span>
      <span class="toast-message">{{ message }}</span>
    </div>
  </transition>
</template>

<script setup>
import { watch } from 'vue'

const props = defineProps({
  message: { type: String, default: '' },
  type: { type: String, default: 'success' },
  visible: { type: Boolean, default: false },
  duration: { type: Number, default: 3000 }
})

const emit = defineEmits(['close'])

const iconMap = {
  success: '🟢',
  error: '🔴',
  warning: '🟡',
  info: '🔵'
}

let timer = null
watch(() => props.visible, (v) => {
  clearTimeout(timer)
  if (v) {
    timer = setTimeout(() => emit('close'), props.duration)
  }
})
</script>

<style scoped>
.toast-bubble {
  position: fixed; top: 30px; left: 50%; transform: translateX(-50%);
  display: flex; align-items: center; gap: 10px;
  padding: 12px 24px; border-radius: var(--radius-md);
  box-shadow: 0 8px 30px rgba(0,0,0,0.12);
  background: var(--panel-bg); border: 1px solid var(--border-color);
  z-index: 9999; font-size: 13.5px; font-weight: 500;
  color: var(--text-primary); backdrop-filter: blur(10px);
}
.toast-bubble.success { border-color: var(--primary); background: var(--primary-light); color: var(--primary-hover); }
.toast-bubble.error   { border-color: var(--warning); background: var(--warning-light); color: var(--warning); }
.toast-bubble.warning { border-color: #f39c12; background: rgba(243,156,18,0.1); color: #D35400; }
.toast-bubble.info    { border-color: #5DADE2; background: rgba(93,173,226,0.1); color: #2980B9; }
.toast-icon { font-size: 16px; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: all 0.3s cubic-bezier(0.16,1,0.3,1); }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translate(-50%, -20px); }
</style>
