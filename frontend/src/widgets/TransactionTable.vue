<template>
  <div class="transaction-table-widget glass-panel">
    <h3>Historial de Movimientos</h3>
    <div v-if="loading" class="loading">Cargando...</div>
    <div v-else-if="transactions.length === 0" class="empty">No hay movimientos registrados aún.</div>
    <div class="table-container" v-else>
      <table>
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Tipo</th>
            <th>Origen</th>
            <th>Estado</th>
            <th class="right">Monto</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tx in transactions" :key="tx.id">
            <td>{{ formatDate(tx.created_at) }}</td>
            <td>
              <span class="badge" :class="getTypeClass(tx.transaction_type)">
                {{ tx.transaction_type }}
              </span>
            </td>
            <td>
              <span class="description-text">{{ tx.description || 'General' }}</span>
            </td>
            <td>
              <span class="status">{{ tx.status }}</span>
            </td>
            <td class="amount right" :class="getAmountClass(tx.transaction_type)">
              {{ getAmountPrefix(tx.transaction_type) }}${{ parseFloat(tx.amount).toFixed(2) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import api from '../shared/api';

const transactions = ref([]);
const loading = ref(true);

const loadTransactions = async () => {
  try {
    const res = await api.get('/wallet/transactions');
    transactions.value = res.data;
  } catch (e) {
    console.error("Error cargando historial", e);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadTransactions();
});

const formatDate = (isoString) => {
  const d = new Date(isoString);
  return d.toLocaleString('es-ES', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
};

const getTypeClass = (type) => {
  if (['DEPOSIT', 'PAYOUT'].includes(type)) return 'badge-green';
  if (['WITHDRAW', 'BET'].includes(type)) return 'badge-red';
  return 'badge-gray';
};

const getAmountClass = (type) => {
  if (['DEPOSIT', 'PAYOUT'].includes(type)) return 'text-green';
  if (['WITHDRAW', 'BET'].includes(type)) return 'text-red';
  return '';
};

const getAmountPrefix = (type) => {
  if (['DEPOSIT', 'PAYOUT'].includes(type)) return '+ ';
  if (['WITHDRAW', 'BET'].includes(type)) return '- ';
  return '';
};
</script>

<style scoped>
.transaction-table-widget {
  padding: 24px;
  margin-top: 24px;
}
h3 {
  margin-top: 0;
  margin-bottom: 16px;
  font-size: 1.2rem;
}
.table-container {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}
th, td {
  padding: 14px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
th {
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.8rem;
  letter-spacing: 0.5px;
}
.right {
  text-align: right;
}
.badge {
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: bold;
  letter-spacing: 0.5px;
}
.badge-green { background: rgba(16, 185, 129, 0.15); color: var(--accent-green); }
.badge-red { background: rgba(239, 68, 68, 0.15); color: var(--accent-red); }
.badge-gray { background: rgba(100, 116, 139, 0.15); color: #cbd5e1; }

.status {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.description-text {
  font-size: 0.85rem;
  font-weight: 500;
  color: #e2e8f0;
}

.text-green { color: var(--accent-green); font-weight: bold; }
.text-red { color: var(--accent-red); font-weight: bold; }

.empty, .loading {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
  font-style: italic;
}
</style>
