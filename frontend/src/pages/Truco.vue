<template>
  <div class="truco-container">
    <div class="glass-panel header-row">
      <button class="back-btn" @click="router.push('/lobby')">← Volver al Lobby</button>
      <span class="saldo">Saldo: ${{ saldo }}</span>
    </div>

    <h2 class="titulo">Truco</h2>

    <!-- Sin partida: se apuesta y se reparte -->
    <div v-if="!partida" class="glass-panel apuesta-panel">
      <h3>Mano a mano contra la casa</h3>
      <p class="ayuda">
        Partida a 30 puntos. Si la ganás cobrás {{ multiplicador }}x lo apostado.
      </p>

      <label class="field">
        <span>Apuesta</span>
        <input type="number" v-model.number="apuesta" min="1" step="1" :disabled="cargando" />
      </label>

      <button class="btn-principal" :disabled="cargando" @click="empezar">
        {{ cargando ? 'Repartiendo…' : 'Jugar' }}
      </button>

      <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
    </div>

    <!-- Con partida abierta -->
    <div v-else class="mesa">
      <aside class="glass-panel panel-lateral">
        <div class="tanteador">
          <div class="tanteador-lado" :class="{ puntero: partida.puntos[0] > partida.puntos[1] }">
            <span>Vos</span>
            <strong>{{ partida.puntos[0] }}</strong>
          </div>
          <div class="tanteador-sep">a</div>
          <div class="tanteador-lado" :class="{ puntero: partida.puntos[1] > partida.puntos[0] }">
            <span>La casa</span>
            <strong>{{ partida.puntos[1] }}</strong>
          </div>
        </div>

        <p class="dato">
          Mano {{ partida.manos_jugadas }} · apuesta ${{ partida.apuesta }} ·
          {{ esMano ? 'sos mano' : 'es mano la casa' }}
        </p>

        <div v-if="cantosDisponibles.length" class="cantos">
          <button
            v-for="canto in cantosDisponibles"
            :key="canto"
            class="btn-canto"
            :class="{ respuesta: canto === 'quiero' || canto === 'no_quiero' }"
            :disabled="cargando"
            @click="jugar(canto)"
          >
            {{ etiqueta(canto) }}
          </button>
        </div>

        <p v-if="partida.mano && partida.mano.pendiente" class="pendiente">
          La casa cantó <strong>{{ etiqueta(partida.mano.pendiente.canto) }}</strong>
        </p>

        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

        <FairnessPanel
          :server-seed-hash="partida.server_seed_hash"
          :client-seed="partida.client_seed"
          :nonce="partida.acciones_jugadas"
          :server-seed="partida.server_seed"
          nonce-label="Acciones jugadas"
          help-text="El hash se publica antes de repartir. Al terminar la partida se revela el seed y podés rehacer todos los repartos."
          formula='mazo = Fisher-Yates con los bytes de HMAC_SHA256(server_seed, "client_seed:nonce")'
        />
      </aside>

      <main class="glass-panel panel-mesa">
        <div class="lado-casa">
          <span class="etiqueta-lado">La casa</span>
          <div class="cartas-rival">
            <div v-for="n in partida.mano.cartas_del_rival" :key="'d' + n" class="carta dorso"></div>
          </div>
        </div>

        <div class="rondas">
          <div v-for="(ronda, indice) in partida.mano.rondas" :key="indice" class="ronda">
            <span class="ronda-numero">{{ indice + 1 }}ª</span>
            <div
              v-for="jugada in ronda"
              :key="jugada.carta"
              class="carta jugada"
              :class="{ mia: jugada.jugador === 0 }"
            >
              <span class="valor">{{ valorDe(jugada.carta) }}</span>
              <span class="palo" :title="nombrePalo(jugada.carta)">{{ paloDe(jugada.carta) }}</span>
            </div>
            <span class="ronda-resultado">{{ resultadoDeRonda(indice) }}</span>
          </div>
        </div>

        <div class="lado-mio">
          <span class="etiqueta-lado">
            {{ partida.terminada ? 'Partida terminada' : (meToca ? 'Te toca' : 'Esperá…') }}
          </span>
          <div class="cartas-mias">
            <button
              v-for="carta in partida.mano.cartas"
              :key="carta"
              class="carta mia"
              :class="{ jugable: puedeJugar(carta) }"
              :disabled="!puedeJugar(carta) || cargando"
              @click="jugar('jugar:' + carta)"
            >
              <span class="valor">{{ valorDe(carta) }}</span>
              <span class="palo" :title="nombrePalo(carta)">{{ paloDe(carta) }}</span>
            </button>
          </div>
        </div>

        <div v-if="partida.terminada" class="resultado" :class="{ ganada: partida.ganador === 0 }">
          <strong>{{ partida.ganador === 0 ? '¡Ganaste la partida!' : 'Ganó la casa' }}</strong>
          <span v-if="partida.ganador === 0">Cobraste ${{ partida.payout }}</span>
          <button class="btn-principal" @click="reiniciar">Otra partida</button>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import api from '../shared/api';
