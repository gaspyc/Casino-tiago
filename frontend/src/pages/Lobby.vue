<template>
  <div class="lobby-container">
    <div v-if="loading" class="loading">Cargando...</div>
    
    <div v-else class="dashboard">
      <div class="glass-panel balance-card">
        <h2>Hola, {{ user?.username }}</h2>
        <div class="balance-display">
          <span class="currency">$</span>
          <span class="amount">{{ balance }}</span>
        </div>
        
        <div class="actions">
          <button @click="showDeposit = true" class="btn btn-deposit">Depositar</button>
          <button @click="showWithdraw = true" class="btn btn-withdraw">Retirar</button>
        </div>
      </div>

      <div class="games-grid">
        <div class="glass-panel game-card" @click="router.push('/roulette')">
          <div class="game-icon">🎡</div>
          <h3>Ruleta Europea</h3>
          <p>Apuesta a números o colores y multiplica tus ganancias.</p>
          <div class="play-btn">Jugar Ahora</div>
        </div>
        
        <div class="glass-panel game-card" @click="router.push('/slots')">
          <div class="game-icon">🎰</div>
          <h3>Tragamonedas</h3>
          <p>La clásica máquina de 3 rodillos. ¡Busca el jackpot x100!</p>
          <div class="play-btn">Jugar Ahora</div>
        </div>

        <div class="glass-panel game-card" style="border-top-color: #22c55e;" @click="router.push('/plinko')">
          <div class="game-icon">PL</div>
          <h3>Plinko</h3>
          <p>Elige riesgo, filas y deja caer la bola para buscar grandes multiplicadores.</p>
          <div class="play-btn" style="color: #22c55e;">Jugar Plinko</div>
        </div>

        <div class="glass-panel game-card" @click="router.push('/blackjack')">
          <div class="game-icon">🃏</div>
          <h3>Blackjack (21)</h3>
          <p>Desafía al Croupier. Demuestra tu estrategia para llegar a 21.</p>
          <div class="play-btn">Jugar Ahora</div>
        </div>
        
        <div class="glass-panel game-card" style="border-top-color: #8b5cf6;" @click="router.push('/lobby-blackjack')">
          <div class="game-icon">👥</div>
          <h3>Blackjack Multijugador</h3>
          <p>Juega en vivo con otros usuarios en la misma mesa.</p>
          <div class="play-btn" style="color: #8b5cf6;">Ver Salas</div>
        </div>

        <div class="glass-panel game-card" style="border-top-color: #ef4444;" @click="router.push('/lobby-poker')">
          <div class="game-icon">♠️</div>
          <h3>Texas Hold'em Poker</h3>
          <p>Torneos y mesas cash en vivo. ¡Farolea y gana el pozo!</p>
          <div class="play-btn" style="color: #ef4444;">Ver Salas</div>
        </div>
        
        <div class="glass-panel game-card" style="border-top-color: #f59e0b;" @click="router.push('/crash')">
          <div class="game-icon">🚀</div>
          <h3>Crash (Multiplayer)</h3>
          <p>El multiplicador sube, ¡retírate antes de que explote!</p>
          <div class="play-btn" style="color: #f59e0b;">Jugar Crash</div>
        </div>
      </div>
    </div>

    <!-- Modal Transacciones -->
    <div v-if="showDeposit || showWithdraw" class="modal-overlay" @click.self="closeModals">
      <div class="glass-panel modal">
        <h3>{{ showDeposit ? 'Depositar Fondos' : 'Retirar Fondos' }}</h3>
        <input type="number" v-model.number="txAmount" placeholder="Monto" min="1" step="0.01" />
        <div v-if="txError" class="tx-error">{{ txError }}</div>
        <div class="modal-actions">
          <button class="btn" @click="closeModals" style="background: transparent; border: 1px solid white;">Cancelar</button>
          <button class="btn" @click="processTransaction" :disabled="txLoading">Confirmar</button>
        </div>
      </div>
    </div>
    
    <TransactionTable />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import api from '../shared/api';
import TransactionTable from '../widgets/TransactionTable.vue';

const router = useRouter();
const loading = ref(true);
const user = ref(null);
const balance = ref('0.00');

const showDeposit = ref(false);
const showWithdraw = ref(false);
const txAmount = ref('');
const txLoading = ref(false);
const txError = ref('');

const loadData = async () => {
  try {
    const userRes = await api.get('/users/me');
    user.value = userRes.data;
    
    const balRes = await api.get('/wallet/balance');
    balance.value = parseFloat(balRes.data.balance).toFixed(2);
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

onMounted(loadData);

const closeModals = () => {
  showDeposit.value = false;
  showWithdraw.value = false;
  txAmount.value = '';
  txError.value = '';
};

const processTransaction = async () => {
  if (!txAmount.value || txAmount.value <= 0) {
    txError.value = 'Ingresa un monto válido';
    return;
  }
  
  txLoading.value = true;
  txError.value = '';
  const endpoint = showDeposit.value ? '/wallet/deposit' : '/wallet/withdraw';
  
  try {
    await api.post(endpoint, { amount: txAmount.value });
    await loadData();
    closeModals();
  } catch (e) {
    txError.value = e.response?.data?.detail || 'Error en la transacción';
  } finally {
    txLoading.value = false;
  }
};
</script>

<style scoped>
.lobby-container {
  padding: 20px 40px;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.dashboard {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.balance-card {
  padding: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9));
}

.balance-card h2 {
  color: var(--text-muted);
  font-weight: 400;
}

.balance-display {
  margin: 20px 0;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.currency {
  font-size: 2rem;
  color: var(--primary);
  margin-top: 10px;
}

.amount {
  font-size: 5rem;
  font-weight: 700;
  letter-spacing: -2px;
}

.actions {
  display: flex;
  gap: 16px;
}

.btn-deposit {
  background: var(--accent-green);
}
.btn-deposit:hover {
  background: #059669;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
}

.btn-withdraw {
  background: transparent;
  border: 1px solid var(--text-muted);
}

.games-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
}

.game-card {
  padding: 30px;
  cursor: pointer;
  transition: all 0.3s ease;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.game-card:hover {
  transform: translateY(-5px);
  border-color: var(--primary);
  box-shadow: 0 10px 40px rgba(138, 43, 226, 0.2);
}

.game-icon {
  font-size: 4rem;
  margin-bottom: 16px;
}

.game-card h3 {
  margin-bottom: 10px;
  font-size: 1.5rem;
}

.game-card p {
  color: var(--text-muted);
  margin-bottom: 24px;
  font-size: 0.9rem;
}

.play-btn {
  color: var(--primary);
  font-weight: 600;
  margin-top: auto;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal {
  padding: 30px;
  width: 100%;
  max-width: 400px;
}

.modal h3 {
  margin-bottom: 20px;
}

.modal-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.modal-actions button {
  flex: 1;
}

.tx-error {
  color: var(--accent-red);
  font-size: 0.85rem;
  margin-top: 10px;
}
</style>
