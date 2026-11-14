/**
 * El catálogo de juegos. Única fuente de verdad.
 *
 * Antes había dos: estas tarjetas escritas a mano en el lobby y una lista en
 * `GET /api/v1/games/` que no llamaba nadie. La del backend se quedó vieja sin
 * que nada lo avisara —le faltaban Mines, Generala y Blackjack Multijugador—
 * porque no la renderizaba ninguna pantalla. Se borró, y quedó esto.
 *
 * Los grupos y las marcas no son decoración: responden lo que la gente se
 * pregunta al entrar, que no es "¿esto es de cartas o de dados?" sino "¿juego
 * ya o tengo que esperar a alguien?" y "¿cuánto tiempo me lleva?".
 *
 * Y resuelven algo que estaba roto: Truco y Generala tienen mesas entre
 * jugadores y desde el lobby no había forma de enterarse.
 */

// Lo que cambia a qué te estás anotando: jugar ya, o esperar un rival.
export const GRUPOS = [
  {
    id: 'criollos',
    titulo: 'Criollos',
    bajada: 'Los de acá. Contra la casa o mano a mano con otro jugador.',
  },
  {
    id: 'casa',
    titulo: 'Contra la casa',
    bajada: 'Entrás y jugás. No hace falta que haya nadie más.',
  },
  {
    id: 'gente',
    titulo: 'Con otros jugadores',
    bajada: 'Mesas en vivo. La casa cobra comisión, no juega.',
  },
];

// Marcas sueltas, que cruzan los grupos.
export const MARCAS = {
  alToque: { texto: 'Al toque', clase: 'marca-rapida' },
  pvp: { texto: 'También PvP', clase: 'marca-pvp' },
};

export const JUEGOS = [
  // --------------------------- criollos ---------------------------
  {
    id: 'truco',
    nombre: 'Truco',
    descripcion:
      'Envido, truco y mentir todo lo que haga falta. Contra la casa o en mesa con otro.',
    icono: '🂡',
    ruta: '/truco',
    color: '#eab308',
    grupo: 'criollos',
    marcas: ['pvp'],
  },
  {
    id: 'generala',
    nombre: 'Generala',
    descripcion:
      'Cinco dados y diez categorías. Contra la casa cobrás por puntaje; en mesa, gana el que más suma.',
    icono: '🎲',
    ruta: '/generala',
    color: '#f97316',
    grupo: 'criollos',
    marcas: ['pvp'],
  },

  // --------------------------- contra la casa ---------------------------
  {
    id: 'dice',
    nombre: 'Dice',
    descripcion:
      'Elegís el objetivo y el lado. El pago sale de la chance: cuanto más difícil, más paga.',
    icono: '🎯',
    ruta: '/dice',
    color: '#38bdf8',
    grupo: 'casa',
    marcas: ['alToque'],
  },
  {
    id: 'limbo',
    nombre: 'Limbo',
    descripcion:
      'Apostá a que el multiplicador sorteado llega al tuyo. El crash, sin esperar.',
    icono: '🚀',
    ruta: '/limbo',
    color: '#a78bfa',
    grupo: 'casa',
    marcas: ['alToque'],
  },
  {
    id: 'mines',
    nombre: 'Mines',
    descripcion:
      'Destapá casillas sin tocar una mina. Cobrá cuando quieras, el multiplicador sube con cada acierto.',
    icono: '💣',
    ruta: '/mines',
    color: '#06b6d4',
    grupo: 'casa',
    marcas: [],
  },
  {
    id: 'plinko',
    nombre: 'Plinko',
    descripcion:
      'Elegí riesgo y filas, y dejá caer la bola buscando los multiplicadores de los bordes.',
    icono: '🔴',
    ruta: '/plinko',
    color: '#22c55e',
    grupo: 'casa',
    marcas: ['alToque'],
  },
  {
    id: 'roulette',
    nombre: 'Ruleta Europea',
    descripcion: 'Apostá a números, colores o docenas. Un solo cero.',
    icono: '🎡',
    ruta: '/roulette',
    color: '#8b5cf6',
    grupo: 'casa',
    marcas: ['alToque'],
  },
  {
    id: 'slots',
    nombre: 'Tragamonedas',
    descripcion: 'La clásica de tres rodillos. Paga en 2 de cada 3 tiradas.',
    icono: '🎰',
    ruta: '/slots',
    color: '#ec4899',
    grupo: 'casa',
    marcas: ['alToque'],
  },
  {
    id: 'blackjack',
    nombre: 'Blackjack (21)',
    descripcion: 'Mano a mano contra el crupier. Doblar, separar y plantarse a tiempo.',
    icono: '🃏',
    ruta: '/blackjack',
    color: '#8b5cf6',
    grupo: 'casa',
    marcas: [],
  },

  // --------------------------- con otros jugadores ---------------------------
  {
    id: 'crash',
    nombre: 'Crash',
    descripcion: 'El multiplicador sube y explota. Retirate antes, con todos mirando.',
    icono: '📈',
    ruta: '/crash',
    color: '#f59e0b',
    grupo: 'gente',
    marcas: [],
  },
  {
    id: 'poker',
    nombre: "Texas Hold'em",
    descripcion: 'Mesas cash en vivo. Farolear y ganar el pozo.',
    icono: '♠️',
    ruta: '/lobby-poker',
    color: '#ef4444',
    grupo: 'gente',
    marcas: [],
    // Abre la lista de salas, no una partida.
    cta: 'Ver salas',
  },
  {
    id: 'blackjack-mp',
    nombre: 'Blackjack Multijugador',
    descripcion: 'La misma mesa de 21, con otros jugadores sentados.',
    icono: '👥',
    ruta: '/lobby-blackjack',
    color: '#8b5cf6',
    grupo: 'gente',
    marcas: [],
    cta: 'Ver salas',
  },
];

export function juegosDe(grupoId) {
  return JUEGOS.filter((juego) => juego.grupo === grupoId);
}