import FairnessPanel from '../widgets/FairnessPanel.vue';

const router = useRouter();

const saldo = ref('0.00');
const apuesta = ref(50);
const partida = ref(null);
const cargando = ref(false);
const errorMsg = ref('');
const multiplicador = ref('1.90');

const PALOS = { E: '⚔', B: '🌿', O: '🪙', C: '🍷' };
const NOMBRES = { E: 'espada', B: 'basto', O: 'oro', C: 'copa' };

const ETIQUETAS = {
  truco: 'Truco',
  retruco: 'Retruco',
  vale_cuatro: 'Vale cuatro',
  envido: 'Envido',
  real_envido: 'Real envido',
  falta_envido: 'Falta envido',
  quiero: 'Quiero',
  no_quiero: 'No quiero',
  irse_al_mazo: 'Irme al mazo',
};

const valorDe = (carta) => carta.slice(0, -1);
const paloDe = (carta) => PALOS[carta.slice(-1)] || carta.slice(-1);
const nombrePalo = (carta) => NOMBRES[carta.slice(-1)] || '';
const etiqueta = (accion) => ETIQUETAS[accion] || accion;

const acciones = computed(() => partida.value?.mano?.acciones || []);
const meToca = computed(() => acciones.value.length > 0);
const esMano = computed(() => partida.value?.mano?.mano === 0);

const cantosDisponibles = computed(() =>
  acciones.value.filter((accion) => !accion.startsWith('jugar:'))
);

const puedeJugar = (carta) => acciones.value.includes('jugar:' + carta);

const resultadoDeRonda = (indice) => {
  const resultado = partida.value?.mano?.resultados?.[indice];
  if (resultado === undefined) return '';
  if (resultado === 'parda') return 'parda';
  return resultado === 0 ? 'tuya' : 'de la casa';
};

const cargarSaldo = async () => {
  const res = await api.get('/wallet/balance');
  saldo.value = parseFloat(res.data.balance).toFixed(2);
};

const cargarPartida = async () => {
  try {
    const res = await api.get('/games/truco/partida');
    partida.value = res.data;
    multiplicador.value = res.data.multiplicador;
  } catch {
    partida.value = null;  // no hay partida abierta, se muestra la apuesta
  }
};

const empezar = async () => {
  errorMsg.value = '';
  cargando.value = true;
  try {
    const res = await api.post('/games/truco/partida', { bet_amount: apuesta.value });
    partida.value = res.data;
    multiplicador.value = res.data.multiplicador;
    await cargarSaldo();
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo empezar la partida';
  } finally {
    cargando.value = false;
  }
};

const jugar = async (accion) => {
  errorMsg.value = '';
  cargando.value = true;
  try {
    const res = await api.post('/games/truco/accion', { accion });
    partida.value = res.data;
    if (res.data.terminada) await cargarSaldo();
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo jugar esa acción';
    await cargarPartida();
  } finally {
    cargando.value = false;
  }
};

