<template>
  <div class="app-container">
    <header v-if="isAuthenticated" class="main-header">
      <div class="header-inner">
        <button class="logo" @click="router.push('/lobby')">
          Casino<span>Social</span>
        </button>

        <nav class="nav">
          <button
            v-for="grupo in GRUPOS"
            :key="grupo.id"
            class="nav-link"
            :class="{ activo: grupoAbierto === grupo.id }"
            @click="alternarGrupo(grupo.id)"
          >
            {{ grupo.titulo }}
          </button>
        </nav>

        <div class="header-derecha">
          <button class="saldo" @click="router.push('/lobby')">
            <span class="saldo-rotulo">Saldo</span>
            <span class="saldo-monto">${{ saldo }}</span>
          </button>
          <button @click="logout" class="btn-logout">Salir</button>
        </div>
      </div>

      <!-- El desplegable del grupo: lleva directo al juego sin pasar por el
           lobby, que es para lo que sirve tener una barra. -->
      <div v-if="grupoAbierto" class="desplegable" @click.self="grupoAbierto = null">
        <div class="desplegable-inner">
          <button
            v-for="juego in juegosDe(grupoAbierto)"
            :key="juego.id"
            class="desplegable-juego"
            @click="irA(juego)"
          >
            <span class="desplegable-icono">{{ juego.icono }}</span>
            <span class="desplegable-nombre">{{ juego.nombre }}</span>
          </button>
        </div>
      </div>
    </header>

    <main class="main-content" @click="grupoAbierto = null">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { GRUPOS, juegosDe } from '../shared/juegos';
import { olvidarSaldo, refrescarSaldo, saldo } from '../shared/saldo';

const router = useRouter();
const route = useRoute();

const grupoAbierto = ref(null);

const isAuthenticated = computed(() => {
  return route.path !== '/login' && !!localStorage.getItem('casino_token');
});

const alternarGrupo = (id) => {
  grupoAbierto.value = grupoAbierto.value === id ? null : id;
};

const irA = (juego) => {
  grupoAbierto.value = null;
  if (route.path !== juego.ruta) router.push(juego.ruta);
};

// El saldo se refresca al entrar a cada pantalla. Las jugadas lo actualizan
// por su cuenta llamando a refrescarSaldo(), así que esto es sólo el arranque.
watch(
  () => route.path,
  () => {
    grupoAbierto.value = null;
    if (isAuthenticated.value) refrescarSaldo();
  },
  { immediate: true },
);

const logout = () => {
  localStorage.removeItem('casino_token');
  olvidarSaldo();
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
  position: sticky;
  top: 0;
  z-index: 40;
  background: rgba(15, 16, 32, 0.82);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.header-inner {
  display: flex;
  align-items: center;
  gap: 22px;
  padding: 12px 26px;
  max-width: var(--ancho-maximo, 1680px);
  margin: 0 auto;
}

.logo {
  background: transparent;
  border: none;
  color: var(--text-main, #fff);
  font-size: 1.3rem;
  font-weight: 700;
  letter-spacing: -1px;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
}

.logo span {
  color: var(--primary);
}

.nav {
  display: flex;
  gap: 4px;
  flex: 1;
}

.nav-link {
  padding: 7px 13px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--text-muted, rgba(255, 255, 255, 0.6));
  cursor: pointer;
  font-size: 0.83rem;
  white-space: nowrap;
}

.nav-link:hover,
.nav-link.activo {
  background: rgba(255, 255, 255, 0.07);
  color: var(--text-main, #fff);
}

.header-derecha {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.saldo {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
  padding: 5px 13px;
  border-radius: 9px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-main, #fff);
  cursor: pointer;
  line-height: 1.1;
}

.saldo-rotulo {
  font-size: 0.58rem;
  color: var(--text-muted, rgba(255, 255, 255, 0.55));
  text-transform: uppercase;
  letter-spacing: 0.6px;
}

.saldo-monto {
  font-size: 0.95rem;
  font-weight: 700;
}

.btn-logout {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: #fff;
  padding: 8px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: background 0.2s;
}

.btn-logout:hover {
  background: rgba(255, 255, 255, 0.1);
}

.desplegable {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(15, 16, 32, 0.95);
}

.desplegable-inner {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 12px 26px;
  max-width: var(--ancho-maximo, 1680px);
  margin: 0 auto;
}

.desplegable-juego {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 8px 13px;
  border-radius: 9px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-main, #fff);
  cursor: pointer;
  font-size: 0.82rem;
}

.desplegable-juego:hover {
  border-color: var(--primary);
  background: rgba(139, 92, 246, 0.12);
}

.desplegable-icono {
  font-size: 1.05rem;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
}

@media (max-width: 760px) {
  .header-inner {
    flex-wrap: wrap;
    gap: 12px;
    padding: 10px 16px;
  }

  .nav {
    order: 3;
    /* flex-basis y no width: la regla de arriba pone `flex: 1`, que es
       `flex-basis: 0%`, y en un contenedor flex eso le gana al width. Con
       width solo, la barra no envolvia y los links se salian de la pantalla. */
    flex: 1 0 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .nav::-webkit-scrollbar {
    display: none;
  }

  .saldo-rotulo {
    display: none;
  }
}
</style>
