<template>
  <div class="blackjack-page">
    <div class="glass-panel header-row">
      <button @click="router.push('/lobby')" class="btn-back">← Volver al Lobby</button>
      <div class="balance">Saldo: ${{ balance }}</div>
    </div>

    <div class="main-layout glass-panel">
      <h2>Blackjack ♠️</h2>
      
      <div v-if="!gameActive" class="bet-section">
        <h3>Haz tu apuesta</h3>
        <div class="bet-controls">
          <button @click="betAmount = Math.max(1, betAmount - 1)">-</button>
          <span class="bet-display">${{ betAmount }}</span>
          <button @click="betAmount += 1">+</button>
        </div>
        <button class="btn-start" @click="startGame" :disabled="loading || betAmount > parseFloat(balance)">
          REPARTIR CARTAS
        </button>
        <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
      </div>
      
      <div v-else class="game-table">
        <div class="dealer-area">
          <div class="hand-header">
            <h3>Croupier</h3>
            <span v-if="gameState.status !== 'ACTIVE'" class="score">{{ gameState.dealer_score }}</span>
          </div>
          <div class="cards">
            <div v-for="(card, i) in gameState.dealer_hand" :key="`d-${i}`" class="card" :class="{ hidden: card === 'HIDDEN' }">
              <span v-if="card !== 'HIDDEN'" :class="getSuitClass(card)">{{ formatCard(card) }}</span>
            </div>
          </div>
        </div>
        
        <div class="table-center">
          <div v-if="gameState.status !== 'ACTIVE'" class="result-banner" :class="getResultClass(gameState.status)">
            {{ getResultMessage(gameState.status, gameState.net_profit) }}
          </div>
        </div>
        
        <div class="player-area">
          <div v-if="!gameState.is_split">
            <div class="hand-header">
              <h3>Tú</h3>
              <span class="score">{{ gameState.player_score }}</span>
            </div>
            <div class="cards">
              <div v-for="(card, i) in gameState.player_hand" :key="`p-${i}`" class="card">
                <span :class="getSuitClass(card)">{{ formatCard(card) }}</span>
              </div>
            </div>
          </div>
          
          <div v-else class="split-hands">
             <div v-for="(hand, idx) in gameState.player_hand" :key="`hand-${idx}`" class="hand-container" :class="{ 'active-hand': gameState.active_hand_index === idx && gameState.status === 'ACTIVE' }">
               <div class="hand-header">
                 <h3>Mano {{ idx + 1 }}</h3>
                 <span class="score">{{ gameState.player_score[idx] }}</span>
               </div>
               <div class="cards">
                 <div v-for="(card, i) in hand" :key="`s-${idx}-${i}`" class="card">
                   <span :class="getSuitClass(card)">{{ formatCard(card) }}</span>
                 </div>
               </div>
             </div>
          </div>
          
          <div class="actions" v-if="gameState.status === 'ACTIVE'">
            <button class="btn-hit" @click="hit" :disabled="loading">PEDIR</button>
            <button class="btn-stand" @click="stand" :disabled="loading">PLANTARSE</button>
            <button class="btn-double" v-if="canDouble" @click="doubleDown" :disabled="loading || (parseFloat(balance) < gameState.bet_amount)">DOBLAR</button>
            <button class="btn-split" v-if="canSplit" @click="splitHand" :disabled="loading || (parseFloat(balance) < gameState.bet_amount)">DIVIDIR</button>
          </div>
        </div>
      </div>
      
      <!-- Modal de Fin de Partida -->
      <Teleport to="body">
        <div v-if="gameActive && gameState && gameState.status !== 'ACTIVE'" class="modal-overlay">
          <div class="glass-panel modal-content">
            <h2 :class="getResultClass(gameState.status)">{{ getModalTitle(gameState.status) }}</h2>
            <div class="summary-details">
              <p><strong>Apuesta Total:</strong> ${{ gameState.is_split ? (Number(gameState.bet_amount) * 2).toFixed(2) : Number(gameState.bet_amount).toFixed(2) }}</p>
              <p><strong>Premio:</strong> ${{ Number(gameState.total_payout).toFixed(2) }}</p>
              <p :class="Number(gameState.net_profit) > 0 ? 'win-text' : (Number(gameState.net_profit) < 0 ? 'lose-text' : 'push-text')">
                <strong>Ganancia Neta:</strong> ${{ Number(gameState.net_profit) > 0 ? '+' : '' }}{{ Number(gameState.net_profit).toFixed(2) }}
              </p>
            </div>
            <button class="btn-start btn-play-again" @click="resetGame">VOLVER A JUGAR</button>
          </div>
        </div>
      </Teleport>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import confetti from 'canvas-confetti';
import api from '../shared/api';

const router = useRouter();
const balance = ref('0.00');
const loading = ref(false);
const errorMsg = ref('');

const betAmount = ref(10);
const gameActive = ref(false);
const gameState = ref(null);

