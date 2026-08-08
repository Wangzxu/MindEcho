# 前端代码维护性与视觉美观优化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除代码重复、拆分大组件、统一视觉系统 — 新增 3 个 composables + 2 个共享组件 + 2 个子组件，重构 SafetyConfig 和 Admin.vue。

**Architecture:** 自底向上：先建 composables 基础层 → 共享 UI 组件 → CSS 统合 → 组件拆分 → 页面瘦身 → 全量织入。每个 Task 独立可测试，完成后 `npm run build` 验证。

**Tech Stack:** Vue 3 + Vite + Composition API

## Global Constraints

- 所有函数名、导出签名以本文为准（不可自行变更）
- `getPayload()`、`getAuthHeader()`、`formatTime()`、`formatSize()` 全项目只能有一处定义
- SafetyConfig.vue 最终 ≤ 80 行，删除"知识检索文档导入"子 Tab
- `npm run build` 通过 = 验收标准
- 组件 `<style scoped>` 不重复定义全局 CSS 已有的选择器（`.btn-primary`、`.card-panel`、`.input-field`）
- 日期格式化统一为 `"YYYY-MM-DD HH:mm"` 格式

---

### Task 1: Composables 基础层

**Files:**
- Create: `frontend/src/composables/useAuth.js`
- Create: `frontend/src/composables/useTheme.js`
- Create: `frontend/src/composables/useFormat.js`

**Interfaces:**
- Produces:
  - `useAuth.js`: `export function getPayload(token)` → object|null, `export function getAuthHeader()` → object
  - `useTheme.js`: `export function useTheme()` → `{ isNight: Ref<boolean>, toggle: () => void }`
  - `useFormat.js`: `export function formatTime(iso)` → string, `export function formatSize(bytes)` → string

- [ ] **Step 1: 创建 `useAuth.js`**

```js
// frontend/src/composables/useAuth.js
import { ref, computed } from 'vue'

/**
 * 解析 JWT Base64 令牌负载，纯函数，不依赖 Vue 响应式。
 * @param {string} token
 * @returns {object|null} { sub, role, exp } | null
 */
export function getPayload(token) {
  if (!token) return null
  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch (e) {
    return null
  }
}

/**
 * 获取带 Bearer token 的 Authorization header 对象。
 * @returns {{ Authorization: string } | {}}
 */
export function getAuthHeader() {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}
```

- [ ] **Step 2: 创建 `useTheme.js`**

```js
// frontend/src/composables/useTheme.js
import { ref } from 'vue'

/**
 * 日夜模式 composable。自动根据当地时间初始化（19:00-07:00 为夜间）。
 * @returns {{ isNight: Ref<boolean>, toggle: () => void }}
 */
export function useTheme() {
  const isNight = ref(false)

  // 初始化：根据当地时间自动检测
  const hour = new Date().getHours()
  if (hour >= 19 || hour < 7) {
    isNight.value = true
    document.body.classList.add('night-mode')
  } else {
    document.body.classList.remove('night-mode')
  }

  function toggle() {
    isNight.value = !isNight.value
    if (isNight.value) {
      document.body.classList.add('night-mode')
    } else {
      document.body.classList.remove('night-mode')
    }
  }

  return { isNight, toggle }
}
```

- [ ] **Step 3: 创建 `useFormat.js`**

```js
// frontend/src/composables/useFormat.js

/**
 * ISO 时间字符串 → "YYYY-MM-DD HH:mm"
 * @param {string} isoString
 * @returns {string}
 */
export function formatTime(isoString) {
  if (!isoString) return '-'
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return isoString
    const pad = n => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch {
    return isoString
  }
}

/**
 * 字节数 → 人类可读大小
 * @param {number} bytes
 * @returns {string}
 */
export function formatSize(bytes) {
  if (!bytes || bytes < 0) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
```

- [ ] **Step 4: 验证文件语法**

Run: `node -e "console.log('syntax ok')"` after checking each file manually.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/
git commit -m "feat: 新增 composables 基础层 — useAuth / useTheme / useFormat"
```

---

### Task 2: 共享 UI 组件 + CSS 统合

**Files:**
- Create: `frontend/src/components/shared/EmptyState.vue`
- Create: `frontend/src/components/shared/ToastBubble.vue`
- Modify: `frontend/src/style.css`

**Interfaces:**
- Produces:
  - `EmptyState` — props: `message: String`, `icon: String` (默认 `'📭'`)
  - `ToastBubble` — props: `message: String`, `type: String` (success/error/warning/info), `visible: Boolean`; emit: `close`

- [ ] **Step 1: 创建 `EmptyState.vue`**

```vue
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
```

- [ ] **Step 2: 创建 `ToastBubble.vue`**

```vue
<template>
  <transition name="toast-fade">
    <div v-if="visible" :class="['toast-bubble', type]">
      <span class="toast-icon">{{ iconMap[type] }}</span>
      <span class="toast-message">{{ message }}</span>
    </div>
  </transition>
