import pandas as pd  # type: ignore
import yaml  # type: ignore
from sqlalchemy import create_engine, inspect, text  # type: ignore
from sqlalchemy.engine import Engine  # type: ignore
import time

from utils.load import *
from utils.transform import *
from utils.extract import *

pd.set_option('display.max_rows', 100)
pd.set_option('display.max_columns', 100)


def test_sql_server_connection(engine: Engine) -> bool:
    print("Probando conexión a SQL Server")
    try:
        with engine.connect() as conn:
            # Consulta simple para verificar conexión y datos
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total_tables,
                    (SELECT COUNT(*) FROM Sales.Customer) as total_customers,
                    (SELECT COUNT(*) FROM Production.Product) as total_products,
                    (SELECT COUNT(*) FROM Sales.SalesOrderHeader) as total_orders
            """))
            
            stats = result.fetchone()
            print(f"SQL Server conectado exitosamente:")
            print(f"   - Tablas en base de datos: {stats[0]}")
            print(f"   - Clientes: {stats[1]:,}")
            print(f"   - Productos: {stats[2]:,}")
            print(f"   - Órdenes: {stats[3]:,}")
            
        return True
    except Exception as e:
        print(f"Error conectando a SQL Server: {e}")
        return False


def test_postgres_connection(engine: Engine) -> bool: 

    print("Probando conexión a PostgreSQL")
    try:
        with engine.connect() as conn:
            schema_exists = conn.execute(
                text("SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'dw')")
            ).scalar()
            
            if schema_exists:
                tables_count = conn.execute(
                    text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'dw'")
                ).scalar()
                print(f"PostgreSQL conectado - Schema 'dw' existe con {tables_count} tablas")
            else:
                print("PostgreSQL conectado - Schema 'dw' no existe (se creará)")
            
            db_info = conn.execute(text("""
                SELECT 
                    current_database() as database,
                    current_user as user,
                    version() as version
            """)).fetchone()
            
            print(f"   - Base de datos: {db_info[0]}")
            print(f"   - Usuario: {db_info[1]}")
            print(f"   - Versión: {db_info[2].split(',')[0]}")
            
        return True
    except Exception as e:
        print(f"Error conectando a PostgreSQL: {e}")
        return False


def test_database_performance(oltp_engine: Engine, dw_engine: Engine):
    print("\nRealizando pruebas de performance")
    
    # Test SQL Server
    try:
        start_time = time.time()
        with oltp_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM Sales.SalesOrderHeader soh
                JOIN Sales.SalesOrderDetail sod ON soh.SalesOrderID = sod.SalesOrderID
                WHERE soh.OrderDate >= '2012-01-01'
            """))
            count = result.scalar()
        sql_server_time = time.time() - start_time
        print(f"SQL Server: Consulta compleja en {sql_server_time:.2f}s ({count:,} registros)")
    except Exception as e:
        print(f"SQL Server performance test falló: {e}")
        sql_server_time = 0

    # Test PostgreSQL
    try:
        start_time = time.time()
        with dw_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM information_schema.tables"))
            count = result.scalar()
        postgres_time = time.time() - start_time
        print(f"PostgreSQL: Consulta system catalog en {postgres_time:.2f}s ({count} tablas)")
    except Exception as e:
        print(f"PostgreSQL performance test falló: {e}")
        postgres_time = 0

    return sql_server_time, postgres_time


