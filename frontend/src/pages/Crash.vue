<template>
  <div class="crash-container">
    <div class="header">
      <button class="back-btn" @click="router.push('/lobby')">← Volver al Lobby</button>
      <h2>🚀 Crash Multiplayer</h2>
    </div>

    <div class="game-area">
      <!-- Izquierda: Controles y Lista de Apuestas -->
      <div class="sidebar glass-panel">
        <div class="bet-controls" v-if="gameState.status === 'BETTING'">
          <h3>Haz tu apuesta</h3>
          <div class="input-group">
            <span class="currency">$</span>
            <input type="number" v-model.number="betAmount" min="1" step="1" />
          </div>
          <button 
            class="btn-action bet" 
            :disabled="hasBet || betAmount <= 0"
            @click="placeBet">
            {{ hasBet ? 'Apostado' : 'Apostar' }}
          </button>
        </div>
        
        <div class="bet-controls" v-else-if="gameState.status === 'IN_PROGRESS'">
          <button 
            class="btn-action cashout" 
            :disabled="!hasBet || hasCashedOut"
            @click="cashOut">
            {{ hasCashedOut ? '¡Retirado!' : 'CASH OUT' }}
          </button>
        </div>

        <div class="bet-controls" v-else>
          <button class="btn-action waiting" disabled>
            Esperando próxima ronda...
          </button>
        </div>

        <div class="players-list">
          <h4>Jugadores Activos ({{ gameState.bets.length }})</h4>
          <ul>
            <li v-for="bet in gameState.bets" :key="bet.user_id" 
                :class="{'cashed-out': bet.cashout_multiplier, 'crashed': gameState.status === 'CRASHED' && !bet.cashout_multiplier}">
              <span class="username">{{ bet.username }}</span>
              <span class="bet-amount">${{ bet.bet_amount }}</span>
              <span v-if="bet.cashout_multiplier" class="cashout-mult">{{ bet.cashout_multiplier }}x</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- Derecha: Pantalla del Juego -->
      <div class="screen-area glass-panel">
        
        <div class="status-badge" :class="gameState.status.toLowerCase()">
          {{ statusText }}
        </div>

        <div class="multiplier-display" :class="{ 'is-crashed': gameState.status === 'CRASHED' }">
          <span v-if="gameState.status === 'BETTING'" class="timer">
            Iniciando en {{ Math.ceil(gameState.timer) }}s
          </span>
          <span v-else class="mult-text">
            {{ gameState.multiplier.toFixed(2) }}x
          </span>
        </div>
        
        <!-- Animacion de Partículas simples o linea -->
        <div class="graph-bg">
           <svg preserveAspectRatio="none" viewBox="0 0 100 100" class="curve" v-if="gameState.status === 'IN_PROGRESS'">
             <path :d="curvePath" fill="none" stroke="url(#gradient)" stroke-width="2" />
             <defs>
               <linearGradient id="gradient" x1="0%" y1="100%" x2="100%" y2="0%">
                 <stop offset="0%" stop-color="#f59e0b" />
                 <stop offset="100%" stop-color="#ef4444" />
               </linearGradient>
             </defs>
           </svg>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const ws = ref(null);
const betAmount = ref(10);
const currentUser = ref(null);

const gameState = ref({
  status: 'BETTING',
  multiplier: 1.00,
  timer: 10.0,
  bets: []
});

const statusText = computed(() => {
  if (gameState.value.status === 'BETTING') return 'HACIENDO APUESTAS';
  if (gameState.value.status === 'IN_PROGRESS') return '¡VOLANDO!';
  return 'CRASHEADO';
});

const curvePath = computed(() => {
  // Simple bezier curve animation based on multiplier
  const progress = Math.min((gameState.value.multiplier - 1) / 10, 1); 
  const x = progress * 100;
  const y = 100 - (progress * 100);
  return `M 0 100 Q ${x * 0.5} 100, ${x} ${y}`;
});

const myBet = computed(() => {
  if (!currentUser.value) return null;
  return gameState.value.bets.find(b => b.username === currentUser.value.username);
});

const hasBet = computed(() => !!myBet.value);
const hasCashedOut = computed(() => myBet.value && myBet.value.cashout_multiplier !== null);

onMounted(() => {
  const token = localStorage.getItem('casino_token');
  if (!token) {
    router.push('/login');
    return;
  }
  
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    currentUser.value = {
      username: payload.sub
    };
  } catch (e) {
    console.error(e);
  }

  connectWebSocket(token);
});

