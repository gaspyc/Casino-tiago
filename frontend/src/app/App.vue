<template>
  <div class="app-container">
    <header v-if="isAuthenticated" class="glass-panel main-header">
      <div class="logo">Casino<span>tiago</span></div>
      <button @click="logout" class="btn-logout">Cerrar Sesión</button>
    </header>
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';

const router = useRouter();
const route = useRoute();

const isAuthenticated = computed(() => {
  return route.path !== '/login' && !!localStorage.getItem('casino_token');
});

const logout = () => {
  localStorage.removeItem('casino_token');
  router.push('/login');
};
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  margin: 16px;
  border-radius: 12px;
}

.logo {
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -1px;
}

.logo span {
  color: var(--primary);
}

.btn-logout {
  background: transparent;
  border: 1px solid rgba(255,255,255,0.2);
  color: white;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-logout:hover {
  background: rgba(255,255,255,0.1);
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
}
</style>
