<template>
  <div class="generala-page">
    <div class="glass-panel header-row">
      <button class="btn-back" @click="salir">← Volver al Lobby</button>
      <div class="balance">Saldo: ${{ balance }}</div>
    </div>

    <!-- Elegir contra quién y apostar -->
    <div v-if="!partida" class="glass-panel panel-apuesta">
      <h2 class="titulo">Generala 🎲</h2>

      <div class="modos">
        <button :class="{ activo: modo === 'casa' }" :disabled="cargando" @click="modo = 'casa'">
          Contra la casa
        </button>
        <button :class="{ activo: modo === 'mesa' }" :disabled="cargando" @click="elegirMesas">
          Con otro jugador
        </button>
      </div>

      <p v-if="modo === 'casa'" class="bajada">
        Diez categorías, tres tiradas por turno. Llenás la planilla entera y
        cobrás por lo que sumaste.
      </p>
      <p v-else class="bajada">
        Diez categorías, tres tiradas por turno. Gana el que más suma.
        La generala servida gana en el acto.
      </p>

      <div class="bet-controls">
        <button :disabled="cargando" @click="ajustar(-5)">−</button>
        <span class="bet-display">${{ apuesta.toFixed(2) }}</span>
        <button :disabled="cargando" @click="ajustar(5)">+</button>
      </div>

      <template v-if="modo === 'casa'">
        <button
          class="btn-principal"
          :disabled="cargando || apuesta > parseFloat(balance)"
          @click="empezar"
        >
          {{ cargando ? 'Repartiendo…' : 'JUGAR' }}
        </button>

        <p class="pago">
          Cobrás por puntaje, no por ganarle a la casa: cada punto paga, y
          <strong>{{ equilibrio }} puntos te devuelven la apuesta</strong>.
          Anotar la generala servida paga {{ premioServida }}× aparte.
        </p>

        <div class="tabla-pagos">
          <div v-for="fila in tablaPagos" :key="fila.puntaje" class="fila-pago">
            <span>{{ fila.puntaje }} puntos</span>
            <strong>{{ Number(fila.multiplicador).toFixed(2) }}×</strong>
          </div>
        </div>
      </template>

      <template v-else>
        <button
          class="btn-principal"
          :disabled="cargando || apuesta > parseFloat(balance)"
          @click="crearMesa"
        >
          {{ cargando ? 'Creando…' : 'CREAR MESA' }}
        </button>

        <p class="pago">
          Los dos ponen la apuesta y el que gana se lleva el pozo menos el
          {{ comisionPorciento }}% de la casa. Acá la casa no juega: pone la mesa.
          Tenés {{ plazoDeTurno }} segundos por turno.
        </p>

        <div class="mesas">
          <h4>Mesas abiertas</h4>
          <p v-if="!mesas.length" class="ayuda">No hay ninguna. Creá una y esperá.</p>
          <div v-for="mesa in mesas" :key="mesa.id" class="mesa-fila">
            <span>
              <strong>{{ mesa.creador }}</strong> · ${{ mesa.apuesta }}
              <em class="pozo">pozo ${{ mesa.pozo }}</em>
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
    <div v-else-if="partida.estado === 'esperando'" class="glass-panel panel-apuesta">
      <h2 class="titulo">Esperando rival…</h2>
      <p class="bajada">
        Mesa #{{ partida.mesa_id }} · apuesta ${{ partida.apuesta }} · pozo ${{ partida.pozo }}
      </p>
      <p class="ayuda">
        Quién arranca sale del seed, así que no lo elige ninguno de los dos.
      </p>
      <button class="btn-secundario" :disabled="cargando" @click="abandonar">
        Cancelar y recuperar la apuesta
      </button>
      <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
    </div>

    <!-- La mesa -->
    <div v-else class="mesa">
      <div class="glass-panel panel-dados">
        <div class="marcador">
          <div class="lado" :class="{ activo: enTurno === miAsiento && !terminada }">
            <span class="quien">Vos</span>
            <strong>{{ partida.totales[miAsiento] }}</strong>
          </div>
          <span class="versus">—</span>
          <div class="lado" :class="{ activo: enTurno === suAsiento && !terminada }">
            <span class="quien">{{ suNombre }}</span>
            <strong>{{ partida.totales[suAsiento] }}</strong>
          </div>
        </div>

        <p v-if="!esMesa && partida.puntaje !== undefined" class="cobro">
          <span class="cobro-puntos">{{ partida.puntaje }} puntos</span>
          <span class="cobro-flecha">→</span>
          <span class="cobro-plata">${{ partida.proyeccion }}</span>
          <span class="cobro-detalle">
            {{ Number(partida.multiplicador).toFixed(2) }}× · empatás en {{ equilibrio }}
            <template v-if="partida.generala_servida">
              · +{{ premioServida }}× por la servida
            </template>
          </span>
        </p>

        <div v-if="terminada" class="banner" :class="claseResultado">
          {{ textoResultado }}
        </div>

        <template v-else-if="partida.turno">
          <p class="de-quien">
            {{ miTurno ? 'Tu turno' : `Juega ${suNombre}…` }}
            <span class="tirada">
              tirada {{ partida.turno.tirada }} de {{ partida.turno.tiradas_por_turno }}
            </span>
            <span v-if="partida.turno.servida" class="servida">servida</span>
          </p>

          <p
            v-if="esMesa && partida.segundos_restantes !== null"
            class="reloj"
            :class="{ apurado: partida.segundos_restantes <= 15 }"
          >
            {{ miTurno ? 'Te quedan' : `A ${suNombre} le quedan` }}
            {{ partida.segundos_restantes }}s para jugar este turno
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

          <div v-if="partida.puedo_reclamar" class="acciones">
            <button class="btn-reclamar" :disabled="cargando" @click="reclamar">
              Se le venció el plazo: llevarme la mesa
            </button>
          </div>
        </template>

        <p v-if="esMesa && !terminada" class="pie-mesa">
          Pozo ${{ partida.pozo }} · comisión {{ comisionPorciento }}%
          <button class="btn-abandonar" :disabled="cargando" @click="abandonar">
            Abandonar
          </button>
        </p>

        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
      </div>

      <div class="glass-panel panel-planilla">
        <div class="planilla-head">
          <span>Categoría</span>
          <span>Vos</span>
          <span>{{ esMesa ? abreviado(suNombre) : 'Casa' }}</span>
        </div>

        <button
          v-for="categoria in CATEGORIAS"
          :key="categoria"
          class="fila"
          :class="{
            usada: miPlanilla[categoria] !== null,
            anotable: puedeAnotar(categoria),
            cero: puedeAnotar(categoria) && puntosDe(categoria) === 0,
          }"
          :disabled="!puedeAnotar(categoria)"
          @click="anotar(categoria)"
        >
          <span class="nombre">{{ NOMBRES[categoria] }}</span>
          <span class="mio">
            <template v-if="miPlanilla[categoria] !== null">
              {{ miPlanilla[categoria] }}
            </template>
            <template v-else-if="puedeAnotar(categoria)">
              <em class="propuesta">{{ puntosDe(categoria) }}</em>
            </template>
            <template v-else>·</template>
          </span>
          <span class="suyo">
            {{ suPlanilla[categoria] === null ? '·' : suPlanilla[categoria] }}
          </span>
        </button>

        <p v-if="miTurno && !terminada" class="ayuda">
          Tocá una categoría para anotar. Si no te sirve ninguna, tenés que tachar una con cero.
        </p>

        <button v-if="terminada" class="btn-principal" @click="limpiar">
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
        :help-text="textoFairness"
        formula='dado = 1 + (byte de HMAC_SHA256(server_seed, "client_seed:nonce:i") mod 6), con muestreo con rechazo'
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
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

