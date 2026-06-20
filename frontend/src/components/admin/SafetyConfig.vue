<template>
  <div class="safety-container">
    <!-- 子选项卡菜单 -->
    <div class="sub-tabs card-panel">
      <button 
        :class="['sub-tab-btn', { active: activeSubTab === 'keywords' }]"
        @click="activeSubTab = 'keywords'"
      >
        ⛔ 安全词库设置
      </button>
      <button 
        :class="['sub-tab-btn', { active: activeSubTab === 'rag_seeds' }]"
        @click="activeSubTab = 'rag_seeds'"
      >
        🧠 预警 RAG 向量导入
      </button>
      <button 
        :class="['sub-tab-btn', { active: activeSubTab === 'knowledge' }]"
        @click="activeSubTab = 'knowledge'"
      >
        📚 知识检索文档导入
      </button>
    </div>

    <!-- 子 Tab 1: 安全词设置 (危险词和违规词) -->
    <div v-if="activeSubTab === 'keywords'" class="sub-content">
      <div class="split-layout">
        <!-- 左侧：添加表单 -->
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

        <!-- 右侧：词库列表 -->
        <div class="list-card card-panel">
          <div class="list-header">
            <h3>📜 活跃安全词过滤库</h3>
            <span class="sync-status">⚡ 自动同步热更新</span>
          </div>
          
          <!-- 分类列表视图 -->
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

    <!-- 子 Tab 2: 预警 RAG 向量导入 (维持 Mock 演示) -->
    <div v-if="activeSubTab === 'rag_seeds'" class="sub-content card-panel">
      <div class="rag-intro">
        <h3>🧠 模糊语义安全预警 (RAG 种子库导入)</h3>
        <p>有些高危或违规言论非常隐蔽（例如：“买好了敌敌畏”、“要在身上划几道”），传统的硬词匹配容易漏报。通过将“预警语义样本”导入 ChromaDB，系统可以在发问时做模糊语义距离比对，距离过近将自动拦截并写入最近活动日志。</p>
      </div>

      <div class="split-layout">
        <!-- 左侧：添加样本 -->
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

        <!-- 右侧：当前样本列表 -->
        <div class="list-card card-panel flat">
          <h4>🗂️ 已生效的预警向量样本数: {{ ragSeeds.length }} 条</h4>
          <div class="seeds-list-scroll">
            <div v-for="seed in ragSeeds" :key="seed.id" class="seed-item">
              <span :class="['seed-type', seed.type === 'high_risk' ? 'red' : 'orange']">
                {{ seed.type === 'high_risk' ? '高危' : '违规' }}
              </span>
              <span class="seed-text">“{{ seed.text }}”</span>
              <span class="seed-vector-tag">1024D Vector</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 子 Tab 3: 心理知识检索文档导入 (维持 Mock 演示) -->
    <div v-if="activeSubTab === 'knowledge'" class="sub-content card-panel">
      <div class="knowledge-intro">
        <h3>📚 心理健康 RAG 专业知识检索导入</h3>
        <p>为了让 AI 心理委员豚豚回答得更专业、更有科学依据，您在此处导入的文档将自动解析分块（Chunking）并生成 1024 维 Embedding，写入 ChromaDB 的 <code>psychology_kb</code> 中，原始记录存入 MySQL 导入任务表以防数据丢失。</p>
      </div>

      <!-- 导入方式切换 -->
      <div class="import-mode-selector">
        <button 
          :class="['mode-btn', { active: importMode === 'file' }]"
          @click="importMode = 'file'"
        >
          📁 拖拽上传文件 (PDF/TXT/Word/Markdown)
        </button>
        <button 
          :class="['mode-btn', { active: importMode === 'manual' }]"
          @click="importMode = 'manual'"
        >
          ✍️ 教师手动表单录入
        </button>
      </div>

      <!-- 文件导入方式 -->
      <div v-if="importMode === 'file'" class="file-import-box">
        <div 
          class="drag-drop-area" 
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="handleFileDrop"
          @click="triggerFileSelect"
        >
          <div class="drag-info">
            <span class="upload-icon">📄</span>
            <p v-if="!selectedFile">将 PDF、TXT、Word、Markdown 文档拖到这里，或点击选择文件</p>
            <p v-else class="selected-file-name">已选择: <strong>{{ selectedFile.name }}</strong> ({{ (selectedFile.size / 1024).toFixed(1) }} KB)</p>
            <span class="format-tip">仅支持 .pdf, .txt, .docx, .md 格式，大小不超过 10MB</span>
          </div>
          <input 
            type="file" 
            ref="fileInputRef" 
            class="hidden-file-input" 
            accept=".pdf,.txt,.docx,.md"
            @change="handleFileSelect"
          />
        </div>

        <!-- 模拟上传及向量化进度条 -->
        <div v-if="uploadStatus.show" class="upload-progress-card card-panel flat">
          <div class="progress-details">
            <span>{{ uploadStatus.text }}</span>
            <span>{{ uploadStatus.percent }}%</span>
          </div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" :style="{ width: uploadStatus.percent + '%' }"></div>
          </div>
        </div>

        <div class="import-actions">
          <button class="btn-primary" :disabled="!selectedFile || uploadStatus.show" @click="startFileUpload">
            💾 开始上传并进行 ChromaDB 向量同步
          </button>
        </div>
      </div>

      <!-- 手动表单录入方式 -->
      <div v-if="importMode === 'manual'" class="manual-import-box">
        <form @submit.prevent="addManualKnowledge" class="admin-form">
          <div class="form-group">
            <label class="form-label">知识概念主题名称</label>
            <input 
              type="text" 
              class="input-field" 
              placeholder="例如: 蝴蝶抱抱法、深呼吸放松" 
              v-model="manualKnowledge.title"
              required
            />
          </div>
          <div class="form-group">
            <label class="form-label">概念白话轻量解释 (Concept)</label>
            <textarea 
              class="input-field textarea-field" 
              placeholder="用学生容易听懂的白话，科普该心理学概念" 
              v-model="manualKnowledge.concept"
              required
            ></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">操作稳定化调节技巧小贴士 (Tip)</label>
            <textarea 
              class="input-field textarea-field" 
              placeholder="提供具体可行、能够在电脑前操练并缓解焦虑的方法" 
              v-model="manualKnowledge.tip"
              required
            ></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">分类标签 (Tags)</label>
            <input 
              type="text" 
              class="input-field" 
              placeholder="以逗号分隔，例如: 焦虑,惊恐,考前压力" 
              v-model="manualKnowledge.tags"
            />
          </div>
          <button type="submit" class="btn-accent">确认写入并将正文同步至向量库</button>
        </form>
      </div>

      <!-- 知识库管理与调试工具区 (双栏布局) -->
      <div class="split-layout" style="margin-top: 30px; border-top: 1px solid var(--border-color); padding-top: 30px;">
        <!-- 左侧：已导入知识库文档列表 -->
        <div class="list-card card-panel flat">
          <div class="list-header" style="border-bottom: none; padding-bottom: 0; margin-bottom: 15px;">
            <h4>📚 已导入知识库文档与记录</h4>
            <div class="search-box">
              <input 
                type="text" 
                class="input-field search-input" 
                placeholder="🔍 输入名称检索..." 
                v-model="searchKeyword"
                @input="fetchKnowledgeImports"
                style="padding: 6px 12px; font-size: 12px; width: 150px;"
              />
            </div>
          </div>
          
          <div class="table-wrapper">
            <table class="admin-table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>存储桶/大小</th>
                  <th>切片数</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in knowledgeImports.items" :key="item.id">
                  <td>
                    <span class="file-name-cell" :title="item.file_name">{{ item.file_name }}</span>
                  </td>
                  <td style="font-size: 11px; color: var(--text-secondary);">
                    <div>{{ item.minio_bucket }}</div>
                    <div>{{ (item.file_size / 1024).toFixed(1) }} KB</div>
                  </td>
                  <td><span class="chunk-badge">{{ item.chunk_count }} Chunks</span></td>
                  <td>
                    <span :class="['status-badge', item.status]">
                      {{ item.status === 'success' ? '🟢 成功' : item.status === 'failed' ? '🔴 失败' : '🟡 处理中' }}
                    </span>
                  </td>
                </tr>
                <tr v-if="knowledgeImports.items.length === 0">
                  <td colspan="4" class="empty-table-cell" style="text-align: center; padding: 20px 0; color: var(--text-secondary); font-style: italic;">
                    暂无知识导入记录
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 分页器 -->
          <div class="pagination-bar" v-if="knowledgeImports.total > 5">
            <button :disabled="currentPage === 1" @click="changePage(currentPage - 1)" class="page-btn">◀</button>
            <span style="font-size: 12px; color: var(--text-secondary);">{{ currentPage }} / {{ Math.ceil(knowledgeImports.total / 5) }}</span>
            <button :disabled="currentPage * 5 >= knowledgeImports.total" @click="changePage(currentPage + 1)" class="page-btn">▶</button>
          </div>
        </div>

        <!-- 右侧：语义检索测试调试器 -->
        <div class="list-card card-panel flat">
          <div class="list-header" style="border-bottom: none; padding-bottom: 0; margin-bottom: 15px;">
            <h4>🔍 知识库语义检索调试 (测试 ChromaDB 召回)</h4>
          </div>
          <p class="section-desc" style="margin-bottom: 10px;">输入任意心理咨询相关的问题，测试 ChromaDB 的向量距离检索，查看被召回的相关 Chunks 文档段落及相似度得分。</p>
          
          <div class="search-test-form">
            <div style="display: flex; gap: 10px; margin-bottom: 15px;">
              <input 
                type="text" 
                class="input-field" 
                placeholder="例如: 怎么进行蝴蝶抱抱法？" 
                v-model="testQuery"
                @keyup.enter="runSemanticSearch"
              />
              <button class="btn-primary" @click="runSemanticSearch" :disabled="isSearching" style="white-space: nowrap;">
                {{ isSearching ? '检索中...' : '测试检索' }}
              </button>
            </div>

            <!-- 召回结果列表 -->
            <div class="search-results-scroll" v-if="searchResults.length > 0">
              <div v-for="(result, idx) in searchResults" :key="result.chunk_id" class="result-chunk-item">
                <div class="result-chunk-header">
                  <span class="rank-badge">Top {{ idx + 1 }}</span>
                  <span class="source-tag" :title="result.file_name">📄 {{ result.file_name }}</span>
                  <span class="score-badge">相似度: {{ (result.score * 100).toFixed(1) }}%</span>
                </div>
                <div class="result-chunk-body">
                  {{ result.content }}
                </div>
              </div>
            </div>
            
            <div v-else-if="hasSearched" class="empty-results-box">
              ⚠️ 未检索到相关 Chunks 匹配，请尝试输入其他关键词或先录入科普内容。
            </div>
            
            <div v-else class="search-placeholder-box">
              💡 在上方输入问题并点击测试，将实时调用 SiliconFlow Embedding 模型进行向量匹配召回。
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import axios from 'axios'

