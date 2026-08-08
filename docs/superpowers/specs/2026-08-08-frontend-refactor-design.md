# 前端代码维护性与视觉美观优化 设计文档

**日期**: 2026-08-08  
**状态**: 设计中  
**关联**: MindEcho 前端全面重构

---

## 1. 背景与动机

当前前端经过多轮功能迭代，积累了以下问题：

**维护性：**
- `SafetyConfig.vue` 1133 行，包含三个独立功能，且"知识检索文档导入"与新增的 `KnowledgeManager` 功能重叠
- `getPayload()` 在 4 个文件中重复定义，`getAuthHeader()` 在 2 个文件中重复，`formatTime()` 在 2 个文件中重复
- 无 composables/hooks 目录，所有逻辑内联在组件中
- `Admin.vue` 495 行，混合布局 + 数据获取 + 状态管理 + 工具函数

**美观：**
- 组件间间距、字号、表格样式不统一
- 全局 CSS 已定义 `.btn-primary`、`.card-panel`、`.input-field`，但组件 scoped style 中大量重复定义
- 空状态、Toast 等 UI 模式各组件自行实现，视觉不一致
- 日夜模式切换逻辑分布在 Login.vue 和 AdminHeader.vue 两处

---

## 2. 设计目标

1. **消除重复** — 所有工具函数收归 composables，所有 UI 模式收归全局 CSS 或共享组件
2. **拆分大组件** — SafetyConfig 拆为 3 个文件（外壳 + 2 个子功能），Admin.vue 瘦身
3. **统一视觉** — 全局 CSS 作为唯一样式真相源，组件 scoped style 只写布局差异
4. **删除死代码** — 移除 SafetyConfig 中与 KnowledgeManager 重叠的知识导入子 Tab

---

## 3. 架构变更

### 3.1 Composables 目录

新增 `frontend/src/composables/`：

```
composables/
├── useAuth.js      ← getPayload(), getAuthHeader(), useAuth()
├── useTheme.js     ← useTheme(): isNight, toggle()
└── useFormat.js    ← formatTime(), formatSize()
```

**接口契约：**

```js
// useAuth.js — 纯函数（可直接 import 使用，不需要在 setup 中调用）
export function getPayload(token)  // string → { sub, role, exp } | null
export function getAuthHeader()     // → { Authorization: `Bearer ${token}` } | {}

// useTheme.js — 响应式 composable
export function useTheme()          // → { isNight: Ref<boolean>, toggle: () => void }

// useFormat.js — 纯函数
export function formatTime(iso)    // → "2026-08-08 14:30"
export function formatSize(bytes)  // → "1.2 MB"
```

**影响范围：**
- `router/index.js` — 用 `getPayload` from useAuth
- `Login.vue` — 用 `useTheme` 替换内联 toggleNightMode
- `Admin.vue` — 用 `useAuth` + `useTheme` 替换内联函数，`formatTime` from useFormat
- `AdminHeader.vue` — 用 `useTheme`，不再透过 emit 传到父组件
- `Chat.vue` — 用 `getPayload` from useAuth
- `SafetyConfig.vue` — 用 `getAuthHeader` from useAuth
- `KnowledgeManager.vue` — 用 `getAuthHeader` from useAuth（移除 getAuthHeader prop）
- `StudentManagement.vue`、`DashboardOverview.vue` 等 — 按需用 `getAuthHeader`

### 3.2 SafetyConfig 拆分

```
Before:
  SafetyConfig.vue  1133 lines  (3 sub-tabs: keywords / rag_seeds / knowledge)

After:
  SafetyConfig.vue   ~60 lines   (外壳：sub-tab 切换 + 接收 keywords prop)
  SafetyKeywords.vue ~350 lines  (添加表单 + 危险词/违规词列表)
  SafetyRagSeeds.vue ~250 lines  (添加样本 + 样本列表)
```

- 删除"知识检索文档导入"sub-tab（功能由 KnowledgeManager 提供）
- `SafetyKeywords.vue`、`SafetyRagSeeds.vue` 内部使用 `useAuth().getAuthHeader()`，不再依赖父组件透传函数
- SafetyConfig.vue 保留作为 Tab 容器，接收 `keywords` prop 管理共享状态

### 3.3 共享 UI 组件

新增 `frontend/src/components/shared/`：

```
components/shared/
├── EmptyState.vue     ← props: message, icon
└── ToastBubble.vue    ← props: message, type (success|error|warning|info), visible
```

