# Dockerfile para Frontend en Desarrollo (Vite + Vue)
FROM node:20-slim

WORKDIR /app

# Copiamos solo el package.json para que instale los binarios nativos correctos de Linux
COPY package.json ./

# Instalamos las dependencias desde cero
RUN npm install

# Exponer el puerto por defecto de Vite
EXPOSE 5173

# Comando para levantar el servidor Vite permitiendo conexiones externas (--host)
CMD ["npm", "run", "dev", "--", "--host"]
