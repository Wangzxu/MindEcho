<template>
  <div class="input-area">
    <input 
      v-model="inputMsg"
      type="text" 
      class="input-field breathe-glow" 
      placeholder="把你的烦恼写在这里，我会一直倾听... (回车发送)"
      @keyup.enter="handleSend"
      :disabled="isGenerating"
      ref="inputRef"
    />
    <button 
      class="btn-primary send-btn" 
      @click="handleSend"
      :disabled="isGenerating || !inputMsg.trim()"
    >
      {{ isGenerating ? '思考中' : '发送' }}
    </button>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'

defineProps({
  isGenerating: { type: Boolean, default: false }
})

const emit = defineEmits(['send-message'])
const inputMsg = ref('')
const inputRef = ref(null)

function handleSend() {
  const content = inputMsg.value.trim()
  if (!content) return
  emit('send-message', content)
  inputMsg.value = ''
}

// 供父组件在加载完会话后自动聚焦输入框
function focus() {
  nextTick(() => {
    if (inputRef.value) {
      inputRef.value.focus()
    }
  })
}

defineExpose({ focus })
</script>

<style scoped>
.input-area {
  padding: 20px 25px;
  border-top: 1px solid var(--border-color);
  display: flex;
  gap: 15px;
  box-sizing: border-box;
}
.input-field {
  flex: 1;
}

/* 呼吸灯效果输入框 */
.breathe-glow {
  transition: border-color 0.4s ease-in-out, box-shadow 0.4s ease-in-out;
  border: 1.5px solid var(--border-color);
}
.breathe-glow:focus {
  border-color: #2E7D32;
  animation: breathe-animation 3s infinite ease-in-out;
}

@keyframes breathe-animation {
  0% { box-shadow: 0 0 3px rgba(46, 125, 50, 0.15); }
  50% { box-shadow: 0 0 15px rgba(46, 125, 50, 0.45); }
  100% { box-shadow: 0 0 3px rgba(46, 125, 50, 0.15); }
}

.send-btn {
  padding: 10px 24px;
  flex-shrink: 0;
}
</style>
