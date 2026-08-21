<template>
  <div class="profile-overlay" @click.self="$emit('close')">
    <div class="profile-panel card-panel">
      <div class="profile-header">
        <div class="profile-avatar">🧠</div>
        <div class="profile-title">
          <h3>我的心理画像</h3>
          <p>由 AI 基于日常对话持续更新 · 隐私数据仅本人可见</p>
        </div>
        <button class="profile-close" @click="$emit('close')">✕</button>
      </div>

      <div v-if="loading" class="profile-empty">画像加载中...</div>

      <div v-else-if="!profile" class="profile-empty">
        <p>暂无画像数据</p>
        <p class="profile-hint">多和小影聊聊你的近况，画像会自动生成 🍃</p>
      </div>

      <div v-else class="profile-body">
        <!-- 基本信息 -->
        <div class="profile-section">
          <div class="section-title">👤 基本信息</div>
          <div class="section-content">
            <div class="info-row">
              <span class="info-label">昵称</span>
              <span class="info-value">{{ profile.nickname || '同学' }}</span>
            </div>
          </div>
        </div>

        <!-- 核心压力源 -->
        <div class="profile-section">
          <div class="section-title">🌧️ 核心压力源</div>
          <div class="section-content">
            <template v-if="profile.core_stressors && profile.core_stressors.length">
              <span v-for="(s, i) in profile.core_stressors" :key="i" class="tag tag-stressor">{{ s }}</span>
            </template>
            <p v-else class="profile-hint">暂未识别到明确的压力源</p>
          </div>
        </div>

        <!-- 历史有效应对方法 -->
        <div class="profile-section">
          <div class="section-title">💡 对你有效的应对方法</div>
          <div class="section-content">
            <template v-if="profile.effective_coping_methods && profile.effective_coping_methods.length">
              <span v-for="(m, i) in profile.effective_coping_methods" :key="i" class="tag tag-coping">{{ m }}</span>
            </template>
            <p v-else class="profile-hint">暂未识别到有效的应对方法</p>
          </div>
        </div>

        <!-- 关键关系网 -->
        <div class="profile-section">
          <div class="section-title">🤝 关键关系网</div>
          <div class="section-content">
            <template v-if="Object.keys(profile.entity_relation_map || {}).length">
              <div v-for="(v, k) in profile.entity_relation_map" :key="k" class="relation-row">
                <span class="relation-key">{{ k }}</span>
                <span class="relation-arrow">→</span>
                <span class="relation-value">{{ v }}</span>
              </div>
            </template>
            <p v-else class="profile-hint">暂未识别到重要人际关系</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { getAuthHeader } from '../../composables/useAuth'

defineEmits(['close'])

const profile = ref(null)
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await axios.get('/api/auth/profile', { headers: getAuthHeader() })
    if (res.data?.code === 200) {
      profile.value = res.data.data
    }
  } catch (err) {
    console.error('获取心理画像失败:', err)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.profile-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0, 0, 0, 0.45);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.profile-panel {
  width: min(480px, 100%);
  max-height: 85vh; overflow-y: auto;
  padding: 24px; border-radius: var(--radius-lg);
  background: var(--panel-bg);
}
.profile-header { display: flex; align-items: center; gap: 14px; margin-bottom: 20px; }
.profile-avatar {
  width: 52px; height: 52px; border-radius: 50%;
  background: linear-gradient(135deg, var(--primary-light), var(--accent-light));
  display: flex; align-items: center; justify-content: center; font-size: 24px;
}
.profile-title { flex: 1; }
.profile-title h3 { font-size: 17px; font-weight: 600; color: var(--text-primary); }
.profile-title p { font-size: 11.5px; color: var(--text-secondary); margin-top: 3px; }
.profile-close {
  border: none; background: none; font-size: 16px; cursor: pointer;
  color: var(--text-secondary); padding: 4px 8px;
}
.profile-close:hover { color: var(--text-primary); }

.profile-body { display: flex; flex-direction: column; gap: 16px; }
.profile-section {
  background: var(--bg-color); border: 1px solid var(--border-color);
  border-radius: var(--radius-md); padding: 14px 16px;
}
.section-title { font-size: 13px; font-weight: 600; color: var(--primary-hover); margin-bottom: 10px; }
.section-content { display: flex; flex-wrap: wrap; gap: 8px; }

.info-row { display: flex; align-items: center; gap: 10px; width: 100%; }
.info-label { font-size: 12.5px; color: var(--text-secondary); min-width: 60px; }
.info-value { font-size: 14px; font-weight: 600; color: var(--text-primary); }

.tag {
  padding: 5px 12px; border-radius: 16px; font-size: 12.5px; font-weight: 500;
}
.tag-stressor { background: var(--warning-light); color: #C0392B; }
.tag-coping { background: var(--primary-light); color: var(--primary-hover); }

.relation-row {
  display: flex; align-items: center; gap: 8px; width: 100%;
  padding: 4px 0; font-size: 13px;
}
.relation-key { font-weight: 600; color: var(--text-primary); }
.relation-arrow { color: var(--text-secondary); }
.relation-value { color: var(--primary-hover); }

.profile-empty { text-align: center; padding: 40px 0; color: var(--text-secondary); font-size: 13px; }
.profile-hint { font-size: 12px; color: var(--text-secondary); width: 100%; }
</style>