const props = defineProps({
  keywords: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['add-keyword', 'toggle-keyword-status', 'increment-mock-stats', 'show-toast'])

const activeSubTab = ref('keywords')
const importMode = ref('file')
const isDragging = ref(false)
const selectedFile = ref(null)
const fileInputRef = ref(null)
const uploadStatus = reactive({ show: false, text: '', percent: 0 })

const newWordForm = reactive({ word: '', type: 'high_risk' })
const newSeedForm = reactive({ text: '', type: 'high_risk' })
const manualKnowledge = reactive({ title: '', concept: '', tip: '', tags: '' })

// 预警 RAG 向量样本库
const ragSeeds = ref([])

// 知识库记录列表与语义匹配调试状态变量
const searchKeyword = ref('')
const currentPage = ref(1)
const knowledgeImports = reactive({ total: 0, items: [] })
const testQuery = ref('')
const searchResults = ref([])
const isSearching = ref(false)
const hasSearched = ref(false)

// 获取 API Authorization Header
function getAuthHeader() {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// 从后端拉取真实的安全预警 RAG 种子列表
async function fetchRagSeeds() {
  try {
    const res = await axios.get('/api/admin/safety-seeds', { headers: getAuthHeader() })
    if (res.data && res.data.code === 200) {
      ragSeeds.value = res.data.data
    } else {
      emit('show-toast', res.data?.message || '获取预警向量样本失败', 'error')
    }
  } catch (err) {
    console.error(err)
    const errorMsg = err.response?.data?.detail || err.message || '网络或服务器异常'
    emit('show-toast', `获取预警向量样本失败: ${errorMsg}`, 'error')
  }
}

// 获取已导入的文档/手动录入任务记录列表
async function fetchKnowledgeImports() {
  try {
    const res = await axios.get('/api/admin/knowledge', {
      params: {
        page: currentPage.value,
        size: 5, // 每页 5 条
        keyword: searchKeyword.value.trim() || undefined
      },
      headers: getAuthHeader()
    })
    if (res.data && res.data.code === 200) {
      knowledgeImports.total = res.data.data.total
      knowledgeImports.items = res.data.data.items
    }
  } catch (err) {
    console.error('拉取知识库导入历史失败:', err)
  }
}

function changePage(page) {
  currentPage.value = page
  fetchKnowledgeImports()
}

// 执行真实语义向量检索测试调试
async function runSemanticSearch() {
  const queryVal = testQuery.value.trim()
  if (!queryVal) return
  isSearching.value = true
  hasSearched.value = true
  try {
    const res = await axios.get('/api/admin/knowledge/search', {
      params: { query: queryVal, limit: 3 },
      headers: getAuthHeader()
    })
    if (res.data && res.data.code === 200) {
      searchResults.value = res.data.data
    } else {
      searchResults.value = []
      emit('show-toast', res.data?.message || '语义检索测试失败', 'error')
    }
  } catch (err) {
    console.error(err)
    searchResults.value = []
    const errorMsg = err.response?.data?.detail || err.message || '网络或服务器异常'
    emit('show-toast', `语义检索失败: ${errorMsg}`, 'error')
  } finally {
    isSearching.value = false
  }
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    const year = d.getFullYear()
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const hour = String(d.getHours()).padStart(2, '0')
    const minute = String(d.getMinutes()).padStart(2, '0')
    return `${year}-${month}-${day} ${hour}:${minute}`
  } catch (e) {
    return dateStr
  }
}

// 监听子选项卡状态，当切换页签时自动拉取最新的真实样本列表
watch(activeSubTab, (newTab) => {
  if (newTab === 'rag_seeds') {
    fetchRagSeeds()
  } else if (newTab === 'knowledge') {
    currentPage.value = 1
    fetchKnowledgeImports()
  }
})

function submitWord() {
  if (!newWordForm.word.trim()) return
  emit('add-keyword', {
    word: newWordForm.word.trim(),
    type: newWordForm.type
  })
  newWordForm.word = ''
}

// 添加预警 RAG 向量种子并自动同步至后端 ChromaDB
async function addRagSeed() {
  const textVal = newSeedForm.text.trim()
  if (!textVal) return
  
  try {
    const res = await axios.post('/api/admin/safety-seeds', {
      text: textVal,
      type: newSeedForm.type
    }, { headers: getAuthHeader() })

    if (res.data && res.data.code === 200) {
      emit('show-toast', 'ChromaDB 已成功完成 1024 维向量提取，并同步至 safety_warnings_kb 样本库！', 'success')
      newSeedForm.text = ''
      // 重新拉取最新的种子列表
      await fetchRagSeeds()
      // 触发父容器自增指标，以维持指标联动视觉效果
      emit('increment-mock-stats', newSeedForm.type)
    } else {
      emit('show-toast', res.data?.message || '导入 ChromaDB 失败', 'error')
    }
  } catch (err) {
    console.error(err)
    const errorMsg = err.response?.data?.detail || err.message || '网络或服务器异常'
    emit('show-toast', `导入向量样本失败: ${errorMsg}`, 'error')
  }
}

// 手动录入科普卡片
async function addManualKnowledge() {
  const titleVal = manualKnowledge.title.trim()
  const conceptVal = manualKnowledge.concept.trim()
  const tipVal = manualKnowledge.tip.trim()
  
  if (!titleVal || !conceptVal || !tipVal) return

  try {
    const res = await axios.post('/api/admin/knowledge/manual', {
      title: titleVal,
      concept: conceptVal,
      tip: tipVal,
      tags: manualKnowledge.tags.trim()
    }, { headers: getAuthHeader() })

    if (res.data && res.data.code === 200) {
      emit('show-toast', `“${titleVal}”科普卡片已成功导入 MySQL 并完成 ChromaDB 同步！`, 'success')
      // 重置表单
      manualKnowledge.title = ''
      manualKnowledge.concept = ''
      manualKnowledge.tip = ''
      manualKnowledge.tags = ''
      // 刷新列表
      fetchKnowledgeImports()
    } else {
      emit('show-toast', res.data?.message || '手动导入科普卡片失败', 'error')
    }
  } catch (err) {
    console.error(err)
    const errorMsg = err.response?.data?.detail || err.message || '网络或服务器异常'
    emit('show-toast', `导入科普卡片失败: ${errorMsg}`, 'error')
  }
}

function triggerFileSelect() {
  if (uploadStatus.show) return
  fileInputRef.value.click()
}

function handleFileSelect(e) {
  const files = e.target.files
  if (files && files.length > 0) {
    selectedFile.value = files[0]
  }
}

function handleFileDrop(e) {
  isDragging.value = false
  const files = e.dataTransfer.files
  if (files && files.length > 0) {
    const file = files[0]
    const ext = file.name.split('.').pop().toLowerCase()
    if (['pdf', 'txt', 'docx', 'md'].includes(ext)) {
      selectedFile.value = file
    } else {
      emit('show-toast', '仅支持 .pdf, .txt, .docx, .md 格式的文档哦~', 'warning')
    }
  }
}

// 文件异步上传与向量化同步
async function startFileUpload() {
  if (!selectedFile.value) return
  
  uploadStatus.show = true
  uploadStatus.percent = 0
  uploadStatus.text = '📂 正在物理上传文件至后端服务器...'

  const formData = new FormData()
  formData.append('file', selectedFile.value)

  try {
    const res = await axios.post('/api/admin/knowledge/upload', formData, {
      headers: {
        ...getAuthHeader(),
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          // 物理上传占比 80%
          uploadStatus.percent = Math.min(Math.round(percentCompleted * 0.8), 80)
          uploadStatus.text = `📂 正在物理上传文件至后端服务器... ${uploadStatus.percent}%`
        }
      }
    })

    if (res.data && res.data.code === 200) {
      // 物理上传成功后，更新提示状态进入分块与向量化流程
      uploadStatus.percent = 90
      uploadStatus.text = '⚙️ 上传成功，服务器正在解析并进行文本切片 (Chunking)...'
      
      setTimeout(() => {
        uploadStatus.percent = 95
        uploadStatus.text = '🧠 正在计算 Chunks 语义 Embedding 向量并同步刷入 ChromaDB (psychology_kb)...'
        
        setTimeout(() => {
          uploadStatus.percent = 100
          uploadStatus.text = '💾 向量数据库刷入成功！'
          
          setTimeout(() => {
            emit('show-toast', `文档 《${selectedFile.value.name}》 导入及 ChromaDB 向量同步成功！`, 'success')
            uploadStatus.show = false
            selectedFile.value = null
            // 刷新列表
            fetchKnowledgeImports()
          }, 500)
        }, 600)
      }, 600)
    } else {
      uploadStatus.show = false
      emit('show-toast', res.data?.message || '文档导入失败', 'error')
    }
  } catch (err) {
    console.error(err)
    uploadStatus.show = false
    const errorMsg = err.response?.data?.detail || err.message || '网络或服务器异常'
    emit('show-toast', `导入文档失败: ${errorMsg}`, 'error')
  }
}
</script>

