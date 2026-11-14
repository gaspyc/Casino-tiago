import { createRouter, createWebHistory } from 'vue-router';
import Login from '../pages/Login.vue';
import Lobby from '../pages/Lobby.vue';
import Roulette from '../pages/Roulette.vue';
import Slots from '../pages/Slots.vue';
import Blackjack from '../pages/Blackjack.vue';
import BlackjackLobby from '../pages/BlackjackLobby.vue';
import BlackjackMultiplayer from '../pages/BlackjackMultiplayer.vue';
import PokerLobby from '../pages/PokerLobby.vue';
import PokerMultiplayer from '../pages/PokerMultiplayer.vue';
import Generala from '../pages/Generala.vue';
import Mines from '../pages/Mines.vue';
import Dice from '../pages/Dice.vue';
import Limbo from '../pages/Limbo.vue';
import Plinko from '../pages/Plinko.vue';
import Truco from '../pages/Truco.vue';

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: Login },
  { path: '/lobby', component: Lobby, meta: { requiresAuth: true } },
  { path: '/roulette', component: Roulette, meta: { requiresAuth: true } },
  { path: '/slots', component: Slots, meta: { requiresAuth: true } },
  { path: '/plinko', component: Plinko, meta: { requiresAuth: true } },
  { path: '/mines', component: Mines, meta: { requiresAuth: true } },
  { path: '/dice', component: Dice, meta: { requiresAuth: true } },
  { path: '/limbo', component: Limbo, meta: { requiresAuth: true } },
  { path: '/generala', component: Generala, meta: { requiresAuth: true } },
  { path: '/truco', component: Truco, meta: { requiresAuth: true } },
  { path: '/blackjack', component: Blackjack, meta: { requiresAuth: true } },
  { path: '/lobby-blackjack', component: BlackjackLobby, meta: { requiresAuth: true } },
  { path: '/blackjack-mp/:id', component: BlackjackMultiplayer, meta: { requiresAuth: true } },
  { path: '/lobby-poker', component: PokerLobby, meta: { requiresAuth: true } },
  { path: '/poker-mp/:id', component: PokerMultiplayer, meta: { requiresAuth: true } },
  { path: '/crash', component: () => import('../pages/Crash.vue'), meta: { requiresAuth: true } }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

router.beforeEach((to, from) => {
  const token = localStorage.getItem('casino_token');
  if (to.meta.requiresAuth && !token) {
    return '/login';
  } else if (to.path === '/login' && token) {
    return '/lobby';
  }
  return true;
});

export default router;
