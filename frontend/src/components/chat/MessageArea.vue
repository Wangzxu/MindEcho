<template>
  <div class="messages-area" ref="areaRef">
    <!-- 欢迎气泡，如果会话历史为空 -->
    <div v-if="messages.length === 0" class="msg-row ai">
      <div class="msg-avatar-svg"><CapybaraSvg size="38px" /></div>
      <div class="msg-bubble ai-bubble welcome-bubble">
        <p>你好呀，{{ nickname }}。我是你的 AI 心理学长/学姐小影。🌿</p>
        <p style="margin-top: 8px;">无论你现在是面临着学业与科研压力、寝室关系困扰，还是处于情感内耗中，我都非常乐意在这里听你倾诉，陪伴你一起度过这段时光。</p>
        <p style="margin-top: 8px;" v-if="isAnonymous">
          当前为 **无痕树洞模式**，我们之间的逐条聊天记录将**不会被保存在服务器数据库中**。你可以毫无顾虑地分享你的真实情感。
        </p>
        <p style="margin-top: 8px;" v-else>
          当前为 **常规记录模式**，聊天记录会安全加密保存，方便下一次进入时连贯沟通。
        </p>
      </div>
    </div>

    <!-- 历史消息渲染 -->
    <div 
      v-for="(msg, index) in messages" 
      :key="index" 
      :class="['msg-row', msg.sender === 'user' ? 'user' : 'ai']"
    >
      <!-- 头像 -->
      <div v-if="msg.sender === 'ai'" class="msg-avatar-svg">
        <CapybaraSvg size="38px" />
      </div>

      <!-- 气泡 -->
      <div :class="['msg-bubble-wrapper', msg.sender === 'user' ? 'user-wrapper' : 'ai-wrapper']">
        <div :class="['msg-bubble', msg.sender === 'user' ? 'user-bubble' : 'ai-bubble']">
          <!-- 回复正文 -->
          <p class="whitespace-pre-wrap">{{ msg.content }}</p>
          
          <!-- 意图分类徽章 (仅 AI 气泡展示) -->
          <div v-if="msg.sender === 'ai' && msg.intent" class="intent-badge-container">
            <span :class="['intent-badge', msg.intent.toLowerCase()]">
              {{ getIntentLabel(msg.intent) }}
            </span>
            <span v-if="msg.reason" class="intent-reason-text" :title="msg.reason">
              🔍 {{ msg.reason }}
            </span>
          </div>
        </div>

        <!-- RAG 科普知识卡片展示 (若存在) -->
        <div 
          v-if="msg.sender === 'ai' && msg.ragCards && msg.ragCards.length > 0" 
          class="rag-cards-section"
        >
          <div class="rag-section-header">📚 关联专业心理科普知识：</div>
          <div class="rag-cards-container">
            <div v-for="(card, cIndex) in msg.ragCards" :key="cIndex" class="rag-card">
              <div class="rag-card-title">📖 {{ card.title || '科普知识卡' }}</div>
              <div class="rag-card-body">
                <p class="concept"><strong>释义：</strong>{{ card.concept || card.content }}</p>
                <p v-if="card.tip" class="tip"><strong>技巧：</strong>{{ card.tip }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="msg.sender === 'user'" class="msg-avatar">👤</div>
    </div>

    <!-- 流式加载中/打字中状态指示器 -->
    <div v-if="isGenerating && messages[messages.length - 1]?.sender === 'user'" class="msg-row ai">
      <div class="msg-avatar-svg"><CapybaraSvg size="38px" /></div>
      <div class="msg-bubble ai-bubble typing-bubble">
        <div class="typing-indicator">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import CapybaraSvg from '../CapybaraSvg.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  isGenerating: { type: Boolean, default: false },
  isAnonymous: { type: Boolean, default: false },
  nickname: { type: String, default: '同学' }
})

const areaRef = ref(null)

// 自动滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (areaRef.value) {
    areaRef.value.scrollTop = areaRef.value.scrollHeight
  }
}

