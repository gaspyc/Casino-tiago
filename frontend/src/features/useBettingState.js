import { ref, computed } from 'vue';

const bets = ref([]);
const selectedChip = ref(10); // Default chip
const isSpinning = ref(false);

export const useBettingState = () => {
  const addBet = (type, value) => {
    if (isSpinning.value) return;
    bets.value.push({
      bet_type: type,
      bet_value: value,
      bet_amount: selectedChip.value
    });
  };

  const clearBets = () => {
    if (isSpinning.value) return;
    bets.value = [];
  };

  const removeBet = (type, value) => {
    if (isSpinning.value) return;
    // Buscamos de atrás hacia adelante para sacar la última ficha que se puso
    const idx = [...bets.value].reverse().findIndex(b => b.bet_type === type && b.bet_value === value);
    if (idx !== -1) {
      const realIdx = bets.value.length - 1 - idx;
      bets.value.splice(realIdx, 1);
    }
  };

  const totalBetAmount = computed(() => {
    return bets.value.reduce((acc, curr) => acc + curr.bet_amount, 0);
  });

  const getChipsForSpot = (type, value) => {
    return bets.value.filter(b => b.bet_type === type && b.bet_value === value);
  };

  return {
    bets,
    selectedChip,
    isSpinning,
    addBet,
    removeBet,
    clearBets,
    totalBetAmount,
    getChipsForSpot
  };
};
