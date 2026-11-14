<template>
  <div class="dice-page">
    <div class="glass-panel header-row">
      <button class="btn-back" @click="router.push('/lobby')">← Volver al Lobby</button>
    </div>

    <div class="main-layout">
      <aside class="glass-panel side-panel">
        <h2 class="titulo">Dice 🎯</h2>
        <p class="bajada">
          Sale un número de 0,00 a 99,99. Elegís el objetivo y el lado, y el
          pago sale de la chance que elegiste.
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
          <label>Lado</label>
          <div class="lados">
            <button
              :class="{ activo: lado === 'menor' }"
              :disabled="cargando"
              @click="lado = 'menor'"
            >
              Menor que
            </button>
            <button
              :class="{ activo: lado === 'mayor' }"
              :disabled="cargando"
              @click="lado = 'mayor'"
            >
              Mayor que
            </button>
          </div>
        </div>

        <div class="campo">
          <label>
            Objetivo: <strong>{{ objetivo.toFixed(2) }}</strong>
          </label>
          <input
            v-model.number="objetivo"
            type="range"
            :min="minObjetivo"
            :max="maxObjetivo"
            step="0.01"
            :disabled="cargando"
          />
        </div>

        <div class="cotizacion">
          <div class="dato">
            <span>Chance</span>
            <strong>{{ chance }}%</strong>
          </div>
          <div class="dato">
            <span>Paga</span>
            <strong class="pago">{{ multiplicadorCorto }}×</strong>
          </div>
          <div class="dato">
            <span>Si ganás</span>
            <strong>${{ siGanas }}</strong>
          </div>
        </div>

        <button
          class="btn-principal"
          :disabled="cargando || apuesta > parseFloat(balance) || !cotizacionValida"
          @click="apostar"
        >
          {{ cargando ? 'Tirando…' : 'APOSTAR' }}
        </button>

        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
      </aside>

      <main class="glass-panel panel-mesa">
        <div class="numero" :class="claseNumero">
          {{ ultima ? ultima.salida : '—' }}
        </div>

        <p v-if="ultima" class="veredicto" :class="claseNumero">
          <template v-if="ultima.gano">
            {{ ultima.salida }} {{ ultima.lado === 'menor' ? '&lt;' : '&gt;' }}
            {{ ultima.objetivo }} · cobrás ${{ ultima.payout }}
          </template>
          <template v-else>
            {{ ultima.salida }} no es {{ ultima.lado === 'menor' ? 'menor' : 'mayor' }}
            que {{ ultima.objetivo }}
          </template>
        </p>
        <p v-else class="veredicto apagado">Elegí tu apuesta y tirá.</p>

        <div class="regla">
          <div class="regla-barra">
            <div class="regla-gana" :style="estiloGana"></div>
            <div
              v-if="ultima"
              class="regla-marca"
              :style="{ left: (parseFloat(ultima.salida) / 99.99 * 100) + '%' }"
            ></div>
          </div>
          <div class="regla-numeros">
            <span>0</span><span>25</span><span>50</span><span>75</span><span>99.99</span>
          </div>
          <p class="ayuda">La franja marcada es la que paga.</p>
        </div>

        <div v-if="historial.length" class="historial">
          <span
            v-for="(tiro, indice) in historial"
            :key="indice"
            class="ficha"
            :class="{ gano: tiro.gano }"
          >
            {{ tiro.salida }}
          </span>
        </div>
      </main>
    </div>

    <FairnessPanel
      v-if="semilla"
      class="dice-fairness"
      :server-seed-hash="semilla.server_seed_hash"
      :client-seed="semilla.client_seed"
      :nonce="semilla.nonce"
      :server-seed="seedRevelado"
      :can-rotate="!cargando"
      :rotating="rotando"
      nonce-label="Tiros con esta semilla"
      help-text="El número sale de un seed comprometido antes de que apuestes. Al rotar la semilla se revela el seed y podés rehacer cada tiro que hiciste con ella, nonce por nonce."
      formula='salida = (primeros 52 bits de HMAC_SHA256(server_seed, "client_seed:nonce:intento")) mod 10000, descartando el sesgo del módulo'
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

const router = useRouter();
const balance = ref('0.00');
const cargando = ref(false);
const rotando = ref(false);
const errorMsg = ref('');

const apuesta = ref(10);
const objetivo = ref(50);
const lado = ref('menor');

const limites = ref(null);
const cotizacion = ref(null);
const ultima = ref(null);
const historial = ref([]);
const semilla = ref(null);
const seedRevelado = ref(null);

// El rango del objetivo depende del lado: de un lado el límite de chance
// aprieta abajo y del otro arriba. Se calcula de los límites del servidor
// para que la pantalla no pueda ofrecer una apuesta que el backend rechaza.
const minObjetivo = computed(() => {
  if (!limites.value) return 0.1;
  const min = parseFloat(limites.value.chance_minima);
  const max = parseFloat(limites.value.chance_maxima);
  return lado.value === 'menor' ? min : (100 - max - 0.01);
});

