<template>
  <div class="knowledge-manager card-panel">
    <!-- Tab 切换栏 -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-btn', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <!-- ============ Tab 1: 文档上传 ============ -->
    <div v-if="activeTab === 'upload'" class="tab-content">
      <div
        class="upload-zone"
        :class="{ dragging: isDragging }"
        @dragenter.prevent="dragCounter++; isDragging = true"
        @dragleave.prevent="dragCounter--; if (dragCounter === 0) isDragging = false"
        @drop.prevent="dragCounter = 0; isDragging = false; handleDrop($event)"
        @click="triggerFileInput"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".pdf,.docx,.doc,.txt,.md"
          style="display: none"
          @change="handleFileSelect"
        />
        <div class="upload-prompt">
          <span class="upload-icon">📤</span>
          <p>拖拽文件到此处，或点击选择</p>
          <p class="upload-hint">支持 PDF / DOCX / TXT / MD</p>
        </div>
      </div>

      <!-- 处理进度 -->
      <div v-if="uploadTasks.length" class="task-list">
        <div
          v-for="task in uploadTasks"
          :key="task.id"
          :class="['task-card', task.status]"
        >
          <div class="task-header">
            <span class="task-file">📄 {{ task.fileName }}</span>
            <span class="task-status">
              {{ statusLabel(task.status) }}
            </span>
          </div>
          <div class="task-steps">
            <span :class="['step', { done: task.step >= 1 }]">📝 转换</span>
            <span class="step-arrow">→</span>
            <span :class="['step', { done: task.step >= 2 }]">✂️ 切片</span>
            <span class="step-arrow">→</span>
            <span :class="['step', { done: task.step >= 3 }]">🧮 向量化</span>
            <span class="step-arrow">→</span>
            <span :class="['step', { done: task.step >= 4 }]">✅ 完成</span>
          </div>
          <div v-if="task.error" class="task-error">{{ task.error }}</div>
        </div>
      </div>
    </div>

    <!-- ============ Tab 2: 知识列表 ============ -->
    <div v-if="activeTab === 'list'" class="tab-content">
      <div class="list-toolbar">
        <input
          v-model="searchKeyword"
          type="text"
          class="search-input"
          placeholder="搜索文件名..."
          @keyup.enter="fetchList"
        />
        <button class="btn btn-primary" @click="fetchList">🔍 搜索</button>
      </div>
      <table v-if="listItems.length" class="data-table">
        <thead>
          <tr>
            <th>文件名</th>
            <th>状态</th>
            <th>Chunks</th>
            <th>大小</th>
            <th>时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in listItems" :key="item.id">
            <td class="file-name-cell">{{ item.file_name }}</td>
            <td>
              <span :class="['status-badge', item.status]">
                {{ statusLabel(item.status) }}
              </span>
            </td>
            <td>{{ item.chunk_count }}</td>
            <td>{{ formatSize(item.file_size) }}</td>
            <td>{{ formatTime(item.created_at) }}</td>
            <td class="action-cell">
              <button class="btn-sm" @click="reprocessItem(item)">🔄 重处理</button>
              <button class="btn-sm" @click="viewChunks(item)">📋 Chunks</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">暂无知识文档</div>
      <div class="pagination">
        <button :disabled="page <= 1" @click="page--; fetchList()">上一页</button>
        <span>第 {{ page }} 页 / 共 {{ totalPages }} 页</span>
        <button :disabled="page >= totalPages" @click="page++; fetchList()">下一页</button>
      </div>
    </div>

    <!-- ============ Tab 3: 链路调试 ============ -->
    <div v-if="activeTab === 'debug'" class="tab-content">
      <div class="debug-input-row">
        <input
          v-model="debugQuery"
          type="text"
          class="search-input debug-input"
          placeholder="输入测试问题，如：焦虑障碍怎么治疗？"
          @keyup.enter="runTrace"
        />
        <button class="btn btn-primary" @click="runTrace" :disabled="tracing">
          {{ tracing ? '⏳ 追踪中...' : '🔍 检索' }}
        </button>
      </div>

      <!-- 链路流程可视化 -->
      <div v-if="traceData" class="trace-timeline">
        <div v-for="(step, si) in traceData.steps" :key="si" class="trace-step">
          <!-- 连接线 -->
          <div v-if="si > 0" class="trace-connector">
            <span class="connector-line">┃</span>
            <span class="connector-duration">▼ {{ step.duration_ms }}ms</span>
          </div>

          <div class="step-card">
            <div class="step-icon">{{ stepIcon(step.name) }}</div>
            <div class="step-body">
              <div class="step-name">{{ step.name }}</div>
              <div class="step-meta">
                <span v-if="step.model">模型: {{ step.model }}</span>
                <span v-if="step.dimension">维度: {{ step.dimension }}</span>
                <span v-if="step.collection">集合: {{ step.collection }}</span>
                <span v-if="step.metric">度量: {{ step.metric }}</span>
                <span v-if="step.top_k">top-{{ step.top_k }}</span>
              </div>

              <!-- 检索结果卡片 -->
              <div v-if="step.results && step.results.length" class="chunk-cards">
                <div
                  v-for="(chunk, ci) in step.results"
                  :key="ci"
                  :class="['chunk-card', `rank-${chunk.rank}`]"
                >
                  <div class="chunk-header">
                    <span class="chunk-rank">{{ ['🥇','🥈','🥉'][ci] || '' }} Chunk #{{ chunk.rank }}</span>
                    <span class="chunk-score">相似度: {{ chunk.score }}</span>
                  </div>
                  <div class="chunk-meta">
                    <span>📄 {{ chunk.file_name }}</span>
                    <span v-if="chunk.h1 || chunk.h2 || chunk.h3" class="chunk-path">
                      📂 {{ [chunk.h1, chunk.h2, chunk.h3].filter(Boolean).join(' > ') }}
                    </span>
                  </div>
                  <div class="chunk-content">
                    <pre>{{ chunk.content }}</pre>
                  </div>
                  <details class="parent-expand">
                    <summary>展开父文档 ▼</summary>
                    <pre class="parent-content">{{ chunk.parent_content }}</pre>
                  </details>
                </div>
              </div>

              <!-- Small-to-Big 统计 -->
              <div v-if="step.child_count !== undefined" class="sbs-stats">
                <span>{{ step.child_count }} 个子 chunk → {{ step.parent_count }} 个父文档</span>
                <span>去重后: {{ step.dedup_count }}</span>
                <span>{{ step.total_chars }} 字符 (~{{ step.estimated_tokens }} tokens)</span>
                <span :class="step.within_budget ? 'budget-ok' : 'budget-over'">
                  {{ step.within_budget ? '✅' : '⚠️' }} 预算 {{ step.budget_tokens }} tokens
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="!tracing" class="empty-state">
        输入测试问题，点击"检索"查看完整的 RAG 链路追踪
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import axios from 'axios'

