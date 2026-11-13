<template>
  <div class="generala-page">
    <div class="glass-panel header-row">
      <button class="btn-back" @click="router.push('/lobby')">← Volver al Lobby</button>
      <div class="balance">Saldo: ${{ balance }}</div>
    </div>

    <!-- Apostar -->
    <div v-if="!partida" class="glass-panel panel-apuesta">
      <h2 class="titulo">Generala 🎲</h2>
      <p class="bajada">
        Diez categorías, tres tiradas por turno. Gana el que más suma.
        La generala servida gana en el acto.
      </p>

      <div class="bet-controls">
        <button :disabled="cargando" @click="ajustar(-5)">−</button>
        <span class="bet-display">${{ apuesta.toFixed(2) }}</span>
        <button :disabled="cargando" @click="ajustar(5)">+</button>
      </div>

      <button
        class="btn-principal"
        :disabled="cargando || apuesta > parseFloat(balance)"
        @click="empezar"
      >
        {{ cargando ? 'Repartiendo…' : 'JUGAR' }}
      </button>

      <p class="pago">
        Si ganás cobrás {{ multiplicador }}× lo apostado. El empate devuelve la apuesta.
      </p>
      <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
    </div>

    <!-- La mesa -->
    <div v-else class="mesa">
      <div class="glass-panel panel-dados">
        <div class="marcador">
          <div class="lado" :class="{ activo: partida.en_turno === 0 && !partida.terminada }">
            <span class="quien">Vos</span>
            <strong>{{ partida.totales[0] }}</strong>
          </div>
          <span class="versus">—</span>
          <div class="lado" :class="{ activo: partida.en_turno === 1 && !partida.terminada }">
            <span class="quien">La casa</span>
            <strong>{{ partida.totales[1] }}</strong>
          </div>
        </div>

        <div v-if="partida.terminada" class="banner" :class="claseResultado">
          {{ textoResultado }}
        </div>

        <template v-else-if="partida.turno">
          <p class="de-quien">
            {{ miTurno ? 'Tu turno' : 'Juega la casa…' }}
            <span class="tirada">tirada {{ partida.turno.tirada }} de {{ partida.turno.tiradas_por_turno }}</span>
            <span v-if="partida.turno.servida" class="servida">servida</span>
          </p>

          <div class="dados">
            <button
              v-for="(dado, indice) in partida.turno.dados"
              :key="indice"
              class="dado"
              :class="{ guardado: !aTirar.includes(indice), tocable: puedeElegir }"
              :disabled="!puedeElegir"
              @click="alternar(indice)"
            >
              {{ CARAS[dado - 1] }}
            </button>
          </div>

          <p v-if="puedeElegir" class="ayuda">
            Los dados apagados son los que se vuelven a tirar. Tocá para elegir.
          </p>

          <div v-if="miTurno" class="acciones">
            <button
              class="btn-tirar"
              :disabled="cargando || !partida.turno.puede_tirar || !aTirar.length"
              @click="tirar"
            >
              Tirar {{ aTirar.length || '' }}
            </button>
          </div>
        </template>
      </div>

      <div class="glass-panel panel-planilla">
        <div class="planilla-head">
          <span>Categoría</span>
          <span>Vos</span>
          <span>Casa</span>
        </div>

        <button
          v-for="categoria in CATEGORIAS"
          :key="categoria"
          class="fila"
          :class="{
            usada: partida.planillas[0][categoria] !== null,
            anotable: puedeAnotar(categoria),
            cero: puedeAnotar(categoria) && puntosDe(categoria) === 0,
          }"
          :disabled="!puedeAnotar(categoria)"
          @click="anotar(categoria)"
        >
          <span class="nombre">{{ NOMBRES[categoria] }}</span>
          <span class="mio">
            <template v-if="partida.planillas[0][categoria] !== null">
              {{ partida.planillas[0][categoria] }}
            </template>
            <template v-else-if="puedeAnotar(categoria)">
              <em class="propuesta">{{ puntosDe(categoria) }}</em>
            </template>
            <template v-else>·</template>
          </span>
          <span class="suyo">
            {{ partida.planillas[1][categoria] === null ? '·' : partida.planillas[1][categoria] }}
          </span>
        </button>

        <p v-if="miTurno && !partida.terminada" class="ayuda">
          Tocá una categoría para anotar. Si no te sirve ninguna, tenés que tachar una con cero.
        </p>

        <button v-if="partida.terminada" class="btn-principal" @click="limpiar">
          JUGAR OTRA
        </button>
      </div>

      <FairnessPanel
        class="gen-fairness"
        :server-seed-hash="partida.server_seed_hash"
        :client-seed="partida.client_seed"
        :nonce="partida.nonce"
        :server-seed="partida.server_seed"
        :can-rotate="false"
        nonce-label="Partida nº"
        help-text="Los dados de toda la partida salen de un seed comprometido antes de empezar y se consumen en orden. Al terminar se revela el seed y podés rehacer cada tirada."
        formula='dado = 1 + (byte de HMAC_SHA256(server_seed, "client_seed:nonce:i") mod 6), con muestreo con rechazo'
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import confetti from 'canvas-confetti';
import api from '../shared/api';
import FairnessPanel from '../widgets/FairnessPanel.vue';

