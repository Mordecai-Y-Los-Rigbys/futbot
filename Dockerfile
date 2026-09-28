FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema requeridas por psycopg2
RUN apt-get update && apt-get install -y libpq-dev gcc

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app

# El comando de ejecución se delega a docker-compose para habilitar el hot-reload