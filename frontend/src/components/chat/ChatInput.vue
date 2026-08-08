<template>
  <div class="input-area">
    <input
      v-model="inputMsg"
      type="text"
      class="input-field"
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

defineProps({ isGenerating: { type: Boolean, default: false } })
const emit = defineEmits(['send-message'])
const inputMsg = ref('')
const inputRef = ref(null)

function handleSend() {
  const content = inputMsg.value.trim()
  if (!content) return
  emit('send-message', content)
  inputMsg.value = ''
}

function focus() {
  nextTick(() => { inputRef.value?.focus() })
}

defineExpose({ focus })
</script>

<style scoped>
.input-area {
  padding: 20px 25px; border-top: 1px solid var(--border-color);
  display: flex; gap: 15px; box-sizing: border-box;
}
.input-field { flex: 1; }
.send-btn { padding: 10px 24px; flex-shrink: 0; }
</style>
