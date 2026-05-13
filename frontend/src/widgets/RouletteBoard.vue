<template>
  <div class="roulette-board glass-panel">
    <div class="board-grid">
      <div class="spot zero" @click="addBet('number', '0')" @contextmenu.prevent.stop="removeBet('number', '0')">
        0
        <div class="chip-stack" v-if="getChipsForSpot('number', '0').length">
           <span class="chip-marker">${{ getChipsForSpot('number', '0').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="numbers">
        <div 
          v-for="n in 36" 
          :key="n" 
          class="spot number"
          :class="isRed(n) ? 'red' : 'black'"
          @click="addBet('number', n.toString())"
          @contextmenu.prevent.stop="removeBet('number', n.toString())"
        >
          {{ n }}
          <div class="chip-stack" v-if="getChipsForSpot('number', n.toString()).length">
             <span class="chip-marker">${{ getChipsForSpot('number', n.toString()).reduce((a,b)=>a+b.bet_amount,0) }}</span>
          </div>

          <!-- Hitboxes Invisibles para Apuestas a Caballo (Split) y Cuadro (Corner) -->
          <!-- Split Derecho -->
          <div class="hitbox split-right" v-if="n <= 33" 
               @click.stop="addBet('split', `${n},${n+3}`)" 
               @contextmenu.prevent.stop="removeBet('split', `${n},${n+3}`)">
             <div class="chip-stack" v-if="getChipsForSpot('split', `${n},${n+3}`).length">
               <span class="chip-marker hitbox-marker">${{ getChipsForSpot('split', `${n},${n+3}`).reduce((a,b)=>a+b.bet_amount,0) }}</span>
             </div>
          </div>

          <!-- Split Inferior -->
          <div class="hitbox split-bottom" v-if="n % 3 !== 0" 
               @click.stop="addBet('split', `${n},${n+1}`)" 
               @contextmenu.prevent.stop="removeBet('split', `${n},${n+1}`)">
             <div class="chip-stack" v-if="getChipsForSpot('split', `${n},${n+1}`).length">
               <span class="chip-marker hitbox-marker">${{ getChipsForSpot('split', `${n},${n+1}`).reduce((a,b)=>a+b.bet_amount,0) }}</span>
             </div>
          </div>

          <!-- Corner (Esquina) -->
          <div class="hitbox corner" v-if="n <= 33 && n % 3 !== 0" 
               @click.stop="addBet('corner', `${n},${n+1},${n+3},${n+4}`)" 
               @contextmenu.prevent.stop="removeBet('corner', `${n},${n+1},${n+3},${n+4}`)">
             <div class="chip-stack" v-if="getChipsForSpot('corner', `${n},${n+1},${n+3},${n+4}`).length">
               <span class="chip-marker hitbox-marker">${{ getChipsForSpot('corner', `${n},${n+1},${n+3},${n+4}`).reduce((a,b)=>a+b.bet_amount,0) }}</span>
             </div>
          </div>
        </div>
      </div>
    </div>
    
    <div class="outside-bets">
      <div class="spot outside" @click="addBet('parity', 'even')" @contextmenu.prevent.stop="removeBet('parity', 'even')">
        PAR
        <div class="chip-stack" v-if="getChipsForSpot('parity', 'even').length">
           <span class="chip-marker">${{ getChipsForSpot('parity', 'even').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="spot outside red-bet" @click="addBet('color', 'red')" @contextmenu.prevent.stop="removeBet('color', 'red')">
        ROJO
        <div class="chip-stack" v-if="getChipsForSpot('color', 'red').length">
           <span class="chip-marker">${{ getChipsForSpot('color', 'red').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="spot outside black-bet" @click="addBet('color', 'black')" @contextmenu.prevent.stop="removeBet('color', 'black')">
        NEGRO
        <div class="chip-stack" v-if="getChipsForSpot('color', 'black').length">
           <span class="chip-marker">${{ getChipsForSpot('color', 'black').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="spot outside" @click="addBet('parity', 'odd')" @contextmenu.prevent.stop="removeBet('parity', 'odd')">
        IMPAR
        <div class="chip-stack" v-if="getChipsForSpot('parity', 'odd').length">
           <span class="chip-marker">${{ getChipsForSpot('parity', 'odd').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useBettingState } from '../features/useBettingState';

const { addBet, removeBet, getChipsForSpot } = useBettingState();

const redNumbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36];
const isRed = (n) => redNumbers.includes(n);
</script>

<style scoped>
.roulette-board {
  padding: 20px;
  user-select: none;
}

.board-grid {
  display: flex;
}

.zero {
  width: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-green);
  border: 1px solid rgba(255,255,255,0.2);
  cursor: pointer;
  position: relative;
  font-weight: bold;
  font-size: 1.2rem;
  border-radius: 8px 0 0 8px;
  z-index: 5;
}

.numbers {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  grid-auto-flow: column;
  grid-template-rows: repeat(3, 1fr);
  flex: 1;
}

.spot {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255,255,255,0.2);
  cursor: pointer;
  position: relative;
  font-weight: bold;
  font-size: 1.2rem;
  transition: opacity 0.2s;
}

.spot:hover {
  opacity: 0.8;
}

.number.red { background: var(--accent-red); }
.number.black { background: var(--accent-black); }

/* --- HITBOXES PARA SPLIT Y CORNER --- */
.hitbox {
  position: absolute;
  z-index: 10;
  opacity: 0;
  transition: opacity 0.2s, background 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.hitbox:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.5);
}

.split-right {
  width: 20px;
  height: 100%;
  right: -10px;
  top: 0;
}

.split-bottom {
  width: 100%;
  height: 20px;
  bottom: -10px;
  left: 0;
}

.corner {
  width: 26px;
  height: 26px;
  right: -13px;
  bottom: -13px;
  z-index: 20; /* Siempre por encima de los splits */
  border-radius: 50%;
}

/* Mantener hitboxes visibles si tienen una ficha */
.hitbox:has(.chip-stack) {
  opacity: 1;
  background: transparent !important;
}

.outside-bets {
  display: flex;
  margin-top: 10px;
}

.outside {
  flex: 1;
  height: 50px;
  background: rgba(255,255,255,0.1);
}
.red-bet { color: var(--accent-red); border-bottom: 4px solid var(--accent-red); }
.black-bet { color: var(--text-main); border-bottom: 4px solid var(--accent-black); }

.chip-stack {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.chip-marker {
  background: var(--primary);
  color: white;
  border-radius: 50%;
  width: 30px; height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  border: 2px solid white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.5);
}

.hitbox-marker {
  width: 24px; height: 24px;
  font-size: 0.7rem;
  background: #3b82f6; /* Distinción visual para fichas en cruces */
}
</style>
