<template>
  <transition name="fade">
    <div class="modal-backdrop" @click.self="$emit('close')">
      <div class="profile-modal card-panel">
        <div class="modal-header">
          <h3>👤 学生心理画像报告 (安全审计)</h3>
          <button class="close-btn" @click="$emit('close')">✕</button>
        </div>
        <div class="modal-body">
          <div class="profile-info-row">
            <span class="info-label">学生账号:</span>
            <span class="info-val"><strong>{{ selectedUser?.username }}</strong></span>
          </div>
          <div class="profile-info-row">
            <span class="info-label">画像状态:</span>
            <span class="info-val"><span class="status-badge active">物理隔离脱敏</span></span>
          </div>
          
          <hr class="divider"/>

          <div class="profile-section">
            <h4>🎯 核心压力源 (Core Stressors)</h4>
            <div class="profile-tags-group">
              <span class="profile-tag accent" v-for="stress in profile?.core_stressors" :key="stress">{{ stress }}</span>
              <span class="empty-text" v-if="!profile?.core_stressors || profile?.core_stressors.length === 0">暂无压力源记录</span>
            </div>
          </div>

          <div class="profile-section">
            <h4>🛡️ 有效应对策略 (Coping Methods)</h4>
            <div class="profile-tags-group">
              <span class="profile-tag primary" v-for="coping in profile?.effective_coping_methods" :key="coping">{{ coping }}</span>
              <span class="empty-text" v-if="!profile?.effective_coping_methods || profile?.effective_coping_methods.length === 0">暂无应对策略记录</span>
            </div>
          </div>

          <div class="profile-section">
            <h4>🧠 长期记忆认知网 (Entity Map)</h4>
            <div class="entity-map-preview">
              <pre>{{ formatJSON(profile?.entity_relation_map) }}</pre>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-primary" @click="$emit('close')">关闭窗口</button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
defineProps({
  selectedUser: {
    type: Object,
    required: true
  },
  profile: {
    type: Object,
    required: true
  }
})

defineEmits(['close'])

function formatJSON(val) {
  if (!val) return '{}'
  return JSON.stringify(val, null, 2)
}
</script>

<style scoped>
/* 弹窗设计 */
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.4);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}
.profile-modal {
  width: 90%;
  max-width: 550px;
  background-color: var(--panel-bg);
  padding: 30px;
  max-height: 85vh;
  overflow-y: auto;
  border-radius: var(--radius-lg);
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.modal-header h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}
.close-btn {
  background: transparent;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: var(--text-secondary);
}
.close-btn:hover {
  color: var(--text-primary);
}
.profile-info-row {
  display: flex;
  gap: 10px;
  font-size: 14px;
  margin-bottom: 8px;
}
.info-label {
  color: var(--text-secondary);
}
.info-val {
  color: var(--text-primary);
}
.divider {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 15px 0;
}
.profile-section {
  margin-bottom: 20px;
}
.profile-section h4 {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 10px 0;
  color: var(--text-primary);
}
.profile-tags-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.profile-tag.accent {
  background-color: var(--accent-light);
  color: var(--accent-hover);
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  padding: 5px 12px;
  font-size: 12px;
}
.profile-tag.primary {
  background-color: var(--primary-light);
  color: var(--primary-hover);
  border: 1px solid var(--primary);
  border-radius: var(--radius-sm);
  padding: 5px 12px;
  font-size: 12px;
}
.empty-text {
  font-size: 12px;
  color: var(--text-secondary);
  font-style: italic;
}
.entity-map-preview {
  background-color: var(--primary-light);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  border: 1px solid var(--border-color);
}
.entity-map-preview pre {
  margin: 0;
  font-family: monospace;
  font-size: 12.5px;
  color: var(--text-primary);
  white-space: pre-wrap;
  text-align: left;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 25px;
}
.status-badge {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}
.status-badge.active {
  background-color: var(--primary-light);
  color: var(--primary);
}
.btn-primary {
  background-color: var(--primary);
  color: #FFFFFF;
  border: none;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-size: 14px;
  cursor: pointer;
  transition: var(--transition-normal);
}
.btn-primary:hover {
  background-color: var(--primary-hover);
}
</style>
