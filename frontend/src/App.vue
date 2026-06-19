<template>
  <router-view v-slot="{ Component }">
    <transition name="fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>

<script setup>
// 主入口视图，由 Vue Router 接管
</script>

<style>
/* 全局样式已在 style.css 中定义 */
</style>