const VACIA = Object.fromEntries(CATEGORIAS.map((categoria) => [categoria, null]));

const router = useRouter();
const balance = ref('0.00');
const cargando = ref(false);
const errorMsg = ref('');

const modo = ref('casa');
const apuesta = ref(20);
const partida = ref(null);
const mesas = ref([]);
const comision = ref('0.05');
const plazoDeTurno = ref(90);

// La tabla de pagos contra la casa. Viene del servidor para que la
// pantalla no pueda quedar diciendo un pago distinto del que se liquida.
const equilibrio = ref(165);
const premioServida = ref('9');
const tablaPagos = ref([]);

let sondeo = null;

// Los índices que se van a volver a tirar. Arranca en todos: lo normal en la
// primera tirada es cambiar casi todo.
const aTirar = ref([0, 1, 2, 3, 4]);

// --------------------------- quién es quién ---------------------------
// Contra la casa el jugador es siempre el asiento 0; en una mesa depende de si
// creó la mesa o se sentó. Todo lo que se muestra pasa por acá, así la
// pantalla es la misma en los dos modos.

const esMesa = computed(() => Boolean(partida.value?.mesa_id));
const miAsiento = computed(() => (esMesa.value ? partida.value.asiento : 0));
const suAsiento = computed(() => 1 - miAsiento.value);

