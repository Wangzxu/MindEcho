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
        @dragover.prevent
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
          <!-- 异步处理进度条 -->
          <div v-if="task.status === 'processing' && task.processedChunks > 0" class="task-progress">
            <div class="progress-track">
              <div
                class="progress-fill"
                :style="{ width: progressPercent(task) + '%' }"
              ></div>
            </div>
            <span class="progress-text">
              {{ task.processedChunks }} / {{ task.chunkCount || '?' }} chunks 已向量化
            </span>
          </div>
          <div v-if="task.error" class="task-error">{{ task.error }}</div>
          <div v-if="task.replacedImportId" class="task-replaced">
            ♻️ 已覆盖旧版本（import_id={{ task.replacedImportId }}），只保留最新一份
          </div>
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
              <button class="btn-sm btn-danger" @click="deleteItem(item)">🗑️ 删除</button>
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
    <div v-if="activeTab === 'debug'" class="tab-content">      <div class="debug-input-row">
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
                <span v-if="step.original" class="rewrite-orig">原输入: {{ step.original }}</span>
                <span v-if="step.rewritten" class="rewrite-new">✏️ 改写: {{ step.rewritten }}</span>
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
                <span v-if="step.fallback_concat_count" class="concat-badge">
                  🧩 {{ step.fallback_concat_count }} 个为子文档拼接（缺父文档）
                </span>
                <span>{{ step.total_chars }} 字符 (~{{ step.estimated_tokens }} tokens)</span>
                <span :class="step.within_budget ? 'budget-ok' : 'budget-over'">
                  {{ step.within_budget ? '✅' : '⚠️' }} 预算 {{ step.budget_tokens }} tokens
                </span>
              </div>

              <!-- 展开后的父文档/拼接内容 -->
              <div v-if="step.expanded && step.expanded.length" class="sbs-parents">
                <div
                  v-for="(p, pi) in step.expanded"
                  :key="pi"
                  :class="['sbs-parent', p.source === 'children_concat' ? 'is-concat' : '']"
                >
                  <div class="sbs-parent-head">
                    <span class="sbs-source">
                      {{ p.source === 'children_concat' ? '🧩 子文档拼接' : '📄 父文档' }} #{{ pi + 1 }}
                    </span>
                    <span v-if="p.file_name">📄 {{ p.file_name }}</span>
                    <span v-if="p.section_id">section: {{ p.section_id }}</span>
                    <span>{{ p.chunk_count }} chunks · 最高分 {{ p.score }}</span>
                  </div>
                  <pre>{{ p.content }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="!tracing" class="empty-state">
        输入测试问题，点击"检索"查看完整的 RAG 链路追踪
      </div>
    </div>

    <!-- ============ Chunks 可视化弹窗 ============ -->
    <div v-if="showChunksModal" class="modal-overlay" @click.self="closeChunksModal">
      <div class="chunks-modal">
        <div class="modal-header">
          <div class="modal-title">
            📋 {{ chunksData?.file_name }}
            <span class="modal-sub">共 {{ chunksData?.total_chunks }} 个 chunks</span>
          </div>
          <button class="modal-close" @click="closeChunksModal">✕</button>
        </div>
        <div class="modal-body">
          <div v-if="chunksLoading" class="empty-state">加载中...</div>
          <div v-else-if="!chunksData?.chunks?.length" class="empty-state">暂无 chunks</div>
          <div v-else class="chunk-list">
            <div v-for="(c, ci) in chunksData.chunks" :key="ci" class="chunk-detail-card">
              <div class="chunk-detail-head">
                <span class="chunk-detail-index">#{{ c.chunk_index ?? ci }}</span>
                <span v-if="c.section_id" class="chunk-detail-sec">section: {{ c.section_id }}</span>
                <span v-if="c.converter" class="chunk-detail-sec">转换器: {{ c.converter }}</span>
              </div>
              <div v-if="c.h1 || c.h2 || c.h3" class="chunk-detail-path">
                📂 {{ [c.h1, c.h2, c.h3].filter(Boolean).join(' > ') }}
              </div>
              <div class="chunk-detail-label">子 chunk 内容</div>
              <pre class="chunk-detail-pre">{{ c.content }}</pre>
              <details v-if="c.parent_content" class="chunk-detail-parent">
                <summary>📄 父文档（{{ c.parent_content.length }} 字符）</summary>
                <pre class="chunk-detail-pre">{{ c.parent_content }}</pre>
              </details>
              <div v-else class="chunk-detail-noparent">⚠️ 无父文档元数据（旧数据/手动录入）</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onUnmounted } from 'vue'
