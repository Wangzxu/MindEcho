<template>
  <div class="students-container">
    <div class="users-list-header">
      <h2>学生账户与心理画像管理</h2>
      <button class="btn-primary" @click="$emit('refresh')">🔄 刷新列表</button>
    </div>

    <div class="table-container card-panel">
      <table class="data-table">
        <thead>
          <tr>
            <th>用户ID</th>
            <th>用户名 / 学号</th>
            <th>状态</th>
            <th>角色</th>
            <th>心理画像摘要</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.id }}</td>
            <td><strong>{{ user.username }}</strong></td>
            <td>
              <span :class="['status-badge', user.is_active ? 'active' : 'inactive']">
                {{ user.is_active ? '已激活' : '已停用' }}
              </span>
            </td>
            <td><span class="role-badge">{{ user.role }}</span></td>
            <td class="profile-preview">
              <span v-if="user.profile_summary" class="profile-tag">
                {{ user.profile_summary }}
              </span>
              <span v-else class="empty-tag">暂无画像特征</span>
            </td>
            <td>
              <div class="action-buttons">
                <button class="btn-accent btn-xs" @click="$emit('view-user-profile', user)">🔍 查阅画像</button>
                <button 
                  :class="['btn-xs', user.is_active ? 'btn-warning-outline' : 'btn-primary-outline']"
                  @click="$emit('toggle-user-status', user)"
                >
                  {{ user.is_active ? '停用' : '激活' }}
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="users.length === 0">
            <td colspan="6" class="empty-row">👥 当前暂无已注册学生账号</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({
  users: {
    type: Array,
    required: true
  }
})

defineEmits(['view-user-profile', 'toggle-user-status', 'refresh'])
</script>

<style scoped>
.students-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
/* 学生管理列表 */
.users-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.users-list-header h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
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
.status-badge.inactive {
  background-color: var(--warning-light);
  color: var(--warning);
}
.role-badge {
  font-size: 12px;
  background-color: var(--border-color);
  padding: 3px 8px;
  border-radius: 4px;
  color: var(--text-primary);
}
.profile-preview {
  max-width: 250px;
}
.profile-tag {
  background-color: var(--primary-light);
  color: var(--primary-hover);
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 4px;
  display: inline-block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.empty-tag {
  color: var(--text-secondary);
  font-style: italic;
  font-size: 12px;
}
.action-buttons {
  display: flex;
  gap: 8px;
}
.btn-xs {
  padding: 6px 12px;
  font-size: 11px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  transition: var(--transition-normal);
}
.btn-accent {
  background-color: var(--accent);
  color: #FFFFFF;
}
.btn-accent:hover {
  background-color: var(--accent-hover);
}
.btn-warning-outline {
  background-color: transparent;
  border: 1px solid var(--warning);
  color: var(--warning);
}
.btn-warning-outline:hover {
  background-color: var(--warning-light);
}
.btn-primary-outline {
  background-color: transparent;
  border: 1px solid var(--primary);
  color: var(--primary);
}
.btn-primary-outline:hover {
  background-color: var(--primary-light);
}
.btn-primary {
  background-color: var(--primary);
  color: #FFFFFF;
  border: none;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition-normal);
}
.btn-primary:hover {
  background-color: var(--primary-hover);
}
</style>