- `EmptyState` — 统一空列表/空结果占位，替换各组件中手写的 `<div class="empty-*">`
- `ToastBubble` — 从 `Admin.vue` 的 toast 逻辑提取，原本只 Admin 能用，提取后 Login/Chat 也能用

### 3.4 Admin.vue 瘦身

| 项目 | Before | After |
|------|--------|-------|
| 行数 | 495 | ~300 |
| 数据获取 | Admin 统一 fetch，通过 props 下发 | 各子组件 onMounted 自行 fetch |
| 工具函数 | 内联 4 个 | 0 个（全部 import from composables） |
| Toast | 内联逻辑 | 改用 `<ToastBubble>` 组件 |

**子组件数据获取下沉：**
- `DashboardOverview.vue` — onMounted 自 fetch stats
- `StudentManagement.vue` — onMounted 自 fetch users
- `SafetyConfig.vue` → `SafetyKeywords.vue` — onMounted 自 fetch keywords

### 3.5 CSS 统合

**全局 `style.css` 新增：**

```css
/* 共享按钮变体 */
.btn-sm     — 小型操作按钮（表格内使用）
.btn-ghost  — 无边框幽灵按钮

/* 统一徽章 */
.badge      — 基础徽章
.badge-success / .badge-warning / .badge-danger / .badge-info

/* 统一表格 */
.data-table  — 基础表格（替代各组件中的 .admin-table / table 裸样式）

/* 统一空状态 */
.empty-state — 空数据占位

/* 间距工具 */
.gap-12 / .gap-16 / .gap-20 / .gap-24
```

**组件 scoped style 清理原则：**
- 凡是全局已定义的类（`.btn-primary`、`.card-panel`、`.input-field`），组件不再重复定义
- 组件 scoped style 只保留：布局（flex/grid）、组件特有的动画、颜色微调

### 3.6 视觉统一基准

以 Login.vue 的 Morandi 调色板 + 圆角 + 动效为全项目基准：
- 所有页面卡片统一 `border-radius: var(--radius-lg)`
- 所有输入框聚焦呼吸灯动效（`emotion-breath`）
- 日夜模式切换统一由 `useTheme()` 管理

---

## 4. 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新增** | `composables/useAuth.js` | getPayload, getAuthHeader |
| **新增** | `composables/useTheme.js` | 日夜模式 |
| **新增** | `composables/useFormat.js` | formatTime, formatSize |
| **新增** | `components/shared/EmptyState.vue` | 空状态组件 |
| **新增** | `components/shared/ToastBubble.vue` | Toast 组件 |
| **新增** | `components/admin/SafetyKeywords.vue` | 安全词管理 |
| **新增** | `components/admin/SafetyRagSeeds.vue` | RAG 种子导入 |
| **重写** | `components/admin/SafetyConfig.vue` | 1133→60 行外壳 |
| **修改** | `pages/Admin.vue` | 495→300 行，用 composables + ToastBubble |
| **修改** | `pages/Login.vue` | 用 useTheme |
| **修改** | `pages/Chat.vue` | 用 getPayload from useAuth |
| **修改** | `router/index.js` | 用 getPayload from useAuth |
| **修改** | `components/admin/AdminHeader.vue` | 用 useTheme |
| **修改** | `components/admin/KnowledgeManager.vue` | 用 getAuthHeader from useAuth，移除 prop |
| **修改** | `components/admin/DashboardOverview.vue` | 自 fetch 数据，统一样式 |
| **修改** | `components/admin/StudentManagement.vue` | 自 fetch 数据，统一样式 |
| **修改** | `components/admin/ProfileModal.vue` | 样式对齐 |
| **修改** | `style.css` | 新增工具类 + 统一表格/徽章/按钮样式 |

---

## 5. 不变更文件

- `components/CapybaraSvg.vue` — 纯 SVG，无问题
- `components/chat/*` — ChatSidebar/ChatInput/MessageArea 已合理拆分
- `components/HelloWorld.vue` — 未使用，保留不动
- `App.vue` — 仅路由出口

---

## 6. 验收标准

1. `getPayload` 全项目只有 1 处定义（useAuth.js）
2. `getAuthHeader` 全项目只有 1 处定义（useAuth.js）
3. `formatTime` 全项目只有 1 处定义（useFormat.js）
4. SafetyConfig.vue ≤ 80 行
5. 删除"知识检索文档导入"子 Tab 后，知识库上传仍可通过侧边栏「知识库管理」正常工作
6. `npm run build` 通过，无引入错误
7. 日夜模式切换在 Login 和 Admin 页均正常工作