import axios from 'axios'
import { getAuthHeader } from '../../composables/useAuth'
import { formatTime, formatSize } from '../../composables/useFormat'

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

function progressPercent(task) {
  if (!task.chunkCount) return 0
  return Math.min(100, Math.round((task.processedChunks / task.chunkCount) * 100))
}

async function uploadFile(file) {
  const tid = ++taskIdCounter
  const task = reactive({
    id: tid, importId: null, fileName: file.name,
    status: 'pending', step: 0, error: '', replacedImportId: null,
    chunkCount: 0, processedChunks: 0, pollTimer: null
  })
  uploadTasks.push(task)

  try {
    task.step = 1
    const formData = new FormData()
    formData.append('file', file)
    const res = await axios.post('/api/admin/knowledge/upload', formData, {
      headers: { ...getAuthHeader() }
    })
    if (res.data?.code === 200) {
      // 上传已入队，立即拿到 import_id，开始轮询后台处理状态
      task.importId = res.data.data.import_id
      task.replacedImportId = res.data.data.replaced_import_id || null
      startPolling(task)
    } else {
      throw new Error(res.data?.message || '上传失败')
    }
  } catch (err) {
    task.status = 'failed'
    task.error = err.response?.data?.detail || err.message || '上传失败'
  }
}

const POLL_INTERVAL_MS = 1500

function startPolling(task) {
  task.step = 2
  task.status = 'processing'
  task.pollTimer = setInterval(async () => {
    try {
      const res = await axios.get(`/api/admin/knowledge/${task.importId}/status`, {
        headers: getAuthHeader()
      })
      if (res.data?.code !== 200) throw new Error(res.data?.message || '状态查询失败')
      const st = res.data.data
      task.status = st.status
      task.chunkCount = st.chunk_count || 0
      task.processedChunks = st.processed_chunks || 0
      if (st.error_message) task.error = st.error_message

      if (st.status === 'processing') {
        task.step = st.processed_chunks > 0 ? 3 : 2   // 已有向量化进度 → 向量化阶段
      } else if (st.status === 'success') {
        task.step = 4
        task.chunkCount = st.chunk_count || 0
        stopPolling(task)
      } else if (st.status === 'failed') {
        stopPolling(task)
      }
    } catch (err) {
      console.error('轮询任务状态失败:', err)
      // 网络抖动不中断，连续失败由任务自身超时兜底（此处保留轮询）
    }
  }, POLL_INTERVAL_MS)
}

function stopPolling(task) {
  if (task.pollTimer) {
    clearInterval(task.pollTimer)
    task.pollTimer = null
  }
}

// 组件卸载时清理所有轮询定时器
onUnmounted(() => {
  uploadTasks.forEach(t => stopPolling(t))
})

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
      headers: getAuthHeader(),
      params: { page: page.value, size: 100, keyword: searchKeyword.value || undefined }
    })
    if (res.data?.code === 200) {
      listItems.value = res.data.data.items || []
    }
  } catch (err) {
    console.error('获取知识列表失败:', err)
  }
}

async function reprocessItem(item) {
  try {
    const res = await axios.post(`/api/admin/knowledge/${item.id}/reprocess`, {}, {
      headers: getAuthHeader()
    })
    if (res.data?.code === 200) {
      // 重处理已入队（异步），立即刷新列表展示 pending/processing 状态
      item.status = 'pending'
      item.chunk_count = 0
      await fetchList()
    }
  } catch (err) {
    console.error('重处理失败:', err)
  }
}

// ---- Tab 2: Chunks 可视化弹窗 ----
const showChunksModal = ref(false)
const chunksLoading = ref(false)
const chunksData = ref(null)          // { file_name, total_chunks, chunks: [...] }