const suNombre = computed(() =>
  esMesa.value ? partida.value.jugadores[suAsiento.value] || 'Rival' : 'La casa',
);

const abreviado = (nombre) => (nombre || '').slice(0, 7);

const terminada = computed(() => Boolean(partida.value?.terminada));
const enTurno = computed(() => partida.value?.en_turno);

const miPlanilla = computed(() => partida.value?.planillas?.[miAsiento.value] || VACIA);
const suPlanilla = computed(() => partida.value?.planillas?.[suAsiento.value] || VACIA);

const miTurno = computed(
  () => Boolean(partida.value) && !terminada.value && enTurno.value === miAsiento.value,
);
const puedeElegir = computed(
  () => miTurno.value && partida.value?.turno?.puede_tirar && !cargando.value,
);

const puntosDe = (categoria) => partida.value?.turno?.puntajes?.[categoria] ?? 0;
const puedeAnotar = (categoria) =>
  !!miTurno.value && !cargando.value && miPlanilla.value[categoria] === null;

const comisionPorciento = computed(() => (parseFloat(comision.value) * 100).toFixed(0));

const claseResultado = computed(() => {
  const estado = partida.value;
  if (!estado) return 'empate';

  // Contra la casa el verde o el rojo los decide la plata, no el duelo.
  if (!esMesa.value) {
    const cobro = Number(estado.payout);
    const apostado = Number(estado.apuesta);
    if (cobro > apostado) return 'gano';
    return cobro === apostado ? 'empate' : 'perdio';
  }

  const ganador = estado.ganador;
  if (ganador === null || ganador === undefined) return 'empate';
  return ganador === miAsiento.value ? 'gano' : 'perdio';
});

const textoResultado = computed(() => {
  const estado = partida.value;
  if (!estado) return '';

  if (estado.motivo === 'plazo_vencido') {
    return estado.ganador === miAsiento.value
      ? `⏱ Se le venció el plazo: cobrás $${estado.premio}`
      : 'Se te venció el plazo del turno y perdiste la mesa';
  }

  if (estado.motivo === 'abandono') {
    return estado.ganador === miAsiento.value
      ? `Abandonó: cobrás $${estado.premio}`
      : 'Abandonaste la mesa';
  }

  const servida =
    estado.generala_servida_de !== null && estado.generala_servida_de !== undefined;
  const cola = servida
    ? estado.generala_servida_de === miAsiento.value
      ? ' con generala servida'
      : ` con generala servida de ${suNombre.value}`
    : '';

  // Contra la casa el resultado es lo que cobrás por tu planilla. Quién
  // sumó más no entra: decirlo como ganar o perder sería mentir sobre de
  // qué depende la plata.
  if (!esMesa.value) {
    const cobro = Number(estado.payout);
    const servida = estado.generala_servida ? ' 🎲 ¡generala servida!' : '';
    const verbo = cobro >= Number(estado.apuesta) ? 'cobrás' : 'te quedan';
    return `${estado.puntaje} puntos · ${verbo} $${cobro.toFixed(2)}`
      + ` (${Number(estado.multiplicador).toFixed(2)}×)${servida}`;
  }

  if (estado.ganador === miAsiento.value) {
    return `🎲 Ganaste $${Number(estado.premio).toFixed(2)}${cola}`;
  }

  if (estado.ganador === suAsiento.value) return `Perdiste${cola}`;

  return `Empate: vuelve tu apuesta de $${Number(estado.apuesta).toFixed(2)}`;
});

const textoFairness = computed(() =>
  esMesa.value
    ? 'Los dados de la mesa salen de un seed comprometido antes de que nadie se siente, y se consumen en orden. Quién arranca también sale del seed, con un prefijo aparte para no desplazar ni un dado. Al cerrar la mesa se revela el seed y podés rehacer cada tirada.'
    : 'Los dados de toda la partida salen de un seed comprometido antes de empezar y se consumen en orden. Al terminar se revela el seed y podés rehacer cada tirada.',
);

