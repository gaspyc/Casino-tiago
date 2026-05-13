<template>
  <div class="slots-page">
    <div class="glass-panel header-row">
      <button @click="router.push('/lobby')" class="btn-back">← Volver al Lobby</button>
      <div class="balance">Saldo: ${{ balance }}</div>
    </div>

    <div class="main-layout glass-panel">
      <h2>Tragamonedas Clásica</h2>
      
      <div class="slot-machine">
        <div class="reels-container">
          <div class="reel" v-for="(reel, index) in 3" :key="index">
            <div class="reel-strip" :style="getReelStyle(index)">
              <!-- Símbolos repetidos para el efecto de giro -->
              <div v-for="(sym, i) in reelStrips[index]" :key="i" class="symbol">
                {{ sym }}
              </div>
            </div>
          </div>
          <!-- Línea indicadora de victoria -->
          <div class="payline"></div>
        </div>
      </div>
      
      <div v-if="lastResult && !isSpinning" class="result-message" :class="{ win: lastResult.net_profit > 0 }">
        {{ lastResult.net_profit > 0 ? `¡GANASTE $${lastResult.total_payout}! 🎉` : 'Sigue intentando' }}
      </div>
      <div v-else class="result-message placeholder">
        Gira para jugar
      </div>

      <div class="controls">
        <div class="bet-controls">
          <label>Apuesta:</label>
          <button @click="betAmount = Math.max(1, betAmount - 1)" :disabled="isSpinning">-</button>
          <span class="bet-display">${{ betAmount }}</span>
          <button @click="betAmount += 1" :disabled="isSpinning">+</button>
        </div>
        
        <button class="btn-spin" @click="spinSlots" :disabled="isSpinning || betAmount > parseFloat(balance)">
          {{ isSpinning ? 'GIRANDO...' : 'TIRAR PALANCA' }}
        </button>
      </div>
      <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
      
      <!-- Tabla de pagos estática -->
      <div class="paytable">
        <div class="pay-item"><span>7️⃣ 7️⃣ 7️⃣</span> <span>100x</span></div>
        <div class="pay-item"><span>💎 💎 💎</span> <span>50x</span></div>
        <div class="pay-item"><span>🔔 🔔 🔔</span> <span>30x</span></div>
        <div class="pay-item"><span>🍇 🍇 🍇</span> <span>20x</span></div>
        <div class="pay-item"><span>🍊 🍊 🍊</span> <span>15x</span></div>
        <div class="pay-item"><span>🍋 🍋 🍋</span> <span>10x</span></div>
        <div class="pay-item"><span>🍒 🍒 🍒</span> <span>5x</span></div>
        <div class="pay-item"><span>🍒 🍒 ❌</span> <span>2x</span></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import confetti from 'canvas-confetti';
import api from '../shared/api';

const router = useRouter();
const balance = ref('0.00');
const isSpinning = ref(false);
const betAmount = ref(5);
const errorMsg = ref('');
const lastResult = ref(null);

const symbols = ["🍒", "🍋", "🍊", "🍇", "🔔", "💎", "7️⃣"];

// Llenamos la tira con muchos símbolos aleatorios y pondremos el resultado ganador al final.
const generateStrip = (len) => Array.from({length: len}, () => symbols[Math.floor(Math.random()*symbols.length)]);

const reelStrips = ref([
  generateStrip(40),
  generateStrip(50),
  generateStrip(60),
]);

const reelOffsets = ref([0, 0, 0]);
const reelTransitions = ref(['none', 'none', 'none']);

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

const getReelStyle = (index) => {
  return {
    transform: `translateY(-${reelOffsets.value[index]}px)`,
    transition: reelTransitions.value[index]
  };
};

