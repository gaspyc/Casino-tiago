<template>
  <div class="truco-container">
    <div class="glass-panel header-row">
      <button class="back-btn" @click="salir">← Volver al Lobby</button>
      <span class="saldo">Saldo: ${{ saldo }}</span>
    </div>

    <h2 class="titulo">Truco</h2>

    <!-- Nada en juego: se elige contra quién -->
    <div v-if="!juego" class="glass-panel panel-inicio">
      <div class="modos">
        <button :class="{ activo: modo === 'casa' }" @click="modo = 'casa'">Contra la casa</button>
        <button :class="{ activo: modo === 'mesa' }" @click="elegirMesas">Con otro jugador</button>
      </div>

      <label class="field">
        <span>Apuesta</span>
        <input type="number" v-model.number="apuesta" min="1" step="1" :disabled="cargando" />
      </label>

      <label class="check">
        <input type="checkbox" v-model="conFlor" :disabled="cargando" />
        <span>Jugar con flor</span>
      </label>

      <template v-if="modo === 'casa'">
        <p class="ayuda">
          Mano a mano contra la casa, partida a 30. Si ganás cobrás {{ multiplicador }}x.
        </p>
        <button class="btn-principal" :disabled="cargando" @click="empezarContraLaCasa">
          {{ cargando ? 'Repartiendo…' : 'Jugar' }}
        </button>
      </template>

      <template v-else>
        <p class="ayuda">
          Mano a mano contra otra persona. Los dos ponen la apuesta y el que gana se
          lleva el pozo menos la comisión de la casa.
        </p>
        <button class="btn-principal" :disabled="cargando" @click="crearMesa">
          {{ cargando ? 'Creando…' : 'Crear mesa' }}
        </button>

        <div class="mesas">
          <h4>Mesas abiertas</h4>
          <p v-if="!mesas.length" class="ayuda">No hay ninguna. Creá una y esperá.</p>
          <div v-for="mesa in mesas" :key="mesa.id" class="mesa-fila">
            <span>
              <strong>{{ mesa.creador }}</strong>
              · ${{ mesa.apuesta }}{{ mesa.con_flor ? ' · con flor' : '' }}
            </span>
            <button v-if="mesa.puedo_sentarme" :disabled="cargando" @click="sentarse(mesa.id)">
              Sentarme
            </button>
            <span v-else class="ayuda">{{ mesa.estado }}</span>
          </div>
        </div>
      </template>

      <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
    </div>

    <!-- Esperando que alguien se siente -->
    <div v-else-if="juego.estado === 'esperando'" class="glass-panel panel-inicio">
      <h3>Esperando rival…</h3>
      <p class="ayuda">
        Mesa #{{ juego.mesa_id }} · apuesta ${{ juego.apuesta }} · pozo ${{ juego.pozo }}
        {{ juego.con_flor ? '· con flor' : '' }}
      </p>
      <button class="btn-secundario" :disabled="cargando" @click="abandonar">
        Cancelar y recuperar la apuesta
      </button>
    </div>

    <!-- En juego -->
    <div v-else class="mesa-juego">
      <aside class="glass-panel panel-lateral">
        <div class="tanteador">
          <div class="tanteador-lado" :class="{ puntero: misPuntos > susPuntos }">
            <span>{{ miNombre }}</span>
            <strong>{{ misPuntos }}</strong>
          </div>
          <div class="tanteador-sep">a</div>
          <div class="tanteador-lado" :class="{ puntero: susPuntos > misPuntos }">
            <span>{{ suNombre }}</span>
            <strong>{{ susPuntos }}</strong>
          </div>
        </div>

        <p class="dato">
          Mano {{ juego.manos_jugadas }} ·
          {{ esMesa ? 'pozo $' + juego.pozo : 'apuesta $' + juego.apuesta }} ·
          {{ soyMano ? 'sos mano' : 'es mano el rival' }}
          {{ juego.con_flor ? '· con flor' : '' }}
        </p>

        <div v-if="cantosDisponibles.length" class="cantos">
          <button
            v-for="canto in cantosDisponibles"
            :key="canto"
            class="btn-canto"
            :class="{ respuesta: canto === 'quiero' || canto === 'no_quiero', flor: canto.includes('flor') }"
            :disabled="cargando"
            @click="jugar(canto)"
          >
            {{ etiqueta(canto) }}
          </button>
        </div>

        <p v-if="pendiente" class="pendiente">
          {{ pendiente.de === miAsiento ? 'Cantaste' : suNombre + ' cantó' }}
          <strong>{{ etiqueta(pendiente.canto) }}</strong>
        </p>

        <p v-if="esMesa && !juego.terminada && !juego.me_toca" class="esperando">
          Esperando a {{ suNombre }}…
        </p>

        <p
          v-if="esMesa && juego.segundos_restantes !== null && !juego.terminada"
          class="reloj"
          :class="{ apurado: juego.segundos_restantes <= 15 }"
        >
          {{ juego.me_toca ? 'Te quedan' : `A ${suNombre} le quedan` }}
          {{ juego.segundos_restantes }}s para hablar
        </p>

        <button
          v-if="juego.puedo_reclamar"
          class="btn-reclamar"
          :disabled="cargando"
          @click="reclamar"
        >
          Se le venció el plazo: llevarme la mesa
        </button>

        <button
          v-if="esMesa && !juego.terminada"
          class="btn-secundario chico"
          :disabled="cargando"
          @click="abandonar"
        >
          Abandonar
        </button>

        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

        <FairnessPanel
          :server-seed-hash="juego.server_seed_hash"
          :client-seed="juego.client_seed"
          :nonce="juego.acciones_jugadas"
          :server-seed="juego.server_seed"
          nonce-label="Acciones jugadas"
          help-text="El hash se publica antes de repartir. Al terminar se revela el seed y podés rehacer todos los repartos."
          formula='mazo = Fisher-Yates con los bytes de HMAC_SHA256(server_seed, "client_seed:nonce")'
        />
      </aside>

      <main class="glass-panel panel-mesa">
        <div class="lado-rival">
          <span class="etiqueta-lado">{{ suNombre }}</span>
          <div class="cartas-rival">
            <div v-for="n in juego.mano.cartas_del_rival" :key="'d' + n" class="carta dorso"></div>
          </div>
        </div>

        <div class="rondas">
          <div v-for="(ronda, indice) in juego.mano.rondas" :key="indice" class="ronda">
            <span class="ronda-numero">{{ indice + 1 }}ª</span>
            <div
              v-for="jugada in ronda"
              :key="jugada.carta"
              class="carta jugada"
              :class="{ mia: jugada.jugador === miAsiento }"
            >
              <span class="valor">{{ valorDe(jugada.carta) }}</span>
              <span class="palo" :title="nombrePalo(jugada.carta)">{{ paloDe(jugada.carta) }}</span>
            </div>
            <span class="ronda-resultado">{{ resultadoDeRonda(indice) }}</span>
          </div>
        </div>

        <div class="lado-mio">
          <span class="etiqueta-lado">
            {{ juego.terminada ? 'Partida terminada' : (meToca ? 'Te toca' : 'Esperá…') }}
            <em v-if="juego.mano.tengo_flor" class="aviso-flor">tenés flor</em>
          </span>
          <div class="cartas-mias">
            <button
              v-for="carta in juego.mano.cartas"
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

        <div v-if="juego.terminada" class="resultado" :class="{ ganada: gane }">
          <strong>{{ gane ? '¡Ganaste!' : 'Perdiste' }}</strong>
          <span v-if="porPlazo" class="motivo">
            {{ gane
              ? '⏱ Se le venció el plazo del turno'
              : '⏱ Se te venció el plazo del turno' }}
          </span>
          <span v-if="gane">Cobraste ${{ esMesa ? juego.premio : juego.payout }}</span>
          <button class="btn-principal" @click="reiniciar">Otra partida</button>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import api from '../shared/api';
