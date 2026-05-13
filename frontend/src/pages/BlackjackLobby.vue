<template>
  <div class="lobby-page">
    <div class="glass-panel header-row">
      <button @click="router.push('/lobby')" class="btn-back">← Volver al Casino</button>
      <h2>Mesas de Blackjack Multijugador</h2>
    </div>

    <div class="tables-grid">
      <div v-for="table in tables" :key="table.id" class="glass-panel table-card">
        <h3>{{ table.name }}</h3>
        <p>Estado: <strong>{{ formatStatus(table.status) }}</strong></p>
        <p>Jugadores: <strong>{{ table.player_count }} / 5</strong></p>
        <button class="btn-join" @click="joinTable(table.id)">UNIRSE A LA MESA</button>
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

const loadTables = async () => {
  try {
    const res = await api.get('/games/blackjack-mp/tables');
    tables.value = res.data;
  } catch (e) {
    console.error(e);
  }
};

onMounted(() => {
  loadTables();
});

const formatStatus = (status) => {
  const map = {
    'WAITING_PLAYERS': 'Esperando...',
    'BETTING': 'Apuestas Abiertas',
    'PLAYING': 'Jugando...',
    'RESOLVED': 'Resolviendo'
  };
  return map[status] || status;
};

const joinTable = (id) => {
  router.push(`/blackjack-mp/${id}`);
};
</script>

<style scoped>
.lobby-page {
  padding: 40px;
  max-width: 1200px;
  margin: 0 auto;
}
.header-row {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 40px;
  padding: 20px;
}
.tables-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}
.table-card {
  padding: 30px;
  text-align: center;
  border-top: 4px solid #10b981;
}
.btn-join {
  margin-top: 20px;
  padding: 12px 24px;
  background: #10b981;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  width: 100%;
}
.btn-join:hover { background: #059669; }
</style>
