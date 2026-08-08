// -*- coding: utf-8 -*-
/**
 * 认证工具 — 纯函数，可在任何地方直接 import 使用。
 */
import { ref, computed } from 'vue'

/**
 * 解析 JWT Base64 令牌负载。
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
 * 用于 axios 请求的 headers 配置。
 */
export function getAuthHeader() {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}
