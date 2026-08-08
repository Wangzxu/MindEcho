<template>
  <div class="admin-container">
    <AdminHeader
      :adminName="adminName"
      @logout="handleLogout"
    />

    <div class="admin-layout">
      <AdminSidebar
        :activeMenu="activeMenu"
        :menus="menus"
        @update:activeMenu="activeMenu = $event"
      />

      <main class="admin-main">
        <DashboardOverview
          v-if="activeMenu === 'overview'"
          @view-audit-log="viewAuditLog"
        />

        <StudentManagement
          v-if="activeMenu === 'users'"
          @view-user-profile="viewUserProfile"
        />

        <SafetyConfig
          v-if="activeMenu === 'safety'"
          :keywords="keywords"
          @add-keyword="addKeyword"
          @toggle-keyword-status="toggleWordStatus"
          @increment-mock-stats="incrementMockStats"
          @show-toast="showToast"
        />

        <KnowledgeManager
          v-if="activeMenu === 'knowledge'"
        />
      </main>
    </div>

    <ProfileModal
      v-if="selectedUserForProfile"
      :selectedUser="selectedUserForProfile"
      :profile="selectedUserProfile"
      @close="selectedUserForProfile = null"
    />

    <ToastBubble
      :message="toast.message"
      :type="toast.type"
      :visible="toast.show"
      @close="toast.show = false"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { getPayload, getAuthHeader } from '../composables/useAuth'
import { useTheme } from '../composables/useTheme'
import { formatTime } from '../composables/useFormat'

import AdminHeader from '../components/admin/AdminHeader.vue'
import AdminSidebar from '../components/admin/AdminSidebar.vue'
import DashboardOverview from '../components/admin/DashboardOverview.vue'
import StudentManagement from '../components/admin/StudentManagement.vue'
import SafetyConfig from '../components/admin/SafetyConfig.vue'
import KnowledgeManager from '../components/admin/KnowledgeManager.vue'
import ProfileModal from '../components/admin/ProfileModal.vue'
import ToastBubble from '../components/shared/ToastBubble.vue'

const router = useRouter()
const adminName = ref('管理员')
const activeMenu = ref('overview')
const { toggle: toggleNightMode } = useTheme()

const toast = reactive({ show: false, message: '', type: 'success' })

function showToast(message, type = 'success') {
  toast.message = message; toast.type = type; toast.show = true
}

const keywords = reactive({ highRisk: [], violation: [] })
const users = ref([])
const selectedUserForProfile = ref(null)
const selectedUserProfile = ref({
  core_stressors: [],
  effective_coping_methods: [],
  entity_relation_map: {},
  semantic_history_recall: ''
})

const menus = [
  { id: 'overview', label: '控制台概览', icon: '📊' },
  { id: 'users', label: '学生心理档案', icon: '👥' },
  { id: 'safety', label: '安全过滤管理', icon: '🛡️' },
  { id: 'knowledge', label: '知识库管理', icon: '📚' }
]

function handleLogout() {
  localStorage.removeItem('token')
  router.push('/login')
}

// --- 安全词 ---

async function fetchKeywords() {
  try {
    const res = await axios.get('/api/admin/safety-keywords', {
      headers: getAuthHeader(), params: { page: 1, size: 500 }
    })
    if (res.data?.code === 200) {
      const items = res.data.data.items || []
      keywords.highRisk = items.filter(k => k.word_type === 'high_risk').map(k => ({ id: k.id, word: k.word, enabled: k.is_enabled }))
      keywords.violation = items.filter(k => k.word_type === 'violation').map(k => ({ id: k.id, word: k.word, enabled: k.is_enabled }))
    }
  } catch (err) { console.error('获取敏感词失败:', err) }
}

async function addKeyword({ word, type }) {
  try {
    const res = await axios.post('/api/admin/safety-keywords', { word, word_type: type, is_enabled: true }, { headers: getAuthHeader() })
    if (res.data && (res.data.code === 200 || res.data.code === 201)) {
      await fetchKeywords()
      showToast(`已成功添加敏感词 "${word}"！`, 'success')
    } else {
      showToast(res.data?.message || '添加失败', 'error')
    }
  } catch (err) {
    const errMsg = err.response?.data?.detail || err.response?.data?.message || err.message || '添加失败'
    showToast(`添加失败: ${errMsg}`, 'error')
  }
}

async function toggleWordStatus(w) {
  try {
    const nextStatus = !w.enabled
    const res = await axios.put(`/api/admin/safety-keywords/${w.id}`, { is_enabled: nextStatus }, { headers: getAuthHeader() })
    if (res.data?.code === 200) w.enabled = nextStatus
  } catch (err) { showToast(err.message || '更新状态失败', 'error') }
}

// --- 学生 ---

async function fetchUsers() {
  try {
    const res = await axios.get('/api/admin/students', { headers: getAuthHeader(), params: { page: 1, size: 100 } })
    if (res.data?.code === 200) {
      users.value = (res.data.data.items || []).map(user => ({
        id: user.id, username: user.username, role: user.role,
        is_active: user.is_active, nickname: user.nickname || '暂无画像特征'
      }))
    }
  } catch (err) { console.error('获取学生列表失败:', err) }
}

async function viewUserProfile(user) {
  selectedUserForProfile.value = user
  selectedUserProfile.value = { core_stressors: [], effective_coping_methods: [], entity_relation_map: {}, semantic_history_recall: '正在加载...' }
  try {
    const res = await axios.get(`/api/admin/students/${user.id}/profile`, { headers: getAuthHeader() })
    if (res.data?.code === 200) selectedUserProfile.value = res.data.data
  } catch (err) { console.error('获取画像失败:', err) }
}

function incrementMockStats(type) {}
function viewAuditLog(log) {
  if (!log.userId) return showToast('该会话为无痕树洞匿名会话，无法查看个人档案。', 'warning')
  const user = users.value.find(u => u.id === log.userId)
  if (user) viewUserProfile(user)
}

onMounted(() => {
  const token = localStorage.getItem('token')
  if (token) {
    const payload = getPayload(token)
    if (payload) adminName.value = payload.sub
  }
  fetchKeywords()
  fetchUsers()
})
</script>

<style scoped>
.admin-container {
  min-height: 100vh; padding: 20px; display: flex; flex-direction: column; gap: 20px;
  background-color: var(--bg-color); transition: var(--transition-slow);
}
.admin-layout { display: flex; flex: 1; gap: 20px; }
.admin-main { flex: 1; display: flex; flex-direction: column; gap: 20px; }
</style>