// 监听消息列表变化并滚动
watch(() => props.messages, () => {
  scrollToBottom()
}, { deep: true })

onMounted(() => {
  scrollToBottom()
})

// 暴露滚动接口供父组件在手动切换或流式打字中触发
defineExpose({ scrollToBottom })

// 意图文本标签转换
function getIntentLabel(intentStr) {
  if (!intentStr) return ''
  const map = {
    'CRISIS': '⚠️ 安全红线预警',
    'KNOWLEDGE': '📚 专业心理科普',
    'EMOTION': '🍃 情绪宣泄共情'
  }
  return map[intentStr.toUpperCase()] || intentStr
}
</script>

<style scoped>
.messages-area {
  flex: 1;
  padding: 25px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  box-sizing: border-box;
}
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  max-width: 85%;
}
.msg-row.ai {
  align-self: flex-start;
}
.msg-row.user {
  align-self: flex-end;
  max-width: 75%;
}
.msg-bubble-wrapper {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}
.ai-wrapper {
  align-items: flex-start;
}
.user-wrapper {
  align-items: flex-end;
}

.msg-avatar {
  font-size: 24px;
  width: 36px;
  height: 36px;
  background-color: var(--primary-light);
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
}
.msg-bubble {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  font-size: 14.5px;
  line-height: 1.6;
  box-shadow: 0 4px 15px rgba(0,0,0,0.015);
  word-break: break-word;
}
.whitespace-pre-wrap {
  white-space: pre-wrap;
}
.ai-bubble {
  background-color: var(--primary-light);
  border-top-left-radius: 4px;
  border: 1px solid var(--border-color);
  color: var(--text-primary);
}
.welcome-bubble {
  background-color: #E8F5E9;
  border: 1px solid rgba(46, 125, 50, 0.15);
}
.user-bubble {
  background-color: var(--accent-light);
  border-top-right-radius: 4px;
  border: 1px solid var(--accent);
  color: #8E44AD;
}

/* 意图徽章 */
.intent-badge-container {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  border-top: 1px dashed rgba(0, 0, 0, 0.05);
  padding-top: 8px;
}
.intent-badge {
  font-size: 10.5px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 12px;
  color: white;
}
.intent-badge.crisis {
  background: linear-gradient(135deg, #EC7063, #C0392B);
  animation: badge-pulse 1.5s infinite;
}
.intent-badge.knowledge {
  background: linear-gradient(135deg, #5DADE2, #2980B9);
}
.intent-badge.emotion {
  background: linear-gradient(135deg, #58D68D, #27AE60);
}
.intent-reason-text {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 250px;
}

@keyframes badge-pulse {
  0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(192, 57, 43, 0.4); }
  70% { transform: scale(1.02); box-shadow: 0 0 0 6px rgba(192, 57, 43, 0); }
  100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(192, 57, 43, 0); }
}

/* RAG 科普卡片 */
.rag-cards-section {
  width: 100%;
  max-width: 480px;
  margin-top: 2px;
  animation: fade-in 0.4s ease-out;
}
.rag-section-header {
  font-size: 11.5px;
  color: var(--text-secondary);
  margin-bottom: 6px;
  padding-left: 4px;
}
.rag-cards-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rag-card {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(5px);
  border: 1px solid rgba(46, 125, 50, 0.12);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  box-shadow: 0 3px 10px rgba(0,0,0,0.02);
}
.rag-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 6px;
}
.rag-card-body {
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--text-primary);
}
.rag-card-body .concept {
  margin-bottom: 4px;
}
.rag-card-body .tip {
  color: #27AE60;
  background-color: #E8F8F5;
  padding: 4px 8px;
  border-radius: 4px;
  margin-top: 6px;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Typing Indicator */
.typing-bubble {
  padding: 14px 20px;
}
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 14px;
}
.typing-indicator span {
  width: 7px;
  height: 7px;
  background-color: var(--primary);
  border-radius: 50%;
  display: inline-block;
  animation: typing-bounce 1.4s infinite ease-in-out both;
}
.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes typing-bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1.0); }
}
</style>