</template>

<script setup>
import { watch } from 'vue'

const props = defineProps({
  message: { type: String, default: '' },
  type: { type: String, default: 'success' },
  visible: { type: Boolean, default: false },
  duration: { type: Number, default: 3000 }
})

const emit = defineEmits(['close'])

const iconMap = {
  success: '🟢',
  error: '🔴',
  warning: '🟡',
  info: '🔵'
}

let timer = null
watch(() => props.visible, (v) => {
  if (v) {
    clearTimeout(timer)
    timer = setTimeout(() => emit('close'), props.duration)
  }
})
</script>

<style scoped>
.toast-bubble {
  position: fixed; top: 30px; left: 50%; transform: translateX(-50%);
  display: flex; align-items: center; gap: 10px;
  padding: 12px 24px; border-radius: var(--radius-md);
  box-shadow: 0 8px 30px rgba(0,0,0,0.12);
  background: var(--panel-bg); border: 1px solid var(--border-color);
  z-index: 9999; font-size: 13.5px; font-weight: 500;
  color: var(--text-primary); backdrop-filter: blur(10px);
}
.toast-bubble.success { border-color: var(--primary); background: var(--primary-light); color: var(--primary-hover); }
.toast-bubble.error   { border-color: var(--warning); background: var(--warning-light); color: var(--warning); }
.toast-bubble.warning { border-color: #f39c12; background: rgba(243,156,18,0.1); color: #D35400; }
.toast-bubble.info    { border-color: #5DADE2; background: rgba(93,173,226,0.1); color: #2980B9; }
.toast-icon { font-size: 16px; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: all 0.3s cubic-bezier(0.16,1,0.3,1); }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translate(-50%, -20px); }
</style>
```

- [ ] **Step 3: 增强 `style.css` — 在文件末尾追加以下内容**

```css
/* =====================================================================
   共享组件样式 (EmptyState, 表格, 徽章, 间距工具)
   ===================================================================== */

/* 空状态占位 */
.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary);
}
.empty-icon {
  font-size: 36px;
  display: block;
  margin-bottom: 12px;
}

/* 统一数据表格 */
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  text-align: left;
}
.data-table th {
  padding: 10px 8px;
  border-bottom: 2px solid var(--border-color);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 12px;
}
.data-table td {
  padding: 10px 8px;
  border-bottom: 1px solid var(--border-color);
}