import FairnessPanel from '../widgets/FairnessPanel.vue';

const router = useRouter();

const saldo = ref('0.00');
const apuesta = ref(50);
const conFlor = ref(false);
const modo = ref('casa');
const juego = ref(null);
const mesas = ref([]);
const cargando = ref(false);
const errorMsg = ref('');
const multiplicador = ref('1.90');

let sondeo = null;

const PALOS = { E: '⚔', B: '🌿', O: '🪙', C: '🍷' };
const NOMBRES_PALO = { E: 'espada', B: 'basto', O: 'oro', C: 'copa' };

const ETIQUETAS = {
  truco: 'Truco',
  retruco: 'Retruco',
  vale_cuatro: 'Vale cuatro',
  envido: 'Envido',
  real_envido: 'Real envido',
  falta_envido: 'Falta envido',
  flor: 'Flor',
  contraflor: 'Contraflor',
  contraflor_al_resto: 'Contraflor al resto',
  quiero: 'Quiero',
  no_quiero: 'No quiero',
  irse_al_mazo: 'Irme al mazo',
};

const valorDe = (carta) => carta.slice(0, -1);
const paloDe = (carta) => PALOS[carta.slice(-1)] || carta.slice(-1);
const nombrePalo = (carta) => NOMBRES_PALO[carta.slice(-1)] || '';
const etiqueta = (accion) => ETIQUETAS[accion] || accion;

