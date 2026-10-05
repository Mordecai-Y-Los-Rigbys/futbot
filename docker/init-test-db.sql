-- Se ejecuta una sola vez, al inicializar el volumen vacío de Postgres.
-- Crea la base que usan los tests de integración (TEST_DATABASE_URL).
CREATE DATABASE futbot_test;