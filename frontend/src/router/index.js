// -*- coding: utf-8 -*-
import { createRouter, createWebHistory } from 'vue-router'
import { getPayload } from '../composables/useAuth'
import Login from '../pages/Login.vue'
import Chat from '../pages/Chat.vue'
import Admin from '../pages/Admin.vue'

const routes = [
  { 
    path: '/', 
    redirect: '/login' 
  },
  { 
    path: '/login', 
    component: Login, 
    name: 'login' 
  },
  { 
    path: '/chat', 
    component: Chat, 
    name: 'chat', 
    meta: { requiresAuth: true, role: 'student' } 
  },
  { 
    path: '/admin', 
    component: Admin, 
    name: 'admin', 
    meta: { requiresAuth: true, role: 'admin' } 
  },
  { 
    path: '/:pathMatch(.*)*', 
    redirect: '/login' 
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 统一导航守卫拦截
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token');
  
  if (to.meta.requiresAuth) {
    if (!token) {
      next('/login');
      return;
    }
    const payload = getPayload(token);
    if (!payload) {
      localStorage.removeItem('token');
      next('/login');
      return;
    }
    
    const userRole = payload.role;
    // 角色不匹配拦截重定向
    if (to.meta.role && to.meta.role !== userRole) {
      if (userRole === 'admin') {
        next('/admin');
      } else {
        next('/chat');
      }
      return;
    }
  } else if (to.name === 'login' && token) {
    // 已登录状态直接跳转入核心工作区
    const payload = getPayload(token);
    if (payload) {
      if (payload.role === 'admin') {
        next('/admin');
      } else {
        next('/chat');
      }
      return;
    }
  }
  next();
})

export default router
