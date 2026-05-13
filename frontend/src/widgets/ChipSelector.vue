<template>
  <div class="chip-selector glass-panel">
    <h4>Selecciona tu ficha</h4>
    <div class="chips">
      <div 
        v-for="val in [1, 5, 10, 50, 100]" 
        :key="val"
        class="chip"
        :class="{ active: selectedChip === val }"
        @click="selectedChip = val"
      >
        ${{ val }}
      </div>
    </div>
    <div class="actions">
      <button class="btn btn-clear" @click="clearBets" :disabled="isSpinning || bets.length === 0">Limpiar Tapete</button>
      <div class="total">Total: ${{ totalBetAmount }}</div>
    </div>
  </div>
</template>

<script setup>
import { useBettingState } from '../features/useBettingState';

const { selectedChip, bets, totalBetAmount, clearBets, isSpinning } = useBettingState();
</script>

<style scoped>
.chip-selector {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 20px;
}
.chips {
  display: flex;
  gap: 16px;
  justify-content: center;
}
.chip {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 1.2rem;
  cursor: pointer;
  background: radial-gradient(circle at 30% 30%, #475569, #1e293b);
  border: 4px dashed rgba(255,255,255,0.2);
  box-shadow: 0 4px 8px rgba(0,0,0,0.4);
  transition: transform 0.2s;
}
.chip.active {
  transform: scale(1.1);
  border-color: var(--primary);
  box-shadow: 0 0 15px var(--primary);
}
.actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}
.btn-clear {
  background: var(--accent-red);
}
.total {
  font-size: 1.2rem;
  font-weight: bold;
}
</style>