const props = defineProps({
  getAuthHeader: { type: Function, required: true }
})

// ---- Tabs ----
const tabs = [
  { id: 'upload', label: '文档上传', icon: '📤' },
  { id: 'list', label: '知识列表', icon: '📋' },
  { id: 'debug', label: '链路调试', icon: '🔍' },
]
const activeTab = ref('upload')

// ---- Tab 1: Upload ----
const fileInput = ref(null)
const isDragging = ref(false)
let dragCounter = 0
const uploadTasks = reactive([])
let taskIdCounter = 0

function triggerFileInput() {
  fileInput.value?.click()
}

function statusLabel(s) {
  const map = { pending: '⏳ 等待', processing: '🔄 处理中', success: '✅ 成功', failed: '❌ 失败' }
  return map[s] || s
}

async function uploadFile(file) {
  const tid = ++taskIdCounter
  const task = reactive({ id: tid, fileName: file.name, status: 'processing', step: 0, error: '' })
  uploadTasks.push(task)

  try {
    task.step = 1
    const formData = new FormData()
    formData.append('file', file)
    const res = await axios.post('/api/admin/knowledge/upload', formData, {
      headers: { ...props.getAuthHeader() }
    })
    if (res.data?.code === 200) {
      task.step = 4
      task.status = 'success'
    } else {
      throw new Error(res.data?.message || '上传失败')
    }
  } catch (err) {
    task.status = 'failed'
    task.error = err.response?.data?.detail || err.message || '上传失败'
  }
}