// --------------------------- cargas ---------------------------

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
    equilibrio.value = res.data.equilibrio;
    premioServida.value = Number(res.data.premio_servida).toFixed(0);
    tablaPagos.value = res.data.tabla;
  } catch {
    // Si falla quedan los valores por defecto, que son sólo informativos.
  }
};

const cargarMesas = async () => {
  const res = await api.get('/games/generala/mesas');
  mesas.value = res.data.mesas;
  comision.value = res.data.comision;
  plazoDeTurno.value = res.data.plazo_de_turno;
  return res.data.mi_mesa;
};

const elegirMesas = async () => {
  modo.value = 'mesa';
  errorMsg.value = '';
  try {
    await cargarMesas();
  } catch {
    mesas.value = [];
  }
};

const aplicar = (datos) => {
  partida.value = datos;
  // Turno nuevo: por defecto se vuelven a tirar todos.
  aTirar.value = datos.turno && datos.turno.tirada === 1 ? [0, 1, 2, 3, 4] : [];
};

// La apuesta se debita al empezar, así que lo que quedó sin terminar está
// esperando: se retoma antes de ofrecer apostar de nuevo.
const retomar = async () => {
  try {
    const miMesa = await cargarMesas();
    if (miMesa) {
      const res = await api.get(`/games/generala/mesas/${miMesa}`);
      modo.value = 'mesa';
      aplicar(res.data);
      arrancarSondeo();
      return;
    }
  } catch {
    // Sin mesas se sigue con la partida contra la casa.
  }

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

onUnmounted(() => detenerSondeo());

// --------------------------- contra la casa ---------------------------

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

// --------------------------- mesas ---------------------------

const crearMesa = async () => {
  cargando.value = true;
  errorMsg.value = '';

  try {
    const res = await api.post('/games/generala/mesas', {
      bet_amount: apuesta.value.toFixed(2),
    });
    aplicar(res.data);
    await cargarSaldo();
    arrancarSondeo();
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo crear la mesa';
  } finally {
    cargando.value = false;
  }
};

const sentarse = async (mesaId) => {
  cargando.value = true;
  errorMsg.value = '';

  try {
    const res = await api.post(`/games/generala/mesas/${mesaId}/sentarse`, {});
    aplicar(res.data);
    await cargarSaldo();

    // La generala servida en la primera tirada cierra la mesa acá mismo.
    if (res.data.terminada) cerrar(res.data);
    else arrancarSondeo();
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo sentar';
    await elegirMesas();
  } finally {
    cargando.value = false;
  }
};

const abandonar = async () => {
  cargando.value = true;
  errorMsg.value = '';

  try {
    const res = await api.post(
      `/games/generala/mesas/${partida.value.mesa_id}/abandonar`,
      {},
    );
    detenerSondeo();
    await cargarSaldo();

    // Cancelar una mesa que nadie ocupó vuelve al listado; entregar una mesa
    // en juego muestra el resultado, como cualquier otra partida.
    if (res.data.ganador === null) {
      partida.value = null;
      await elegirMesas();
    } else {
      aplicar(res.data);
    }
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo abandonar';
  } finally {
    cargando.value = false;
  }
};

const reclamar = async () => {
  cargando.value = true;
  errorMsg.value = '';

  try {
    const res = await api.post(
      `/games/generala/mesas/${partida.value.mesa_id}/reclamar`,
      {},
    );
    detenerSondeo();
    aplicar(res.data);
    await cargarSaldo();
    cerrar(res.data);
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || 'No se pudo reclamar';
  } finally {
    cargando.value = false;
  }
};

// --------------------------- jugar ---------------------------

const alternar = (indice) => {
  if (!puedeElegir.value) return;

  aTirar.value = aTirar.value.includes(indice)
    ? aTirar.value.filter((otro) => otro !== indice)
    : [...aTirar.value, indice];
};

const enviar = async (accion) => {
  cargando.value = true;
  errorMsg.value = '';

  const ruta = esMesa.value
    ? `/games/generala/mesas/${partida.value.mesa_id}/accion`
    : '/games/generala/accion';

  try {
    const res = await api.post(ruta, { accion });
    aplicar(res.data);
    if (res.data.terminada) {
      detenerSondeo();
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
  const gano = esMesa.value
    ? datos.ganador === miAsiento.value
    : Number(datos.payout) > Number(datos.apuesta);

  if (gano) {
    confetti({ particleCount: 110, spread: 80, origin: { y: 0.6 } });
  }
};

const limpiar = async () => {
  detenerSondeo();
  partida.value = null;
  errorMsg.value = '';
  if (modo.value === 'mesa') await elegirMesas();
};

const salir = () => {
  detenerSondeo();
  router.push('/lobby');
};

// --------------------------- sondeo ---------------------------
// Mientras le toca al rival el cliente pregunta cada dos segundos. Para un
// juego por turnos alcanza y evita mantener una conexión abierta. El reloj del
// turno se actualiza con la misma respuesta, así que no hace falta un contador
// aparte que pueda desincronizarse del servidor.

const refrescarMesa = async () => {
  if (!esMesa.value || terminada.value || cargando.value) return;

  try {
    const res = await api.get(`/games/generala/mesas/${partida.value.mesa_id}`);
    const avanzo = res.data.acciones_jugadas !== partida.value.acciones_jugadas;

    // Si no pasó nada nuevo, los dados elegidos no se pisan: el jugador podría
    // estar justo tildando cuáles guardar.
    if (avanzo) aplicar(res.data);
    else partida.value = res.data;

    if (avanzo || res.data.terminada) await cargarSaldo();

    if (res.data.terminada) {
      detenerSondeo();
      cerrar(res.data);
    }
  } catch {
    // Un error puntual no corta la partida: se reintenta en el próximo sondeo.
  }
};

const arrancarSondeo = () => {
  detenerSondeo();
  sondeo = setInterval(refrescarMesa, 2000);
};

// Declarada con `function` a propósito: se usa en onUnmounted, que se registra
// antes de esta línea.
function detenerSondeo() {
  if (sondeo) {
    clearInterval(sondeo);
    sondeo = null;
  }
}
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

.btn-secundario {
  width: 100%;
  margin-top: 14px;
  padding: 11px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-secundario:hover {
  color: var(--text-main);
  border-color: var(--primary);
}

.pago {
  margin: 14px 0 0;
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.5;
}

.error-msg {
  margin-top: 12px;
  color: #f87171;
  font-size: 0.82rem;
}

.mesas {
  margin-top: 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 12px;
  text-align: left;
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

.mesa-fila .pozo {
  font-style: normal;
  color: var(--text-muted);
  font-size: 0.74rem;
  margin-left: 6px;
}

.mesa-fila button {
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid var(--primary);
  background: transparent;
  color: var(--primary);
  cursor: pointer;
  font-size: 0.78rem;
  white-space: nowrap;
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

.tabla-pagos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(84px, 1fr));
  gap: 6px;
  margin-top: 12px;
}

.fila-pago {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 7px 4px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  font-size: 0.66rem;
  color: var(--text-muted);
}

.fila-pago strong {
  font-size: 0.85rem;
  color: var(--text-main);
}

.cobro {
  display: flex;
  align-items: baseline;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.cobro-puntos {
  font-size: 1.05rem;
  font-weight: 700;
}

.cobro-flecha {
  color: var(--text-muted);
}

.cobro-plata {
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--accent-green, #22c55e);
}

.cobro-detalle {
  width: 100%;
  text-align: center;
  font-size: 0.68rem;
  color: var(--text-muted);
}

.reloj {
  text-align: center;
  margin: -8px 0 14px;
  font-size: 0.73rem;
  color: var(--text-muted);
}

.reloj.apurado {
  color: #fbbf24;
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

.btn-reclamar {
  padding: 9px 18px;
  border-radius: 10px;
  border: 1px solid #fbbf24;
  background: rgba(251, 191, 36, 0.12);
  color: #fbbf24;
  font-size: 0.8rem;
  font-weight: 700;
  cursor: pointer;
}

.pie-mesa {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin: 16px 0 0;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
  font-size: 0.73rem;
  color: var(--text-muted);
}

.btn-abandonar {
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.72rem;
}

.btn-abandonar:hover {
  color: #f87171;
  border-color: #f87171;
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
