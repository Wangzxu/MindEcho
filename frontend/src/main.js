import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import axios from 'axios'

// 1. 配置全局 Axios 默认 BaseURL 指向后端服务运行端口
axios.defaults.baseURL = 'http://localhost:5000'

// 2. 配置全局 Axios 响应拦截器：温和处理各类异常，提供莫兰迪治愈系的异常提示，拒绝将后端堆栈错误生硬展示给用户
axios.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    let friendlyMessage = '遇到了一点小麻烦，水豚委员正在抓紧查看，请稍后再试哦。'
    
    if (error.response) {
      const status = error.response.status
      const data = error.response.data
      
      if (status === 400) {
        friendlyMessage = data.detail || data.message || '填入的数据格式不合规范，请仔细检查后再试哦。'
      } else if (status === 401) {
        friendlyMessage = '登录令牌已失效，请重新登录，水豚委员在这等您。'
      } else if (status === 403) {
        friendlyMessage = data.detail || '您的账户似乎未激活或无权访问，请联系心理辅导老师激活哦。'
      } else if (status === 404) {
        friendlyMessage = '请求的资源丢失在虚无里了，请换个功能重试。'
      } else if (status === 422) {
        // 特殊处理 Pydantic 数据验证错误
        friendlyMessage = '数据字数或格式不符合规定。'
        if (data.detail && Array.isArray(data.detail)) {
          const firstErr = data.detail[0]
          if (firstErr) {
            // 提取被限制的字段名及提示，汉化展示
            const fieldName = firstErr.loc ? firstErr.loc[firstErr.loc.length - 1] : '字段'
            const msg = firstErr.msg || '格式错误'
            friendlyMessage = `输入内容有误：[${fieldName}] 格式不满足要求 (${msg})`
          }
        }
      } else if (status >= 500) {
        friendlyMessage = '树洞后台发生了一点网络波动（服务暂不可用），水豚委员正在紧急修复，请稍候。'
      }
    } else if (error.request) {
      // 网络超时或后端服务未启动
      friendlyMessage = '无法连接到后端树洞服务，请检查您的网络连接并确保后端已正常启动哦。'
    } else {
      friendlyMessage = error.message || '网络连接发生了未知的异常，请刷新页面重试。'
    }

    // 覆盖原生的 error.message，方便外部组件统一用 error.message 提取治愈系中文
    error.message = friendlyMessage
    return Promise.reject(error)
  }
)

const app = createApp(App)
app.use(router)
app.mount('#app')
