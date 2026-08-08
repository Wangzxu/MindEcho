<template>
  <div class="safety-container">
    <div class="sub-tabs card-panel">
      <button :class="['sub-tab-btn', { active: activeSubTab === 'keywords' }]"
              @click="activeSubTab = 'keywords'">⛔ 安全词库设置</button>
      <button :class="['sub-tab-btn', { active: activeSubTab === 'rag_seeds' }]"
              @click="activeSubTab = 'rag_seeds'">🧠 预警 RAG 向量导入</button>
    </div>

    <SafetyKeywords
      v-if="activeSubTab === 'keywords'"
      :keywords="keywords"
      @add-keyword="(data) => $emit('add-keyword', data)"
      @toggle-keyword-status="(w, cat) => $emit('toggle-keyword-status', w, cat)"
    />

    <SafetyRagSeeds
      v-if="activeSubTab === 'rag_seeds'"
      @increment-mock-stats="(type) => $emit('increment-mock-stats', type)"
      @show-toast="(msg, type) => $emit('show-toast', msg, type)"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import SafetyKeywords from './SafetyKeywords.vue'
import SafetyRagSeeds from './SafetyRagSeeds.vue'

defineProps({ keywords: { type: Object, required: true } })
defineEmits(['add-keyword', 'toggle-keyword-status', 'increment-mock-stats', 'show-toast'])

const activeSubTab = ref('keywords')
</script>

<style scoped>
.safety-container { display: flex; flex-direction: column; gap: 20px; }
.sub-tabs { display: flex; padding: 5px; background: var(--panel-bg); border-radius: var(--radius-md); }
.sub-tab-btn {
  flex: 1; background: transparent; border: none; padding: 12px;
  font-size: 14px; font-weight: 500; color: var(--text-secondary);
  border-radius: var(--radius-sm); cursor: pointer; transition: var(--transition-normal);
}
.sub-tab-btn:hover { background: var(--primary-light); color: var(--primary-hover); }
.sub-tab-btn.active { background: var(--primary-light); color: var(--primary-hover); box-shadow: 0 2px 8px var(--shadow-color); font-weight: 600; }
</style>
