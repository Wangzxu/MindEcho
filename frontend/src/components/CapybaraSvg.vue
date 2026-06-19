<template>
  <div class="capybara-svg-wrapper" :style="{ width: size, height: size }">
    <svg viewBox="0 0 200 200" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
      <!-- 渐变定义 -->
      <defs>
        <!-- 温泉水面渐变 -->
        <linearGradient id="waterGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#9BC2F5" />
          <stop offset="100%" stop-color="#72A1DF" />
        </linearGradient>
        <!-- 水豚身子渐变 -->
        <linearGradient id="capyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#C59670" />
          <stop offset="100%" stop-color="#A27450" />
        </linearGradient>
      </defs>

      <!-- 背景圆圈 (非必须，如果开启的话能形成好看的头像框底) -->
      <circle v-if="withBg" cx="100" cy="100" r="95" fill="var(--primary-light)" stroke="var(--border-color)" stroke-width="2" />

      <!-- 后方远景温泉水波 -->
      <path d="M 10 140 Q 55 130, 100 140 T 190 140 L 190 190 L 10 190 Z" fill="#A8CAFB" opacity="0.5" />

      <!-- 【水豚泡温泉主体】 - 带有慢速平移呼吸动效 -->
      <g class="capybara-group">
        <!-- 耳朵 -->
        <path d="M 68 83 C 65 72, 77 70, 77 82 Z" fill="#885E3B" stroke="#463121" stroke-width="3" stroke-linejoin="round" />
        
        <!-- 身子和头连在一起 (呆萌面包状) -->
        <path d="M 65 160 
                 C 62 120, 68 90, 85 80 
                 C 100 72, 125 75, 130 85 
                 C 134 92, 136 102, 134 112
                 C 132 122, 127 132, 128 160 Z" 
              fill="url(#capyGrad)" stroke="#463121" stroke-width="4" stroke-linejoin="round" />

        <!-- 嘴巴/鼻头区域 (向前突出的深色斑块) -->
        <path d="M 112 88 
                 C 123 88, 134 90, 134 102 
                 C 134 115, 122 126, 114 122 
                 C 108 120, 106 105, 112 88 Z" 
              fill="#885E3B" stroke="#463121" stroke-width="3" stroke-linejoin="round" opacity="0.9" />

        <!-- 鼻孔线条 -->
        <path d="M 126 95 L 126 110 M 122 102 L 130 102" stroke="#463121" stroke-width="3" stroke-linecap="round" />

        <!-- 呆滞的小眼睛 (水豚标志性的平静无神眼) -->
        <circle cx="98" cy="98" r="3.5" fill="#463121" />
        <!-- 轻轻眨眼效果 -->
        <ellipse class="capy-eyelid" cx="98" cy="98" rx="4" ry="0" fill="#C59670" />

        <!-- 【头顶的小黄鸭】 - 带有独立的晃动小动效 -->
        <g class="duck-on-head">
          <!-- 鸭子身子 -->
          <path d="M 90 73 C 82 73, 80 65, 90 55 C 98 55, 104 63, 100 73 Z" fill="#F9D75E" stroke="#5E4627" stroke-width="2.5" />
          <!-- 鸭子小翅膀 -->
          <path d="M 88 67 Q 94 64, 96 70" fill="none" stroke="#5E4627" stroke-width="2.5" stroke-linecap="round" />
          <!-- 鸭子头部 -->
          <circle cx="97" cy="52" r="7" fill="#F9D75E" stroke="#5E4627" stroke-width="2.5" />
          <!-- 鸭子眼睛 -->
          <circle cx="98" cy="51" r="1" fill="#5E4627" />
          <!-- 鸭子橘色嘴巴 -->
          <path d="M 103 50 C 108 50, 108 55, 103 55 Z" fill="#F58B39" stroke="#5E4627" stroke-width="2" />
        </g>
      </g>

      <!-- 前方温泉水面 (完全遮挡水豚胸部以下) -->
      <path d="M 10 150 Q 50 142, 100 150 T 190 150 L 190 195 L 10 195 Z" fill="url(#waterGrad)" stroke="#463121" stroke-width="3" />

      <!-- 【水中游着的小鸭子】 -->
      <g class="swimming-duck">
        <!-- 身子 -->
        <path d="M 145 156 C 137 156, 135 148, 145 138 C 153 138, 159 146, 155 156 Z" fill="#F9D75E" stroke="#5E4627" stroke-width="2" />
        <path d="M 143 150 Q 149 147, 151 153" fill="none" stroke="#5E4627" stroke-width="2" stroke-linecap="round" />
        <!-- 头部 -->
        <circle cx="152" cy="135" r="6" fill="#F9D75E" stroke="#5E4627" stroke-width="2" />
        <circle cx="153" cy="134" r="0.8" fill="#5E4627" />
        <!-- 嘴巴 -->
        <path d="M 157 133 C 161 133, 161 137, 157 137 Z" fill="#F58B39" stroke="#5E4627" stroke-width="1.5" />
      </g>

      <!-- 动态温泉水波纹 -->
      <path class="water-ripple ripple-1" d="M 40 160 Q 60 156, 80 160" fill="none" stroke="#FFFFFF" stroke-width="2.5" stroke-linecap="round" opacity="0.7" />
      <path class="water-ripple ripple-2" d="M 115 168 Q 130 165, 145 168" fill="none" stroke="#FFFFFF" stroke-width="2.5" stroke-linecap="round" opacity="0.6" />
      <path class="water-ripple ripple-3" d="M 75 180 Q 100 176, 125 180" fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" opacity="0.5" />
    </svg>
  </div>