function handleDrop(e) {
  isDragging.value = false
  for (const file of e.dataTransfer.files) {
    uploadFile(file)
  }
}

function handleFileSelect(e) {
  for (const file of e.target.files) {
    uploadFile(file)
  }
  e.target.value = ''
}

// ---- Tab 2: List ----
const searchKeyword = ref('')
const listItems = ref([])
const page = ref(1)
const size = 10

const totalPages = computed(() => Math.max(1, Math.ceil(listItems.value.length / size)))

async function fetchList() {
  try {
    const res = await axios.get('/api/admin/knowledge', {
      headers: props.getAuthHeader(),
      params: { page: page.value, size: 100, keyword: searchKeyword.value || undefined }
    })
    if (res.data?.code === 200) {
      listItems.value = res.data.data.items || []
    }
  } catch (err) {
    console.error('获取知识列表失败:', err)
  }
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatTime(iso) {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    const pad = n => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch { return iso }
}

async function reprocessItem(item) {
  try {
    const res = await axios.post(`/api/admin/knowledge/${item.id}/reprocess`, {}, {
      headers: props.getAuthHeader()
    })
    if (res.data?.code === 200) {
      item.status = 'success'
      item.chunk_count = res.data.data.chunk_count
    }
  } catch (err) {
    console.error('重处理失败:', err)
  }
}

async function viewChunks(item) {
  try {
    const res = await axios.get(`/api/admin/knowledge/${item.id}/chunks`, {
      headers: props.getAuthHeader()
    })
    if (res.data?.code === 200) {
      // 在控制台输出，后续可扩展为弹窗
      console.log(`Chunks for ${item.file_name}:`, res.data.data)
      alert(`${item.file_name} 共 ${res.data.data.total_chunks} 个 chunks，详情见控制台`)
    }
  } catch (err) {
    console.error('获取 chunks 失败:', err)
  }
}

// ---- Tab 3: Debug ----
const debugQuery = ref('')
const tracing = ref(false)
const traceData = ref(null)

function stepIcon(name) {
  if (name.includes('Embedding')) return '🧮'
  if (name.includes('ChromaDB') || name.includes('向量')) return '🗄️'
  if (name.includes('父文档') || name.includes('Small')) return '📤'
  return '🔍'
}

async function runTrace() {
  if (!debugQuery.value.trim() || tracing.value) return
  tracing.value = true
  traceData.value = null
  try {
    const res = await axios.post('/api/admin/knowledge/trace',
      { query: debugQuery.value.trim() },
      { headers: props.getAuthHeader() }
    )
    if (res.data?.code === 200) {
      traceData.value = res.data.data
    }
  } catch (err) {
    console.error('链路追踪失败:', err)
    alert('追踪失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    tracing.value = false
  }
}

// 加载列表
fetchList()
</script>

<style scoped>
.knowledge-manager {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  background: var(--panel-bg);
  border-radius: var(--radius-md);
}

/* ---- Tab Bar ---- */
.tab-bar {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid var(--border-color);
  padding-bottom: 0;
}
.tab-btn {
  padding: 10px 20px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: var(--transition-normal);
  display: flex;
  align-items: center;
  gap: 6px;
}
.tab-btn:hover { color: var(--primary-hover); }
.tab-btn.active {
  color: var(--primary-hover);
  border-bottom-color: var(--primary);
  font-weight: 600;
}
.tab-icon { font-size: 16px; }

.tab-content { padding-top: 8px; }

/* ---- Upload Zone ---- */
.upload-zone {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-md);
  padding: 48px;
  text-align: center;
  cursor: pointer;
  transition: var(--transition-normal);
}
.upload-zone:hover, .upload-zone.dragging {
  border-color: var(--primary);
  background: var(--primary-light);
}
.upload-icon { font-size: 40px; display: block; margin-bottom: 12px; }
.upload-hint { font-size: 12px; color: var(--text-secondary); margin-top: 8px; }

/* ---- Task Cards ---- */
.task-list { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }
.task-card {
  padding: 14px 18px;
  border-radius: var(--radius-sm);
  background: var(--bg-color);
  border: 1px solid var(--border-color);
}
.task-card.success { border-color: #27ae60; }
.task-card.failed { border-color: #e74c3c; }
.task-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.task-file { font-weight: 600; }
.task-steps { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.step { color: var(--text-secondary); }
.step.done { color: #27ae60; font-weight: 500; }
.step-arrow { color: var(--text-secondary); }
.task-error { color: #e74c3c; font-size: 12px; margin-top: 8px; }

/* ---- Data Table ---- */
.list-toolbar { display: flex; gap: 10px; margin-bottom: 16px; }
.search-input { flex: 1; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: var(--radius-sm); background: var(--bg-color); color: var(--text-primary); font-size: 13px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th { text-align: left; padding: 10px 8px; border-bottom: 2px solid var(--border-color); color: var(--text-secondary); font-weight: 600; }
.data-table td { padding: 10px 8px; border-bottom: 1px solid var(--border-color); }
.file-name-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-badge { padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 500; }
.status-badge.success { background: #d5f5e3; color: #27ae60; }
.status-badge.processing { background: #fef9e7; color: #f39c12; }
.status-badge.failed { background: #fadbd8; color: #e74c3c; }
.status-badge.pending { background: #ebf5fb; color: #2980b9; }
.action-cell { display: flex; gap: 6px; }
.btn-sm { padding: 4px 10px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--bg-color); color: var(--text-primary); font-size: 12px; cursor: pointer; }
.btn-sm:hover { background: var(--primary-light); }
.btn { padding: 8px 16px; border: none; border-radius: var(--radius-sm); cursor: pointer; font-size: 13px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-hover); }
.empty-state { text-align: center; padding: 40px; color: var(--text-secondary); }
.pagination { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 16px; font-size: 13px; }
.pagination button { padding: 6px 14px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--bg-color); color: var(--text-primary); cursor: pointer; }
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }

/* ---- Debug / Trace ---- */
.debug-input-row { display: flex; gap: 10px; margin-bottom: 20px; }
.debug-input { font-size: 14px; padding: 10px 14px; }

.trace-timeline { display: flex; flex-direction: column; gap: 0; }
.trace-connector { text-align: center; padding: 2px 0; color: var(--text-secondary); font-size: 12px; }
.connector-line { display: block; font-size: 18px; line-height: 1; }

.step-card {
  display: flex; gap: 14px;
  padding: 16px;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
}
.step-icon { font-size: 24px; flex-shrink: 0; }
.step-body { flex: 1; }
.step-name { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
.step-meta { display: flex; gap: 12px; font-size: 12px; color: var(--text-secondary); flex-wrap: wrap; }

.chunk-cards { display: flex; flex-direction: column; gap: 12px; margin-top: 12px; }
.chunk-card { border: 1px solid var(--border-color); border-radius: var(--radius-sm); overflow: hidden; }
.chunk-card.rank-1 { border-left: 3px solid #f39c12; }
.chunk-card.rank-2 { border-left: 3px solid #888; }
.chunk-card.rank-3 { border-left: 3px solid #b87333; }
.chunk-header { display: flex; justify-content: space-between; padding: 8px 12px; background: var(--panel-bg); font-size: 13px; font-weight: 500; }
.chunk-score { color: var(--primary); font-weight: 600; }
.chunk-meta { display: flex; flex-direction: column; gap: 2px; padding: 6px 12px; font-size: 12px; color: var(--text-secondary); }
.chunk-path { color: var(--primary-hover); }
.chunk-content { padding: 0 12px 8px; }
.chunk-content pre, .parent-content {
  white-space: pre-wrap; word-break: break-word;
  font-size: 12px; line-height: 1.6;
  background: var(--panel-bg); padding: 10px; border-radius: 4px;
  max-height: 200px; overflow-y: auto;
}
.parent-expand { padding: 0 12px 8px; }
.parent-expand summary { cursor: pointer; font-size: 12px; color: var(--primary); padding: 4px 0; }

.sbs-stats {
  display: flex; gap: 14px; margin-top: 10px;
  font-size: 13px; color: var(--text-secondary); flex-wrap: wrap;
}
.budget-ok { color: #27ae60; font-weight: 500; }
.budget-over { color: #e74c3c; font-weight: 500; }
</style>