/* 统一徽章 */
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}
.badge-success { background: #d5f5e3; color: #27ae60; }
.badge-warning { background: #fef9e7; color: #f39c12; }
.badge-danger  { background: #fadbd8; color: #e74c3c; }
.badge-info    { background: #ebf5fb; color: #2980b9; }

/* 按钮变体 */
.btn-sm {
  padding: 4px 10px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--bg-color);
  color: var(--text-primary);
  font-size: 12px;
  cursor: pointer;
  transition: var(--transition-normal);
}
.btn-sm:hover { background: var(--primary-light); border-color: var(--primary); }

.btn-ghost {
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-secondary);
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: var(--transition-normal);
}
.btn-ghost:hover { background: var(--primary-light); color: var(--primary-hover); }

/* 间距工具 */
.gap-12 { gap: 12px; }
.gap-16 { gap: 16px; }
.gap-20 { gap: 20px; }
.gap-24 { gap: 24px; }

/* 文本截断 */
.text-ellipsis {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* 通用过渡 */
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/shared/ frontend/src/style.css
git commit -m "feat: 新增 EmptyState/ToastBubble 共享组件，CSS 增强表格徽章按钮工具类"
```

---

### Task 3: SafetyConfig 拆分

**Files:**
- Create: `frontend/src/components/admin/SafetyKeywords.vue`
- Create: `frontend/src/components/admin/SafetyRagSeeds.vue`
- Modify: `frontend/src/components/admin/SafetyConfig.vue` (重写为外壳)

**Interfaces:**
- Consumes:
  - `getAuthHeader` from `@/composables/useAuth`
  - `formatTime` from `@/composables/useFormat`
- SafetyConfig.vue 接收 `keywords` prop（维持与 Admin.vue 的现有接口），传给 SafetyKeywords
- SafetyKeywords emit: `add-keyword`, `toggle-keyword-status`
- SafetyRagSeeds emit: `increment-mock-stats`, `show-toast`

- [ ] **Step 1: 创建 `SafetyKeywords.vue`**

从原 SafetyConfig.vue 提取"安全词设置"子 Tab 的全部代码（template 第 26-91 行 + script 中 keywords 相关逻辑 + style 中对应 CSS），作以下改动：
- 内部 `import { getAuthHeader } from '@/composables/useAuth'`，删除自身的 `getAuthHeader` 函数
- 接收 `keywords` prop（从父组件传入，替代原 emit 模式）
- emit: `add-keyword`, `toggle-keyword-status`

- [ ] **Step 2: 创建 `SafetyRagSeeds.vue`**

从原 SafetyConfig.vue 提取"预警 RAG 向量导入"子 Tab（template 第 93-140 行 + script 中 ragSeeds 相关逻辑 + style 中对应 CSS）：
- 内部 `import { getAuthHeader } from '@/composables/useAuth'`
- 自身管理 ragSeeds 数据（fetchRagSeeds onMounted）
- emit: `show-toast`, `increment-mock-stats`

- [ ] **Step 3: 重写 `SafetyConfig.vue` 为外壳**

仅保留子 Tab 切换 + 两个子组件：

```vue
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
      @show-toast="(msg, type) => $emit('show-toast', msg, type)"
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
```

- [ ] **Step 4: 验证构建**

Run: `cd frontend && npm run build`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/admin/SafetyConfig.vue frontend/src/components/admin/SafetyKeywords.vue frontend/src/components/admin/SafetyRagSeeds.vue
git commit -m "refactor: 拆分 SafetyConfig — 安全词/种子独立组件, 删除知识导入子Tab"
```

---

### Task 4: Admin.vue 瘦身

**Files:**
- Modify: `frontend/src/pages/Admin.vue`

**Interfaces:**
- Consumes: `useTheme` from `@/composables/useTheme`, `getPayload` + `getAuthHeader` from `@/composables/useAuth`, `formatTime` from `@/composables/useFormat`
- Consumes: `ToastBubble` from `@/components/shared/ToastBubble`
- Removes: 内联的 `getPayload`、`getAuthHeader`、`formatTime`、`toggleNightMode`、toast 逻辑
- KnowledgeManager 的 `:getAuthHeader` prop 移除（组件内部自行 import）

具体的 Admin.vue 修改：

**script 部分改动：**
```js
// 新增 import:
import { useTheme } from '../composables/useTheme'
import { getPayload, getAuthHeader } from '../composables/useAuth'
import { formatTime } from '../composables/useFormat'
import ToastBubble from '../components/shared/ToastBubble.vue'

// 删除以下函数（已迁移到 composables）：
// - getPayload()       → 改用 import { getPayload }
// - getAuthHeader()    → 改用 import { getAuthHeader }
// - formatTime()       → 改用 import { formatTime }
// - toggleNightMode()  → 改用 useTheme().toggle

// 新增:
const { isNight, toggle: toggleNightMode } = useTheme()

// Toast 状态简化（不再需要 setTimeout 管理）:
const toast = reactive({ show: false, message: '', type: 'success' })
function showToast(message, type = 'success') {
  toast.message = message; toast.type = type; toast.show = true
}
function closeToast() { toast.show = false }

// KnowledgeManager 不再需要传 :getAuthHeader
```

**template 部分改动：**
- KnowledgeManager 移除 `:getAuthHeader="getAuthHeader"` prop
- Toast 部分替换为 `<ToastBubble :message="toast.message" :type="toast.type" :visible="toast.show" @close="closeToast" />`

- [ ] **Step 1: 应用上述所有修改到 Admin.vue**
- [ ] **Step 2: `npm run build` 验证**
- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Admin.vue
git commit -m "refactor: Admin.vue 瘦身 — 使用 composables + ToastBubble, 移除内联工具函数"
```

---

### Task 5: 全量织入 — 所有组件迁移到 composables

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/pages/Login.vue`
- Modify: `frontend/src/pages/Chat.vue`
- Modify: `frontend/src/components/admin/AdminHeader.vue`
- Modify: `frontend/src/components/admin/KnowledgeManager.vue`
- Modify: `frontend/src/components/admin/DashboardOverview.vue`
- Modify: `frontend/src/components/admin/StudentManagement.vue`
- Modify: `frontend/src/components/admin/ProfileModal.vue`

**Interfaces:**
- 所有文件中出现 `getPayload`、`getAuthHeader`、`formatTime`、`formatSize`、`toggleNightMode` 的内联定义 → 替换为从 composables import

- [ ] **Step 1: `router/index.js` — 替换 getPayload**

```js
// 删除原有的 getPayload 函数（第 8-20 行）
// 新增 import:
import { getPayload } from '../composables/useAuth'
```

- [ ] **Step 2: `Login.vue` — 替换 toggleNightMode**

```js
// 新增 import:
import { useTheme } from '../composables/useTheme'

// 删除内联: isNightMode ref, toggleNightMode 函数, onMounted 中的时间检测
// 替换为:
const { isNight: isNightMode, toggle: toggleNightMode } = useTheme()

// 删除 getPayload 内联 → import { getPayload } from '../composables/useAuth'
```

- [ ] **Step 3: `Chat.vue` — 替换 getPayload**

```js
// 删除内联 getPayload 函数（第 83-89 行）
// 新增 import:
import { getPayload } from '../composables/useAuth'
```

- [ ] **Step 4: `AdminHeader.vue` — 替换 toggleNightMode**

```js
// 新增 import:
import { useTheme } from '../../composables/useTheme'

// 删除通过 props/emit 的 isNightMode 和 toggle 逻辑
// 改为内部调用 useTheme()
// 移除 props 中的 isNightMode, 移除 emit 中的 toggle-night-mode
```

- [ ] **Step 5: `KnowledgeManager.vue` — 替换 getAuthHeader**

```js
// 新增 import:
import { getAuthHeader } from '../../composables/useAuth'

// 修改 defineProps: 移除 getAuthHeader prop
// 所有调用 props.getAuthHeader() 的地方 → 改为 getAuthHeader()
```

- [ ] **Step 6: `DashboardOverview.vue` — 添加 getAuthHeader**

```js
// 新增 import:
import { getAuthHeader } from '../../composables/useAuth'

// onMounted 中自行 fetch 数据（不再依赖父组件 props 传入 stats）:
async function fetchStats() {
  const res = await axios.get('/api/admin/dashboard/stats', { headers: getAuthHeader() })
  if (res.data?.code === 200) { /* 更新本地 stats */ }
}
onMounted(() => fetchStats())
```

- [ ] **Step 7: `StudentManagement.vue` — 添加 getAuthHeader**

```js
// 新增 import:
import { getAuthHeader } from '../../composables/useAuth'

// onMounted 中自行 fetch 数据:
async function fetchUsers() {
  const res = await axios.get('/api/admin/students', { headers: getAuthHeader(), params: { page: 1, size: 100 } })
  if (res.data?.code === 200) { /* 更新本地 users */ }
}
onMounted(() => fetchUsers())
```

- [ ] **Step 8: `ProfileModal.vue` — 样式对齐**

将 scoped style 中使用硬编码颜色的地方改为 CSS 变量（`var(--text-primary)` 等）。

- [ ] **Step 9: `npm run build` 验证**
- [ ] **Step 10: Commit**

```bash
git add frontend/src/router/index.js frontend/src/pages/Login.vue frontend/src/pages/Chat.vue frontend/src/components/admin/AdminHeader.vue frontend/src/components/admin/KnowledgeManager.vue frontend/src/components/admin/DashboardOverview.vue frontend/src/components/admin/StudentManagement.vue frontend/src/components/admin/ProfileModal.vue
git commit -m "refactor: 全量织入 composables — 消除 getPayload/getAuthHeader/formatTime/useTheme 重复定义"
```

---

### Task 6: 最终验证

- [ ] **Step 1: `npm run build`**

Run: `cd frontend && npm run build`
Expected: PASS, 无错误

- [ ] **Step 2: 验证 spec 验收标准**

```bash
# 确认 getPayload 全项目只有 1 处定义
grep -rn "function getPayload" frontend/src/ | grep -v node_modules
# 预期: 只有 composables/useAuth.js 一行

# 确认 getAuthHeader 全项目只有 1 处定义
grep -rn "function getAuthHeader" frontend/src/ | grep -v node_modules
# 预期: 只有 composables/useAuth.js 一行

# 确认 formatTime 全项目只有 1 处定义
grep -rn "function formatTime" frontend/src/ | grep -v node_modules
# 预期: 只有 composables/useFormat.js 一行

# 确认 SafetyConfig.vue ≤ 80 行
wc -l frontend/src/components/admin/SafetyConfig.vue
# 预期: ≤ 80

# 确认 "知识检索文档导入" 已从 SafetyConfig 中删除
grep "知识检索文档导入" frontend/src/components/admin/SafetyConfig.vue
# 预期: 无结果
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: 前端重构最终验证通过"
```