onUnmounted(() => {
  if (ws.value) {
    ws.value.close();
  }
});

function connectWebSocket(token) {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';
  const wsUrl = apiUrl.replace('http', 'ws');
  
  ws.value = new WebSocket(`${wsUrl}/games/crash/ws?token=${token}`);

  ws.value.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'state') {
      gameState.value = msg.data;
    }
  };

  ws.value.onerror = (err) => {
    console.error("Crash WebSocket error:", err);
  };
}

function placeBet() {
  if (!ws.value || ws.value.readyState !== WebSocket.OPEN) return;
  ws.value.send(JSON.stringify({
    action: 'place_bet',
    amount: betAmount.value
  }));
}

function cashOut() {
  if (!ws.value || ws.value.readyState !== WebSocket.OPEN) return;
  ws.value.send(JSON.stringify({
    action: 'cash_out'
  }));
}
</script>

<style scoped>
.crash-container {
  padding: 1rem;
  max-width: 1200px;
  margin: 0 auto;
  min-height: 100vh;
}

.header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.header h2 {
  font-size: 1.5rem;
  margin: 0;
}

.back-btn {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.game-area {
  display: flex;
  gap: 2rem;
  flex-direction: row;
}

.sidebar {
  flex: 0 0 300px;
}

.screen-area {
  flex: 1;
}

.glass-panel {
  background: rgba(20, 20, 30, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 1.5rem;
}

/* Sidebar */
.bet-controls {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.input-group {
  position: relative;
  margin: 1rem 0;
}

.currency {
  position: absolute;
  left: 1rem;
  top: 50%;
  transform: translateY(-50%);
  color: #10b981;
  font-weight: bold;
}

.input-group input {
  width: 100%;
  padding: 0.8rem 1rem 0.8rem 2rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: white;
  font-size: 1.2rem;
  font-weight: bold;
}

.btn-action {
  width: 100%;
  padding: 1rem;
  border: none;
  border-radius: 8px;
  font-size: 1.2rem;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.2s;
  color: white;
}

.btn-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-action.bet {
  background: #10b981;
}

.btn-action.cashout {
  background: #f59e0b;
  animation: pulse 1s infinite;
}

.btn-action.waiting {
  background: rgba(255, 255, 255, 0.1);
  color: #9ca3af;
}

@keyframes pulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.02); }
  100% { transform: scale(1); }
}

/* Players List */
.players-list ul {
  list-style: none;
  padding: 0;
  margin: 1rem 0 0 0;
  max-height: 300px;
  overflow-y: auto;
}

.players-list li {
  display: flex;
  justify-content: space-between;
  padding: 0.8rem;
  background: rgba(0, 0, 0, 0.2);
  margin-bottom: 0.5rem;
  border-radius: 6px;
  font-size: 0.9rem;
}

.players-list li.cashed-out {
  color: #10b981;
  border-left: 3px solid #10b981;
}

.players-list li.crashed {
  color: #ef4444;
  opacity: 0.7;
}

.cashout-mult {
  font-weight: bold;
}

/* Screen Area */
.screen-area {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  overflow: hidden;
}

.status-badge {
  position: absolute;
  top: 1rem;
  left: 1rem;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: bold;
  letter-spacing: 1px;
}

.status-badge.betting { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
.status-badge.in_progress { background: rgba(16, 185, 129, 0.2); color: #10b981; }
.status-badge.crashed { background: rgba(239, 68, 68, 0.2); color: #ef4444; }

.multiplier-display {
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 5rem;
  font-weight: 900;
  color: white;
  z-index: 10;
  text-shadow: 0 0 20px rgba(255, 255, 255, 0.2);
  transition: color 0.3s ease;
  font-variant-numeric: tabular-nums;
  font-family: monospace;
  width: 350px;
  text-align: center;
}

.timer {
  font-size: 2.5rem;
  color: #9ca3af;
}

.multiplier-display.is-crashed .mult-text {
  color: #ef4444;
  text-shadow: 0 0 30px rgba(239, 68, 68, 0.5);
}

.graph-bg {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 50%;
  z-index: 1;
  pointer-events: none;
}

.curve {
  width: 100%;
  height: 100%;
}

@media (max-width: 800px) {
  .game-area {
    flex-direction: column-reverse;
  }
  .sidebar {
    flex: none;
    width: 100%;
  }
  .screen-area {
    min-height: 250px;
  }
  .multiplier-display {
    font-size: 4rem;
    width: 100%;
  }
}
</style>
