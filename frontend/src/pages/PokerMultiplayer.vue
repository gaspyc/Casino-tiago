<template>
  <div class="mp-poker">
    <div class="header-row">
      <button class="btn-back" @click="$router.push('/lobby-poker')">← Salir al Lobby</button>
      <div class="table-info" v-if="tableState">
        <h2>{{ tableState.name }}</h2>
        <span class="status-badge">{{ formatStatus(tableState.status) }}</span>
      </div>
      <div class="user-wallet">
        <span>Billetera: <span class="balance">${{ balance }}</span></span>
      </div>
    </div>

    <div v-if="!tableState" class="loading-state">
      <h2>Conectando a la mesa...</h2>
    </div>

    <div v-else class="main-layout">
      
      <!-- Oval Table -->
      <div class="poker-table-wrapper">
        <div class="poker-table">
          
          <!-- Community Cards & Pot -->
          <div class="center-area">
            <div class="pot-display" v-if="tableState.pot > 0">
              POT: ${{ tableState.pot.toFixed(2) }}
            </div>
            <div class="community-cards">
              <div v-for="(c, i) in paddedCommunityCards" :key="`cc-${i}`" class="card" :class="{'empty': c === 'EMPTY'}">
                <span v-if="c !== 'EMPTY'" :class="getSuitClass(c)">{{ formatCard(c) }}</span>
              </div>
            </div>
          </div>

          <!-- Players Ring -->
          <div v-for="(p, i) in playersWithPositions" :key="p.user_id" 
               class="player-seat" :style="getSeatStyle(i, playersWithPositions.length)">
            <div class="player-card" :class="{'my-turn': isPlayerTurn(p.user_id), 'folded': p.status === 'FOLDED'}">
              <div class="dealer-button" v-if="tableState.dealer_button_index === getPlayerIndex(p.user_id)">D</div>
              <div class="player-name">{{ p.user_id === myUserId ? 'Tú' : p.username }}</div>
              <div class="player-chips">${{ p.balance_in_play.toFixed(2) }}</div>
              <div class="player-round-bet" v-if="p.round_bet > 0">Apuesta: ${{ p.round_bet }}</div>
              
              <div class="cards-area" v-if="p.hand && p.hand.length > 0">
                <div v-for="(c, ci) in p.hand" :key="`hc-${ci}`" class="card mini" :class="{'hidden': c === 'HIDDEN'}">
                  <span v-if="c !== 'HIDDEN'" :class="getSuitClass(c)">{{ formatCard(c) }}</span>
                </div>
              </div>
              
              <div class="hand-name" v-if="p.best_hand_name && tableState.status === 'SHOWDOWN'">
                {{ p.best_hand_name }}
              </div>
            </div>
          </div>

        </div>
      </div>
      
      <!-- Actions panel (only for local user) -->
      <div class="actions-panel" v-if="amISeated">
        
        <div v-if="tableState.status === 'WAITING_PLAYERS' || tableState.status === 'SHOWDOWN'" class="pre-game-controls">
          <span class="waiting-text" v-if="tableState.players.length < 2">Esperando más jugadores (mínimo 2)...</span>
          <button class="btn-primary" v-if="tableState.players.length >= 2" @click="sendAction('start_game')">NUEVA MANO</button>
        </div>
        
        <div v-if="isMyTurn" class="game-controls">
          <div class="bet-slider" v-if="canRaise">
            <input type="range" :min="minRaise" :max="myPlayer.balance_in_play" v-model="raiseAmount" />
            <span>${{ raiseAmount }}</span>
          </div>
          
          <div class="action-buttons">
            <button class="btn-danger" @click="sendAction('fold')">RETIRARSE</button>
            <button class="btn-secondary" v-if="canCheck" @click="sendAction('check')">PASAR</button>
            <button class="btn-warning" v-if="!canCheck" @click="sendAction('call')">IGUALAR (${{ callAmount }})</button>
            <button class="btn-success" v-if="canRaise" @click="sendAction('raise', {amount: raiseAmount})">SUBIR</button>
          </div>
        </div>

      </div>
      <div class="actions-panel" v-else>
        <div class="buy-in-controls">
          <label>Buy In: </label>
          <input type="number" v-model="buyInAmount" min="100" step="100" />
          <button class="btn-join" @click="joinTable">SENTARSE</button>
        </div>
      </div>
      
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '../shared/api';

const route = useRoute();
const router = useRouter();
const tableId = route.params.id;

const balance = ref('0.00');
const tableState = ref(null);
const myUserId = ref(null);
const buyInAmount = ref(1000);
const raiseAmount = ref(0);
let ws = null;

const loadUserData = async () => {
  try {
    const res = await api.get('/wallet/balance');
    balance.value = parseFloat(res.data.balance).toFixed(2);
    
    const userRes = await api.get('/users/me');
    myUserId.value = userRes.data.id;
  } catch (e) {
    console.error(e);
  }
};

