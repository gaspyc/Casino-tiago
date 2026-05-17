<template>
  <div class="plinko-page">
    <div class="glass-panel header-row">
      <button @click="router.push('/lobby')" class="btn-back">← Volver al Lobby</button>
      <div class="balance">Saldo: ${{ balance }}</div>
    </div>

    <div class="plinko-shell">
      <aside class="glass-panel controls-panel">
        <h2>Plinko</h2>

        <label class="field">
          <span>Apuesta</span>
          <input type="number" v-model.number="betAmount" min="1" step="0.01" :disabled="isDropping" />
        </label>

        <label class="field">
          <span>Riesgo</span>
          <select v-model="risk" :disabled="isDropping">
            <option value="low">Bajo</option>
            <option value="medium">Medio</option>
            <option value="high">Alto</option>
          </select>
        </label>

        <label class="field">
          <span>Filas: {{ rows }}</span>
          <input type="range" v-model.number="rows" min="8" max="16" step="1" :disabled="isDropping" />
        </label>

        <div class="quick-rows">
          <button v-for="item in [8, 10, 12, 14, 16]" :key="item" @click="rows = item" :class="{ active: rows === item }" :disabled="isDropping">
            {{ item }}
          </button>
        </div>

        <label class="auto-toggle">
          <input type="checkbox" v-model="autoPlay" :disabled="isDropping && autoPlay" />
          <span>Re-apostar en automatico</span>
        </label>

        <label class="field">
          <span>Rondas automaticas</span>
          <input type="number" v-model.number="autoRounds" min="1" max="200" step="1" :disabled="hasActiveDrops" />
        </label>

        <button class="btn-drop" @click="dropBall" :disabled="!canBet">
          {{ autoPlay ? (autoRunning ? 'Detener Auto' : 'Iniciar Auto') : 'Soltar Bola' }}
        </button>
        <button v-if="autoRunning" class="btn-stop" @click="stopAuto">Detener auto</button>

        <div v-if="lastResult" class="result-card" :class="{ win: lastResult.net_profit > 0 }">
          <span>{{ lastMultiplier }}x</span>
          <strong>{{ lastResult.net_profit > 0 ? `Ganaste $${formatMoney(lastResult.total_payout)}` : 'Sin premio' }}</strong>
        </div>

        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
      </aside>

      <main class="glass-panel board-panel">
        <canvas ref="canvasRef" width="900" height="640" class="plinko-canvas"></canvas>

        <!-- FIX: el ancho de los slots ahora usa getColGap() igual que el backend -->
        <div class="slots-row" :style="{ width: `${(rows + 1) * getColGap(rows)}px`, gridTemplateColumns: `repeat(${rows + 1}, minmax(0, 1fr))` }">
          <div v-for="(multiplier, index) in multipliers" :key="index" class="slot" :class="{ hit: lastSlot === index }">
            {{ multiplier }}x
          </div>
        </div>

        <div class="stats-row">
          <div>
            <span>Riesgo</span>
            <strong>{{ riskLabel }}</strong>
          </div>
          <div>
            <span>Filas</span>
            <strong>{{ rows }}</strong>
          </div>
          <div>
            <span>Auto restante</span>
            <strong>{{ autoRunning ? remainingAuto : '-' }}</strong>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import confetti from 'canvas-confetti';
import api from '../shared/api';

const router = useRouter();
const balance = ref('0.00');
const betAmount = ref(5);
const risk = ref('medium');
const rows = ref(12);
const autoPlay = ref(false);
const autoRounds = ref(10);
const remainingAuto = ref(0);
const autoRunning = ref(false);
const errorMsg = ref('');
const lastResult = ref(null);
const lastSlot = ref(null);
const currentBoard = ref(null);

const canvasRef = ref(null);
let ctx = null;
let animationFrame = null;

const chips = ref([]);
const gainFlashes = ref([]);

const BOARD_CENTER_X = 450;
const BALL_START_Y = 24;
const PEG_START_Y = 58;
const ROW_GAP = 35;
const BOARD_WIDTH = 620;
const pegRadius = 6;
const ballRadius = 9;

// FIX: función unificada, idéntica a la del backend.
// Antes el frontend usaba COL_GAP=46 fijo para los pines pero
// BOARD_WIDTH/(rows+1) para los slots, generando un desajuste visual
// entre donde caía la bola y qué slot se iluminaba.
const getColGap = (rowCount) => BOARD_WIDTH / (rowCount + 2);

const hasActiveDrops = computed(() => chips.value.length > 0);

const riskConfig = {
  low: { alpha: 0.28, floor: 0.45, cap: 16 },
  medium: { alpha: 0.42, floor: 0.25, cap: 120 },
  high: { alpha: 0.62, floor: 0, cap: 1000 },
};

const riskLabel = computed(() => ({ low: 'Bajo', medium: 'Medio', high: 'Alto' }[risk.value]));
const canBet = computed(() => betAmount.value > 0 && betAmount.value <= parseFloat(balance.value));
const lastMultiplier = computed(() => lastResult.value?.result_data?.multiplier || '0.00');