const canDouble = computed(() => {
  if (!gameState.value) return false;
  return !gameState.value.is_split && gameState.value.player_hand.length === 2;
});

const canSplit = computed(() => {
  if (!gameState.value) return false;
  if (gameState.value.is_split || gameState.value.player_hand.length !== 2) return false;
  const rank1 = gameState.value.player_hand[0].slice(0, -1);
  const rank2 = gameState.value.player_hand[1].slice(0, -1);
  return rank1 === rank2 || (["10","J","Q","K"].includes(rank1) && ["10","J","Q","K"].includes(rank2));
});

const loadBalance = async () => {
  try {
    const res = await api.get('/wallet/balance');
    balance.value = parseFloat(res.data.balance).toFixed(2);
  } catch (e) {
    console.error(e);
  }
};

onMounted(() => {
  loadBalance();
});

const startGame = async () => {
  loading.value = true;
  errorMsg.value = '';
  try {
    const res = await api.post('/games/blackjack/start', { bet_amount: betAmount.value });
    gameState.value = res.data;
    gameActive.value = true;
    await loadBalance();
    
    if (res.data.status !== 'ACTIVE') {
      handleGameEnd(res.data);
    }
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || "Error al iniciar";
  } finally {
    loading.value = false;
  }
};

const hit = async () => {
  loading.value = true;
  try {
    const res = await api.post('/games/blackjack/hit', { game_id: gameState.value.game_id });
    gameState.value = res.data;
    
    if (res.data.status !== 'ACTIVE') {
      handleGameEnd(res.data);
    }
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const stand = async () => {
  loading.value = true;
  try {
    const res = await api.post('/games/blackjack/stand', { game_id: gameState.value.game_id });
    gameState.value = res.data;
    handleGameEnd(res.data);
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const doubleDown = async () => {
  loading.value = true;
  try {
    const res = await api.post('/games/blackjack/double', { game_id: gameState.value.game_id });
    gameState.value = res.data;
    handleGameEnd(res.data);
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const splitHand = async () => {
  loading.value = true;
  try {
    const res = await api.post('/games/blackjack/split', { game_id: gameState.value.game_id });
    gameState.value = res.data;
    await loadBalance();
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const handleGameEnd = async (state) => {
  await loadBalance();
  if (state.status === 'PLAYER_WON') {
    confetti({ particleCount: 150, spread: 80, origin: { y: 0.6 } });
  }
};

const resetGame = () => {
  gameActive.value = false;
  gameState.value = null;
};

const formatCard = (cardStr) => {
  if (!cardStr || cardStr === 'HIDDEN') return '';
  return cardStr;
};

const getSuitClass = (cardStr) => {
  if (!cardStr) return '';
  if (cardStr.includes('♥') || cardStr.includes('♦')) return 'red-suit';
  return 'black-suit';
};

const getResultMessage = (status, profit) => {
  if (status === 'PLAYER_WON') return `¡GANASTE $${(Number(profit) + Number(betAmount.value)).toFixed(2)}!`;
  if (status === 'DEALER_WON') return 'GANA EL CROUPIER';
  if (status === 'PUSH') return 'EMPATE (Se devuelve la apuesta)';
  if (status === 'BUSTED') return '¡TE PASASTE!';
  return status;
};

const getModalTitle = (status) => {
  if (status === 'PLAYER_WON') return '¡VICTORIA!';
  if (status === 'DEALER_WON') return 'FIN DEL JUEGO';
  if (status === 'PUSH') return 'EMPATE';
  if (status === 'BUSTED') return '¡TE PASASTE!';
  return 'PARTIDA FINALIZADA';
};

const getResultClass = (status) => {
  if (status === 'PLAYER_WON') return 'win-text';
  if (status === 'PUSH') return 'push-text';
  return 'lose-text';
};
</script>

<style scoped>
.blackjack-page {
  padding: 20px 40px;
  max-width: 1000px;
  margin: 0 auto;
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
.balance { font-size: 1.25rem; font-weight: 700; color: var(--primary); }

.main-layout {
  padding: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  /* Fondo estilo tapete de casino verde */
  background: linear-gradient(135deg, #064e3b 0%, #022c22 100%);
  border: 4px solid #b45309;
}

h2 { margin-top: 0; color: #fff; font-size: 2.5rem; letter-spacing: 2px;}

.bet-section {
  text-align: center;
  padding: 40px;
  background: rgba(0,0,0,0.3);
  border-radius: 16px;
}
.bet-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
  margin: 20px 0;
}
.bet-controls button {
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  font-size: 1.5rem;
  cursor: pointer;
  transition: opacity 0.2s;
}
.bet-controls button:hover { opacity: 0.8; }
.bet-display { font-size: 1.5rem; font-weight: bold; width: 80px; text-align: center;}
.btn-start {
  padding: 15px 40px;
  background: #f59e0b;
  color: #000;
  font-weight: bold;
  font-size: 1.2rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  text-transform: uppercase;
}
.btn-start:disabled { opacity: 0.5; cursor: not-allowed; }

.game-table { width: 100%; display: flex; flex-direction: column; gap: 30px; }
.dealer-area, .player-area {
  background: rgba(255,255,255,0.05);
  padding: 20px;
  border-radius: 12px;
  min-height: 180px;
}
.hand-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  padding-bottom: 10px;
}
.hand-header h3 { margin: 0; font-size: 1.2rem; color: #cbd5e1; }
.score {
  background: rgba(0,0,0,0.5);
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: bold;
  font-size: 1.2rem;
}

.cards {
  display: flex;
  gap: 10px;
  justify-content: center;
  flex-wrap: wrap;
}
.card {
  width: 90px;
  height: 130px;
  background: white;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.2rem;
  font-weight: bold;
  box-shadow: 2px 2px 10px rgba(0,0,0,0.5);
  color: black;
  transition: transform 0.3s;
}
.card:hover { transform: translateY(-5px); }
.card.hidden {
  background: repeating-linear-gradient(45deg, #b41c1c, #b41c1c 10px, #fff 10px, #fff 20px);
  border: 4px solid white;
}
.red-suit { color: #dc2626; }
.black-suit { color: #000000; }

.table-center {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.result-banner {
  padding: 10px 40px;
  border-radius: 8px;
  font-size: 1.5rem;
  font-weight: bold;
  background: rgba(0,0,0,0.8);
  text-shadow: 1px 1px 2px black;
}
.win-text { color: #10b981; border: 1px solid #10b981; }
.lose-text { color: #ef4444; border: 1px solid #ef4444; }
.push-text { color: #f59e0b; border: 1px solid #f59e0b; }

.actions {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-top: 30px;
}
.btn-hit {
  padding: 12px 24px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  font-size: 1.1rem;
}
.btn-stand {
  padding: 12px 24px;
  background: #ef4444;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  font-size: 1.1rem;
}
.btn-double {
  padding: 12px 24px;
  background: #eab308;
  color: #000;
  border: none;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  font-size: 1.1rem;
}
.btn-split {
  padding: 12px 24px;
  background: #8b5cf6;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  font-size: 1.1rem;
}
.actions button:disabled { opacity: 0.5; cursor: not-allowed; }

.split-hands {
  display: flex;
  gap: 20px;
  justify-content: center;
  width: 100%;
}
.hand-container {
  flex: 1;
  background: rgba(0,0,0,0.2);
  padding: 15px;
  border-radius: 8px;
  border: 2px solid transparent;
  transition: all 0.3s;
}
.hand-container.active-hand {
  border-color: #f59e0b;
  box-shadow: 0 0 15px rgba(245, 158, 11, 0.5);
  background: rgba(0,0,0,0.4);
}

/* Modal Overlay */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; width: 100vw; height: 100vh;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(5px);
}

.modal-content {
  background: linear-gradient(135deg, #1f2937, #111827);
  border: 2px solid #f59e0b;
  padding: 40px;
  text-align: center;
  border-radius: 16px;
  min-width: 350px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.8);
  animation: popIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.modal-content h2 {
  font-size: 2.5rem;
  margin-bottom: 20px;
  text-transform: uppercase;
}

.summary-details {
  background: rgba(0,0,0,0.3);
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 30px;
  text-align: left;
}

.summary-details p {
  font-size: 1.2rem;
  margin: 10px 0;
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  padding-bottom: 5px;
}
.summary-details p:last-child {
  border-bottom: none;
}

.btn-play-again {
  width: 100%;
}

@keyframes popIn {
  0% { transform: scale(0.8); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}

/* --- Mobile Responsiveness --- */
@media (max-width: 768px) {
  .blackjack-page {
    padding: 10px;
  }
  .header-row {
    flex-direction: row;
    padding: 10px;
    margin-bottom: 10px;
  }
  .main-layout {
    padding: 15px;
  }
  .game-table {
    padding: 10px;
  }
  .card {
    width: 65px;
    height: 95px;
    font-size: 1.6rem;
  }
  .cards {
    gap: 5px;
  }
  .actions {
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 20px;
  }
  .actions button {
    flex: 1 1 45%;
    padding: 10px;
    font-size: 0.9rem;
  }
  .split-hands {
    flex-direction: column;
    gap: 10px;
  }
  .modal-content {
    min-width: 300px;
    padding: 20px;
  }
  .modal-content h2 {
    font-size: 2rem;
  }
  .summary-details p {
    font-size: 1rem;
  }
}

@media (max-width: 480px) {
  .card {
    width: 55px;
    height: 80px;
    font-size: 1.4rem;
  }
  /* Card overlap if too many cards */
  .cards .card:not(:first-child) {
    margin-left: -20px;
  }
  .cards .card:hover {
    transform: translateY(-10px) scale(1.1);
    z-index: 10;
  }
}
</style>