const initWebSocket = () => {
  const token = localStorage.getItem('casino_token');
  const apiBaseUrl = api.defaults.baseURL || 'http://localhost:8001/api/v1';
  const wsBaseUrl = apiBaseUrl.replace('http://', 'ws://').replace('https://', 'wss://');
  const wsUrl = `${wsBaseUrl}/games/poker-mp/ws/${tableId}?token=${token}`;
  
  ws = new WebSocket(wsUrl);
  
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'state_update') {
      tableState.value = msg.data;
      if (msg.data.status === 'SHOWDOWN' || msg.data.status === 'WAITING_PLAYERS') {
        loadUserData(); 
      }
      
      // Update raise amount
      if (isMyTurn.value && canRaise.value) {
        raiseAmount.value = minRaise.value;
      }
    }
  };
};

onMounted(() => {
  loadUserData();
  initWebSocket();
});

onUnmounted(() => {
  if (ws) {
    ws.close();
  }
});

const sendAction = (action, extraData = {}) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action, ...extraData }));
  }
};

const joinTable = () => {
  sendAction('join', { buy_in: buyInAmount.value });
  setTimeout(() => loadUserData(), 500);
};

// Computeds
const amISeated = computed(() => {
  if (!tableState.value || !tableState.value.players) return false;
  return tableState.value.players.some(p => p.user_id === myUserId.value);
});

const myPlayer = computed(() => {
  if (!tableState.value || !tableState.value.players) return null;
  return tableState.value.players.find(p => p.user_id === myUserId.value);
});

const isMyTurn = computed(() => {
  if (!tableState.value || !['PRE_FLOP', 'FLOP', 'TURN', 'RIVER'].includes(tableState.value.status)) return false;
  return tableState.value.players[tableState.value.current_turn_index]?.user_id === myUserId.value;
});

const playersWithPositions = computed(() => {
  if (!tableState.value || !tableState.value.players) return [];
  // For simplicity, just return them in order
  return tableState.value.players;
});

const getPlayerIndex = (uid) => {
  return tableState.value.players.findIndex(p => p.user_id === uid);
};

const isPlayerTurn = (uid) => {
  if (!tableState.value || !['PRE_FLOP', 'FLOP', 'TURN', 'RIVER'].includes(tableState.value.status)) return false;
  return getPlayerIndex(uid) === tableState.value.current_turn_index;
};

// Betting logic
const canCheck = computed(() => {
  if (!myPlayer.value || !tableState.value) return false;
  return myPlayer.value.round_bet >= tableState.value.current_bet;
});

const callAmount = computed(() => {
  if (!myPlayer.value || !tableState.value) return 0;
  return Math.min(tableState.value.current_bet - myPlayer.value.round_bet, myPlayer.value.balance_in_play);
});

const canRaise = computed(() => {
  if (!myPlayer.value || !tableState.value) return false;
  return myPlayer.value.balance_in_play > callAmount.value;
});

const minRaise = computed(() => {
  if (!tableState.value) return 0;
  return tableState.value.big_blind; // Simple min raise logic
});

const paddedCommunityCards = computed(() => {
  const cards = tableState.value?.community_cards || [];
  const padded = [...cards];
  while (padded.length < 5) padded.push('EMPTY');
  return padded;
});

// Formatters
const formatStatus = (status) => {
  const map = {
    'WAITING_PLAYERS': 'Esperando',
    'PRE_FLOP': 'Pre-Flop',
    'FLOP': 'Flop',
    'TURN': 'Turn',
    'RIVER': 'River',
    'SHOWDOWN': 'Showdown'
  };
  return map[status] || status;
};

const formatCard = (cardStr) => {
  if (!cardStr || cardStr === 'HIDDEN' || cardStr === 'EMPTY') return '';
  return cardStr;
};

const getSuitClass = (cardStr) => {
  if (!cardStr) return '';
  if (cardStr.includes('♥') || cardStr.includes('♦')) return 'red-suit';
  return 'black-suit';
};

// Geometry for oval table
const getSeatStyle = (index, total) => {
  // Simple circle distribution
  const angle = (index / total) * 2 * Math.PI - Math.PI / 2; // Start top
  const rx = 350; // Oval x radius
  const ry = 180; // Oval y radius
  
  const x = Math.cos(angle) * rx;
  const y = Math.sin(angle) * ry;
  
  return {
    transform: `translate(${x}px, ${y}px)`
  };
};

</script>

<style scoped>
.mp-poker {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 25px;
  margin-bottom: 40px;
}
.btn-back {
  background: transparent;
  color: var(--text-muted);
  border: none;
  cursor: pointer;
  font-weight: 600;
}
.table-info { text-align: center; }
.table-info h2 { margin: 0; }
.status-badge {
  background: #f59e0b; color: black; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 0.8rem;
}
.balance { font-size: 1.25rem; font-weight: 700; color: var(--primary); }

