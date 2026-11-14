<template>
  <div class="mines-page">
    <div class="glass-panel header-row">
      <button class="btn-back" @click="router.push('/lobby')">← Volver al Lobby</button>
    </div>

    <div class="main-layout">
      <aside class="glass-panel side-panel">
        <h2 class="titulo">Mines 💣</h2>

        <div class="campo">
          <label>Apuesta</label>
          <div class="bet-controls">
            <button :disabled="jugando" @click="ajustarApuesta(-5)">−</button>
            <span class="bet-display">${{ apuesta.toFixed(2) }}</span>
            <button :disabled="jugando" @click="ajustarApuesta(5)">+</button>
          </div>
        </div>

        <div class="campo">
          <label>Minas: <strong>{{ minas }}</strong></label>
          <input
            v-model.number="minas"
            type="range"
            min="1"
            max="24"
            :disabled="jugando"
          />
          <p class="ayuda">
            Más minas pagan más, pero el primer acierto es más difícil.
          </p>
        </div>

        <button
          v-if="!jugando"
          class="btn-principal"
          :disabled="cargando || apuesta > parseFloat(balance)"
          @click="empezar"
        >
          {{ cargando ? 'Repartiendo…' : 'EMPEZAR' }}
        </button>

        <button
          v-else
          class="btn-cobrar"
          :disabled="cargando || !grilla.destapadas.length"
          @click="cobrar"
        >
          <span v-if="!grilla.destapadas.length">Destapá una casilla</span>
          <span v-else>COBRAR ${{ Number(grilla.premio_actual).toFixed(2) }}</span>
        </button>

        <div v-if="jugando" class="marcadores">
          <div class="marcador">
            <span class="etiqueta">Ahora</span>
            <strong>{{ Number(grilla.multiplicador).toFixed(2) }}×</strong>
          </div>
          <div v-if="grilla.proximo_multiplicador" class="marcador">
            <span class="etiqueta">Si acertás</span>
            <strong class="proximo">
              {{ Number(grilla.proximo_multiplicador).toFixed(2) }}×
            </strong>
          </div>
        </div>

        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

        <FairnessPanel
          class="mines-fairness"
          :server-seed-hash="semilla.server_seed_hash"
          :client-seed="semilla.client_seed"
          :nonce="semilla.nonce"
          :server-seed="seedRevelado"
          :can-rotate="!jugando"
          :rotating="rotando"
          nonce-label="Grillas con esta semilla"
          help-text="Las minas quedan puestas antes de tu primer destape. Al rotar la semilla se revela el seed y podés comprobar que la mina ya estaba ahí. No se puede rotar con una grilla abierta: el seed es el mapa."
          formula='minas = las primeras N de mezclar([0..24], HMAC_SHA256(server_seed, "client_seed:nonce:i"))'
          @rotate="rotarSemilla"
        />
      </aside>

      <main class="glass-panel tablero-panel">
        <div v-if="resultado" class="banner" :class="resultado.tipo">
          {{ resultado.texto }}
        </div>

        <div class="grilla">
          <button
            v-for="casilla in 25"
            :key="casilla"
            class="casilla"
            :class="claseDeCasilla(casilla - 1)"
            :disabled="!jugando || cargando || estaDestapada(casilla - 1)"
            @click="destapar(casilla - 1)"
          >
            <span v-if="esMina(casilla - 1)">💣</span>
            <span v-else-if="estaDestapada(casilla - 1)">💎</span>
          </button>
        </div>

        <p v-if="!jugando && !resultado" class="pie">
          Elegí la apuesta y cuántas minas querés, y empezá.
        </p>
        <p v-else-if="!jugando" class="pie">
          <button class="btn-otra" @click="limpiar">Jugar otra</button>
        </p>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import confetti from 'canvas-confetti';
import api from '../shared/api';
import { fijarSaldo } from '../shared/saldo';
import FairnessPanel from '../widgets/FairnessPanel.vue';

