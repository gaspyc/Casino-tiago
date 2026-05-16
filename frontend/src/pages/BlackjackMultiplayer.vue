<template>
  <div class="mp-blackjack">
    <div class="glass-panel header-row">
      <button @click="leaveTable" class="btn-back">← Salir de la Mesa</button>
      <div class="table-info">
        <h2>{{ tableState?.name || 'Cargando...' }}</h2>
        <span class="status-badge">{{ tableState?.status || '...' }}</span>
      </div>
      <div class="balance">Saldo: ${{ balance }}</div>
    </div>
    
    <div class="main-layout glass-panel" v-if="tableState">
      
      <!-- Dealer Area -->
      <div class="dealer-area">
        <h3>Croupier</h3>
        <div class="cards">
          <div v-for="(card, i) in tableState.dealer_hand" :key="`d-${i}`" class="card" :class="{ hidden: card === 'HIDDEN' }">
            <span v-if="card !== 'HIDDEN'" :class="getSuitClass(card)">{{ formatCard(card) }}</span>
          </div>
        </div>
      </div>
      
      <!-- Semicircle of Players -->
      <div class="players-circle">
        <div v-for="(p, idx) in tableState.players" :key="p.user_id" 
             class="player-spot" 
             :class="{ 
               'is-me': p.user_id === myUserId, 
               'active-turn': tableState.status === 'PLAYING' && idx === tableState.current_turn_index
             }">
          
          <div class="player-name">{{ p.user_id === myUserId ? 'Tú' : p.username }}</div>
          <div class="player-bet" v-if="p.bet > 0">Apuesta: ${{ p.bet }}</div>
          <div class="player-status">{{ p.status }}</div>
          
          <div class="cards mini">
            <div v-for="(c, i) in p.hand" :key="`c-${i}`" class="card mini">
              <span :class="getSuitClass(c)">{{ formatCard(c) }}</span>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Actions panel (only for local user) -->
      <div class="actions-panel" v-if="amISeated">
        
        <div v-if="tableState.status === 'WAITING_PLAYERS' || tableState.status === 'BETTING' || tableState.status === 'RESOLVED'" class="bet-controls">
          <div v-if="myPlayer.bet === 0">
             <button @click="betAmount = Math.max(1, betAmount - 1)">-</button>
             <span class="bet-display">${{ betAmount }}</span>
             <button @click="betAmount += 1">+</button>
             <button class="btn-bet" @click="placeBet">APOSTAR</button>
          </div>
          <div v-else>
             <span class="waiting-text">Esperando al resto...</span>
             <button class="btn-deal" v-if="canStartDeal" @click="startDeal">REPARTIR A TODOS</button>
          </div>
        </div>
        
        <div v-if="tableState.status === 'PLAYING' && isMyTurn" class="game-controls">
          <button class="btn-hit" @click="sendAction('hit')">PEDIR</button>
          <button class="btn-stand" @click="sendAction('stand')">PLANTARSE</button>
        </div>
        
      </div>
      <div class="actions-panel" v-else>
        <button class="btn-join" @click="sendAction('join')">SENTARSE EN LA MESA</button>
      </div>
      
    </div>

    <!-- Result Modal (End of Round) -->
    <Teleport to="body">
      <div v-if="showResultModal" class="modal-overlay" @click.self="closeResultModal">
        <div class="glass-panel modal result-modal bounce-in">
          <h2>Ronda Finalizada</h2>
          <div class="result-details">
            <p>La mesa ha resuelto todas las manos.</p>
            <p class="profit" :class="{'positive': myProfit > 0, 'negative': myProfit < 0}">
              {{ myProfit > 0 ? `¡Ganaste $${myProfit}!` : (myProfit < 0 ? 'Perdiste tu apuesta.' : 'Empate.') }}
            </p>
          </div>
          <div class="modal-actions">
            <button class="btn btn-secondary" @click="leaveTable">Levantarse y Salir</button>
            <button class="btn btn-primary" @click="closeResultModal">Apostar Nueva Mano</button>
          </div>
        </div>
      </div>
    </Teleport>
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
const betAmount = ref(10);
const showResultModal = ref(false);
const myProfit = ref(0);
let ws = null;

const loadUserData = async () => {
  try {
    const res = await api.get('/wallet/balance');
    balance.value = parseFloat(res.data.balance).toFixed(2);
    
    // Obtener información del usuario real desde la API
    const userRes = await api.get('/users/me');
    myUserId.value = userRes.data.id;
  } catch (e) {
    console.error(e);
  }
};

const closeResultModal = () => {
  showResultModal.value = false;
};

const initWebSocket = () => {
  const token = localStorage.getItem('casino_token');
  
  // Construir WS URL usando el baseURL del cliente de Axios para que siempre coincida con la API
  const apiBaseUrl = api.defaults.baseURL || 'http://localhost:8001/api/v1';
  const wsBaseUrl = apiBaseUrl.replace('http://', 'ws://').replace('https://', 'wss://');
  const wsUrl = `${wsBaseUrl}/games/blackjack-mp/ws/${tableId}?token=${token}`;
  
  ws = new WebSocket(wsUrl);
  
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'state_update') {
      tableState.value = msg.data;
      if (msg.data.status === 'RESOLVED') {
        showResultModal.value = true;
        loadUserData(); // Actualizar saldo al final de la mano
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

const leaveTable = () => {
  if (amISeated.value) {
    sendAction('leave');
  }
  router.push('/lobby-blackjack');
};

const sendAction = (action, extraData = {}) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action, ...extraData }));
  }
};

const placeBet = () => {
  sendAction('bet', { bet_amount: betAmount.value });
  setTimeout(() => loadUserData(), 500); // optimistic balance update
};

