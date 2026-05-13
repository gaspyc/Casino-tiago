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

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: Login },
  { path: '/lobby', component: Lobby, meta: { requiresAuth: true } },
  { path: '/roulette', component: Roulette, meta: { requiresAuth: true } },
  { path: '/slots', component: Slots, meta: { requiresAuth: true } },
  { path: '/blackjack', component: Blackjack, meta: { requiresAuth: true } },
  { path: '/lobby-blackjack', component: BlackjackLobby, meta: { requiresAuth: true } },
  { path: '/blackjack-mp/:id', component: BlackjackMultiplayer, meta: { requiresAuth: true } },
  { path: '/lobby-poker', component: PokerLobby, meta: { requiresAuth: true } },
  { path: '/poker-mp/:id', component: PokerMultiplayer, meta: { requiresAuth: true } }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('casino_token');
  if (to.meta.requiresAuth && !token) {
    next('/login');
  } else if (to.path === '/login' && token) {
    next('/lobby');
  } else {
    next();
  }
});

export default router;
