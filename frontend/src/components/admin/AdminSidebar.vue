<template>
  <aside class="admin-sidebar card-panel">
    <nav class="sidebar-nav">
      <button 
        v-for="menu in menus" 
        :key="menu.id"
        :class="['nav-item', { active: activeMenu === menu.id }]"
        @click="$emit('update:activeMenu', menu.id)"
      >
        <span class="nav-icon">{{ menu.icon }}</span>
        <span class="nav-text">{{ menu.label }}</span>
      </button>
    </nav>
    <div class="sidebar-footer">
      <p>🔒 心理档案受物理脱敏保护</p>
      <p>版本 v1.0.0 (MVP)</p>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  activeMenu: {
    type: String,
    required: true
  },
  menus: {
    type: Array,
    required: true
  }
})

defineEmits(['update:activeMenu'])
</script>

<style scoped>
.admin-sidebar {
  width: 240px;
  padding: 25px 15px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background-color: var(--panel-bg);
  border-radius: var(--radius-md);
}
.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 15px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  transition: var(--transition-normal);
}
.nav-item:hover {
  background-color: var(--primary-light);
  color: var(--primary-hover);
}
.nav-item.active {
  background-color: var(--primary-light);
  color: var(--primary-hover);
  border-left: 4px solid var(--primary);
  padding-left: 11px;
}
.nav-icon {
  font-size: 16px;
}
.sidebar-footer {
  text-align: center;
  font-size: 11px;
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  gap: 5px;
}
</style>