const router = useRouter();
const balance = ref('0.00');
const cargando = ref(false);
const errorMsg = ref('');

const apuesta = ref(10);
const minas = ref(3);
const grilla = ref(null);
const resultado = ref(null);

const semilla = ref({ server_seed_hash: null, client_seed: null, nonce: 0 });
const seedRevelado = ref(null);
const rotando = ref(false);

const jugando = computed(() => grilla.value?.status === 'ACTIVE');

const estaDestapada = (casilla) => !!grilla.value?.destapadas.includes(casilla);
const esMina = (casilla) => !!grilla.value?.minas_en?.includes(casilla);

const claseDeCasilla = (casilla) => ({
  destapada: estaDestapada(casilla) && !esMina(casilla),
  mina: esMina(casilla),
  // La que tocó para perder: se marca distinto de las que se revelan al final.
  fatal: esMina(casilla) && estaDestapada(casilla),
});

const ajustarApuesta = (delta) => {
  apuesta.value = Math.max(1, Math.min(500, apuesta.value + delta));
};

const cargarSaldo = async () => {
  try {
    const res = await api.get('/wallet/balance');
    balance.value = parseFloat(res.data.balance).toFixed(2);
    fijarSaldo(balance.value);
  } catch {
    // El saldo se vuelve a pedir en cada jugada.
  }
};

const cargarSemilla = async () => {
  try {
    const res = await api.get('/games/mines/semilla');
    semilla.value = res.data;
  } catch {
    // Si falla, el panel queda en guiones: no bloquea el juego.
  }
};

// La apuesta se debita al empezar: si el jugador se fue con la grilla abierta,
// esa grilla lo está esperando y hay que devolvérsela.
const retomarGrilla = async () => {
  try {
    const res = await api.get('/games/mines/activa');
    if (res.data) grilla.value = res.data;
  } catch {
    // Si falla, se ve la pantalla de empezar.
  }
};

onMounted(async () => {
  await Promise.all([cargarSaldo(), cargarSemilla(), retomarGrilla()]);
});

const aplicar = (datos) => {
  grilla.value = datos;
  semilla.value = {
    server_seed_hash: datos.server_seed_hash,
    client_seed: datos.client_seed,
    nonce: datos.nonce,
  };
};

const empezar = async () => {
  cargando.value = true;
  errorMsg.value = '';
  resultado.value = null;
  seedRevelado.value = null;

  try {
    const res = await api.post('/games/mines/empezar', {
      bet_amount: apuesta.value.toFixed(2),
      minas: minas.value,
    });
    aplicar(res.data);
    await cargarSaldo();
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo empezar';
  } finally {
    cargando.value = false;
  }
};

const destapar = async (casilla) => {
  cargando.value = true;
  errorMsg.value = '';

  try {
    const res = await api.post('/games/mines/destapar', { casilla });
    aplicar(res.data);

    if (res.data.status !== 'ACTIVE') {
      await cerrar(res.data);
    }
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo destapar';
  } finally {
    cargando.value = false;
  }
};

const cobrar = async () => {
  cargando.value = true;
  errorMsg.value = '';

  try {
    const res = await api.post('/games/mines/cobrar');
    aplicar(res.data);
    await cerrar(res.data);
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo cobrar';
  } finally {
    cargando.value = false;
  }
};

const cerrar = async (datos) => {
  await cargarSaldo();

  if (datos.status === 'BUSTED') {
    resultado.value = { tipo: 'perdio', texto: '💣 Tocaste una mina' };
    return;
  }

  const ganancia = Number(datos.net_profit);
  resultado.value = {
    tipo: 'gano',
    texto: `💎 Cobraste $${Number(datos.payout).toFixed(2)} (${ganancia >= 0 ? '+' : ''}${ganancia.toFixed(2)})`,
  };

  if (ganancia > 0) {
    confetti({ particleCount: 80, spread: 70, origin: { y: 0.6 } });
  }
};