const maxObjetivo = computed(() => {
  if (!limites.value) return 95;
  const min = parseFloat(limites.value.chance_minima);
  const max = parseFloat(limites.value.chance_maxima);
  return lado.value === 'menor' ? max : (100 - min - 0.01);
});

const cotizacionValida = computed(() => Boolean(cotizacion.value));
const chance = computed(() => cotizacion.value?.chance ?? '—');
const multiplicadorCorto = computed(() =>
  cotizacion.value ? Number(cotizacion.value.multiplicador).toFixed(2) : '—',
);

const siGanas = computed(() => {
  if (!cotizacion.value) return '0.00';
  return (apuesta.value * Number(cotizacion.value.multiplicador)).toFixed(2);
});

const claseNumero = computed(() => {
  if (!ultima.value) return '';
  return ultima.value.gano ? 'gano' : 'perdio';
});

// La franja que paga, para dibujarla sobre la regla.
const estiloGana = computed(() => {
  const objetivoPct = (objetivo.value / 99.99) * 100;
  return lado.value === 'menor'
    ? { left: '0%', width: objetivoPct + '%' }
    : { left: objetivoPct + '%', width: (100 - objetivoPct) + '%' };
});

const ajustarApuesta = (delta) => {
  const tope = limites.value ? parseFloat(limites.value.apuesta_maxima) : 500;
  apuesta.value = Math.max(1, Math.min(tope, apuesta.value + delta));
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
    const res = await api.get('/games/dice/limites');
    limites.value = res.data;
  } catch {
    // Sin límites la pantalla igual funciona; el backend valida de todas formas.
  }
};

const cargarSemilla = async () => {
  try {
    const res = await api.get('/games/dice/semilla');
    semilla.value = res.data;
  } catch {
    semilla.value = null;
  }
};

// El multiplicador lo dice el servidor, no la pantalla: así no puede quedar
// mostrando un pago distinto del que se liquida.
const cotizar = async () => {
  try {
    const res = await api.get('/games/dice/cotizar', {
      params: { objetivo: objetivo.value.toFixed(2), lado: lado.value },
    });
    cotizacion.value = res.data;
    errorMsg.value = '';
  } catch (e) {
    cotizacion.value = null;
    errorMsg.value = e.response?.data?.detail || '';
  }
};

const acomodarObjetivo = () => {
  const min = minObjetivo.value;
  const max = maxObjetivo.value;
  objetivo.value = Math.min(max, Math.max(min, objetivo.value));
};

watch([objetivo, lado], cotizar);
watch(lado, () => {
  acomodarObjetivo();
});

onMounted(async () => {
  await Promise.all([cargarSaldo(), cargarLimites(), cargarSemilla()]);
  acomodarObjetivo();
  await cotizar();
});

const apostar = async () => {
  cargando.value = true;
  errorMsg.value = '';

  try {
    const res = await api.post('/games/dice/apostar', {
      bet_amount: apuesta.value.toFixed(2),
      objetivo: objetivo.value.toFixed(2),
      lado: lado.value,
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
    const res = await api.post('/games/dice/semilla/rotar', {
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
.dice-page {
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

.campo input[type='range'] {
  width: 100%;
  accent-color: var(--primary);
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

.lados {
  display: flex;
  gap: 8px;
}

.lados button {
  flex: 1;
  padding: 9px;
  border-radius: 9px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.8rem;
}

.lados button.activo {
  background: rgba(139, 92, 246, 0.2);
  border-color: var(--primary);
  color: var(--text-main);
}

.cotizacion {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
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
  min-height: 340px;
  justify-content: center;
}

.numero {
  font-size: 4.2rem;
  font-weight: 800;
  letter-spacing: -2px;
  color: var(--text-muted);
  transition: color 0.2s;
}

.numero.gano {
  color: var(--accent-green, #22c55e);
}

.numero.perdio {
  color: #f87171;
}

.veredicto {
  margin: 6px 0 26px;
  font-size: 0.85rem;
  text-align: center;
}

.veredicto.apagado {
  color: var(--text-muted);
}

.regla {
  width: 100%;
  max-width: 460px;
}

.regla-barra {
  position: relative;
  height: 12px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.07);
  overflow: visible;
}

.regla-gana {
  position: absolute;
  top: 0;
  bottom: 0;
  background: rgba(34, 197, 94, 0.35);
  border-radius: 6px;
  transition: left 0.12s, width 0.12s;
}

.regla-marca {
  position: absolute;
  top: -5px;
  width: 3px;
  height: 22px;
  background: var(--text-main);
  border-radius: 2px;
  transform: translateX(-1.5px);
}

.regla-numeros {
  display: flex;
  justify-content: space-between;
  margin-top: 7px;
  font-size: 0.65rem;
  color: var(--text-muted);
}

.ayuda {
  text-align: center;
  color: var(--text-muted);
  font-size: 0.7rem;
  margin: 10px 0 0;
}

.historial {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
  margin-top: 24px;
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

.dice-fairness {
  margin-top: 18px;
}

@media (max-width: 880px) {
  .main-layout {
    grid-template-columns: 1fr;
  }
}
</style>