</template>

<script setup>
defineProps({
  size: {
    type: String,
    default: '120px'
  },
  withBg: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.capybara-svg-wrapper {
  display: inline-block;
  user-select: none;
  transition: transform 0.3s ease;
}

/* 1. 水豚轻柔的呼吸浮动效 */
@keyframes capy-breath {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(3px);
  }
}
.capybara-group {
  animation: capy-breath 4s infinite ease-in-out;
}

/* 2. 水豚眨眼效果 (每 6 秒眨一次) */
@keyframes blink-eye {
  0%, 95%, 100% {
    transform: scaleY(0);
  }
  97%, 98% {
    transform: scaleY(1);
  }
}
.capy-eyelid {
  animation: blink-eye 6s infinite ease-in-out;
  transform-origin: 98px 98px;
}

/* 3. 头顶小黄鸭的轻微晃动 (与水豚呼吸稍微错开) */
@keyframes duck-wobble {
  0%, 100% {
    transform: rotate(-3deg) translateY(0);
  }
  50% {
    transform: rotate(3deg) translateY(-1px);
  }
}
.duck-on-head {
  animation: duck-wobble 3s infinite ease-in-out;
  transform-origin: 95px 75px;
}

/* 4. 水中游泳鸭子的随波逐流 */
@keyframes duck-swim {
  0%, 100% {
    transform: translate(0, 0) rotate(-1deg);
  }
  50% {
    transform: translate(-3px, -2px) rotate(2deg);
  }
}
.swimming-duck {
  animation: duck-swim 4.5s infinite ease-in-out;
}

/* 5. 温泉水波纹扩散动效 */
@keyframes ripple-wave {
  0%, 100% {
    transform: scaleX(0.95) translateY(0);
    opacity: 0.4;
  }
  50% {
    transform: scaleX(1.05) translateY(1px);
    opacity: 0.8;
  }
}
.water-ripple {
  transform-origin: 100px 160px;
  animation: ripple-wave 3.5s infinite ease-in-out;
}
.ripple-2 {
  animation-delay: 1s;
}
.ripple-3 {
  animation-delay: 1.8s;
  transform-origin: 100px 180px;
}
</style>
