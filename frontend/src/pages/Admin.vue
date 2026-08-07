<template>
  <div class="admin-container">
    <!-- 顶部导航栏 -->
    <AdminHeader 
      :adminName="adminName" 
      :isNightMode="isNightMode"
      @toggle-night-mode="toggleNightMode"
      @logout="handleLogout"
    />

    <div class="admin-layout">
      <!-- 侧边菜单栏 -->
      <AdminSidebar 
        :activeMenu="activeMenu" 
        :menus="menus"
        @update:activeMenu="activeMenu = $event"
      />

      <!-- 主工作区 -->
      <main class="admin-main">
        <!-- 1. 控制台概览 -->
        <DashboardOverview 
          v-if="activeMenu === 'overview'" 
          :stats="stats"
          :activityLogs="activityLogs"
          @view-audit-log="viewAuditLog"
        />

        <!-- 2. 学生用户管理 -->
        <StudentManagement 
          v-if="activeMenu === 'users'" 
          :users="users"
          @view-user-profile="viewUserProfile"
          @toggle-user-status="toggleUserStatus"
          @refresh="fetchUsers"
        />

        <!-- 3. 安全过滤管理 -->
        <SafetyConfig
          v-if="activeMenu === 'safety'"
          :keywords="keywords"
          @add-keyword="addKeyword"
          @toggle-keyword-status="toggleWordStatus"
          @increment-mock-stats="incrementMockStats"
          @show-toast="showToast"
        />

        <!-- 4. 知识库管理 -->
        <KnowledgeManager
          v-if="activeMenu === 'knowledge'"
          :getAuthHeader="getAuthHeader"
        />
      </main>
    </div>

    <!-- 审计画像查阅弹窗 -->
    <ProfileModal 
      v-if="selectedUserForProfile"
      :selectedUser="selectedUserForProfile"
      :profile="selectedUserProfile"
      @close="selectedUserForProfile = null"
    />

    <!-- 全局美化提示气泡 -->
    <transition name="toast-fade">
      <div v-if="toast.show" :class="['toast-bubble', toast.type]">
        <span class="toast-icon">
          {{ toast.type === 'success' ? '🟢' : toast.type === 'error' ? '🔴' : toast.type === 'warning' ? '🟡' : '🔵' }}
        </span>
        <span class="toast-message">{{ toast.message }}</span>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

// 导入重构出的模块化展示型子组件
import AdminHeader from '../components/admin/AdminHeader.vue'
import AdminSidebar from '../components/admin/AdminSidebar.vue'
import DashboardOverview from '../components/admin/DashboardOverview.vue'
import StudentManagement from '../components/admin/StudentManagement.vue'
import SafetyConfig from '../components/admin/SafetyConfig.vue'
import ProfileModal from '../components/admin/ProfileModal.vue'
import KnowledgeManager from '../components/admin/KnowledgeManager.vue'

const router = useRouter()
const adminName = ref('管理员')
const activeMenu = ref('overview')
const isNightMode = ref(false)

// 全局美化提示气泡状态
const toast = reactive({
  show: false,
  message: '',
  type: 'success'
})

let toastTimeout = null

function showToast(message, type = 'success') {
  if (toastTimeout) clearTimeout(toastTimeout)
  toast.message = message
  toast.type = type
  toast.show = true
  toastTimeout = setTimeout(() => {
    toast.show = false
  }, 3000)
}

// 1. 看板统计指标
const stats = reactive({
  studentCount: 0,
  sessionCount: 0,
  highRiskCount: 0,
  violationCount: 0
})

// 2. 安全审计日志
const activityLogs = ref([])

// 3. 活跃敏感词过滤词列表
const keywords = reactive({
  highRisk: [],
  violation: []
})

// 4. 注册学生及其画像列表
const users = ref([])

// 选中的心理画像关联学生与画像实体
const selectedUserForProfile = ref(null)
const selectedUserProfile = ref({
  core_stressors: [],
  effective_coping_methods: [],
  entity_relation_map: {},
  semantic_history_recall: ''
})

// 侧边栏主菜单配置
const menus = [
  { id: 'overview', label: '控制台概览', icon: '📊' },
  { id: 'users', label: '学生心理档案', icon: '👥' },
  { id: 'safety', label: '安全过滤管理', icon: '🛡️' },
  { id: 'knowledge', label: '知识库管理', icon: '📚' }
]

