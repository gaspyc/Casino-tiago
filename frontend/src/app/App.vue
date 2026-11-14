<template>
  <div class="app-container" :class="{ 'con-barra': isAuthenticated }">
    <!-- Arriba queda solo identidad y plata. La navegacion se fue a la barra
         lateral: el topbar llevaba logo, tres secciones, billetera y cuenta,
         y eso es demasiado trabajo para una sola fila. -->
    <header v-if="isAuthenticated" class="topbar">
      <button class="logo" @click="ir('/lobby')">
        Casino<span>Social</span>
      </button>

      <div class="topbar-derecha">
        <div class="billetera">
          <span class="saldo-monto">${{ saldo }}</span>
          <button class="btn-depositar" @click="abrirModal('deposito')">
            <span class="depositar-largo">Depositar</span>
            <span class="depositar-corto" aria-hidden="true">+</span>
          </button>
        </div>

        <button class="btn-cuenta" @click="menuCuenta = !menuCuenta">
          {{ usuario?.username || 'Cuenta' }}
        </button>

        <div v-if="menuCuenta" class="menu-cuenta">
          <button @click="abrirModal('retiro')">Retirar</button>
          <button @click="logout">Cerrar sesión</button>
        </div>
      </div>
    </header>

    <div class="cuerpo">
      <!-- La misma navegacion en los dos lados: lateral en pantalla grande,
           abajo en telefono. Son los mismos destinos y el mismo contenido,
           cambia donde se apoya la mano. -->
      <nav v-if="isAuthenticated" class="barra">
        <button
          class="barra-item"
          :class="{ activo: route.path === '/lobby' && !grupoAbierto }"
          @click="ir('/lobby')"
        >
          <span class="barra-icono">🏠</span>
          <span class="barra-texto">Inicio</span>
          <span class="barra-texto-corto">Inicio</span>
        </button>

        <div v-for="grupo in GRUPOS" :key="grupo.id" class="barra-grupo">
          <button
            class="barra-item"
            :class="{ activo: grupoAbierto === grupo.id || grupoDelJuegoActual === grupo.id }"
            :style="{ '--acento': grupo.color }"
            @click="alternarGrupo(grupo.id)"
          >
            <span class="barra-icono">{{ grupo.icono }}</span>
            <span class="barra-texto">{{ grupo.titulo }}</span>
            <span class="barra-texto-corto">{{ grupo.tituloCorto }}</span>
          </button>

          <div v-if="grupoAbierto === grupo.id" class="barra-juegos">
            <button
              v-for="juego in juegosDe(grupo.id)"
              :key="juego.id"
              class="barra-juego"
              :class="{ activo: route.path === juego.ruta }"
              :style="{ '--color-juego': juego.color }"
              @click="irAlJuego(juego)"
            >
              <span class="barra-juego-icono">{{ juego.icono }}</span>
              <span>{{ juego.nombre }}</span>
            </button>
          </div>
        </div>
      </nav>

      <main class="main-content" @click="cerrarMenus">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <!-- En telefono la lista de juegos de un grupo no entra en la barra de
         abajo, asi que se abre como hoja sobre el contenido. -->
    <div v-if="grupoAbierto" class="velo" @click="grupoAbierto = null"></div>

    <div v-if="modal" class="modal-overlay" @click.self="cerrarModal">
      <div class="glass-panel modal">
        <h3>{{ modal === 'deposito' ? 'Depositar fondos' : 'Retirar fondos' }}</h3>
        <input
          v-model.number="montoTx"
          type="number"
          placeholder="Monto"
          min="1"
          step="0.01"
          @keyup.enter="procesarTransaccion"
        />
        <div v-if="errorTx" class="tx-error">{{ errorTx }}</div>
        <div class="modal-actions">
          <button class="btn-cancelar" @click="cerrarModal">Cancelar</button>
          <button class="btn-confirmar" :disabled="cargandoTx" @click="procesarTransaccion">
            {{ cargandoTx ? 'Procesando…' : 'Confirmar' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import api from '../shared/api';
import { GRUPOS, JUEGOS, juegosDe } from '../shared/juegos';
import { olvidarSaldo, refrescarSaldo, saldo } from '../shared/saldo';

const router = useRouter();
const route = useRoute();

const grupoAbierto = ref(null);
const menuCuenta = ref(null);
const usuario = ref(null);

const modal = ref(null);
const montoTx = ref('');
const cargandoTx = ref(false);
const errorTx = ref('');

const isAuthenticated = computed(() => {
  return route.path !== '/login' && !!localStorage.getItem('casino_token');
});

// Para marcar la seccion del juego en el que estás parado, no sólo la que
// abriste a mano.
const grupoDelJuegoActual = computed(() => {
  const juego = JUEGOS.find((j) => j.ruta === route.path);
  return juego ? juego.grupo : null;
});

const cerrarMenus = () => {
  grupoAbierto.value = null;
  menuCuenta.value = null;
};

const ir = (ruta) => {
  cerrarMenus();
  if (route.path !== ruta) router.push(ruta);
};

const alternarGrupo = (id) => {
  grupoAbierto.value = grupoAbierto.value === id ? null : id;
  menuCuenta.value = null;
};

const irAlJuego = (juego) => {
  cerrarMenus();
  if (route.path !== juego.ruta) router.push(juego.ruta);
};

const abrirModal = (cual) => {
  modal.value = cual;
  montoTx.value = '';
  errorTx.value = '';
  menuCuenta.value = null;
};

const cerrarModal = () => {
  modal.value = null;
  montoTx.value = '';
  errorTx.value = '';
};

const procesarTransaccion = async () => {
  if (!montoTx.value || montoTx.value <= 0) {
    errorTx.value = 'Ingresá un monto válido';
    return;
  }

  cargandoTx.value = true;
  errorTx.value = '';

  try {
    await api.post(
      modal.value === 'deposito' ? '/wallet/deposit' : '/wallet/withdraw',
      { amount: montoTx.value },
    );
    await refrescarSaldo();
    cerrarModal();
  } catch (e) {
    errorTx.value = e.response?.data?.detail || 'Error en la transacción';
  } finally {
    cargandoTx.value = false;
  }
};

watch(
  () => route.path,
  () => {
    cerrarMenus();
    if (!isAuthenticated.value) return;

    refrescarSaldo();
    if (!usuario.value) {
      api
        .get('/users/me')
        .then((res) => {
          usuario.value = res.data;
        })
        .catch(() => {});
    }
  },
  { immediate: true },
);

const logout = () => {
  localStorage.removeItem('casino_token');
  olvidarSaldo();
  usuario.value = null;
  cerrarMenus();
  router.push('/login');
};
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* ------------------------------ arriba ------------------------------ */

.topbar {
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 11px 22px;
  background: rgba(15, 16, 32, 0.86);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.logo {
  background: transparent;
  border: none;
  color: var(--text-main, #fff);
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -1px;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
}

.logo span {
  color: var(--primary);
}

.topbar-derecha {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
}

.billetera {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 3px 3px 3px 13px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
}

.saldo-monto {
  font-size: 0.95rem;
  font-weight: 700;
  margin-right: 8px;
  white-space: nowrap;
}

.btn-depositar {
  padding: 7px 14px;
  border-radius: 8px;
  border: none;
  background: var(--accent-green, #22c55e);
  color: #06230f;
  font-weight: 700;
  font-size: 0.78rem;
  cursor: pointer;
}

.btn-depositar:hover {
  filter: brightness(1.08);
}

.depositar-corto {
  display: none;
}

.btn-cuenta {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: #fff;
  padding: 8px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.8rem;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-cuenta:hover {
  background: rgba(255, 255, 255, 0.1);
}

.menu-cuenta {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  display: flex;
  flex-direction: column;
  min-width: 170px;
  padding: 5px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(20, 21, 40, 0.98);
  z-index: 50;
}

.menu-cuenta button {
  padding: 9px 12px;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--text-main, #fff);
  text-align: left;
  cursor: pointer;
  font-size: 0.82rem;
}

.menu-cuenta button:hover {
  background: rgba(255, 255, 255, 0.07);
}

/* ------------------------------ la barra ------------------------------ */

.cuerpo {
  flex: 1;
  display: flex;
  align-items: stretch;
  min-height: 0;
}

.barra {
  position: sticky;
  top: 55px;
  align-self: flex-start;
  width: 212px;
  flex-shrink: 0;
  max-height: calc(100vh - 55px);
  overflow-y: auto;
  padding: 14px 10px;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
}

.barra-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 11px;
  border: none;
  border-radius: 9px;
  background: transparent;
  color: var(--text-muted, rgba(255, 255, 255, 0.62));
  cursor: pointer;
  font-size: 0.85rem;
  text-align: left;
}

.barra-item:hover {
  background: rgba(255, 255, 255, 0.055);
  color: var(--text-main, #fff);
}

.barra-item.activo {
  background: color-mix(in srgb, var(--acento, var(--primary)) 16%, transparent);
  color: var(--text-main, #fff);
  font-weight: 600;
}

.barra-texto-corto {
  display: none;
}

.barra-icono {
  font-size: 1rem;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

.barra-grupo {
  margin-top: 2px;
}

.barra-juegos {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin: 2px 0 6px;
  padding-left: 14px;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  margin-left: 20px;
}

.barra-juego {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 9px;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--text-muted, rgba(255, 255, 255, 0.6));
  cursor: pointer;
  font-size: 0.79rem;
  text-align: left;
}

.barra-juego:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-main, #fff);
}

.barra-juego.activo {
  color: var(--color-juego);
  font-weight: 600;
}

.barra-juego-icono {
  font-size: 0.95rem;
}

.main-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  position: relative;
}

.velo {
  display: none;
}

/* ------------------------------ el modal ------------------------------ */

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(5, 5, 15, 0.72);
  backdrop-filter: blur(3px);
}

.modal {
  width: 100%;
  max-width: 380px;
  padding: 26px;
}

.modal h3 {
  margin: 0 0 16px;
}

.modal input {
  width: 100%;
  padding: 11px 13px;
  border-radius: 9px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.04);
  color: #fff;
  font-size: 1rem;
}

.tx-error {
  margin-top: 10px;
  color: #f87171;
  font-size: 0.8rem;
}

.modal-actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.btn-cancelar,
.btn-confirmar {
  flex: 1;
  padding: 11px;
  border-radius: 9px;
  cursor: pointer;
  font-weight: 700;
  font-size: 0.85rem;
}

.btn-cancelar {
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: transparent;
  color: #fff;
}

.btn-confirmar {
  border: none;
  background: var(--primary);
  color: #fff;
}

.btn-confirmar:disabled {
  opacity: 0.5;
  cursor: default;
}

/* ------------------------------ telefono ------------------------------
   La misma barra, apoyada abajo: es donde llega el pulgar. Los juegos de un
   grupo no entran en una fila de cuatro, asi que se abren como hoja. */

@media (max-width: 860px) {
  .topbar {
    padding: 10px 14px;
  }

  .logo {
    font-size: 1.08rem;
  }

  .depositar-largo {
    display: none;
  }

  .depositar-corto {
    display: inline;
    font-size: 1.1rem;
    line-height: 1;
  }

  .btn-depositar {
    padding: 7px 13px;
  }

  .btn-cuenta {
    max-width: 92px;
  }

  .saldo-monto {
    font-size: 0.86rem;
    margin-right: 6px;
  }

  .cuerpo {
    display: block;
  }

  .barra {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    top: auto;
    z-index: 60;
    display: flex;
    width: auto;
    max-height: none;
    overflow: visible;
    padding: 6px 4px calc(6px + env(safe-area-inset-bottom, 0px));
    background: rgba(15, 16, 32, 0.96);
    backdrop-filter: blur(14px);
    border-right: none;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }

  .barra-grupo {
    flex: 1;
    margin-top: 0;
    min-width: 0;
  }

  .barra > .barra-item {
    flex: 1;
    min-width: 0;
  }

  .barra-item {
    flex-direction: column;
    gap: 3px;
    padding: 6px 2px;
    font-size: 0.62rem;
    text-align: center;
  }

  .barra-texto {
    display: none;
  }

  .barra-texto-corto {
    display: block;
    width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .barra-icono {
    font-size: 1.15rem;
    width: auto;
  }

  /* La hoja con los juegos del grupo, sobre el contenido y arriba de la
     barra de abajo. */
  .barra-juegos {
    position: fixed;
    left: 0;
    right: 0;
    /* Contra el viewport, no contra la barra: position fixed mide desde la
       ventana, asi que un 100% aca mandaba la hoja fuera de pantalla. */
    bottom: calc(64px + env(safe-area-inset-bottom, 0px));
    z-index: 61;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
    gap: 4px;
    margin: 0;
    padding: 12px 12px 14px;
    border-left: none;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px 16px 0 0;
    background: rgba(20, 21, 40, 0.99);
  }

  .velo {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 55;
    background: rgba(5, 5, 15, 0.55);
  }

  /* Que el contenido no quede tapado por la barra de abajo. */
  .main-content {
    padding-bottom: 72px;
  }
}
</style>