const factorial = (value) => {
  let result = 1;
  for (let i = 2; i <= value; i += 1) result *= i;
  return result;
};

const combination = (n, k) => factorial(n) / (factorial(k) * factorial(n - k));

const multipliers = computed(() => {
  const config = riskConfig[risk.value];
  const probabilities = Array.from({ length: rows.value + 1 }, (_, slot) => combination(rows.value, slot) / (2 ** rows.value));
  const raw = probabilities.map((probability) => Math.min(config.floor + ((1 / probability) ** config.alpha) * 0.12, config.cap));
  const expectedValue = raw.reduce((sum, multiplier, index) => sum + multiplier * probabilities[index], 0);
  const scale = 0.96 / expectedValue;
  return raw.map((multiplier) => (multiplier * scale).toFixed(2));
});

const pegs = computed(() => {
  const items = [];
  // FIX: usa getColGap() unificado en lugar de COL_GAP=46 fijo
  const colGap = getColGap(rows.value);

  for (let row = 0; row < rows.value; row += 1) {
    for (let index = 0; index <= row; index += 1) {
      items.push({
        row,
        index,
        x: BOARD_CENTER_X + (index - row / 2.0) * colGap,
        y: PEG_START_Y + row * ROW_GAP,
      });
    }
  }
  return items;
});

const renderedPegs = computed(() => currentBoard.value?.pegs || pegs.value);
const renderedPegRadius = computed(() => currentBoard.value?.peg_radius || pegRadius);
const renderedBallRadius = computed(() => currentBoard.value?.ball_radius || ballRadius);

const loadBalance = async () => {
  const res = await api.get('/wallet/balance');
  balance.value = parseFloat(res.data.balance).toFixed(2);
};

const formatMoney = (value) => parseFloat(value).toFixed(2);

const cancelAnimation = () => {
  if (animationFrame) {
    cancelAnimationFrame(animationFrame);
    animationFrame = null;
  }
};

