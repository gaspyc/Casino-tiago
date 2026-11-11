# Dockerfile para Frontend en Desarrollo (Vite + Vue)
FROM node:20-slim

WORKDIR /app

# Copiamos package.json y package-lock.json para instalar dependencias con versiones exactas
COPY package*.json ./

# Instalamos las dependencias
RUN npm ci --verbose

# Exponer el puerto por defecto de Vite
EXPOSE 5173

# Comando para levantar el servidor Vite permitiendo conexiones externas (--host)
CMD ["npm", "run", "dev", "--", "--host"]