async function viewChunks(item) {
  try {
    chunksLoading.value = true
    const res = await axios.get(`/api/admin/knowledge/${item.id}/chunks`, {
      headers: getAuthHeader()
    })
    if (res.data?.code === 200) {
      chunksData.value = res.data.data
      showChunksModal.value = true
    }
  } catch (err) {
    console.error('获取 chunks 失败:', err)
    alert('获取 chunks 失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    chunksLoading.value = false
  }
}

function closeChunksModal() {
  showChunksModal.value = false
  chunksData.value = null
}

async function deleteItem(item) {
  if (!confirm(`确定要删除文档《${item.file_name}》吗？\n将同时删除其全部 ${item.chunk_count} 个向量 chunks，且不可恢复。`)) return
  try {
    const res = await axios.delete(`/api/admin/knowledge/${item.id}`, {
      headers: getAuthHeader()
    })
    if (res.data?.code === 200) {
      await fetchList()
    }
  } catch (err) {
    console.error('删除文档失败:', err)
    alert('删除失败: ' + (err.response?.data?.detail || err.message))
  }
}

// ---- Tab 3: Debug ----
const debugQuery = ref('')
const tracing = ref(false)
const traceData = ref(null)

function stepIcon(name) {
  if (name.includes('重写') || name.includes('Rewriting')) return '✏️'
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
      { headers: getAuthHeader() }
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

/* 异步处理进度条 */
.task-progress { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
.progress-track {
  flex: 1; height: 6px; border-radius: 3px;
  background: var(--border-color); overflow: hidden;
}
.progress-fill {
  height: 100%; border-radius: 3px;
  background: var(--primary); transition: width 0.4s ease;
}
.progress-text { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }

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
.rewrite-orig { color: var(--text-secondary); }
.rewrite-new { color: #8e44ad; font-weight: 500; }

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

.sbs-parents { display: flex; flex-direction: column; gap: 10px; margin-top: 12px; }
.sbs-parent {
  border: 1px solid var(--border-color); border-radius: var(--radius-sm); overflow: hidden;
}
.sbs-parent.is-concat { border-left: 3px solid #8e44ad; }
.sbs-parent-head {
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
  padding: 6px 12px; background: var(--panel-bg); font-size: 12px; color: var(--text-secondary);
}
.sbs-source { font-weight: 600; }
.sbs-parent.is-concat .sbs-source { color: #8e44ad; }
.sbs-parent pre {
  white-space: pre-wrap; word-break: break-word;
  font-size: 12px; line-height: 1.6;
  background: var(--panel-bg); padding: 10px; border-radius: 4px;
  max-height: 200px; overflow-y: auto; margin: 0;
}
.concat-badge { color: #8e44ad; font-weight: 500; }

/* ---- 删除按钮 / 覆盖提示 ---- */
.btn-danger { color: #e74c3c; }
.btn-danger:hover { background: #fadbd8; }
.task-replaced {
  margin-top: 8px; font-size: 12px; color: #2980b9;
  background: #ebf5fb; padding: 6px 10px; border-radius: 4px;
}

/* ---- Chunks 可视化弹窗 ---- */
.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0, 0, 0, 0.45);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.chunks-modal {
  width: min(880px, 100%);
  max-height: 85vh;
  display: flex; flex-direction: column;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-color);
  background: var(--panel-bg);
}
.modal-title { font-weight: 600; font-size: 14px; }
.modal-sub { font-weight: 400; font-size: 12px; color: var(--text-secondary); margin-left: 8px; }
.modal-close {
  border: none; background: none; font-size: 16px;
  color: var(--text-secondary); cursor: pointer; padding: 4px 8px;
}
.modal-close:hover { color: var(--text-primary); }
.modal-body { flex: 1; overflow-y: auto; padding: 16px 18px; }
.chunk-list { display: flex; flex-direction: column; gap: 12px; }
.chunk-detail-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  background: var(--panel-bg);
}
.chunk-detail-head { display: flex; gap: 12px; align-items: center; font-size: 12px; color: var(--text-secondary); flex-wrap: wrap; }
.chunk-detail-index { font-weight: 700; color: var(--primary); font-size: 13px; }
.chunk-detail-sec { background: var(--bg-color); padding: 1px 6px; border-radius: 4px; }
.chunk-detail-path { margin-top: 6px; font-size: 12px; color: var(--primary-hover); }
.chunk-detail-label { margin-top: 10px; font-size: 12px; color: var(--text-secondary); font-weight: 500; }
.chunk-detail-pre {
  white-space: pre-wrap; word-break: break-word;
  font-size: 12px; line-height: 1.6;
  background: var(--bg-color); padding: 10px; border-radius: 4px;
  max-height: 220px; overflow-y: auto; margin: 4px 0 0;
}
.chunk-detail-parent { margin-top: 8px; }
.chunk-detail-parent summary { cursor: pointer; font-size: 12px; color: var(--primary); padding: 4px 0; }
.chunk-detail-noparent { margin-top: 8px; font-size: 12px; color: #8e44ad; }
</style>