const esMesa = computed(() => Boolean(juego.value?.mesa_id));
const miAsiento = computed(() => juego.value?.asiento ?? 0);
const acciones = computed(() => juego.value?.mano?.acciones || []);
const meToca = computed(() => acciones.value.length > 0);
const pendiente = computed(() => juego.value?.mano?.pendiente || null);
const soyMano = computed(() => juego.value?.mano?.mano === miAsiento.value);

const misPuntos = computed(() => juego.value?.puntos?.[miAsiento.value] ?? 0);
const susPuntos = computed(() => juego.value?.puntos?.[1 - miAsiento.value] ?? 0);
const gane = computed(() => juego.value?.ganador === miAsiento.value);
const porPlazo = computed(() => juego.value?.motivo === 'plazo_vencido');

const miNombre = computed(() =>
  esMesa.value ? juego.value.jugadores[miAsiento.value] || 'Vos' : 'Vos'
);
const suNombre = computed(() =>
  esMesa.value ? juego.value.jugadores[1 - miAsiento.value] || 'Rival' : 'La casa'
);

const cantosDisponibles = computed(() =>
  acciones.value.filter((accion) => !accion.startsWith('jugar:'))
);

const puedeJugar = (carta) => acciones.value.includes('jugar:' + carta);

const resultadoDeRonda = (indice) => {
  const resultado = juego.value?.mano?.resultados?.[indice];
  if (resultado === undefined) return '';
  if (resultado === 'parda') return 'parda';
  return resultado === miAsiento.value ? 'tuya' : 'del rival';
};

// --------------------------- llamadas ---------------------------

const cargarSaldo = async () => {
  const res = await api.get('/wallet/balance');
  saldo.value = parseFloat(res.data.balance).toFixed(2);
};

const cargarMesas = async () => {
  const res = await api.get('/games/truco/mesas');
  mesas.value = res.data.mesas;
  return res.data.mi_mesa;
};

const elegirMesas = async () => {
  modo.value = 'mesa';
  try {
    await cargarMesas();
  } catch {
    mesas.value = [];
  }
};

const conError = async (accion) => {
  errorMsg.value = '';
  cargando.value = true;
  try {
    await accion();
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo completar la acción';
  } finally {
    cargando.value = false;
  }
};

const empezarContraLaCasa = () =>
  conError(async () => {
    const res = await api.post('/games/truco/partida', {
      bet_amount: apuesta.value,
      con_flor: conFlor.value,
    });
    juego.value = res.data;
    multiplicador.value = res.data.multiplicador;
    await cargarSaldo();
  });

const crearMesa = () =>
  conError(async () => {
    const res = await api.post('/games/truco/mesas', {
      bet_amount: apuesta.value,
      con_flor: conFlor.value,
    });
    juego.value = res.data;
    await cargarSaldo();
    arrancarSondeo();
  });

const sentarse = (mesaId) =>
  conError(async () => {
    const res = await api.post(`/games/truco/mesas/${mesaId}/sentarse`, {});
    juego.value = res.data;
    await cargarSaldo();
    arrancarSondeo();
  });

const jugar = (accion) =>
  conError(async () => {
    const ruta = esMesa.value
      ? `/games/truco/mesas/${juego.value.mesa_id}/accion`
      : '/games/truco/accion';
    const res = await api.post(ruta, { accion });
    juego.value = res.data;
    if (res.data.terminada) {
      detenerSondeo();
      await cargarSaldo();
    }
  });

const abandonar = () =>
  conError(async () => {
    await api.post(`/games/truco/mesas/${juego.value.mesa_id}/abandonar`, {});
    detenerSondeo();
    juego.value = null;
    await cargarSaldo();
    await cargarMesas();
  });

