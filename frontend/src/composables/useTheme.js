// -*- coding: utf-8 -*-
/**
 * 日夜模式 composable。自动根据当地时间初始化（19:00-07:00 夜间）。
 */
import { ref } from 'vue'

export function useTheme() {
  const isNight = ref(false)

  // 根据当地时间自动检测
  const hour = new Date().getHours()
  if (hour >= 19 || hour < 7) {
    isNight.value = true
    document.body.classList.add('night-mode')
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
