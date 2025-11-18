-- init_dw.sql
CREATE DATABASE DataWarehouse;

-- Conectar a la nueva base de datos
\c DataWarehouse;

-- Crear el schema dw si no existe
CREATE SCHEMA IF NOT EXISTS dw;