const startDeal = () => {
  sendAction('start_deal');
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
  if (!tableState.value || tableState.value.status !== 'PLAYING') return false;
  const idx = tableState.value.players.findIndex(p => p.user_id === myUserId.value);
  return idx === tableState.value.current_turn_index;
});

const canStartDeal = computed(() => {
  if (!tableState.value || tableState.value.status !== 'BETTING') return false;
  const bettingPlayers = tableState.value.players.filter(p => p.bet > 0);
  return bettingPlayers.length > 0;
});

// Formatters
const formatCard = (cardStr) => {
  if (!cardStr || cardStr === 'HIDDEN') return '';
  return cardStr;
};

const getSuitClass = (cardStr) => {
  if (!cardStr) return '';
  if (cardStr.includes('♥') || cardStr.includes('♦')) return 'red-suit';
  return 'black-suit';
};
</script>

<style scoped>
.mp-blackjack {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 25px;
  margin-bottom: 20px;
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
  padding: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: linear-gradient(135deg, #064e3b 0%, #022c22 100%);
  border: 4px solid #b45309;
  min-height: 600px;
}

.dealer-area {
  margin-bottom: 60px;
  text-align: center;
}
.dealer-area h3 { color: white; margin-bottom: 10px; }

.cards { display: flex; gap: 10px; justify-content: center; }
.card {
  width: 90px; height: 130px; background: white; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 2.2rem; font-weight: bold; color: black;
  box-shadow: 2px 2px 10px rgba(0,0,0,0.5);
}
.card.hidden {
  background: repeating-linear-gradient(45deg, #b41c1c, #b41c1c 10px, #fff 10px, #fff 20px);
  border: 4px solid white;
}
.card.mini {
  width: 60px; height: 85px; font-size: 1.5rem;
}
.red-suit { color: #dc2626; }
.black-suit { color: #000000; }

.players-circle {
  display: flex; gap: 30px; justify-content: center; width: 100%; flex-wrap: wrap; margin-bottom: 40px;
}
.player-spot {
  background: rgba(0,0,0,0.4); padding: 15px; border-radius: 12px; text-align: center;
  min-width: 150px; border: 2px solid transparent; transition: all 0.3s;
}
.player-spot.is-me { background: rgba(0,0,0,0.6); }
.player-spot.active-turn {
  border-color: #10b981;
  box-shadow: 0 0 15px rgba(16, 185, 129, 0.5);
}
.player-name { color: #fff; font-weight: bold; margin-bottom: 5px; }
.player-bet { color: #f59e0b; font-size: 0.9rem; margin-bottom: 5px; }
.player-status { color: #cbd5e1; font-size: 0.8rem; margin-bottom: 10px; text-transform: uppercase;}

.actions-panel {
  background: rgba(0,0,0,0.8); padding: 20px; border-radius: 12px; width: 100%; max-width: 600px;
  text-align: center;
}
.bet-controls { display: flex; align-items: center; justify-content: center; gap: 15px; }
.bet-controls button {
  background: var(--primary); color: white; border: none; border-radius: 50%;
  width: 40px; height: 40px; font-size: 1.5rem; cursor: pointer;
}
.bet-display { font-size: 1.5rem; font-weight: bold; width: 80px; color: white;}
.btn-bet, .btn-deal, .btn-join {
  padding: 12px 24px; background: #10b981; color: white; border: none; border-radius: 8px;
  font-weight: bold; cursor: pointer; text-transform: uppercase;
}
.game-controls { display: flex; gap: 15px; justify-content: center; }
.btn-hit { padding: 12px 24px; background: #3b82f6; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer;}
.btn-stand { padding: 12px 24px; background: #ef4444; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer;}
.waiting-text { color: white; font-style: italic; margin-right: 15px;}

/* Modal Overlay & Styling */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(5px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal {
  padding: 40px;
  max-width: 500px;
  width: 100%;
  text-align: center;
  background: linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.98));
  border-top: 4px solid var(--primary);
  border-radius: 12px;
}

.result-modal h2 { margin-bottom: 20px; font-size: 2rem; color: #fff; }
.result-details { margin-bottom: 30px; font-size: 1.2rem; }
.profit { font-weight: bold; font-size: 1.5rem; margin-top: 10px; }
.profit.positive { color: #10b981; }
.profit.negative { color: #ef4444; }

.modal-actions {
  display: flex;
  gap: 15px;
  justify-content: center;
}

.modal-actions .btn {
  flex: 1;
  padding: 12px;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  border: none;
}
.btn-primary { background: var(--primary); color: white; }
.btn-secondary { background: transparent; border: 1px solid var(--text-muted); color: var(--text-muted); }

.bounce-in {
  animation: bounceIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
@keyframes bounceIn {
  0% { transform: scale(0.5); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}

/* --- Mobile Responsiveness --- */
@media (max-width: 768px) {
  .mp-blackjack {
    padding: 10px;
  }
  .header-row {
    flex-direction: column;
    padding: 10px;
    gap: 10px;
    margin-bottom: 10px;
  }
  .main-layout {
    padding: 15px;
    min-height: auto;
  }
  .players-circle {
    gap: 10px;
    margin-bottom: 20px;
  }
  .player-spot {
    min-width: 120px;
    padding: 10px;
  }
  .card {
    width: 60px;
    height: 85px;
    font-size: 1.5rem;
  }
  .card.mini {
    width: 45px;
    height: 65px;
    font-size: 1.2rem;
  }
  .actions-panel {
    padding: 15px;
  }
  .bet-controls {
    flex-wrap: wrap;
  }
  .btn-bet, .btn-deal, .btn-join {
    width: 100%;
    margin-top: 10px;
  }
  .modal {
    padding: 20px;
    width: 90%;
  }
  .modal-actions {
    flex-direction: column;
  }
}
</style>
