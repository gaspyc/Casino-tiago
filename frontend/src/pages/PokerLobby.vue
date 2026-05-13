<template>
  <div class="lobby-container">
    <div class="header">
      <button class="btn-back" @click="$router.push('/lobby')">← Volver al Casino</button>
      <h1>Poker Texas Hold'em</h1>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Cargando mesas...</p>
    </div>

    <div v-else class="tables-grid">
      <div v-for="t in tables" :key="t.id" class="table-card glass-panel" @click="joinTable(t.id)">
        <div class="table-icon">♠️</div>
        <h3>{{ t.name }}</h3>
        <p class="status" :class="t.status.toLowerCase()">{{ formatStatus(t.status) }}</p>
        <div class="players-count">
          <span>👥 Jugadores: {{ t.player_count }}</span>
        </div>
        <button class="btn-join">Entrar a la mesa</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import api from '../shared/api';

const router = useRouter();
const tables = ref([]);
const loading = ref(true);

const fetchTables = async () => {
  try {
    const res = await api.get('/games/poker-mp/tables');
    tables.value = res.data;
  } catch (e) {
    console.error("Error cargando mesas", e);
  } finally {
    loading.value = false;
  }
};

const formatStatus = (status) => {
  const map = {
    'WAITING_PLAYERS': 'Esperando Jugadores',
    'PRE_FLOP': 'Pre-Flop',
    'FLOP': 'Flop',
    'TURN': 'Turn',
    'RIVER': 'River',
    'SHOWDOWN': 'Showdown'
  };
  return map[status] || status;
};

const joinTable = (id) => {
  router.push(`/poker-mp/${id}`);
};

onMounted(() => {
  fetchTables();
});
</script>

<style scoped>
.lobby-container {
  padding: 40px;
  max-width: 1200px;
  margin: 0 auto;
}

.header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 40px;
}

.btn-back {
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border-color);
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
}

.tables-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 30px;
}

.table-card {
  padding: 30px;
  text-align: center;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  border-top: 4px solid #ef4444; /* Rojo para Poker */
}

.table-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 25px rgba(239, 68, 68, 0.2);
}

.table-icon {
  font-size: 3rem;
  margin-bottom: 15px;
}

.status {
  font-weight: 600;
  margin-bottom: 15px;
}
.status.waiting_players { color: #f59e0b; }
.status.pre_flop, .status.flop, .status.turn, .status.river { color: #10b981; }

.btn-join {
  margin-top: 20px;
  width: 100%;
  padding: 12px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: bold;
}
</style>
