// -*- coding: utf-8 -*-
/**
 * 格式化工具 — 纯函数。
 */

/**
 * ISO 时间字符串 → "YYYY-MM-DD HH:mm"
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
 * 字节数 → 人类可读大小。
 */
export function formatSize(bytes) {
  if (!bytes || bytes < 0) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
