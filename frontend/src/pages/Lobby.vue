<template>
  <div class="lobby-container">
    <div class="dashboard">
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
              {{ juego.cta || 'Jugar ' + juego.nombre }}
            </div>
          </div>
        </div>
      </section>
    </div>

    <TransactionTable />
  </div>
</template>

<script setup>
// El saldo, el deposito y el retiro viven en la barra de arriba (App.vue):
// el saldo se muestra en todas las pantallas, asi que repetirlo aca en una
// tarjeta gigante lo dejaba dos veces en la misma pantalla y empujaba los
// juegos abajo del pliegue.
import { useRouter } from 'vue-router';
import { GRUPOS, MARCAS, juegosDe } from '../shared/juegos';
import TransactionTable from '../widgets/TransactionTable.vue';

const router = useRouter();
</script>

<style scoped>
.lobby-container {
  padding: 20px 40px;
  max-width: var(--ancho-maximo, 1680px);
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
  grid-template-columns: repeat(auto-fill, minmax(216px, 1fr));
  gap: 14px;
}

.game-card {
  padding: 18px 16px;
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
  font-size: 2.3rem;
  margin-bottom: 9px;
}

.game-card h3 {
  margin-bottom: 6px;
  font-size: 1.02rem;
}

.game-card p {
  color: var(--text-muted);
  margin-bottom: 12px;
  font-size: 0.73rem;
  line-height: 1.4;
  /* A dos lineas: la descripcion ayuda a elegir, pero si crece empareja la
     altura de todas las tarjetas con la del texto mas largo. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
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
