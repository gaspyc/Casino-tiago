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

      <section v-for="grupo in GRUPOS" :key="grupo.id" class="grupo">
        <header class="grupo-head">
          <h3>{{ grupo.titulo }}</h3>
          <p>{{ grupo.bajada }}</p>
        </header>

        <div class="games-grid">
          <div
            v-for="juego in juegosDe(grupo.id)"
            :key="juego.id"
            class="glass-panel game-card"
            :style="{ borderTopColor: juego.color }"
            @click="router.push(juego.ruta)"
          >
            <div class="game-icon">{{ juego.icono }}</div>
            <h3>{{ juego.nombre }}</h3>

            <div v-if="juego.marcas.length" class="marcas">
              <span
                v-for="marca in juego.marcas"
                :key="marca"
                class="marca"
                :class="MARCAS[marca].clase"
              >
                {{ MARCAS[marca].texto }}
              </span>
            </div>

            <p>{{ juego.descripcion }}</p>
            <div class="play-btn" :style="{ color: juego.color }">
              Jugar {{ juego.nombre }}
            </div>
          </div>
        </div>
      </section>
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
import { GRUPOS, MARCAS, juegosDe } from '../shared/juegos';
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

.grupo {
  margin-bottom: 30px;
}

.grupo-head {
  margin-bottom: 14px;
  padding-left: 2px;
}

.grupo-head h3 {
  margin: 0;
  font-size: 1.05rem;
  letter-spacing: 0.2px;
}

.grupo-head p {
  margin: 3px 0 0;
  font-size: 0.78rem;
  color: var(--text-muted, rgba(255, 255, 255, 0.55));
}

.marcas {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 5px;
  margin: 6px 0 2px;
}

.marca {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.3px;
  border: 1px solid currentColor;
}

.marca-rapida {
  color: #38bdf8;
}

.marca-pvp {
  color: #34d399;
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