const spinSlots = async () => {
  if (betAmount.value > parseFloat(balance.value)) {
    errorMsg.value = "Saldo insuficiente";
    return;
  }
  
  errorMsg.value = '';
  isSpinning.value = true;
  lastResult.value = null;
  balance.value = (parseFloat(balance.value) - betAmount.value).toFixed(2);
  
  // Refrescar las tiras de símbolos para no quedarse sin pista en futuros giros
  reelStrips.value = [generateStrip(40), generateStrip(50), generateStrip(60)];
  
  // Resetear posición instantáneamente
  reelTransitions.value = ['none', 'none', 'none'];
  reelOffsets.value = [0, 0, 0];
  
  // Forzar reflow para que Vue aplique el reset CSS inmediatamente
  await new Promise(r => setTimeout(r, 50));
  
  try {
    const res = await api.post('/games/slots/spin', {
      bet_amount: betAmount.value
    });
    
    const resultLine = res.data.result_data.line;
    
    for(let i=0; i<3; i++) {
      const stripLen = reelStrips.value[i].length;
      // Posicionamos el símbolo ganador en el penúltimo lugar de la tira 
      // (el último se ve abajo, el ganador en el medio, y el antepenúltimo arriba)
      reelStrips.value[i][stripLen - 2] = resultLine[i];
    }
    
    const SYMBOL_HEIGHT = 100; // px
    
    // Animar
    setTimeout(() => {
      // Rodillo 1 frena a los 2s
      reelTransitions.value[0] = 'transform 2s cubic-bezier(0.1, 0.7, 0.1, 1)';
      reelOffsets.value[0] = (reelStrips.value[0].length - 3) * SYMBOL_HEIGHT;
      
      // Rodillo 2 frena a los 3s
      reelTransitions.value[1] = 'transform 3s cubic-bezier(0.1, 0.7, 0.1, 1)';
      reelOffsets.value[1] = (reelStrips.value[1].length - 3) * SYMBOL_HEIGHT;
      
      // Rodillo 3 frena a los 4s
      reelTransitions.value[2] = 'transform 4s cubic-bezier(0.1, 0.7, 0.1, 1)';
      reelOffsets.value[2] = (reelStrips.value[2].length - 3) * SYMBOL_HEIGHT;
    }, 50);
    
    // Terminar
    setTimeout(async () => {
      isSpinning.value = false;
      lastResult.value = res.data;
      await loadBalance();
      
      if (res.data.net_profit > 0) {
        confetti({
          particleCount: 150,
          spread: 80,
          origin: { y: 0.6 }
        });
      }
    }, 4050);
    
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || e.message || "Error al jugar";
    isSpinning.value = false;
    await loadBalance();
  }
};
</script>

<style scoped>
.slots-page {
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
.balance {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--primary);
}

.main-layout {
  padding: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

h2 {
  margin-top: 0;
  margin-bottom: 30px;
  font-size: 2.5rem;
  color: #fff;
  text-shadow: 0 2px 4px rgba(0,0,0,0.5);
  font-weight: 900;
  letter-spacing: 2px;
}

.slot-machine {
  background: linear-gradient(180deg, #334155 0%, #0f172a 100%);
  padding: 20px;
  border-radius: 16px;
  border: 4px solid #f59e0b; /* dorado */
  box-shadow: 0 10px 25px rgba(0,0,0,0.8), inset 0 0 20px rgba(0,0,0,0.5);
  margin-bottom: 30px;
}

.reels-container {
  display: flex;
  gap: 15px;
  background: #fff;
  padding: 15px;
  border-radius: 8px;
  box-shadow: inset 0 0 15px rgba(0,0,0,0.8);
  height: 300px; /* 3 símbolos visibles de 100px c/u */
  overflow: hidden;
  position: relative;
}

/* Payline horizontal */
.payline {
  position: absolute;
  top: 50%;
  left: 0;
  width: 100%;
  height: 4px;
  background: rgba(239, 68, 68, 0.7);
  transform: translateY(-50%);
  z-index: 10;
  box-shadow: 0 0 10px red;
  pointer-events: none;
}

.reel {
  width: 120px;
  height: 100%;
  background: #f8fafc;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  overflow: hidden;
  box-shadow: inset 0 0 10px rgba(0,0,0,0.1);
}

.reel-strip {
  display: flex;
  flex-direction: column;
  width: 100%;
  /* El transition y transform son inyectados vía Vue */
}

.symbol {
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 4rem;
  text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
}

.controls {
  display: flex;
  align-items: center;
  gap: 30px;
  margin-top: 10px;
}

.bet-controls {
  display: flex;
  align-items: center;
  gap: 15px;
  background: rgba(255,255,255,0.1);
  padding: 10px 20px;
  border-radius: 8px;
}
.bet-controls button {
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  font-size: 1.2rem;
  cursor: pointer;
  transition: opacity 0.2s;
}
.bet-controls button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.bet-controls label {
  font-weight: 600;
  color: var(--text-muted);
}
.bet-display {
  font-size: 1.2rem;
  font-weight: bold;
  min-width: 50px;
  text-align: center;
}

.btn-spin {
  font-size: 1.2rem;
  padding: 16px 40px;
  background: linear-gradient(180deg, var(--accent-red) 0%, #991b1b 100%);
  color: white;
  border: 2px solid #fca5a5;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
  box-shadow: 0 4px 6px rgba(0,0,0,0.3);
  text-transform: uppercase;
}
.btn-spin:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.result-message {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 20px;
  height: 36px;
}
.result-message.win { color: var(--accent-green); }
.placeholder { color: transparent; }

.error-msg {
  color: var(--accent-red);
  margin-top: 10px;
}

/* Paytable */
.paytable {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 15px;
  margin-top: 40px;
  background: rgba(0,0,0,0.3);
  padding: 20px;
  border-radius: 12px;
  width: 100%;
}
.pay-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 1.2rem;
  background: rgba(255,255,255,0.05);
  padding: 10px 15px;
  border-radius: 6px;
}
.pay-item span:first-child { letter-spacing: 2px; }
.pay-item span:last-child { font-weight: bold; color: var(--accent-green); }
</style>
