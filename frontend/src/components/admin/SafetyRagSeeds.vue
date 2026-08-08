<template>
  <div class="sub-content card-panel">
    <div class="rag-intro">
      <h3>🧠 模糊语义安全预警 (RAG 种子库导入)</h3>
      <p>有些高危或违规言论非常隐蔽（例如："买好了敌敌畏"、"要在身上划几道"），传统的硬词匹配容易漏报。通过将"预警语义样本"导入 ChromaDB，系统可以在发问时做模糊语义距离比对，距离过近将自动拦截并写入最近活动日志。</p>
    </div>

    <div class="split-layout">
      <div class="form-card card-panel flat">
        <h4>📥 导入语义拦截样本句</h4>
        <form @submit.prevent="addRagSeed" class="admin-form">
          <div class="form-group">
            <label class="form-label">预警样本短句</label>
            <input
              type="text"
              class="input-field"
              placeholder="输入口语化高危/违规倾向句子"
              v-model="newSeedForm.text"
              required
            />
          </div>
          <div class="form-group">
            <label class="form-label">判定倾向</label>
            <select v-model="newSeedForm.type" class="input-field select-field">
              <option value="high_risk">🚨 判定为: 高危情况 (CRISIS 意图)</option>
              <option value="violation">⚠️ 判定为: 违规情况 (SAFETY 意图)</option>
            </select>
          </div>
          <button type="submit" class="btn-accent">ChromaDB 向量化导入</button>
        </form>
      </div>

      <div class="list-card card-panel flat">
        <h4>🗂️ 已生效的预警向量样本数: {{ ragSeeds.length }} 条</h4>
        <div class="seeds-list-scroll">
          <div v-for="seed in ragSeeds" :key="seed.id" class="seed-item">
            <span :class="['seed-type', seed.type === 'high_risk' ? 'red' : 'orange']">
              {{ seed.type === 'high_risk' ? '高危' : '违规' }}
            </span>
            <span class="seed-text">"{{ seed.text }}"</span>
            <span class="seed-vector-tag">1024D Vector</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import axios from 'axios'
import { getAuthHeader } from '../../composables/useAuth'

const emit = defineEmits(['increment-mock-stats', 'show-toast'])

const newSeedForm = reactive({ text: '', type: 'high_risk' })
const ragSeeds = ref([])

async function fetchRagSeeds() {
  try {
    const res = await axios.get('/api/admin/safety-seeds', { headers: getAuthHeader() })
    if (res.data?.code === 200) {
      ragSeeds.value = res.data.data
    }
  } catch (err) {
    console.error('获取预警向量样本失败:', err)
  }
}

async function addRagSeed() {
  const textVal = newSeedForm.text.trim()
  if (!textVal) return
  try {
    const res = await axios.post('/api/admin/safety-seeds', {
      text: textVal,
      type: newSeedForm.type
    }, { headers: getAuthHeader() })
    if (res.data?.code === 200) {
      emit('show-toast', 'ChromaDB 已成功完成 1024 维向量提取，并同步至 safety_warnings_kb 样本库！', 'success')
      newSeedForm.text = ''
      await fetchRagSeeds()
      emit('increment-mock-stats', newSeedForm.type)
    } else {
      emit('show-toast', res.data?.message || '导入 ChromaDB 失败', 'error')
    }
  } catch (err) {
    const errorMsg = err.response?.data?.detail || err.message || '网络或服务器异常'
    emit('show-toast', `导入向量样本失败: ${errorMsg}`, 'error')
  }
}

onMounted(() => fetchRagSeeds())
</script>

<style scoped>
.sub-content { padding: 25px; }
.rag-intro { margin-bottom: 25px; border-left: 4px solid var(--primary); padding-left: 15px; }
.rag-intro h3 { font-size: 16px; font-weight: 600; margin: 0 0 6px 0; }
.rag-intro p { font-size: 12.5px; color: var(--text-secondary); line-height: 1.6; margin: 0; }
.split-layout { display: grid; grid-template-columns: 1fr 1.2fr; gap: 20px; }
.form-card, .list-card { padding: 20px; }
.flat { box-shadow: none !important; border: 1px solid var(--border-color) !important; }
.flat:hover { transform: none !important; }
.seeds-list-scroll { max-height: 320px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.seed-item { display: flex; align-items: center; padding: 12px; background: var(--bg-color); border-radius: var(--radius-sm); border: 1px solid var(--border-color); font-size: 13px; }
.seed-type { font-size: 10.5px; font-weight: 600; padding: 2px 6px; border-radius: 4px; margin-right: 12px; }
.seed-type.red { background: var(--warning-light); color: var(--warning); }
.seed-type.orange { background: rgba(243,156,18,0.15); color: #D35400; }
.seed-text { flex: 1; font-weight: 500; color: var(--text-primary); }
.seed-vector-tag { font-size: 10.5px; color: var(--text-secondary); font-family: monospace; }
.admin-form { display: flex; flex-direction: column; gap: 15px; }
.form-group { display: flex; flex-direction: column; gap: 8px; }
.form-label { font-size: 13.5px; font-weight: 500; color: var(--text-primary); }
.select-field { cursor: pointer; }
</style>
