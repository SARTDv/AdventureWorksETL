# AdventureWorks ETL Pipeline

## ¿De qué trata?

Este proyecto es un pipeline **ETL (Extract, Transform, Load)** diseñado para migrar y transformar datos desde una base de datos transaccional **AdventureWorks** (SQL Server) hacia un Data Warehouse analítico en **PostgreSQL**.

El sistema automatiza el flujo completo de datos:
1.  **Extract**: Obtiene datos desde SQL Server y archivos CSV complementarios.
2.  **Transform**: Limpia y estructura los datos en modelos dimensionales (Esquema Estrella).
3.  **Load**: Carga dimensiones y tablas de hechos en el Data Warehouse.
4.  **Validación**: Genera esquemas, aplica claves foráneas, índices y verifica la integridad de los datos.

## ¿Cómo ejecutarlo?

### 1. Requisitos Previos
*   Python 3.8+
*   Servidor SQL Server (Base de datos origen AdventureWorks).
*   Servidor PostgreSQL (Base de datos destino).
*   Archivos de configuración y scripts SQL presentes en el directorio.

### 2. Instalación
Instala las dependencias necesarias ejecutando:
```bash
pip install -r requirements.txt
```

### 3. Configuración
Crea o edita el archivo `config.yml` con las credenciales de conexión para ambas bases de datos. Puedes usar `config_fill.yml` como plantilla.

### 4. Ejecución
Para iniciar el proceso ETL completo, ejecuta el script principal:
```bash
python main.py
```

El script realizará pruebas de conexión, creará el esquema si es necesario, y procederá con la carga y validación de los datos, mostrando el progreso en la consola.
