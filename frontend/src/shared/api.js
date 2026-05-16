import axios from 'axios';
// Fuerza un nuevo commit para que Coolify reconstruya la imagen con las nuevas variables de entorno

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('casino_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('casino_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