def create_data_warehouse_schema(engine: Engine):
    print("Creando esquema del Data Warehouse")
    
    with open('sqlscripts.yml', 'r', encoding='utf-8') as f:
        sql_scripts = yaml.safe_load(f)
    
    with engine.connect() as conn:
        # Ejecutar en orden específico para respetar dependencias
        execution_order = [
            'create_schema',
            'set_search_path',
            # Dimensiones base
            'dim_date',
            'dim_currency', 
            'dim_sales_territory',
            'dim_geography',
            'dim_product_category',
            'dim_product_subcategory',
            'dim_product',
            'dim_promotion',
            'dim_sales_reason',
            'dim_customer',
            'dim_reseller', 
            'dim_employee',
            # Hechos
            'fact_internet_sales',
            'fact_reseller_sales',
            # Foreign Keys
            'fk_customer_geography',
            'fk_employee_salesterritory',
            'fk_geography_salesterritory',
            'fk_product_subcategory',
            'fk_productsubcat_category',
            'fk_reseller_geography',
            # FKs para Internet Sales
            'fk_fis_currency',
            'fk_fis_customer', 
            'fk_fis_orderdate',
            'fk_fis_duedate',
            'fk_fis_shipdate',
            'fk_fis_product',
            'fk_fis_promotion',
            'fk_fis_salesterritory',
            # FKs para Reseller Sales
            'fk_frs_currency',
            'fk_frs_orderdate',
            'fk_frs_duedate', 
            'fk_frs_shipdate',
            'fk_frs_employee',
            'fk_frs_product',
            'fk_frs_promotion',
            'fk_frs_reseller',
            'fk_frs_salesterritory',
            # Índices
            'idx_fis_order_date',
            'idx_fis_customer',
            'idx_fis_product',
            'idx_fis_ship_date', 
            'idx_fis_promotion',
            'idx_fis_currency',
            'idx_frs_order_date',
            'idx_frs_reseller',
            'idx_frs_product',
            'idx_frs_ship_date',
            'idx_frs_employee',
            'idx_frs_promotion',
            'idx_customer_geography',
            'idx_reseller_geography',
            'idx_product_subcategory',
            'idx_subcategory_category'
        ]
        
        for script_key in execution_order:
            if script_key in sql_scripts:
                try:
                    print(f"Ejecutando: {script_key}")
                    conn.execute(text(sql_scripts[script_key]))
                    conn.commit()
                except Exception as e:
                    print(f"Advertencia en {script_key}: {e}")
                    conn.rollback()