const limpiar = () => {
  grilla.value = null;
  resultado.value = null;
};

const rotarSemilla = async () => {
  rotando.value = true;
  try {
    const res = await api.post('/games/mines/semilla/rotar', {});
    seedRevelado.value = res.data.revelada.server_seed;
    semilla.value = res.data.activa;
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo rotar la semilla';
  } finally {
    rotando.value = false;
  }
};
</script>

<style scoped>
.mines-page {
  padding: 20px;
  max-width: 1100px;
  margin: 0 auto;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  margin-bottom: 18px;
}

.btn-back {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.9rem;
}

.btn-back:hover {
  color: var(--primary);
}

.balance {
  font-weight: 700;
}

.main-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 18px;
  align-items: start;
}

.side-panel,
.tablero-panel {
  padding: 18px;
}

.titulo {
  margin: 0 0 16px;
  font-size: 1.3rem;
}

.campo {
  margin-bottom: 16px;
}

.campo label {
  display: block;
  color: var(--text-muted);
  font-size: 0.8rem;
  margin-bottom: 6px;
}

.campo input[type='range'] {
  width: 100%;
}

.ayuda {
  margin: 6px 0 0;
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.35;
}

.bet-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bet-controls button {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: transparent;
  color: var(--text-main);
  cursor: pointer;
  font-size: 1rem;
}

.bet-controls button:disabled {
  opacity: 0.4;
  cursor: default;
}

.bet-display {
  flex: 1;
  text-align: center;
  font-weight: 700;
}

.btn-principal,
.btn-cobrar {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 10px;
  font-weight: 700;
  cursor: pointer;
  font-size: 0.95rem;
}

.btn-principal {
  background: var(--primary);
  color: #fff;
}

.btn-cobrar {
  background: var(--accent-green, #22c55e);
  color: #06230f;
}

.btn-principal:disabled,
.btn-cobrar:disabled {
  opacity: 0.45;
  cursor: default;
}

.marcadores {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}

.marcador {
  flex: 1;
  background: rgba(0, 0, 0, 0.22);
  border-radius: 10px;
  padding: 8px 10px;
  text-align: center;
}

.marcador .etiqueta {
  display: block;
  font-size: 0.68rem;
  color: var(--text-muted);
}

.marcador strong {
  font-size: 1.05rem;
}

.marcador .proximo {
  color: var(--accent-green, #22c55e);
}

.error-msg {
  margin-top: 12px;
  color: #f87171;
  font-size: 0.8rem;
}

.mines-fairness {
  margin-top: 18px;
}

.grilla {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
  max-width: 460px;
  margin: 0 auto;
}

.casilla {
  aspect-ratio: 1;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  font-size: 1.6rem;
  cursor: pointer;
  transition: transform 0.08s, background 0.15s;
}

.casilla:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
  transform: translateY(-2px);
}

.casilla:disabled {
  cursor: default;
}

.casilla.destapada {
  background: rgba(34, 197, 94, 0.18);
  border-color: rgba(34, 197, 94, 0.45);
}

.casilla.mina {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.3);
}

.casilla.fatal {
  background: rgba(239, 68, 68, 0.4);
  border-color: #ef4444;
}

.banner {
  text-align: center;
  padding: 10px;
  border-radius: 10px;
  font-weight: 700;
  margin-bottom: 16px;
}

.banner.gano {
  background: rgba(34, 197, 94, 0.18);
  color: var(--accent-green, #22c55e);
}

.banner.perdio {
  background: rgba(239, 68, 68, 0.18);
  color: #f87171;
}

.pie {
  text-align: center;
  margin: 18px 0 0;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.btn-otra {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.25);
  color: var(--text-main);
  border-radius: 8px;
  padding: 7px 16px;
  cursor: pointer;
}

.btn-otra:hover {
  border-color: var(--primary);
  color: var(--primary);
}

@media (max-width: 860px) {
  .main-layout {
    grid-template-columns: 1fr;
  }
}
</style>
