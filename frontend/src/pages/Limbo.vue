<template>
  <div class="limbo-page">
    <div class="glass-panel header-row">
      <button class="btn-back" @click="router.push('/lobby')">← Volver al Lobby</button>
    </div>

    <div class="main-layout">
      <aside class="glass-panel side-panel">
        <h2 class="titulo">Limbo 🚀</h2>
        <p class="bajada">
          El juego sortea un multiplicador. Si llega al tuyo, cobrás el tuyo.
          Es el crash de un jugador y sin esperar.
        </p>

        <div class="campo">
          <label>Apuesta</label>
          <div class="bet-controls">
            <button :disabled="cargando" @click="ajustarApuesta(-5)">−</button>
            <span class="bet-display">${{ apuesta.toFixed(2) }}</span>
            <button :disabled="cargando" @click="ajustarApuesta(5)">+</button>
          </div>
        </div>

        <div class="campo">
          <label>Tu objetivo</label>
          <div class="objetivo-fila">
            <input
              v-model="objetivoTexto"
              type="text"
              inputmode="decimal"
              :disabled="cargando"
              @blur="normalizarObjetivo"
            />
            <span class="equis">×</span>
          </div>
          <div class="atajos">
            <button
              v-for="valor in ATAJOS"
              :key="valor"
              :disabled="cargando"
              @click="ponerObjetivo(valor)"
            >
              {{ valor }}×
            </button>
          </div>
        </div>

        <div class="cotizacion">
          <div class="dato">
            <span>Chance</span>
            <strong>{{ chance }}%</strong>
          </div>
          <div class="dato">
            <span>Si ganás</span>
            <strong class="pago">${{ siGanas }}</strong>
          </div>
        </div>

        <button
          class="btn-principal"
          :disabled="cargando || apuesta > parseFloat(balance) || !cotizacion"
          @click="apostar"
        >
          {{ cargando ? 'Sorteando…' : 'APOSTAR' }}
        </button>

        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
      </aside>

      <main class="glass-panel panel-mesa">
        <div class="sorteado" :class="claseResultado">
          {{ ultima ? ultima.sorteado + '×' : '—' }}
        </div>

        <p v-if="ultima" class="veredicto" :class="claseResultado">
          <template v-if="ultima.gano">
            Llegó a tu {{ ultima.objetivo }}× · cobrás ${{ ultima.payout }}
          </template>
          <template v-else>
            Se quedó abajo de tu {{ ultima.objetivo }}×
          </template>
        </p>
        <p v-else class="veredicto apagado">Elegí tu objetivo y apostá.</p>

        <div v-if="historial.length" class="historial">
          <span
            v-for="(tiro, indice) in historial"
            :key="indice"
            class="ficha"
            :class="{ gano: tiro.gano }"
          >
            {{ tiro.sorteado }}×
          </span>
        </div>

        <p class="nota">
          Cuanto más alto el objetivo, menos seguido llega — y el retorno es el
          mismo para todos: {{ rtpTexto }}.
        </p>
      </main>
    </div>

    <FairnessPanel
      v-if="semilla"
      class="limbo-fairness"
      :server-seed-hash="semilla.server_seed_hash"
      :client-seed="semilla.client_seed"
      :nonce="semilla.nonce"
      :server-seed="seedRevelado"
      :can-rotate="!cargando"
      :rotating="rotando"
      nonce-label="Sorteos con esta semilla"
      help-text="El multiplicador sorteado sale de un seed comprometido antes de que apuestes, con la misma cuenta que usa el Crash. Al rotar la semilla se revela el seed y podés rehacer cada sorteo."
      formula='sorteado = truncar(0.99 / u, 2) con u = primeros 52 bits de HMAC_SHA256(server_seed, "client_seed:nonce")'
      @rotate="rotarSemilla"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import confetti from 'canvas-confetti';
import api from '../shared/api';
import { fijarSaldo } from '../shared/saldo';
import FairnessPanel from '../widgets/FairnessPanel.vue';

const ATAJOS = ['1.50', '2.00', '5.00', '10.00', '50.00'];

const router = useRouter();
const balance = ref('0.00');
const cargando = ref(false);
const rotando = ref(false);
const errorMsg = ref('');

const apuesta = ref(10);
const objetivoTexto = ref('2.00');

const limites = ref(null);
const cotizacion = ref(null);
const ultima = ref(null);
const historial = ref([]);
const semilla = ref(null);
const seedRevelado = ref(null);

const chance = computed(() =>
  cotizacion.value ? Number(cotizacion.value.chance).toFixed(2) : '—',
);

const siGanas = computed(() => {
  const objetivo = parseFloat(objetivoTexto.value);
  if (!cotizacion.value || Number.isNaN(objetivo)) return '0.00';
  return (apuesta.value * objetivo).toFixed(2);
});

const rtpTexto = computed(() => {
  if (!limites.value) return '99%';
  return (parseFloat(limites.value.rtp) * 100).toFixed(0) + '%';
});

const claseResultado = computed(() => {
  if (!ultima.value) return '';
  return ultima.value.gano ? 'gano' : 'perdio';
});

const ajustarApuesta = (delta) => {
  const tope = limites.value ? parseFloat(limites.value.apuesta_maxima) : 500;
  apuesta.value = Math.max(1, Math.min(tope, apuesta.value + delta));
};

const ponerObjetivo = (valor) => {
  objetivoTexto.value = valor;
};

