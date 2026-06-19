<template>
  <div class="login-wrapper">
    <!-- 日夜间模式切换小按钮 -->
    <button class="mode-toggle" @click="toggleNightMode" :title="isNightMode ? '切换为日间燕麦色' : '切换为夜间暖灰蓝'">
      <span v-if="isNightMode">☀️ 日间</span>
      <span v-else>🌙 夜间</span>
    </button>

    <div class="login-card card-panel">
      <!-- 手绘风格顶部微视觉 -->
      <div class="brand-header">
        <div class="brand-icon">
          <CapybaraSvg size="140px" />
        </div>
        <h1 class="brand-title">MindEcho</h1>
        <p class="brand-subtitle">校园 AI 心理委员 • 水豚豚树洞</p>
      </div>

      <!-- 选项卡切换 (学生登录 / 教师登录 / 注册) -->
      <div class="tabs-header">
        <button 
          :class="['tab-btn', { active: activeTab === 'student' }]" 
          @click="switchTab('student')"
        >
          学生登录
        </button>
        <button 
          :class="['tab-btn', { active: activeTab === 'admin' }]" 
          @click="switchTab('admin')"
        >
          教师管理
        </button>
        <button 
          :class="['tab-btn', { active: activeTab === 'register' }]" 
          @click="switchTab('register')"
        >
          账户注册
        </button>
      </div>

      <!-- 登录/注册表单区域 -->
      <div class="form-container">
        <!-- 错误提示组件 (淡绛红/柔和红背景) -->
        <transition name="fade">
          <div v-if="errorMsg" class="alert-box">
            <span>⚠️ {{ errorMsg }}</span>
          </div>
        </transition>

        <!-- 注册成功提示 -->
        <transition name="fade">
          <div v-if="successMsg" class="success-box">
            <span>🎉 {{ successMsg }}</span>
          </div>
        </transition>

        <form @submit.prevent="handleSubmit" class="auth-form">
          <div class="form-group">
            <label class="form-label">账号 / 学号 / 工号</label>
            <input 
              type="text" 
              class="input-field" 
              placeholder="请输入学号/工号或账号"
              v-model="form.username"
              required
            />
          </div>

          <!-- 注册时填写的昵称 -->
          <div class="form-group" v-if="activeTab === 'register'">
            <label class="form-label">自拟昵称 (匿名倾诉时使用)</label>
            <input 
              type="text" 
              class="input-field" 
              placeholder="请输入您的自选昵称(可选)"
              v-model="form.nickname"
            />
          </div>

          <div class="form-group">
            <label class="form-label">密码</label>
            <input 
              type="password" 
              class="input-field" 
              placeholder="请输入您的密码"
              v-model="form.password"
              required
            />
          </div>

          <button 
            type="submit" 
            :class="['submit-btn', activeTab === 'register' ? 'btn-accent' : 'btn-primary']"
            :disabled="isLoading"
          >
            <span v-if="isLoading">正在加载中...</span>
            <span v-else-if="activeTab === 'register'">立即注册并开启树洞</span>
            <span v-else>安全登录</span>
          </button>
        </form>
      </div>

      <div class="footer-tip">
        <p>🔒 树洞采取物理加密与脱敏方案，保障隐私与安全</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import CapybaraSvg from '../components/CapybaraSvg.vue'

const router = useRouter()
const activeTab = ref('student') // student, admin, register
const isLoading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
const isNightMode = ref(false)

const form = reactive({
  username: '',
  password: '',
  nickname: ''
})

