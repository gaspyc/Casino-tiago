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

    <main class="main-content" @click="cerrarMenus">
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
import api from '../shared/api';
import { GRUPOS, juegosDe } from '../shared/juegos';
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

const alternarGrupo = (id) => {
  grupoAbierto.value = grupoAbierto.value === id ? null : id;
  menuCuenta.value = null;
};

const cerrarMenus = () => {
  grupoAbierto.value = null;
  menuCuenta.value = null;
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

const irA = (juego) => {
  grupoAbierto.value = null;
  if (route.path !== juego.ruta) router.push(juego.ruta);
};

// El saldo se refresca al entrar a cada pantalla. Las jugadas lo actualizan
// por su cuenta llamando a refrescarSaldo(), así que esto es sólo el arranque.
watch(
  () => route.path,
  () => {
    cerrarMenus();
    if (!isAuthenticated.value) return;

    refrescarSaldo();
    if (!usuario.value) {
      api.get('/users/me').then((res) => {
        usuario.value = res.data;
      }).catch(() => {});
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

.main-header {
  position: sticky;
  top: 0;
  z-index: 40;
  background: rgba(15, 16, 32, 0.82);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.header-inner {
  position: relative;
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

/* El saldo y la via para depositar, juntos: el saldo es la razon por la que
   abris la billetera, asi que el boton va pegado al numero y no en una
   tarjeta aparte abajo. Eso ademas deja depositar desde adentro de un juego,
   que es justo cuando te quedas sin. */
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
  top: calc(100% - 4px);
  right: 26px;
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

  .btn-cuenta {
    max-width: 88px;
  }

  /* En telefono el logo, la billetera y la cuenta no entran en una fila con
     la palabra "Depositar" completa. Se achica a un "+", que es como lo
     resuelven los lobbies reales, y asi el encabezado baja de tres filas a
     dos: una de cuenta y otra de secciones. */
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

  .logo {
    font-size: 1.08rem;
  }

  .saldo-monto {
    font-size: 0.86rem;
    margin-right: 6px;
  }
}
</style>