<style scoped>
.safety-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
/* 子 Tab 配置菜单 */
.sub-tabs {
  display: flex;
  padding: 5px;
  background-color: var(--panel-bg);
  border-radius: var(--radius-md);
  margin-bottom: 0px;
}
.sub-tab-btn {
  flex: 1;
  background: transparent;
  border: none;
  padding: 12px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-normal);
}
.sub-tab-btn:hover {
  background-color: var(--primary-light);
  color: var(--primary-hover);
}
.sub-tab-btn.active {
  background-color: var(--primary-light);
  color: var(--primary-hover);
  box-shadow: 0 2px 8px var(--shadow-color);
  font-weight: 600;
}

/* 拆分布局 */
.split-layout {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 20px;
}
.form-card, .list-card {
  padding: 25px;
  background-color: var(--panel-bg);
  border-radius: var(--radius-md);
}
.form-card h3, .list-card h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 8px 0;
  color: var(--text-primary);
}
.section-desc {
  font-size: 11.5px;
  color: var(--text-secondary);
  margin-bottom: 20px;
}
.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 12px;
  margin-bottom: 20px;
}
.sync-status {
  font-size: 10px;
  color: var(--primary);
  background-color: var(--primary-light);
  padding: 2px 6px;
  border-radius: 4px;
}
.category-block {
  margin-bottom: 25px;
}
.category-block h4 {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 12px 0;
  font-weight: 500;
}
.keyword-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.keyword-tag {
  font-size: 12.5px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.keyword-tag.danger {
  background-color: var(--warning-light);
  color: var(--warning);
  border: 1px solid var(--warning);
}
.keyword-tag.warning {
  background-color: rgba(243, 156, 18, 0.1);
  color: #D35400;
  border: 1px solid rgba(243, 156, 18, 0.3);
}
.keyword-tag.disabled {
  opacity: 0.4;
  text-decoration: line-through;
}
.toggle-word-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 12px;
  padding: 0;
  display: inline-flex;
}