const renderLoop = () => {
  if (!ctx || !canvasRef.value) return;
  const W = canvasRef.value.width;
  const H = canvasRef.value.height;

  ctx.clearRect(0, 0, W, H);

  // Draw pegs
  ctx.fillStyle = '#dbeafe';
  renderedPegs.value.forEach(p => {
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r || renderedPegRadius.value, 0, Math.PI * 2);
    ctx.fill();
  });

  // Update and draw chips
  for (let i = chips.value.length - 1; i >= 0; i--) {
    const chip = chips.value[i];
    
    if (!chip.done) {
      chip.frame++;
      if (chip.frame >= chip.path.length) {
        chip.done = true;
        const finalX = chip.path[chip.path.length - 1].x;
        gainFlashes.value.push({
          x: finalX,
          y: H - 80,
          val: chip.gain,
          alpha: 1,
          vy: -1.2,
          isWin: chip.isWin
        });
        chips.value.splice(i, 1);
        continue;
      } else {
        chip.x = chip.path[chip.frame].x;
        chip.y = chip.path[chip.frame].y;
      }
    }

    // Draw chip
    ctx.beginPath();
    ctx.arc(chip.x, chip.y, renderedBallRadius.value, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(83, 74, 183, 1)`;
    ctx.fill();
    ctx.strokeStyle = `rgba(60, 52, 137, 1)`;
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // Draw flashes
  for (let i = gainFlashes.value.length - 1; i >= 0; i--) {
    const g = gainFlashes.value[i];
    ctx.globalAlpha = Math.max(0, g.alpha);
    ctx.font = 'bold 20px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = g.isWin ? '#4ade80' : '#94a3b8';
    ctx.fillText(g.isWin ? '+' + g.val : g.val, g.x, g.y);
    ctx.globalAlpha = 1;
    g.y += g.vy;
    g.alpha -= 0.02;
    if (g.alpha <= 0) {
      gainFlashes.value.splice(i, 1);
    }
  }

  animationFrame = requestAnimationFrame(renderLoop);
};

const stopAuto = () => {
  autoRunning.value = false;
  remainingAuto.value = 0;
};

const scheduleNextAuto = () => {
  if (!autoRunning.value || remainingAuto.value <= 0 || !canBet.value) {
    stopAuto();
    return;
  }

  if (chips.value.length > 0) {
    setTimeout(scheduleNextAuto, 350);
    return;
  }

  setTimeout(dropBall, 850);
};

const dropBall = async () => {
  if (!canBet.value) {
    errorMsg.value = 'Saldo insuficiente';
    stopAuto();
    return;
  }

  if (autoPlay.value) {
    if (autoRunning.value) {
      stopAuto();
      return;
    } else {
      remainingAuto.value = Math.max(1, Math.min(200, Number(autoRounds.value) || 1));
      autoRunning.value = true;
    }
  }

  errorMsg.value = '';
  balance.value = (parseFloat(balance.value) - Number(betAmount.value)).toFixed(2);

  try {
    const res = await api.post('/games/plinko/drop', {
      bet_amount: betAmount.value,
      risk: risk.value,
      rows: rows.value,
    });

    currentBoard.value = res.data.result_data.board || null;
    
    if (res.data.result_data.visual_path) {
      chips.value.push({
        path: res.data.result_data.visual_path,
        frame: 0,
        x: BOARD_CENTER_X,
        y: BALL_START_Y,
        done: false,
        gain: res.data.result_data.multiplier,
        isWin: res.data.net_profit > 0
      });
    }

    lastResult.value = res.data;
    lastSlot.value = res.data.result_data.slot_index;
    await loadBalance();

    if (res.data.net_profit > 0 && Math.random() > 0.5) {
      confetti({ particleCount: 30, spread: 70, origin: { y: 0.7 } });
    }

    if (autoRunning.value) {
      remainingAuto.value -= 1;
      scheduleNextAuto();
    }
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || e.message || 'Error al jugar';
    await loadBalance();
    stopAuto();
  }
};

watch([rows, risk], () => {
  if (hasActiveDrops.value) return;
  lastSlot.value = null;
  currentBoard.value = null;
});

onMounted(() => {
  loadBalance();
  ctx = canvasRef.value.getContext('2d');
  animationFrame = requestAnimationFrame(renderLoop);
});

onBeforeUnmount(() => {
  stopAuto();
  cancelAnimation();
});
</script>

<style scoped>
.plinko-page {
  padding: 20px 40px;
  max-width: 1280px;
  margin: 0 auto;
  width: 100%;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  margin-bottom: 24px;
}

.btn-back {
  background: transparent;
  color: var(--text-muted);
  border: none;
  cursor: pointer;
  font-weight: 600;
}

.balance {
  color: var(--accent-green);
  font-size: 1.25rem;
  font-weight: 700;
}

.plinko-shell {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 24px;
}

.controls-panel,
.board-panel {
  padding: 24px;
}

.controls-panel h2 {
  font-size: 2rem;
  margin-bottom: 22px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
  color: var(--text-muted);
  font-size: 0.9rem;
  font-weight: 600;
}

select {
  width: 100%;
  padding: 12px 16px;
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: white;
  font-family: 'Inter', sans-serif;
}

input[type='range'] {
  padding: 0;
  accent-color: var(--accent-green);
}

.quick-rows {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  margin-bottom: 18px;
}

.quick-rows button {
  min-height: 38px;
  background: rgba(255, 255, 255, 0.08);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  cursor: pointer;
}

.quick-rows button.active {
  background: var(--accent-green);
  border-color: var(--accent-green);
}

.auto-toggle {
  display: flex;
  gap: 10px;
  align-items: center;
  margin: 8px 0 16px;
  color: var(--text-main);
  font-weight: 600;
}

.auto-toggle input {
  width: auto;
}

.btn-drop,
.btn-stop {
  width: 100%;
  border: none;
  border-radius: 8px;
  color: white;
  font-weight: 800;
  padding: 15px 18px;
  cursor: pointer;
}

.btn-drop {
  background: linear-gradient(180deg, #22c55e, #15803d);
}

.btn-drop:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-stop {
  margin-top: 10px;
  background: rgba(239, 68, 68, 0.9);
}

.result-card {
  margin-top: 18px;
  padding: 16px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.result-card span {
  display: block;
  color: #facc15;
  font-size: 2rem;
  font-weight: 900;
}

.result-card strong {
  color: var(--text-muted);
}

.result-card.win strong {
  color: var(--accent-green);
}

.error-msg {
  color: var(--accent-red);
  margin-top: 12px;
}

.board-panel {
  min-width: 0;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.82), rgba(30, 41, 59, 0.72));
}

.plinko-canvas {
  width: 100%;
  height: auto;
  border-radius: 12px;
  background: transparent;
  display: block;
}

.slots-row {
  display: grid;
  gap: 4px;
  margin-top: -28px;
  margin-left: auto;
  margin-right: auto;
  max-width: 100%;
}

.slot {
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  background: rgba(34, 197, 94, 0.16);
  border: 1px solid rgba(34, 197, 94, 0.32);
  border-radius: 6px;
  color: #bbf7d0;
  font-size: 0.72rem;
  font-weight: 800;
  overflow: hidden;
}

.slot.hit {
  background: #facc15;
  border-color: #fef08a;
  color: #1f2937;
  transform: translateY(-4px);
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 18px;
}

.stats-row div {
  padding: 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
}

.stats-row span {
  display: block;
  color: var(--text-muted);
  font-size: 0.78rem;
  margin-bottom: 4px;
}

.stats-row strong {
  font-size: 1.1rem;
}

@media (max-width: 900px) {
  .plinko-page {
    padding: 12px;
  }

  .plinko-shell {
    grid-template-columns: 1fr;
  }

  .controls-panel,
  .board-panel {
    padding: 16px;
  }
}

@media (max-width: 520px) {
  .header-row {
    padding: 12px;
  }

  .slots-row {
    gap: 2px;
  }

  .slot {
    min-height: 30px;
    font-size: 0.58rem;
  }

  .stats-row {
    grid-template-columns: 1fr;
  }
}
</style>