const CARAS = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'];

const CATEGORIAS = ['1', '2', '3', '4', '5', '6', 'escalera', 'full', 'poker', 'generala'];
const NOMBRES = {
  1: 'Unos', 2: 'Doses', 3: 'Treses', 4: 'Cuatros', 5: 'Cincos', 6: 'Seises',
  escalera: 'Escalera', full: 'Full', poker: 'Póker', generala: 'Generala',
};

const router = useRouter();
const balance = ref('0.00');
const cargando = ref(false);
const errorMsg = ref('');

const apuesta = ref(20);
const partida = ref(null);
const multiplicador = ref('1.95');

// Los índices que se van a volver a tirar. Arranca en todos: lo normal en la
// primera tirada es cambiar casi todo.
const aTirar = ref([0, 1, 2, 3, 4]);

const miTurno = computed(
  () => partida.value && !partida.value.terminada && partida.value.en_turno === 0,
);
const puedeElegir = computed(
  () => miTurno.value && partida.value?.turno?.puede_tirar && !cargando.value,
);

const puntosDe = (categoria) => partida.value?.turno?.puntajes?.[categoria] ?? 0;
const puedeAnotar = (categoria) =>
  !!miTurno.value && !cargando.value && partida.value?.planillas[0][categoria] === null;

const claseResultado = computed(() => {
  if (partida.value?.ganador === 0) return 'gano';
  if (partida.value?.ganador === 1) return 'perdio';
  return 'empate';
});

const textoResultado = computed(() => {
  const estado = partida.value;
  if (!estado) return '';

  const servida = estado.generala_servida_de !== null && estado.generala_servida_de !== undefined;
  const cola = servida
    ? (estado.generala_servida_de === 0 ? ' con generala servida' : ' con generala servida de la casa')
    : '';

  if (estado.ganador === 0) return `🎲 Ganaste $${Number(estado.payout).toFixed(2)}${cola}`;
  if (estado.ganador === 1) return `Perdiste${cola}`;
  return `Empate: vuelve tu apuesta de $${Number(estado.payout).toFixed(2)}`;
});

const ajustar = (delta) => {
  apuesta.value = Math.max(1, Math.min(500, apuesta.value + delta));
};

const cargarSaldo = async () => {
  try {
    const res = await api.get('/wallet/balance');
    balance.value = parseFloat(res.data.balance).toFixed(2);
  } catch {
    // El saldo se vuelve a pedir en cada jugada.
  }
};

const cargarReglas = async () => {
  try {
    const res = await api.get('/games/generala/reglas');
    multiplicador.value = res.data.multiplicador;
  } catch {
    // Si falla queda el valor por defecto, que es sólo informativo.
  }
};

// La apuesta se debita al empezar: la partida sin terminar lo está esperando.
const retomar = async () => {
  try {
    const res = await api.get('/games/generala/partida');
    if (res.data) aplicar(res.data);
  } catch {
    // Si falla, se ve la pantalla de apostar.
  }
};

onMounted(async () => {
  await Promise.all([cargarSaldo(), cargarReglas(), retomar()]);
});

const aplicar = (datos) => {
  partida.value = datos;
  // Turno nuevo: por defecto se vuelven a tirar todos.
  aTirar.value = datos.turno && datos.turno.tirada === 1 ? [0, 1, 2, 3, 4] : [];
};

const alternar = (indice) => {
  if (!puedeElegir.value) return;

  aTirar.value = aTirar.value.includes(indice)
    ? aTirar.value.filter((otro) => otro !== indice)
    : [...aTirar.value, indice];
};

const empezar = async () => {
  cargando.value = true;
  errorMsg.value = '';

  try {
    const res = await api.post('/games/generala/partida', {
      bet_amount: apuesta.value.toFixed(2),
    });
    aplicar(res.data);
    await cargarSaldo();
    if (res.data.terminada) cerrar(res.data);
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo empezar';
  } finally {
    cargando.value = false;
  }
};

const enviar = async (accion) => {
  cargando.value = true;
  errorMsg.value = '';

  try {
    const res = await api.post('/games/generala/accion', { accion });
    aplicar(res.data);
    if (res.data.terminada) {
      await cargarSaldo();
      cerrar(res.data);
    }
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo jugar';
  } finally {
    cargando.value = false;
  }
};

const tirar = () => {
  if (!aTirar.value.length) return;
  enviar(`tirar:${[...aTirar.value].sort((a, b) => a - b).join(',')}`);
};