// 原生 Base64 令牌负载解析
function getPayload(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch (e) {
    return null;
  }
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

// 初始化日夜模式
onMounted(() => {
  // 根据时间自动切换模式：晚上 7 点到早上 7 点自动切换为夜间模式
  const hour = new Date().getHours()
  if (hour >= 19 || hour < 7) {
    isNightMode.value = true
    document.body.classList.add('night-mode')
  }
})

// 切换选项卡
function switchTab(tab) {
  activeTab.value = tab
  errorMsg.value = ''
  successMsg.value = ''
  form.username = ''
  form.password = ''
  form.nickname = ''
}

// 处理表单提交
async function handleSubmit() {
  errorMsg.value = ''
  successMsg.value = ''
  isLoading.value = true

  try {
    if (activeTab.value === 'register') {
      // 1. 前端强校验拦截
      const username = form.username.trim()
      const password = form.password
      const nickname = form.nickname ? form.nickname.trim() : ''

      if (username.length < 3 || username.length > 50) {
        errorMsg.value = '账号/学号长度需在 3 到 50 个字符之间哦~'
        isLoading.value = false
        return
      }

      if (password.length < 6 || password.length > 100) {
        errorMsg.value = '密码安全非常重要，长度需在 6 到 100 个字符之间哦~'
        isLoading.value = false
        return
      }

      if (nickname && nickname.length > 20) {
        errorMsg.value = '自拟昵称有点太长了，建议在 20 个字符以内哦~'
        isLoading.value = false
        return
      }

      // 2. 注册逻辑
      const response = await axios.post('/api/auth/register', {
        username: username,
        password: password,
        nickname: nickname || null
      })

      if (response.data && response.data.code === 200) {
        successMsg.value = '注册成功！正在为您自动登录...'
        
        // 自动完成登录
        const loginResponse = await axios.post('/api/auth/login', {
          username: username,
          password: password
        })
        
        const token = loginResponse.data.data.access_token
        localStorage.setItem('token', token)
        
        // 注册用户默认跳转到学生聊天室
        setTimeout(() => {
          router.push('/chat')
        }, 1200)
      }
    } else {
      // 3. 登录逻辑
      const response = await axios.post('/api/auth/login', {
        username: form.username.trim(),
        password: form.password
      })

      if (response.data && response.data.code === 200) {
        const token = response.data.data.access_token
        const payload = getPayload(token)
        
        if (!payload) {
          errorMsg.value = '授权密钥解析异常，请重新登录'
          isLoading.value = false
          return
        }

        const role = payload.role

        // 校验选择的 Tab 角色是否吻合
        if (activeTab.value === 'admin' && role !== 'admin') {
          errorMsg.value = '您的账户没有管理端权限，请从学生通道登录'
          isLoading.value = false
          return
        }

        // 保存 Token 到本地
        localStorage.setItem('token', token)

        if (role === 'admin') {
          successMsg.value = '管理员登录成功！正在进入教师端后台...'
          setTimeout(() => {
            router.push('/admin')
          }, 1000)
        } else {
          successMsg.value = '登录成功！正在进入水豚委员聊天室...'
          setTimeout(() => {
            router.push('/chat')
          }, 1000)
        }
      }
    }
  } catch (error) {
    // 借由全局 Axios 拦截器，这里捕获到的 error.message 已经是友好包装后的中文提示
    errorMsg.value = error.message
    console.error('鉴权交互发生异常: ', error)
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 20px;
  position: relative;
}

/* 顶部日夜间模式切换按钮 */
.mode-toggle {
  position: absolute;
  top: 20px;
  right: 20px;
  background-color: var(--panel-bg);
  border: 1px solid var(--border-color);
  padding: 8px 16px;
  font-size: 13px;
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  cursor: pointer;
  box-shadow: 0 4px 10px var(--shadow-color);
  transition: var(--transition-normal);
}
.mode-toggle:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 14px var(--shadow-hover);
}

.login-card {
  width: 100%;
  max-width: 460px;
  padding: 40px 30px;
}

/* 顶部品牌区 */
.brand-header {
  text-align: center;
  margin-bottom: 30px;
}
.brand-icon {
  font-size: 48px;
  margin-bottom: 10px;
  display: inline-block;
  animation: float 3s ease-in-out infinite;
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}
.brand-title {
  font-size: 32px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 1px;
}
.brand-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 5px;
}

/* Tab 切换区 */
.tabs-header {
  display: flex;
  background-color: var(--primary-light);
  padding: 6px;
  border-radius: var(--radius-md);
  margin-bottom: 25px;
  border: 1px solid var(--border-color);
}
.tab-btn {
  flex: 1;
  border: none;
  background: transparent;
  padding: 10px 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: var(--transition-normal);
}
.tab-btn.active {
  background-color: var(--panel-bg);
  color: var(--text-primary);
  box-shadow: 0 4px 10px var(--shadow-color);
}

/* 警告框与成功框 */
.alert-box {
  background-color: var(--warning-light);
  border: 1px solid var(--warning);
  color: #C0392B;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  margin-bottom: 20px;
  line-height: 1.4;
}
body.night-mode .alert-box {
  color: #FFA39E;
}
.success-box {
  background-color: var(--primary-light);
  border: 1px solid var(--primary);
  color: #27AE60;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  margin-bottom: 20px;
}
body.night-mode .success-box {
  color: #B7EB8F;
}

/* 表单组 */
.form-group {
  margin-bottom: 20px;
}
.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.submit-btn {
  width: 100%;
  margin-top: 15px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.footer-tip {
  margin-top: 30px;
  text-align: center;
}
.footer-tip p {
  font-size: 11px;
  color: var(--text-secondary);
}
</style>
