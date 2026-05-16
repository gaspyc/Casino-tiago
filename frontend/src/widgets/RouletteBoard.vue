<template>
  <div class="roulette-board-wrapper">
    <div class="roulette-board">
      
      <!-- Docenas (1-12, 13-24, 25-36) -->
      <div class="board-cell dozen" style="grid-column: 2 / span 4; grid-row: 1;" 
           @click="addBet('dozen', '1')" @contextmenu.prevent.stop="removeBet('dozen', '1')">
        1st 12
        <div class="chip-stack" v-if="getChipsForSpot('dozen', '1').length">
           <span class="chip-marker">${{ getChipsForSpot('dozen', '1').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="board-cell dozen" style="grid-column: 6 / span 4; grid-row: 1;" 
           @click="addBet('dozen', '2')" @contextmenu.prevent.stop="removeBet('dozen', '2')">
        2nd 12
        <div class="chip-stack" v-if="getChipsForSpot('dozen', '2').length">
           <span class="chip-marker">${{ getChipsForSpot('dozen', '2').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="board-cell dozen" style="grid-column: 10 / span 4; grid-row: 1;" 
           @click="addBet('dozen', '3')" @contextmenu.prevent.stop="removeBet('dozen', '3')">
        3rd 12
        <div class="chip-stack" v-if="getChipsForSpot('dozen', '3').length">
           <span class="chip-marker">${{ getChipsForSpot('dozen', '3').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>

      <!-- Zero -->
      <div class="board-cell zero" style="grid-column: 1; grid-row: 2 / span 3;" 
           @click="addBet('number', '0')" @contextmenu.prevent.stop="removeBet('number', '0')">
        0
        <div class="chip-stack" v-if="getChipsForSpot('number', '0').length">
           <span class="chip-marker">${{ getChipsForSpot('number', '0').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>

      <!-- Números y Hitboxes -->
      <template v-for="n in 36" :key="n">
        <div class="board-cell number" 
             :class="isRed(n) ? 'red' : 'black'"
             :style="{ gridColumn: Math.ceil(n/3) + 1, gridRow: 4 - ((n-1)%3) }"
             @click="addBet('number', n.toString())"
             @contextmenu.prevent.stop="removeBet('number', n.toString())">
             
          {{ n }}
          
          <div class="chip-stack" v-if="getChipsForSpot('number', n.toString()).length">
             <span class="chip-marker">${{ getChipsForSpot('number', n.toString()).reduce((a,b)=>a+b.bet_amount,0) }}</span>
          </div>

          <!-- Split Derecha (n, n+3) -->
          <div class="hitbox split-right" v-if="n <= 33" 
               @click.stop="addBet('split', `${n},${n+3}`)" 
               @contextmenu.prevent.stop="removeBet('split', `${n},${n+3}`)">
             <div class="chip-stack" v-if="getChipsForSpot('split', `${n},${n+3}`).length">
               <span class="chip-marker hitbox-marker">${{ getChipsForSpot('split', `${n},${n+3}`).reduce((a,b)=>a+b.bet_amount,0) }}</span>
             </div>
          </div>

          <!-- Split Arriba (n, n+1) -->
          <div class="hitbox split-top" v-if="n % 3 !== 0" 
               @click.stop="addBet('split', `${n},${n+1}`)" 
               @contextmenu.prevent.stop="removeBet('split', `${n},${n+1}`)">
             <div class="chip-stack" v-if="getChipsForSpot('split', `${n},${n+1}`).length">
               <span class="chip-marker hitbox-marker">${{ getChipsForSpot('split', `${n},${n+1}`).reduce((a,b)=>a+b.bet_amount,0) }}</span>
             </div>
          </div>

          <!-- Corner Arriba-Derecha (n, n+1, n+3, n+4) -->
          <div class="hitbox corner-tr" v-if="n <= 33 && n % 3 !== 0" 
               @click.stop="addBet('corner', `${n},${n+1},${n+3},${n+4}`)" 
               @contextmenu.prevent.stop="removeBet('corner', `${n},${n+1},${n+3},${n+4}`)">
             <div class="chip-stack" v-if="getChipsForSpot('corner', `${n},${n+1},${n+3},${n+4}`).length">
               <span class="chip-marker hitbox-marker">${{ getChipsForSpot('corner', `${n},${n+1},${n+3},${n+4}`).reduce((a,b)=>a+b.bet_amount,0) }}</span>
             </div>
          </div>
          
        </div>
      </template>

      <!-- Columnas (2to1) -->
      <div class="board-cell column-bet" style="grid-column: 14; grid-row: 2;" 
           @click="addBet('column', '3')" @contextmenu.prevent.stop="removeBet('column', '3')">
        2to1
        <div class="chip-stack" v-if="getChipsForSpot('column', '3').length">
           <span class="chip-marker">${{ getChipsForSpot('column', '3').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="board-cell column-bet" style="grid-column: 14; grid-row: 3;" 
           @click="addBet('column', '2')" @contextmenu.prevent.stop="removeBet('column', '2')">
        2to1
        <div class="chip-stack" v-if="getChipsForSpot('column', '2').length">
           <span class="chip-marker">${{ getChipsForSpot('column', '2').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="board-cell column-bet" style="grid-column: 14; grid-row: 4;" 
           @click="addBet('column', '1')" @contextmenu.prevent.stop="removeBet('column', '1')">
        2to1
        <div class="chip-stack" v-if="getChipsForSpot('column', '1').length">
           <span class="chip-marker">${{ getChipsForSpot('column', '1').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>

      <!-- Apuestas Externas (Mitades, Colores, Paridad) -->
      <div class="board-cell outside" style="grid-column: 2 / span 2; grid-row: 5;" 
           @click="addBet('half', 'low')" @contextmenu.prevent.stop="removeBet('half', 'low')">
        1-18
        <div class="chip-stack" v-if="getChipsForSpot('half', 'low').length">
           <span class="chip-marker">${{ getChipsForSpot('half', 'low').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="board-cell outside" style="grid-column: 4 / span 2; grid-row: 5;" 
           @click="addBet('parity', 'even')" @contextmenu.prevent.stop="removeBet('parity', 'even')">
        EVEN
        <div class="chip-stack" v-if="getChipsForSpot('parity', 'even').length">
           <span class="chip-marker">${{ getChipsForSpot('parity', 'even').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="board-cell outside" style="grid-column: 6 / span 2; grid-row: 5;" 
           @click="addBet('color', 'red')" @contextmenu.prevent.stop="removeBet('color', 'red')">
        <div class="diamond red-diamond"></div>
        <div class="chip-stack" v-if="getChipsForSpot('color', 'red').length">
           <span class="chip-marker">${{ getChipsForSpot('color', 'red').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="board-cell outside" style="grid-column: 8 / span 2; grid-row: 5;" 
           @click="addBet('color', 'black')" @contextmenu.prevent.stop="removeBet('color', 'black')">
        <div class="diamond black-diamond"></div>
        <div class="chip-stack" v-if="getChipsForSpot('color', 'black').length">
           <span class="chip-marker">${{ getChipsForSpot('color', 'black').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="board-cell outside" style="grid-column: 10 / span 2; grid-row: 5;" 
           @click="addBet('parity', 'odd')" @contextmenu.prevent.stop="removeBet('parity', 'odd')">
        ODD
        <div class="chip-stack" v-if="getChipsForSpot('parity', 'odd').length">
           <span class="chip-marker">${{ getChipsForSpot('parity', 'odd').reduce((a,b)=>a+b.bet_amount,0) }}</span>
        </div>
      </div>
      <div class="board-cell outside" style="grid-column: 12 / span 2; grid-row: 5;" 
           @click="addBet('half', 'high')" @contextmenu.prevent.stop="removeBet('half', 'high')">
        19-36
        <div class="chip-stack" v-if="getChipsForSpot('half', 'high').length">
           <span class="chip-marker">${{ getChipsForSpot('half', 'high').reduce((a,b)=>a+b.bet_amount,0) }}</span>
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
.roulette-board-wrapper {
  width: 100%;
  overflow-x: auto;
  padding-bottom: 10px;
}

.roulette-board {
  display: grid;
  grid-template-columns: 50px repeat(12, 1fr) 50px;
  grid-template-rows: 45px repeat(3, 50px) 45px;
  gap: 0;
  background: #115934; /* Green felt classic color */
  padding: 10px;
  border: 4px solid #fff;
  border-radius: 12px;
  min-width: 700px;
  box-shadow: inset 0 0 40px rgba(0,0,0,0.4);
  user-select: none;
}

.board-cell {
  border: 1px solid #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: bold;
  font-size: 1.1rem;
  cursor: pointer;
  position: relative;
  transition: opacity 0.2s;
  box-sizing: border-box;
}

.board-cell:hover {
  opacity: 0.8;
}

/* Colors matching your global variables where possible */
.board-cell.red { background: var(--accent-red); }
.board-cell.black { background: var(--accent-black); }
.board-cell.zero { background: var(--accent-green); }

.board-cell.dozen, .board-cell.column-bet, .board-cell.outside {
  font-size: 1rem;
  text-transform: uppercase;
  background: rgba(255, 255, 255, 0.05);
}

.diamond {
  width: 20px;
  height: 20px;
  transform: rotate(45deg);
}
.red-diamond { background: var(--accent-red); }
.black-diamond { background: var(--accent-black); }

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
  width: 20px; height: 100%; right: -10px; top: 0;
}

.split-top {
  width: 100%; height: 20px; top: -10px; left: 0;
}

.corner-tr {
  width: 26px; height: 26px; right: -13px; top: -13px; z-index: 20; border-radius: 50%;
}

/* Mantener hitboxes visibles si tienen una ficha */
.hitbox:has(.chip-stack) {
  opacity: 1;
  background: transparent !important;
}

/* --- CHIPS --- */
.chip-stack {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
  z-index: 50;
}

.chip-marker {
  background: var(--primary);
  color: white;
  border-radius: 50%;
  width: 28px; height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  border: 2px solid white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.5);
}

.hitbox-marker {
  width: 24px; height: 24px;
  font-size: 0.65rem;
  background: #3b82f6; 
}

@media (max-width: 900px) {
  .roulette-board-wrapper {
    padding-bottom: 0;
  }
  .roulette-board {
    min-width: 320px;
    grid-template-columns: 25px repeat(12, 1fr) 25px;
    grid-template-rows: 25px repeat(3, 30px) 25px;
    padding: 5px;
    border-width: 2px;
    border-radius: 8px;
  }
  .board-cell {
    font-size: 0.75rem;
  }
  .board-cell.dozen, .board-cell.column-bet, .board-cell.outside {
    font-size: 0.6rem;
  }
  .chip-marker {
    width: 18px; height: 18px; font-size: 0.5rem; border-width: 1px;
  }
  .hitbox-marker {
    width: 14px; height: 14px; font-size: 0.45rem;
  }
  .diamond {
    width: 12px; height: 12px;
  }
  .split-right { width: 10px; right: -5px; }
  .split-top { height: 10px; top: -5px; }
  .corner-tr { width: 16px; height: 16px; right: -8px; top: -8px; }
}
</style>
