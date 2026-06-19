<template>
  <div class="overview-container">
    <!-- 统计指标 -->
    <div class="stats-grid">
      <div class="stat-card card-panel">
        <div class="stat-icon student-bg">👥</div>
        <div class="stat-info">
          <span class="stat-label">注册学生总数</span>
          <span class="stat-value">{{ stats.studentCount }} 人</span>
        </div>
      </div>
      <div class="stat-card card-panel">
        <div class="stat-icon session-bg">💬</div>
        <div class="stat-info">
          <span class="stat-label">咨询人次 (Session数)</span>
          <span class="stat-value">{{ stats.sessionCount }} 次</span>
        </div>
      </div>
      <div class="stat-card card-panel">
        <div class="stat-icon high-risk-bg">🚨</div>
        <div class="stat-info">
          <span class="stat-label">危险警报拦截 (高危)</span>
          <span class="stat-value">{{ stats.highRiskCount }} 次</span>
        </div>
      </div>
      <div class="stat-card card-panel">
        <div class="stat-icon violation-bg">⚠️</div>
        <div class="stat-info">
          <span class="stat-label">违规行为拦截 (违规)</span>
          <span class="stat-value">{{ stats.violationCount }} 次</span>
        </div>
      </div>
    </div>

    <!-- 最近活动日志表格 (只记录高危与违规，日常对话不计入) -->
    <div class="activity-section card-panel">
      <div class="activity-header">
        <h3>📝 安全预警与行为审计日志 (最近活动)</h3>
        <span class="audit-tip">🔒 仅记录高危与违规行为，日常聊天对话不计入日志以保护树洞隐私</span>
      </div>
      
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>会话ID</th>
              <th>类型</th>
              <th>触发敏感内容</th>
              <th>命中拦截规则</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in activityLogs" :key="log.id">
              <td class="log-time">{{ log.time }}</td>
              <td class="log-session"><code>{{ log.sessionId }}</code></td>
              <td>
                <span :class="['type-badge', log.type === 'high_risk' ? 'badge-danger' : 'badge-warning']">
                  {{ log.type === 'high_risk' ? '高危情况' : '违规情况' }}
                </span>
              </td>
              <td class="log-content">“{{ log.content }}”</td>
              <td class="log-rule"><span class="rule-tag">{{ log.rule }}</span></td>
              <td>
                <button class="btn-primary-outline btn-xs" @click="$emit('view-audit-log', log)">查阅画像</button>
              </td>
            </tr>
            <tr v-if="activityLogs.length === 0">
              <td colspan="6" class="empty-row">🎉 暂无安全拦截或行为违规审计记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  stats: {
    type: Object,
    required: true
  },
  activityLogs: {
    type: Array,
    required: true
  }
})

defineEmits(['view-audit-log'])
</script>

<style scoped>
.overview-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
/* 统计卡片区 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 22px;
  background-color: var(--panel-bg);
  border-radius: var(--radius-md);
}
.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 22px;
}
.student-bg { background-color: var(--primary-light); color: var(--primary); }
.session-bg { background-color: var(--accent-light); color: var(--accent); }
.high-risk-bg { background-color: var(--warning-light); color: var(--warning); }
.violation-bg { background-color: rgba(243, 156, 18, 0.1); color: #F39C12; }
.stat-info {
  display: flex;
  flex-direction: column;
}
.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
}
.stat-value {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin-top: 5px;
}

/* 活动日志模块 */
.activity-section {
  padding: 25px;
  background-color: var(--panel-bg);
  border-radius: var(--radius-md);
}
.activity-header {
  margin-bottom: 20px;
}
.activity-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}
.audit-tip {
  font-size: 11px;
  color: var(--text-secondary);
  display: block;
  margin-top: 5px;
}
.table-container {
  overflow-x: auto;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 13.5px;
}
.data-table th, .data-table td {
  padding: 14px 12px;
  border-bottom: 1px solid var(--border-color);
}
.data-table th {
  font-weight: 600;
  color: var(--text-secondary);
}
.empty-row {
  text-align: center;
  padding: 30px;
  color: var(--text-secondary);
  font-style: italic;
}
.log-time {
  font-family: monospace;
  color: var(--text-secondary);
}
.log-session code {
  background-color: var(--primary-light);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-primary);
}
.log-content {
  font-style: italic;
  font-weight: 500;
  color: var(--text-primary);
}
.rule-tag {
  background-color: var(--border-color);
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11.5px;
  color: var(--text-primary);
}
.type-badge {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}
.badge-danger {
  background-color: var(--warning-light);
  color: var(--warning);
  border: 1px solid var(--warning);
}
.badge-warning {
  background-color: rgba(243, 156, 18, 0.1);
  color: #D35400;
  border: 1px solid rgba(243, 156, 18, 0.3);
}
.btn-xs {
  padding: 6px 12px;
  font-size: 11px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  transition: var(--transition-normal);
}
.btn-primary-outline {
  background-color: transparent;
  border: 1px solid var(--primary);
  color: var(--primary);
}
.btn-primary-outline:hover {
  background-color: var(--primary-light);
}
</style>