const normalizarObjetivo = () => {
  const valor = parseFloat(objetivoTexto.value);
  if (Number.isNaN(valor)) {
    objetivoTexto.value = '2.00';
    return;
  }

  const min = limites.value ? parseFloat(limites.value.objetivo_minimo) : 1.01;
  const max = limites.value ? parseFloat(limites.value.objetivo_maximo) : 1000;
  objetivoTexto.value = Math.min(max, Math.max(min, valor)).toFixed(2);
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

const cargarLimites = async () => {
  try {
    const res = await api.get('/games/limbo/limites');
    limites.value = res.data;
  } catch {
    // Sin límites la pantalla igual funciona; el backend valida igual.
  }
};

const cargarSemilla = async () => {
  try {
    const res = await api.get('/games/limbo/semilla');
    semilla.value = res.data;
  } catch {
    semilla.value = null;
  }
};

// La chance la dice el servidor: la pantalla no la calcula para que no pueda
// quedar mostrando otra cosa que la que se liquida.
const cotizar = async () => {
  const valor = parseFloat(objetivoTexto.value);
  if (Number.isNaN(valor)) {
    cotizacion.value = null;
    return;
  }

  try {
    const res = await api.get('/games/limbo/cotizar', {
      params: { objetivo: valor.toFixed(2) },
    });
    cotizacion.value = res.data;
    errorMsg.value = '';
  } catch (e) {
    cotizacion.value = null;
    errorMsg.value = e.response?.data?.detail || '';
  }
};

watch(objetivoTexto, cotizar);

onMounted(async () => {
  await Promise.all([cargarSaldo(), cargarLimites(), cargarSemilla()]);
  normalizarObjetivo();
  await cotizar();
});

const apostar = async () => {
  cargando.value = true;
  errorMsg.value = '';

  try {
    const res = await api.post('/games/limbo/apostar', {
      bet_amount: apuesta.value.toFixed(2),
      objetivo: parseFloat(objetivoTexto.value).toFixed(2),
    });

    ultima.value = res.data;
    historial.value = [res.data, ...historial.value].slice(0, 12);
    semilla.value = {
      server_seed_hash: res.data.server_seed_hash,
      client_seed: res.data.client_seed,
      nonce: res.data.nonce + 1,
    };

    await cargarSaldo();

    if (res.data.gano) {
      confetti({ particleCount: 70, spread: 70, origin: { y: 0.6 } });
    }
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo apostar';
  } finally {
    cargando.value = false;
  }
};

const rotarSemilla = async (clientSeed) => {
  rotando.value = true;
  try {
    const res = await api.post('/games/limbo/semilla/rotar', {
      client_seed: clientSeed || null,
    });
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
.limbo-page {
  padding: 20px;
  max-width: 1040px;
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
  grid-template-columns: 320px 1fr;
  gap: 18px;
  align-items: start;
}

.side-panel,
.panel-mesa {
  padding: 20px;
}

.titulo {
  margin: 0 0 8px;
  font-size: 1.35rem;
}

.bajada {
  color: var(--text-muted);
  font-size: 0.78rem;
  line-height: 1.45;
  margin: 0 0 18px;
}

.campo {
  margin-bottom: 16px;
}

.campo label {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 7px;
}

.bet-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.bet-controls button {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: transparent;
  color: var(--text-main);
  cursor: pointer;
  font-size: 1.05rem;
}

.bet-display {
  font-size: 1.15rem;
  font-weight: 700;
}

.objetivo-fila {
  display: flex;
  align-items: center;
  gap: 8px;
}

.objetivo-fila input {
  flex: 1;
  padding: 9px 11px;
  border-radius: 9px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-main);
  font-size: 1.05rem;
  font-weight: 700;
}

.equis {
  color: var(--text-muted);
  font-size: 1.05rem;
}

.atajos {
  display: flex;
  gap: 5px;
  margin-top: 8px;
}

.atajos button {
  flex: 1;
  padding: 5px 2px;
  border-radius: 7px;
  border: 1px solid rgba(255, 255, 255, 0.13);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.68rem;
}

.atajos button:hover {
  border-color: var(--primary);
  color: var(--text-main);
}

.cotizacion {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin: 18px 0;
  padding: 12px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.dato {
  text-align: center;
}

.dato span {
  display: block;
  font-size: 0.65rem;
  color: var(--text-muted);
  margin-bottom: 3px;
}

.dato strong {
  font-size: 0.95rem;
}

.dato .pago {
  color: var(--accent-green, #22c55e);
}

.btn-principal {
  width: 100%;
  padding: 13px;
  border: none;
  border-radius: 10px;
  background: var(--primary);
  color: #fff;
  font-weight: 700;
  font-size: 0.95rem;
  cursor: pointer;
}

.btn-principal:disabled {
  opacity: 0.45;
  cursor: default;
}

.error-msg {
  margin-top: 12px;
  color: #f87171;
  font-size: 0.8rem;
}

.panel-mesa {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 340px;
}

.sorteado {
  font-size: 4.2rem;
  font-weight: 800;
  letter-spacing: -2px;
  color: var(--text-muted);
  transition: color 0.2s;
}

.sorteado.gano {
  color: var(--accent-green, #22c55e);
}

.sorteado.perdio {
  color: #f87171;
}

.veredicto {
  margin: 6px 0 20px;
  font-size: 0.85rem;
  text-align: center;
}

.veredicto.apagado {
  color: var(--text-muted);
}

.historial {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
}

.ficha {
  padding: 4px 9px;
  border-radius: 7px;
  background: rgba(239, 68, 68, 0.16);
  color: #f87171;
  font-size: 0.72rem;
  font-weight: 600;
}

.ficha.gano {
  background: rgba(34, 197, 94, 0.16);
  color: var(--accent-green, #22c55e);
}

.nota {
  margin: 22px 0 0;
  max-width: 420px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.7rem;
  line-height: 1.5;
}

.limbo-fairness {
  margin-top: 18px;
}

@media (max-width: 880px) {
  .main-layout {
    grid-template-columns: 1fr;
  }
}
</style>
