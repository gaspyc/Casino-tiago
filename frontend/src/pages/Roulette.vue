<template>
  <div class="roulette-page">
    <div class="glass-panel header-row">
      <button @click="router.push('/lobby')" class="btn-back">← Volver al Lobby</button>
      <div class="balance">Saldo: ${{ balance }}</div>
    </div>

    <div class="main-layout">
      <!-- Rueda y Resultados -->
      <div class="wheel-panel glass-panel">
        
        <div class="wheel-container">
          <!-- Flecha marcadora -->
          <div class="wheel-pointer"></div>
          <!-- Gráfico SVG de la ruleta -->
          <img 
            src="/roulette-wheel.svg" 
            class="wheel-img" 
            :style="{ transform: `rotate(${wheelRotation}deg)`, transition: wheelTransition }" 
          />
          <!-- Resultado superpuesto al centro cuando se detiene -->
          <div class="result-number" v-if="lastResult && !isSpinning" :class="lastResult.result_data.winning_color">
            {{ lastResult.result_data.winning_number }}
          </div>
        </div>
        
        <div v-if="lastResult && !isSpinning" class="result-message" :class="{ win: lastResult.net_profit > 0, lose: lastResult.net_profit <= 0 }">
          {{ lastResult.net_profit > 0 ? `¡Ganaste $${lastResult.total_payout}!` : 'No hubo suerte' }}
        </div>

        <button class="btn btn-spin" @click="spinWheel" :disabled="isSpinning || bets.length === 0">
          {{ isSpinning ? 'Girando...' : 'GIRAR RULETA' }}
        </button>
        <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
      </div>

      <!-- Tapete interactivo -->
      <div class="board-panel">
        <RouletteBoard />
        <ChipSelector />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import confetti from 'canvas-confetti';
import api from '../shared/api';
import RouletteBoard from '../widgets/RouletteBoard.vue';
import ChipSelector from '../widgets/ChipSelector.vue';
import { useBettingState } from '../features/useBettingState';

const router = useRouter();
const balance = ref('0.00');
const lastResult = ref(null);
const errorMsg = ref('');

// Configuración de la Rueda Física
const wheelRotation = ref(0);
const wheelTransition = ref('none');
// Orden oficial de los números en la ruleta europea
const rouletteOrder = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26];

const { bets, isSpinning, totalBetAmount, clearBets } = useBettingState();

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
  clearBets(); // reset state
});
onUnmounted(() => {
  clearBets();
});

const spinWheel = async () => {
  if (bets.value.length === 0) return;
  if (totalBetAmount.value > parseFloat(balance.value)) {
    errorMsg.value = "Saldo insuficiente para el total apostado";
    return;
  }

  errorMsg.value = '';
  isSpinning.value = true;
  lastResult.value = null;

  try {
    // Descontar visualmente
    balance.value = (parseFloat(balance.value) - totalBetAmount.value).toFixed(2);

    // Enviar batch al backend
    const res = await api.post('/games/roulette/bet', {
      bets: bets.value
    });

    // Calcular rotación física de la rueda SVG
    const winningNum = res.data.result_data.winning_number;
    const index = rouletteOrder.indexOf(winningNum);
    const anglePerPocket = 360 / 37;
    
    // Calculamos el ángulo objetivo (hacia atrás para que coincida con la flecha superior)
    // Agregamos un ligero offset aleatorio dentro de la misma cuña para realismo
    const offset = (Math.random() - 0.5) * (anglePerPocket * 0.8);
    const targetAngle = -(index * anglePerPocket + offset);
    
    // Calculamos la distancia desde la posición actual para seguir girando
    const currentAngle = wheelRotation.value % 360;
    let diff = targetAngle - currentAngle;
    if (diff > 0) diff -= 360; // Siempre girar en sentido horario (ángulos negativos)
    
    // Activamos transición realista y sumamos 5 giros rápidos extras (1800 grados)
    wheelTransition.value = 'transform 4s cubic-bezier(0.2, 0.8, 0.2, 1)';
    wheelRotation.value += diff - (360 * 5);

    // Esperamos 4 segundos a que termine la animación física
    setTimeout(async () => {
      lastResult.value = res.data;
      isSpinning.value = false;
      clearBets(); // limpiar tapete
      await loadBalance(); // actualizar saldo real
      
      // Si hubo victoria, lanzar confeti!
      if (res.data.net_profit > 0) {
        confetti({
          particleCount: 150,
          spread: 80,
          origin: { y: 0.6 }
        });
      }
    }, 4000);

  } catch (e) {
    errorMsg.value = e.response?.data?.detail || e.message || "Error al apostar";
    isSpinning.value = false;
    await loadBalance();
  }
};
</script>

<style scoped>
.roulette-page {
  padding: 20px 40px;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
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

.balance {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--primary);
}

.main-layout {
  display: flex;
  gap: 24px;
}

.wheel-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px;
  min-height: 500px;
}

.board-panel {
  flex: 2;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* --- Rueda Física --- */
.wheel-container {
  position: relative;
  width: 300px;
  height: 300px;
  margin-bottom: 30px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.wheel-img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  box-shadow: 0 0 20px rgba(0,0,0,0.8), inset 0 0 10px rgba(0,0,0,0.5);
  /* El transition y transform son inyectados vía Vue */
}

.wheel-pointer {
  position: absolute;
  top: -15px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 15px solid transparent;
  border-right: 15px solid transparent;
  border-top: 30px solid white;
  z-index: 10;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.8));
}

.result-number {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 4rem;
  font-weight: 900;
  color: white;
  text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
  background: rgba(0,0,0,0.5);
  border-radius: 50%;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
  border: 4px solid rgba(255,255,255,0.2);
}
.result-number.red { background: rgba(239, 68, 68, 0.8); }
.result-number.black { background: rgba(15, 23, 42, 0.8); }
.result-number.green { background: rgba(16, 185, 129, 0.8); }

.btn-spin {
  font-size: 1.2rem;
  padding: 16px 32px;
  width: 100%;
  margin-top: auto;
}

.result-message {
  font-size: 1.5rem;
  font-weight: 700;
  padding: 10px 20px;
  border-radius: 8px;
  text-align: center;
  margin-bottom: 20px;
}
.result-message.win { background: rgba(16, 185, 129, 0.2); color: var(--accent-green); }
.result-message.lose { background: rgba(239, 68, 68, 0.2); color: var(--accent-red); }

.error-msg {
  color: var(--accent-red);
  margin-top: 16px;
  font-size: 0.9rem;
}

@media (max-width: 900px) {
  .roulette-page {
    padding: 10px;
  }
  
  .header-row {
    margin-bottom: 10px;
    padding: 10px;
  }
  
  .main-layout {
    flex-direction: column;
    gap: 10px;
  }
  
  .wheel-panel {
    min-height: auto;
    padding: 10px;
  }
  
  .wheel-container {
    width: 180px;
    height: 180px;
    margin-bottom: 10px;
  }
  
  .result-number {
    width: 50px;
    height: 50px;
    font-size: 2rem;
  }
  
  .btn-spin {
    padding: 10px 16px;
    font-size: 1rem;
  }
  
  .board-panel {
    gap: 10px;
  }
}
</style>
