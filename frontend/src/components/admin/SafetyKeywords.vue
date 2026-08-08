<template>
  <div class="sub-content">
    <div class="split-layout">
      <div class="form-card card-panel">
        <h3>➕ 添加安全拦截词</h3>
        <p class="section-desc">请输入要拦截的敏感字词。输入框聚焦时将开启 3.75s 情绪呼呼吸调节引导。</p>
        <form @submit.prevent="submitWord" class="admin-form">
          <div class="form-group">
            <label class="form-label">敏感词条</label>
            <input
              type="text"
              class="input-field"
              placeholder="例如: 烧炭、傻逼"
              v-model="newWordForm.word"
              required
            />
          </div>
          <div class="form-group">
            <label class="form-label">词库类型</label>
            <select v-model="newWordForm.type" class="input-field select-field">
              <option value="high_risk">🚨 危险词 (高危自残等极恶劣词汇)</option>
              <option value="violation">⚠️ 违规词 (谩骂人身攻击等不合规词)</option>
            </select>
          </div>
          <button type="submit" class="btn-primary">确认添加并热同步</button>
        </form>
      </div>

      <div class="list-card card-panel">
        <div class="list-header">
          <h3>📜 活跃安全词过滤库</h3>
          <span class="sync-status">⚡ 自动同步热更新</span>
        </div>
        <div class="keyword-categories">
          <div class="category-block">
            <h4>🚨 危险词列表 (触发高危熔断)</h4>
            <div class="keyword-tags">
              <span v-for="w in keywords.highRisk" :key="w.id" :class="['keyword-tag danger', { disabled: !w.enabled }]">
                {{ w.word }}
                <button class="toggle-word-btn" @click="$emit('toggle-keyword-status', w, 'highRisk')">
                  {{ w.enabled ? '🟢' : '⚪' }}
                </button>
              </span>
              <span v-if="keywords.highRisk.length === 0" class="empty-tag">无危险词</span>
            </div>
          </div>

          <div class="category-block">
            <h4>⚠️ 违规词列表 (触发柔性警示)</h4>
            <div class="keyword-tags">
              <span v-for="w in keywords.violation" :key="w.id" :class="['keyword-tag warning', { disabled: !w.enabled }]">
                {{ w.word }}
                <button class="toggle-word-btn" @click="$emit('toggle-keyword-status', w, 'violation')">
                  {{ w.enabled ? '🟢' : '⚪' }}
                </button>
              </span>
              <span v-if="keywords.violation.length === 0" class="empty-tag">无违规词</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'

const props = defineProps({
  keywords: { type: Object, required: true }
})

const emit = defineEmits(['add-keyword', 'toggle-keyword-status'])

const newWordForm = reactive({ word: '', type: 'high_risk' })

function submitWord() {
  if (!newWordForm.word.trim()) return
  emit('add-keyword', { word: newWordForm.word.trim(), type: newWordForm.type })
  newWordForm.word = ''
}
</script>

<style scoped>
.sub-content { display: flex; flex-direction: column; gap: 20px; }
.split-layout { display: grid; grid-template-columns: 1fr 1.2fr; gap: 20px; }
.form-card, .list-card { padding: 25px; background: var(--panel-bg); border-radius: var(--radius-md); }
.form-card h3, .list-card h3 { font-size: 15px; font-weight: 600; margin: 0 0 8px 0; color: var(--text-primary); }
.section-desc { font-size: 11.5px; color: var(--text-secondary); margin-bottom: 20px; }
.list-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; margin-bottom: 20px; }
.sync-status { font-size: 10px; color: var(--primary); background: var(--primary-light); padding: 2px 6px; border-radius: 4px; }
.category-block { margin-bottom: 25px; }
.category-block h4 { font-size: 13px; color: var(--text-secondary); margin: 0 0 12px 0; font-weight: 500; }
.keyword-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.keyword-tag { font-size: 12.5px; padding: 6px 12px; border-radius: var(--radius-sm); font-weight: 500; display: inline-flex; align-items: center; gap: 6px; }
.keyword-tag.danger { background: var(--warning-light); color: var(--warning); border: 1px solid var(--warning); }
.keyword-tag.warning { background: rgba(243,156,18,0.1); color: #D35400; border: 1px solid rgba(243,156,18,0.3); }
.keyword-tag.disabled { opacity: 0.4; text-decoration: line-through; }
.toggle-word-btn { background: transparent; border: none; cursor: pointer; font-size: 12px; padding: 0; display: inline-flex; }
.empty-tag { font-size: 12px; color: var(--text-secondary); font-style: italic; }
.admin-form { display: flex; flex-direction: column; gap: 15px; }
.form-group { display: flex; flex-direction: column; gap: 8px; }
.form-label { font-size: 13.5px; font-weight: 500; color: var(--text-primary); }
.select-field { cursor: pointer; }
</style>