/* 种子列表 */
.seeds-list-scroll {
  max-height: 320px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.seed-item {
  display: flex;
  align-items: center;
  padding: 12px;
  background-color: var(--bg-color);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  font-size: 13px;
}
.seed-type {
  font-size: 10.5px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  margin-right: 12px;
  display: inline-block;
}
.seed-type.red { background-color: var(--warning-light); color: var(--warning); }
.seed-type.orange { background-color: rgba(243, 156, 18, 0.15); color: #D35400; }
.seed-text {
  flex: 1;
  font-weight: 500;
  color: var(--text-primary);
}
.seed-vector-tag {
  font-size: 10.5px;
  color: var(--text-secondary);
  font-family: monospace;
}

/* RAG/知识库导入介绍 */
.knowledge-intro, .rag-intro {
  margin-bottom: 25px;
  border-left: 4px solid var(--primary);
  padding-left: 15px;
}
.knowledge-intro h3, .rag-intro h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 6px 0;
}
.knowledge-intro p, .rag-intro p {
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}
.import-mode-selector {
  display: flex;
  gap: 15px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 15px;
  margin-bottom: 25px;
}
.mode-btn {
  background-color: var(--panel-bg);
  border: 1px solid var(--border-color);
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-secondary);
  transition: var(--transition-normal);
}
.mode-btn.active {
  background-color: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary-hover);
  font-weight: 600;
}
.drag-drop-area {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-md);
  padding: 50px 20px;
  text-align: center;
  cursor: pointer;
  background-color: var(--bg-color);
  transition: var(--transition-normal);
}
.drag-drop-area:hover {
  border-color: var(--primary);
  background-color: var(--primary-light);
}
.upload-icon {
  font-size: 40px;
  display: block;
  margin-bottom: 12px;
}
.drag-info p {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
}
.format-tip {
  font-size: 11px;
  color: var(--text-secondary);
  display: block;
  margin-top: 10px;
}
.hidden-file-input {
  display: none;
}
.import-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
.textarea-field {
  min-height: 100px;
  resize: vertical;
}