const reiniciar = async () => {
  partida.value = null;
  await cargarSaldo();
};

onMounted(async () => {
  await cargarSaldo();
  await cargarPartida();
});
</script>

<style scoped>
.truco-container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 16px;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.back-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.9rem;
}

.back-btn:hover {
  color: var(--primary);
}

.saldo {
  font-weight: 700;
}

.titulo {
  margin: 0 0 16px;
}

.apuesta-panel {
  padding: 24px;
  max-width: 420px;
}

.ayuda {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.field {
  display: block;
  margin: 16px 0;
}

.field span {
  display: block;
  color: var(--text-muted);
  font-size: 0.8rem;
  margin-bottom: 4px;
}

.field input {
  width: 100%;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text-main);
}

.btn-principal {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 12px;
  background: var(--primary);
  color: white;
  font-weight: 700;
  cursor: pointer;
}

.btn-principal:disabled {
  opacity: 0.6;
  cursor: default;
}

.mesa {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  align-items: start;
}

.panel-lateral,
.panel-mesa {
  padding: 16px;
}

.tanteador {
  display: flex;
  align-items: center;
  justify-content: space-around;
  margin-bottom: 10px;
}

.tanteador-lado {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: var(--text-muted);
}

.tanteador-lado strong {
  font-size: 2rem;
  color: var(--text-main);
}

.tanteador-lado.puntero strong {
  color: var(--accent-green);
}

.tanteador-sep {
  color: var(--text-muted);
}

.dato {
  color: var(--text-muted);
  font-size: 0.8rem;
  text-align: center;
  margin: 0 0 14px;
}

.cantos {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.btn-canto {
  flex: 1 1 auto;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-main);
  cursor: pointer;
  font-size: 0.8rem;
}

.btn-canto:hover:not(:disabled) {
  border-color: var(--primary);
}

.btn-canto.respuesta {
  background: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.4);
}

.pendiente {
  font-size: 0.8rem;
  color: var(--accent-green);
  margin: 0 0 10px;
}

.panel-mesa {
  min-height: 420px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 16px;
}

.etiqueta-lado {
  display: block;
  color: var(--text-muted);
  font-size: 0.75rem;
  margin-bottom: 6px;
}

.cartas-rival,
.cartas-mias {
  display: flex;
  gap: 8px;
}

.carta {
  width: 58px;
  height: 84px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  color: #0f172a;
  border: 1px solid rgba(0, 0, 0, 0.2);
  font-weight: 700;
}

.carta .valor {
  font-size: 1.3rem;
  line-height: 1;
}

.carta .palo {
  font-size: 1rem;
}

.carta.dorso {
  background: repeating-linear-gradient(45deg, #1e293b, #1e293b 6px, #334155 6px, #334155 12px);
  border-color: rgba(255, 255, 255, 0.15);
}

.carta.mia {
  cursor: default;
  opacity: 0.55;
  transition: transform 0.12s ease, opacity 0.12s ease;
}

.carta.mia.jugable {
  cursor: pointer;
  opacity: 1;
}

.carta.mia.jugable:hover {
  transform: translateY(-6px);
}

.rondas {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  min-height: 110px;
}

.ronda {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ronda-numero,
.ronda-resultado {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.carta.jugada {
  width: 42px;
  height: 60px;
}

.carta.jugada.mia {
  opacity: 1;
  box-shadow: 0 0 0 2px var(--primary);
}

.resultado {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 14px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.12);
}

.resultado.ganada {
  background: rgba(16, 185, 129, 0.15);
}

.resultado .btn-principal {
  max-width: 220px;
}

.error-msg {
  color: var(--accent-red);
  font-size: 0.8rem;
}

@media (max-width: 860px) {
  .mesa {
    grid-template-columns: 1fr;
  }
}
</style>