// Al rival se le venció el plazo: la mesa es del que reclama. A diferencia de
// abandonar, acá la partida queda a la vista con el resultado.
const reclamar = () =>
  conError(async () => {
    const res = await api.post(
      `/games/truco/mesas/${juego.value.mesa_id}/reclamar`,
      {},
    );
    detenerSondeo();
    juego.value = res.data;
    await cargarSaldo();
  });

const reiniciar = async () => {
  detenerSondeo();
  juego.value = null;
  await cargarSaldo();
  if (modo.value === 'mesa') await cargarMesas();
};

const salir = () => {
  detenerSondeo();
  router.push('/lobby');
};

// --------------------------- sondeo ---------------------------
// Mientras espera al rival el cliente pregunta cada dos segundos. Para un juego
// por turnos alcanza y evita mantener una conexión abierta.

const refrescarMesa = async () => {
  if (!esMesa.value || juego.value?.terminada) return;

  try {
    const res = await api.get(`/games/truco/mesas/${juego.value.mesa_id}`);
    const antes = juego.value.acciones_jugadas;
    juego.value = res.data;

    if (res.data.terminada || res.data.acciones_jugadas !== antes) {
      await cargarSaldo();
    }
    if (res.data.terminada) detenerSondeo();
  } catch {
    // Un error puntual no corta la partida: se reintenta en el próximo sondeo.
  }
};

const arrancarSondeo = () => {
  detenerSondeo();
  sondeo = setInterval(refrescarMesa, 2000);
};

const detenerSondeo = () => {
  if (sondeo) {
    clearInterval(sondeo);
    sondeo = null;
  }
};

onMounted(async () => {
  await cargarSaldo();

  // Si quedó algo sin terminar, se retoma.
  try {
    const miMesa = await cargarMesas();
    if (miMesa) {
      const res = await api.get(`/games/truco/mesas/${miMesa}`);
      juego.value = res.data;
      modo.value = 'mesa';
      arrancarSondeo();
      return;
    }
  } catch {
    // sin mesas, se sigue
  }

  try {
    const res = await api.get('/games/truco/partida');
    juego.value = res.data;
    multiplicador.value = res.data.multiplicador;
  } catch {
    juego.value = null;
  }
});

onBeforeUnmount(detenerSondeo);
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

.panel-inicio {
  padding: 24px;
  max-width: 460px;
}

.modos {
  display: flex;
  gap: 8px;
  margin-bottom: 18px;
}

.modos button {
  flex: 1;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.modos button.activo {
  background: rgba(139, 92, 246, 0.2);
  border-color: var(--primary);
  color: var(--text-main);
}

.ayuda {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.field {
  display: block;
  margin: 16px 0 10px;
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

.check {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  font-size: 0.85rem;
  color: var(--text-muted);
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

.btn-secundario {
  width: 100%;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  margin-top: 10px;
}

.btn-secundario.chico {
  font-size: 0.78rem;
  padding: 6px;
}

.btn-secundario:hover:not(:disabled) {
  color: var(--accent-red);
  border-color: var(--accent-red);
}

.mesas {
  margin-top: 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 12px;
}

.mesas h4 {
  margin: 0 0 8px;
  font-size: 0.85rem;
}

.mesa-fila {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 0.82rem;
}

.mesa-fila button {
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid var(--primary);
  background: transparent;
  color: var(--primary);
  cursor: pointer;
  font-size: 0.78rem;
}

.mesa-juego {
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
  max-width: 45%;
}

.tanteador-lado span {
  font-size: 0.75rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
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
  font-size: 0.78rem;
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

.btn-canto.flor {
  background: rgba(234, 179, 8, 0.15);
  border-color: rgba(234, 179, 8, 0.45);
}

.pendiente,
.esperando {
  font-size: 0.8rem;
  color: var(--accent-green);
  margin: 0 0 10px;
}

.esperando {
  color: var(--text-muted);
}

.reloj {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin: 0 0 10px;
}

.reloj.apurado {
  color: #fbbf24;
}

.btn-reclamar {
  width: 100%;
  padding: 9px;
  border-radius: 10px;
  border: 1px solid #fbbf24;
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
}

.btn-reclamar:disabled {
  opacity: 0.4;
  cursor: default;
}

.resultado .motivo {
  font-size: 0.78rem;
  color: var(--text-muted);
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

.aviso-flor {
  color: #eab308;
  font-style: normal;
  margin-left: 6px;
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
  .mesa-juego {
    grid-template-columns: 1fr;
  }
}
</style>
