/**
 * El saldo del jugador, en un solo lugar.
 *
 * Antes cada pantalla tenía su propio `balance` y su propio `cargarSaldo`, y
 * lo mostraba en su propio encabezado: doce copias de lo mismo. Con el saldo
 * en la barra de arriba eso pasa a ser una sola copia, pero entonces tiene
 * que ser compartido de verdad — si no, cobrás en el dice y el número de la
 * barra se queda viejo hasta que recargues.
 *
 * Las pantallas ya no lo muestran: llaman a `refrescarSaldo()` después de
 * cada jugada y la barra se actualiza sola.
 */

import { ref } from 'vue';
import api from './api';

export const saldo = ref('0.00');
export const saldoCargado = ref(false);

export async function refrescarSaldo() {
  try {
    const res = await api.get('/wallet/balance');
    saldo.value = parseFloat(res.data.balance).toFixed(2);
    saldoCargado.value = true;
  } catch {
    // Un error puntual no borra el saldo que ya se mostraba: dejar el número
    // viejo es mejor que parpadear a cero y asustar a alguien.
  }

  return saldo.value;
}

/**
 * Para las pantallas que ya traen el saldo en su propia llamada: en vez de
 * pedirlo dos veces, avisan el valor que acaban de recibir.
 */
export function fijarSaldo(valor) {
  if (valor === null || valor === undefined) return;
  saldo.value = typeof valor === 'string' ? valor : parseFloat(valor).toFixed(2);
  saldoCargado.value = true;
}

export function olvidarSaldo() {
  saldo.value = '0.00';
  saldoCargado.value = false;
}