.main-layout {
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* Poker Table Surface */
.poker-table-wrapper {
  position: relative;
  width: 100%;
  max-width: 900px;
  height: 500px;
  margin-bottom: 50px;
}

.poker-table {
  width: 800px;
  height: 400px;
  background: radial-gradient(circle at center, #1b5e20 0%, #0a3d10 100%);
  border-radius: 200px;
  border: 15px solid #3e2723;
  box-shadow: inset 0 0 40px rgba(0,0,0,0.5), 0 20px 40px rgba(0,0,0,0.4);
  display: flex;
  justify-content: center;
  align-items: center;
  
  /* Absolute centering to allow scale transform without layout shifts */
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.center-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 15px;
  z-index: 5;
}

.pot-display {
  background: rgba(0,0,0,0.6);
  padding: 5px 15px;
  border-radius: 20px;
  font-weight: bold;
  color: #fbbf24;
  border: 1px solid #fbbf24;
}

.community-cards {
  display: flex;
  gap: 10px;
}

.card {
  width: 60px;
  height: 90px;
  background: white;
  border-radius: 6px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 1.5rem;
  font-weight: bold;
  box-shadow: 0 4px 8px rgba(0,0,0,0.3);
}

.card.empty {
  background: rgba(255,255,255,0.1);
  border: 2px dashed rgba(255,255,255,0.3);
  box-shadow: none;
}

.card.mini {
  width: 40px;
  height: 60px;
  font-size: 1rem;
}

.card.hidden {
  background: linear-gradient(135deg, #1e3a8a, #172554);
  border: 2px solid white;
}

.red-suit { color: #ef4444; }
.black-suit { color: #111827; }

/* Players */
.player-seat {
  position: absolute;
  /* Centro absoluto de la mesa redonda */
  top: 50%;
  left: 50%;
  margin-top: -60px; /* half height */
  margin-left: -75px; /* half width */
  z-index: 10;
}

.player-card {
  background: rgba(15, 23, 42, 0.85);
  border: 2px solid var(--border-color);
  padding: 10px;
  border-radius: 12px;
  width: 150px;
  text-align: center;
  backdrop-filter: blur(4px);
  position: relative;
  transition: all 0.3s;
}

.player-card.my-turn {
  border-color: #fbbf24;
  box-shadow: 0 0 20px rgba(251, 191, 36, 0.4);
  transform: scale(1.05);
}

.player-card.folded {
  opacity: 0.5;
  filter: grayscale(1);
}

.dealer-button {
  position: absolute;
  top: -15px;
  right: -15px;
  background: white;
  color: black;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  font-weight: bold;
  border: 2px solid #333;
}

.player-name { font-weight: bold; color: white; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.player-chips { color: #10b981; font-family: monospace; font-size: 1.1rem; }
.player-round-bet { font-size: 0.8rem; color: #fbbf24; margin-top: 5px; }

.cards-area {
  display: flex;
  justify-content: center;
  gap: 5px;
  margin-top: 10px;
}

.hand-name {
  margin-top: 8px;
  font-size: 0.85rem;
  background: var(--primary);
  color: white;
  padding: 2px 5px;
  border-radius: 4px;
}

/* Actions */
.actions-panel {
  background: var(--surface-light);
  padding: 25px;
  border-radius: 16px;
  min-width: 400px;
  text-align: center;
}

.buy-in-controls {
  display: flex;
  align-items: center;
  gap: 15px;
  justify-content: center;
}
.buy-in-controls input {
  padding: 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: rgba(0,0,0,0.2);
  color: white;
  width: 100px;
}
.btn-join {
  padding: 12px 24px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
}

.action-buttons {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 15px;
}

.btn-danger { background: #ef4444; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-weight: bold; cursor: pointer;}
.btn-secondary { background: #64748b; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-weight: bold; cursor: pointer;}
.btn-warning { background: #f59e0b; color: black; border: none; padding: 12px 20px; border-radius: 8px; font-weight: bold; cursor: pointer;}
.btn-success { background: #10b981; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-weight: bold; cursor: pointer;}

.bet-slider {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 15px;
}
.bet-slider input[type=range] {
  flex: 1;
}

/* --- Mobile Responsiveness --- */
@media (max-width: 900px) {
  .mp-poker {
    padding: 10px;
    overflow-x: hidden;
  }
  .poker-table-wrapper {
    height: 350px;
    margin-bottom: 20px;
  }
  .poker-table {
    transform: translate(-50%, -50%) scale(0.7);
  }
}

@media (max-width: 600px) {
  .header-row {
    flex-direction: column;
    padding: 10px;
    gap: 10px;
    align-items: stretch;
    text-align: center;
  }
  .poker-table-wrapper {
    height: 250px;
  }
  .poker-table {
    transform: translate(-50%, -50%) scale(0.42);
  }
  .actions-panel {
    min-width: 100%;
    padding: 15px;
  }
  .action-buttons {
    flex-wrap: wrap;
  }
  .action-buttons button {
    flex: 1 1 45%;
    font-size: 0.9rem;
    padding: 10px;
  }
  .buy-in-controls {
    flex-wrap: wrap;
  }
}
</style>