// 原生 Base64 令牌负载解析
function getPayload(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch (e) {
    return null;
  }
}

// 获取 API Authorization Header
function getAuthHeader() {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// 切换日夜间模式
function toggleNightMode() {
  isNightMode.value = !isNightMode.value
  if (isNightMode.value) {
    document.body.classList.add('night-mode')
  } else {
    document.body.classList.remove('night-mode')
  }
}

// 退出登录
function handleLogout() {
  localStorage.removeItem('token')
  router.push('/login')
}

// 1. 获取 Dashboard 统计数据
async function fetchDashboardStats() {
  try {
    const res = await axios.get('/api/admin/dashboard/stats', { headers: getAuthHeader() })
    if (res.data && res.data.code === 200) {
      const data = res.data.data
      stats.studentCount = data.student_count
      stats.sessionCount = data.session_count
      stats.highRiskCount = data.high_risk_count
      stats.violationCount = data.violation_count
    }
  } catch (err) {
    console.error('获取统计数据失败:', err)
  }
}

// 时间格式化辅助函数
function formatTime(isoString) {
  if (!isoString) return ''
  try {
    const d = new Date(isoString)
    const pad = (n) => n.toString().padStart(2, '0')
    const year = d.getFullYear()
    const month = pad(d.getMonth() + 1)
    const date = pad(d.getDate())
    const hours = pad(d.getHours())
    const minutes = pad(d.getMinutes())
    const seconds = pad(d.getSeconds())
    return `${year}-${month}-${date} ${hours}:${minutes}:${seconds}`
  } catch (e) {
    return isoString
  }
}

// 2. 获取拦截活动日志
async function fetchActivityLogs() {
  try {
    const res = await axios.get('/api/admin/security/logs', { 
      headers: getAuthHeader(),
      params: { page: 1, size: 50 }
    })
    if (res.data && res.data.code === 200) {
      const items = res.data.data.items || []
      activityLogs.value = items.map(log => ({
        id: log.id,
        time: formatTime(log.created_at),
        sessionId: log.session_id,
        type: log.log_type,
        content: log.trigger_content,
        rule: log.matched_rule,
        userId: log.user_id
      }))
    }
  } catch (err) {
    console.error('获取活动日志失败:', err)
  }
}

// 3. 获取学生账户与心理画像列表
async function fetchUsers() {
  try {
    const res = await axios.get('/api/admin/students', {
      headers: getAuthHeader(),
      params: { page: 1, size: 100 }
    })
    if (res.data && res.data.code === 200) {
      const items = res.data.data.items || []
      users.value = items.map(user => ({
        id: user.id,
        username: user.username,
        role: user.role,
        is_active: user.is_active,
        profile_summary: user.nickname || '暂无画像特征'
      }))
    }
  } catch (err) {
    console.error('获取学生列表失败:', err)
  }
}

// 4. 查看指定学生的详细心理特征画像
async function viewUserProfile(user) {
  selectedUserForProfile.value = user
  selectedUserProfile.value = {
    core_stressors: [],
    effective_coping_methods: [],
    entity_relation_map: {},
    semantic_history_recall: '正在加载心理画像数据...'
  }
  try {
    const res = await axios.get(`/api/admin/students/${user.id}/profile`, { headers: getAuthHeader() })
    if (res.data && res.data.code === 200) {
      selectedUserProfile.value = res.data.data
    } else {
      selectedUserProfile.value = {
        core_stressors: [],
        effective_coping_methods: [],
        entity_relation_map: {},
        semantic_history_recall: '该学生暂无历史画像汇总。'
      }
    }
  } catch (err) {
    console.error('获取学生画像详情失败:', err)
    selectedUserProfile.value = {
      core_stressors: [],
      effective_coping_methods: [],
      entity_relation_map: {},
      semantic_history_recall: err.message || '获取画像失败。'
    }
  }
}

// 5. 切换用户账号启用/禁用状态
async function toggleUserStatus(user) {
  try {
    const nextStatus = !user.is_active
    const res = await axios.put(`/api/admin/students/${user.id}/status`, { is_active: nextStatus }, { headers: getAuthHeader() })
    if (res.data && res.data.code === 200) {
      user.is_active = nextStatus
    }
  } catch (err) {
    console.error('修改用户状态失败:', err)
    showToast(err.message || '操作失败', 'error')
  }
}

// 6. 查阅高危拦截日志关联的学生脱敏画像
async function viewAuditLog(log) {
  if (!log.userId) {
    showToast('该会话为无痕树洞匿名会话，为了保护隐私，已对用户信息及心理画像进行物理隔离，无法查看个人档案。', 'warning')
    return
  }
  const user = users.value.find(u => u.id === log.userId)
  if (user) {
    viewUserProfile(user)
  } else {
    viewUserProfile({ id: log.userId, username: '审计关联学生' })
  }
}

// 7. 获取安全词配置列表
async function fetchKeywords() {
  try {
    const res = await axios.get('/api/admin/safety-keywords', {
      headers: getAuthHeader(),
      params: { page: 1, size: 500 }
    })
    if (res.data && res.data.code === 200) {
      const items = res.data.data.items || []
      keywords.highRisk = items.filter(k => k.word_type === 'high_risk').map(k => ({
        id: k.id,
        word: k.word,
        enabled: k.is_enabled
      }))
      keywords.violation = items.filter(k => k.word_type === 'violation').map(k => ({
        id: k.id,
        word: k.word,
        enabled: k.is_enabled
      }))
    }
  } catch (err) {
    console.error('获取敏感词配置失败:', err)
  }
}

// 8. 新增敏感拦截词并热同步
async function addKeyword({ word, type }) {
  try {
    const res = await axios.post('/api/admin/safety-keywords', {
      word: word,
      word_type: type,
      is_enabled: true
    }, { headers: getAuthHeader() })
    
    if (res.data && (res.data.code === 200 || res.data.code === 201)) {
      await fetchKeywords() // 刷新列表
      showToast(`已成功添加敏感词 "${word}"！`, 'success')
    } else {
      showToast(res.data?.message || '添加失败', 'error')
    }
  } catch (err) {
    console.error('新增敏感词失败:', err)
    const errMsg = err.response?.data?.detail || err.response?.data?.message || err.message || '添加失败'
    showToast(`添加失败: ${errMsg}`, 'error')
  }
}

// 9. 安全词的启用停用
async function toggleWordStatus(w, category) {
  try {
    const nextStatus = !w.enabled
    const res = await axios.put(`/api/admin/safety-keywords/${w.id}`, {
      is_enabled: nextStatus
    }, { headers: getAuthHeader() })
    
    if (res.data && res.data.code === 200) {
      w.enabled = nextStatus
    }
  } catch (err) {
    console.error('更新敏感词启用状态失败:', err)
    showToast(err.message || '更新状态失败', 'error')
  }
}

// 10. 用于与 RAG 向量面板 Mock 状态同步的方法
function incrementMockStats(type) {
  if (type === 'high_risk') {
    stats.highRiskCount++
  } else {
    stats.violationCount++
  }
}

onMounted(() => {
  const token = localStorage.getItem('token')
  if (token) {
    const payload = getPayload(token)
    if (payload) {
      adminName.value = payload.sub
    }
  }
  isNightMode.value = document.body.classList.contains('night-mode')
  
  // 挂载时获取真实数据
  fetchDashboardStats()
  fetchActivityLogs()
  fetchUsers()
  fetchKeywords()
})
</script>

<style scoped>
.admin-container {
  min-height: 100vh;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background-color: var(--bg-color);
  transition: var(--transition-slow);
}
.admin-layout {
  display: flex;
  flex: 1;
  gap: 20px;
}
.admin-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 全局美化提示气泡样式 */
.toast-bubble {
  position: fixed;
  top: 30px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
  border-radius: var(--radius-md);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
  background-color: var(--panel-bg);
  border: 1px solid var(--border-color);
  z-index: 9999;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text-primary);
  backdrop-filter: blur(10px);
}

.toast-bubble.success {
  border-color: var(--primary);
  background-color: var(--primary-light);
  color: var(--primary-hover);
}

.toast-bubble.error {
  border-color: var(--warning);
  background-color: var(--warning-light);
  color: var(--warning);
}

.toast-bubble.warning {
  border-color: #f39c12;
  background-color: rgba(243, 156, 18, 0.1);
  color: #D35400;
}

.toast-icon {
  font-size: 16px;
  display: inline-flex;
  align-items: center;
}

/* 渐变动画 */
.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.toast-fade-enter-from {
  opacity: 0;
  transform: translate(-50%, -20px);
}

.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -10px);
}
</style>
