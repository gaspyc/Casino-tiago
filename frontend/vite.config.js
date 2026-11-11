import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    watch: {
      // El bind mount de Docker en Windows no propaga los eventos de cambio de
      // archivo al contenedor: vite no se entera de que editaste algo y sigue
      // sirviendo la transformación cacheada, así que el cambio no aparece
      // hasta reiniciar el contenedor. Con polling lo detecta igual.
      usePolling: true,
      interval: 300,
    },
  },
})