const anotar = (categoria) => enviar(`anotar:${categoria}`);

const cerrar = (datos) => {
  if (datos.ganador === 0) {
    confetti({ particleCount: 110, spread: 80, origin: { y: 0.6 } });
  }
};

const limpiar = () => {
  partida.value = null;
  errorMsg.value = '';
};
</script>

<style scoped>
.generala-page {
  padding: 20px;
  max-width: 1000px;
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

.panel-apuesta {
  padding: 26px;
  text-align: center;
  max-width: 460px;
  margin: 0 auto;
}

.titulo {
  margin: 0 0 8px;
  font-size: 1.5rem;
}

.bajada {
  color: var(--text-muted);
  font-size: 0.85rem;
  line-height: 1.45;
  margin: 0 0 20px;
}

.bet-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-bottom: 18px;
}

.bet-controls button {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: transparent;
  color: var(--text-main);
  cursor: pointer;
  font-size: 1.1rem;
}

.bet-display {
  font-size: 1.3rem;
  font-weight: 700;
  min-width: 100px;
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

.pago {
  margin: 14px 0 0;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.error-msg {
  margin-top: 12px;
  color: #f87171;
  font-size: 0.82rem;
}

.mesa {
  display: grid;
  grid-template-columns: 1fr 330px;
  gap: 18px;
  align-items: start;
}

.panel-dados,
.panel-planilla {
  padding: 18px;
}

.gen-fairness {
  grid-column: 1 / -1;
}

.marcador {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  margin-bottom: 16px;
}

.lado {
  text-align: center;
  padding: 8px 18px;
  border-radius: 10px;
  border: 1px solid transparent;
}

.lado.activo {
  border-color: var(--primary);
  background: rgba(139, 92, 246, 0.12);
}

.lado .quien {
  display: block;
  font-size: 0.7rem;
  color: var(--text-muted);
}

.lado strong {
  font-size: 1.5rem;
}

.versus {
  color: var(--text-muted);
}

.de-quien {
  text-align: center;
  margin: 0 0 14px;
  font-size: 0.85rem;
}

.tirada {
  color: var(--text-muted);
  font-size: 0.75rem;
  margin-left: 8px;
}

.servida {
  margin-left: 8px;
  font-size: 0.68rem;
  color: var(--accent-green, #22c55e);
  border: 1px solid currentColor;
  border-radius: 6px;
  padding: 1px 6px;
}

.dados {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-bottom: 10px;
}

.dado {
  width: 62px;
  height: 62px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-muted);
  font-size: 2.3rem;
  line-height: 1;
  cursor: default;
  transition: transform 0.1s, background 0.15s, color 0.15s;
}

.dado.tocable {
  cursor: pointer;
}

.dado.guardado {
  background: rgba(139, 92, 246, 0.18);
  border-color: var(--primary);
  color: var(--text-main);
}

.dado.tocable:hover {
  transform: translateY(-2px);
}

.acciones {
  display: flex;
  justify-content: center;
  margin-top: 8px;
}

.btn-tirar {
  padding: 10px 26px;
  border-radius: 10px;
  border: none;
  background: var(--primary);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.btn-tirar:disabled {
  opacity: 0.4;
  cursor: default;
}

.ayuda {
  text-align: center;
  color: var(--text-muted);
  font-size: 0.72rem;
  line-height: 1.4;
  margin: 10px 0 0;
}

.planilla-head,
.fila {
  display: grid;
  grid-template-columns: 1fr 48px 48px;
  gap: 6px;
  align-items: center;
  text-align: right;
  width: 100%;
}

.planilla-head {
  font-size: 0.68rem;
  color: var(--text-muted);
  padding: 0 8px 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.planilla-head span:first-child,
.fila .nombre {
  text-align: left;
}

.fila {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  color: var(--text-main);
  padding: 7px 8px;
  font-size: 0.8rem;
  cursor: default;
}

.fila.usada .mio {
  color: var(--text-muted);
}

.fila.anotable {
  cursor: pointer;
  border-color: rgba(255, 255, 255, 0.12);
}

.fila.anotable:hover {
  border-color: var(--primary);
  background: rgba(139, 92, 246, 0.1);
}

.propuesta {
  font-style: normal;
  font-weight: 700;
  color: var(--accent-green, #22c55e);
}

.fila.cero .propuesta {
  color: #f87171;
}

.banner {
  text-align: center;
  padding: 12px;
  border-radius: 10px;
  font-weight: 700;
  margin: 10px 0;
}

.banner.gano {
  background: rgba(34, 197, 94, 0.18);
  color: var(--accent-green, #22c55e);
}

.banner.perdio {
  background: rgba(239, 68, 68, 0.18);
  color: #f87171;
}

.banner.empate {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-muted);
}

@media (max-width: 880px) {
  .mesa {
    grid-template-columns: 1fr;
  }
}
</style>
