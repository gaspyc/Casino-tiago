FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias para PostgreSQL y utilidades
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar Poetry
RUN pip install --no-cache-dir poetry

# Copiar configuración de dependencias
COPY pyproject.toml ./

# Configurar poetry para no usar virtualenvs (el contenedor ya es un entorno aislado)
# e instalar dependencias
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copiar el resto del código
COPY . .

# Exponer el puerto
EXPOSE 8000

# Comando para correr en desarrollo con recarga automática, ejecutando primero las migraciones
CMD sh -c "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
