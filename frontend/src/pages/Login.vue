<template>
  <div class="login-container">
    <div class="glass-panel login-card">
      <div class="header">
        <h1>Casino<span>tiago</span></h1>
        <p>Inicia sesión o regístrate para jugar</p>
      </div>
      
      <div class="tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">Ingresar</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'">Registrarse</button>
      </div>

      <form @submit.prevent="submitForm">
        <div class="form-group">
          <label>Usuario</label>
          <input v-model="form.username" type="text" required placeholder="Tu usuario" />
        </div>
        
        <div v-if="mode === 'register'" class="form-group">
          <label>Email</label>
          <input v-model="form.email" type="email" required placeholder="tu@email.com" />
        </div>

        <div class="form-group">
          <label>Contraseña</label>
          <input v-model="form.password" type="password" required placeholder="••••••••" />
        </div>

        <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>

        <button type="submit" class="btn btn-block" :disabled="loading">
          {{ loading ? 'Cargando...' : (mode === 'login' ? 'Entrar al Casino' : 'Crear Cuenta') }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';
import { useRouter } from 'vue-router';
import api from '../shared/api';

const router = useRouter();
const mode = ref('login');
const loading = ref(false);
const errorMsg = ref('');

const form = reactive({
  username: '',
  email: '',
  password: ''
});

const submitForm = async () => {
  loading.value = true;
  errorMsg.value = '';
  
  try {
    if (mode.value === 'register') {
      await api.post('/users/register', {
        username: form.username,
        email: form.email,
        password: form.password
      });
      // Auto login after register
      mode.value = 'login';
      await doLogin();
    } else {
      await doLogin();
    }
  } catch (err) {
    errorMsg.value = err.response?.data?.detail || 'Ocurrió un error inesperado';
  } finally {
    loading.value = false;
  }
};

const doLogin = async () => {
  const formData = new URLSearchParams();
  formData.append('username', form.username);
  formData.append('password', form.password);

  const res = await api.post('/users/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
  
  localStorage.setItem('casino_token', res.data.access_token);
  router.push('/lobby');
};
</script>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 400px;
  padding: 40px;
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.header h1 {
  font-size: 2rem;
}
.header span {
  color: var(--primary);
}
.header p {
  color: var(--text-muted);
  margin-top: 8px;
  font-size: 0.9rem;
}

.tabs {
  display: flex;
  margin-bottom: 24px;
  background: rgba(0,0,0,0.2);
  border-radius: 8px;
  padding: 4px;
}

.tabs button {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-muted);
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.3s;
}

.tabs button.active {
  background: var(--bg-card);
  color: white;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.btn-block {
  width: 100%;
  margin-top: 10px;
  padding: 14px;
  font-size: 1rem;
}

.error-msg {
  color: var(--accent-red);
  font-size: 0.85rem;
  text-align: center;
  margin-bottom: 16px;
  background: rgba(239, 68, 68, 0.1);
  padding: 10px;
  border-radius: 6px;
}
</style>