def main():
    print("=" * 70)
    print("🚀 PIPELINE ETL ADVENTUREWORKSDW 2022")
    print("=" * 70)
    
    print("\nCargando configuración para contenedores docker")
    
    with open('config.yml', 'r') as f:
        config = yaml.safe_load(f)
        config_oltp = config['ADVENTUREWORKS_OLTP']
        config_dw = config['ADVENTUREWORKS_DW']

    url_oltp = (f"{config_oltp['drivername']}://{config_oltp['user']}:{config_oltp['password']}@"
                f"{config_oltp['host']}:{config_oltp['port']}/{config_oltp['dbname']}"
                f"{config_oltp.get('query', '')}")
    
    url_dw = (f"{config_dw['drivername']}://{config_dw['user']}:{config_dw['password']}@"
              f"{config_dw['host']}:{config_dw['port']}/{config_dw['dbname']}")

    oltp_engine = create_engine(url_oltp)
    dw_engine = create_engine(url_dw)
    
    print(f"OK - SQL Server Docker: {config_oltp['host']}:{config_oltp['port']}/{config_oltp['dbname']}")
    print(f"OK - PostgreSQL Docker: {config_dw['host']}:{config_dw['port']}/{config_dw['dbname']}")


    print("\n" + "=" * 70)
    print("PRUEBAS DE CONEXIÓN A BASES DE DATOS")
    print("=" * 70)
    
    # Probar conexión a SQL Server
    sql_server_ok = test_sql_server_connection(oltp_engine)
    
    # Probar conexión a PostgreSQL
    postgres_ok = test_postgres_connection(dw_engine)
    
    # Pruebas de performance
    test_database_performance(oltp_engine, dw_engine)
    
    if not sql_server_ok or not postgres_ok:
        print(f"\nOKnt -  CONEXIONES FALLIDAS:")
        if not sql_server_ok:
            print("   - SQL Server: No se pudo conectar")
        if not postgres_ok:
            print("   - PostgreSQL: No se pudo conectar")
        print("Revise la configuración en config.yml y asegúrese de que los servicios estén ejecutándose")
        return
    
    print("\nOK - Todas las conexiones verificadas exitosamente")

    inspector = inspect(dw_engine)
    existing_tables = inspector.get_table_names(schema='dw')

    if not existing_tables:
        print("\n Data Warehouse vacío. Creando esquema")
        create_data_warehouse_schema(dw_engine)
        print("Esquema DW creado exitosamente")
    else:
        print(f"\nData Warehouse encontrado con {len(existing_tables)} tablas")

    try:
        print("\n" + "=" * 70)
        print("FASE 1: EXTRACCIÓN DE DATOS (EXTRACT)")
        print("=" * 70)
        
        print("\nExtrayendo desde SQL Server (OLTP)")
        extraction_dict = extract_for_data_warehouse(oltp_engine)
        
        csv_folder = './csv'
        print(f"\nCargando dimensiones desde CSV ({csv_folder})")
        csv_data = load_dimensions_from_csv(csv_folder)
        
        print(f"\nExtracción completada:")
        print(f"   - Tablas desde OLTP: {len(extraction_dict)}")
        print(f"   - Dimensiones desde CSV: {len(csv_data)}")
        
        total_records = sum(len(df) for df in extraction_dict.values())
        total_records += sum(len(df) for df in csv_data.values() if not df.empty)
        print(f"   - Total registros extraídos: {total_records:,}")

        print("\n" + "=" * 70)
        print("FASE 2: TRANSFORMACIÓN DE DATOS (TRANSFORM)")
        print("=" * 70)
        
        transformed_data = transform_all_data(extraction_dict, csv_data)
        
        print(f"\nTransformación de dimensiones nivel 1 completada:")
        dimensions_count = len([k for k in transformed_data.keys() if k.startswith('dim_')])
        print(f"   - Total dimensiones preparadas: {dimensions_count}")


        print("\n" + "=" * 70)
        print("FASE 3: CARGA AL DATA WAREHOUSE (LOAD)")
        print("=" * 70)
        
        # Separar dimensiones y hechos
        transformed_dims = {k: v for k, v in transformed_data.items() if k.startswith('dim_')}
        
        # Configurar modo de carga (definido en config.yml)
        truncate_tables = config.get('TRUNCATE_TABLES', False)
        
        if truncate_tables:
            print("\nModo: CARGA INICIAL (truncate habilitado)")
        else:
            print("\nModo: CARGA INCREMENTAL (append)")
        
        print("\n" + "-" * 70)
        print("Cargando dimensiones")
        print("-" * 70)
        
        transformed_dims = transform_all_data(extraction_dict, csv_data)

        dims_with_keys = load_all_dimensions(transformed_dims, dw_engine, truncate_tables)
        
        print(f"\nDimensiones cargadas: {len(dims_with_keys)}")
        
        print("\n" + "-" * 70)
        print("Transformando y cargando hechos")
        print("-" * 70)
        
        
        transformed_facts = transform_facts_with_dimensions(extraction_dict, dims_with_keys)

        fact_stats = load_all_facts(transformed_facts, dw_engine, truncate_tables)
        
        print(f"\nHechos cargados: {len(fact_stats)}")

        print("\n" + "=" * 70)
        print("FASE 4: VALIDACIÓN POST-CARGA")
        print("=" * 70)
        
        # Validar estructura del DW
        print("\nValidando estructura del Data Warehouse")
        df_validation = validate_datawarehouse(dw_engine)
        
        # Validar integridad referencial
        print("\nValidando integridad referencial")
        fk_integrity_ok = check_foreign_key_integrity(dw_engine)


        print("\n" + "=" * 70)
        print("REPORTE FINAL DEL ETL")
        print("=" * 70)
        
        summary = {
            'dimensions_loaded': len(dims_with_keys),
            'facts_loaded': len(fact_stats),
            'total_fact_records': sum(fact_stats.values()),
            'fact_stats': fact_stats
        }
        
        print(f"\nResumen de carga:")
        print(f"   - Dimensiones cargadas: {summary['dimensions_loaded']}")
        print(f"   - Tablas de hechos cargadas: {summary['facts_loaded']}")
        print(f"   - Total registros en hechos: {summary['total_fact_records']:,}")
        
        print(f"\nDetalle de hechos:")
        for table, count in summary['fact_stats'].items():
            print(f"   - {table}: {count:,} registros")
        
        print(f"\nIntegridad referencial: {'PASÓ' if fk_integrity_ok else ' CON PROBLEMAS'}")
        
        # Validación final del DW
        tables_ok = len(df_validation[df_validation['status'].str.contains('OK')])
        total_tables = len(df_validation)
        
        print(f"\nEstado de tablas: {tables_ok}/{total_tables} con datos")
        
        # Verificar éxito completo
        if summary['total_fact_records'] > 0 and fk_integrity_ok and tables_ok == total_tables:
            print("\n" + "=" * 70)
            print("MELO - PROCESO ETL COMPLETADO EXITOSAMENTE")
            print("=" * 70)
        elif summary['total_fact_records'] > 0:
            print("\n" + "=" * 70)
            print("PROCESO ETL COMPLETADO CON ADVERTENCIAS")
            print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print("OKn't  PROCESO ETL COMPLETADO PERO SIN REGISTROS EN HECHOS")
            print("=" * 70)

    except Exception as e:
        print(f"\n" + "=" * 70)
        print(f"ERROR EN EL PROCESO ETL")
        print("=" * 70)
        print(f"\n{str(e)}")
        import traceback
        traceback.print_exc()
        raise
    
    finally:
        oltp_engine.dispose()
        dw_engine.dispose()
        print("\nConexiones cerradas")

if __name__ == "__main__":
    main()