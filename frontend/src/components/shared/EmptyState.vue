<template>
  <div class="empty-state">
    <span class="empty-icon">{{ icon }}</span>
    <p>{{ message }}</p>
  </div>
</template>

<script setup>
defineProps({
  message: { type: String, default: '暂无数据' },
  icon: { type: String, default: '📭' }
})
</script>