/* 进度条样式 */
.upload-progress-card {
  margin-top: 20px;
  padding: 15px 20px;
  background-color: var(--primary-light);
  border-radius: var(--radius-md);
}
.progress-details {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 8px;
  color: var(--text-primary);
}
.progress-bar-bg {
  height: 8px;
  background-color: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}
.progress-bar-fill {
  height: 100%;
  background-color: var(--primary);
  border-radius: 4px;
  transition: width 0.3s ease;
}

/* 表单通用 */
.admin-form {
  display: flex;
  flex-direction: column;
  gap: 15px;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.form-label {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text-primary);
}
.select-field {
  cursor: pointer;
}
.flat {
  box-shadow: none !important;
  border: 1px solid var(--border-color) !important;
}
.flat:hover {
  transform: none !important;
}
.empty-tag {
  font-size: 12px;
  color: var(--text-secondary);
  font-style: italic;
}

/* 已导入文档记录与检索调试相关样式 */
.search-box {
  display: flex;
  align-items: center;
}
.search-input {
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  background-color: var(--bg-color);
  color: var(--text-primary);
}
.table-wrapper {
  overflow-x: auto;
  margin-bottom: 15px;
}
.admin-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  text-align: left;
}
.admin-table th, .admin-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
}
.admin-table th {
  font-weight: 600;
  color: var(--text-secondary);
  background-color: var(--bg-color);
}
.file-name-cell {
  display: block;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
  color: var(--text-primary);
}
.chunk-badge {
  font-size: 11px;
  background-color: var(--primary-light);
  color: var(--primary-hover);
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.status-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.status-badge.success {
  background-color: var(--primary-light);
  color: var(--primary-hover);
}
.status-badge.processing {
  background-color: rgba(243, 156, 18, 0.15);
  color: #D35400;
}
.status-badge.failed {
  background-color: var(--warning-light);
  color: var(--warning);
}
.pagination-bar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
}
.page-btn {
  background-color: var(--bg-color);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  width: 26px;
  height: 26px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 12px;
  transition: var(--transition-normal);
}
.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.page-btn:not(:disabled):hover {
  border-color: var(--primary);
  color: var(--primary-hover);
  background-color: var(--primary-light);
}

/* 语义检索测试调试器样式 */
.search-test-form {
  display: flex;
  flex-direction: column;
}
.search-results-scroll {
  max-height: 280px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 5px;
}
.result-chunk-item {
  background-color: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.result-chunk-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 11px;
}
.rank-badge {
  background-color: var(--primary-hover);
  color: #fff;
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 600;
}
.source-tag {
  color: var(--text-secondary);
  font-weight: 500;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.score-badge {
  margin-left: auto;
  color: var(--primary-hover);
  font-weight: 600;
  font-family: monospace;
}
.result-chunk-body {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-primary);
  background-color: var(--panel-bg);
  padding: 8px 12px;
  border-radius: 4px;
  border-left: 3px solid var(--primary);
  white-space: pre-wrap;
}
.empty-results-box {
  padding: 30px 10px;
  text-align: center;
  font-size: 12.5px;
  color: var(--warning);
  border: 1px dashed var(--warning);
  border-radius: var(--radius-sm);
  background-color: var(--warning-light);
}
.search-placeholder-box {
  padding: 40px 10px;
  text-align: center;
  font-size: 12.5px;
  color: var(--text-secondary);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-sm);
  background-color: var(--bg-color);
  line-height: 1.5;
}
</style>
